# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

from datetime import date

from dateutil.relativedelta import relativedelta

from odoo import fields, models, api, _
from odoo.exceptions import ValidationError
from odoo.osv import expression
from odoo.tools.float_utils import float_compare, float_is_zero


class TransferModel(models.Model):
    _name = "account.transfer.model"
    _description = "Account Transfer Model"

    # DEFAULTS
    def _get_default_date_start(self):
        company = self.env.company
        return company.compute_fiscalyear_dates(date.today())['date_from'] if company else None

    def _get_default_journal(self):
        return self.env['account.journal'].search([('company_id', '=', self.env.company.id), ('type', '=', 'general')], limit=1)

    name = fields.Char(required=True)
    journal_id = fields.Many2one('account.journal', required=True, string="Destination Journal", default=_get_default_journal)
    company_id = fields.Many2one('res.company', readonly=True, related='journal_id.company_id')
    date_start = fields.Date(string="Start Date", required=True, default=_get_default_date_start)
    date_stop = fields.Date(string="Stop Date", required=False)
    frequency = fields.Selection([('month', 'Monthly'), ('quarter', 'Quarterly'), ('year', 'Yearly')],
                                 required=True, default='month')
    account_ids = fields.Many2many('account.account', 'account_model_rel', string="Origin Accounts", domain="[('is_off_balance', '=', False)]")
    line_ids = fields.One2many('account.transfer.model.line', 'transfer_model_id', string="Destination Accounts")
    move_ids = fields.One2many('account.move', 'transfer_model_id', string="Generated Moves")
    move_ids_count = fields.Integer(compute="_compute_move_ids_count")
    total_percent = fields.Float(compute="_compute_total_percent", string="Total Percent", readonly=True)
    state = fields.Selection([('disabled', 'Disabled'), ('in_progress', 'Running')], default='disabled', required=True)

    def copy(self, default=None):
        default = default or {}
        res = super(TransferModel, self).copy(default)
        res.account_ids += self.account_ids
        for line in self.line_ids:
            line.copy({'transfer_model_id': res.id})
        return res


    # COMPUTEDS / CONSTRAINS
    @api.depends('move_ids')
    def _compute_move_ids_count(self):
        """ Compute the amount of move ids have been generated by this transfer model. """
        for record in self:
            record.move_ids_count = len(record.move_ids)

    @api.constrains('line_ids')
    def _check_line_ids_percent(self):
        """ Check that the total percent is not bigger than 100.0 """
        for record in self:
            if not (0 < record.total_percent <= 100.0):
                raise ValidationError(_('The total percentage (%s) should be less or equal to 100 !', record.total_percent))

    @api.constrains('line_ids')
    def _check_line_ids_filters(self):
        """ Check that the filters on the lines make sense """
        for record in self:
            combinations = []
            for line in record.line_ids:
                if line.partner_ids and line.analytic_account_ids:
                    for p in line.partner_ids:
                        for a in line.analytic_account_ids:
                            combination = (p.id, a.id)
                            if combination in combinations:
                                raise ValidationError(_("The partner filter %s in combination with the analytic filter %s is duplicated", p.display_name, a.display_name))
                            combinations.append(combination)
                elif line.partner_ids:
                    for p in line.partner_ids:
                        combination = (p.id, None)
                        if combination in combinations:
                            raise ValidationError(_("The partner filter %s is duplicated", p.display_name))
                        combinations.append(combination)
                elif line.analytic_account_ids:
                    for a in line.analytic_account_ids:
                        combination = (None, a.id)
                        if combination in combinations:
                            raise ValidationError(_("The analytic filter %s is duplicated", a.display_name))
                        combinations.append(combination)

    @api.depends('line_ids')
    def _compute_total_percent(self):
        """ Compute the total percentage of all lines linked to this model. """
        for record in self:
            non_filtered_lines = record.line_ids.filtered(lambda l: not l.partner_ids and not l.analytic_account_ids)
            if record.line_ids and not non_filtered_lines:
                # Lines are only composed of filtered ones thus percentage does not matter, make it 100
                record.total_percent = 100.0
            else:
                total_percent = sum(non_filtered_lines.mapped('percent'))
                if float_compare(total_percent, 100.0, precision_digits=6) == 0:
                    total_percent = 100.0
                record.total_percent = total_percent

    # ACTIONS
    def action_activate(self):
        """ Put this move model in "in progress" state. """
        return self.write({'state': 'in_progress'})

    def action_disable(self):
        """ Put this move model in "disabled" state. """
        return self.write({'state': 'disabled'})

    @api.model
    def action_cron_auto_transfer(self):
        """ Perform the automatic transfer for the all active move models. """
        self.search([('state', '=', 'in_progress')]).action_perform_auto_transfer()

    def action_perform_auto_transfer(self):
        """ Perform the automatic transfer for the current recordset of models  """
        for record in self:
            # If no account to ventilate or no account to ventilate into : nothing to do
            if record.account_ids and record.line_ids:
                today = date.today()
                max_date = record.date_stop and min(today, record.date_stop) or today
                start_date = record._determine_start_date()
                next_move_date = record._get_next_move_date(start_date)

                # (Re)Generate moves in draft untill today
                # Journal entries will be recomputed everyday until posted.
                while next_move_date <= max_date:
                    record._create_or_update_move_for_period(start_date, next_move_date)
                    start_date = next_move_date + relativedelta(days=1)
                    next_move_date = record._get_next_move_date(start_date)

                # (Re)Generate move for one more period if needed
                if not record.date_stop:
                    record._create_or_update_move_for_period(start_date, next_move_date)
                elif today < record.date_stop:
                    record._create_or_update_move_for_period(start_date, min(next_move_date, record.date_stop))
        return False

    def _get_move_lines_base_domain(self, start_date, end_date):
        """
        Determine the domain to get all account move lines posted in a given period, for an account in origin accounts
        :param start_date: the start date of the period
        :param end_date: the end date of the period
        :return: the computed domain
        :rtype: list
        """
        self.ensure_one()
        return [
            ('account_id', 'in', self.account_ids.ids),
            ('date', '>=', start_date),
            ('date', '<=', end_date),
            ('move_id.state', '=', 'posted')
        ]

    # PROTECTEDS

    def _create_or_update_move_for_period(self, start_date, end_date):
        """
        Create or update a move for a given period. This means (re)generates all the needed moves to execute the
        transfers
        :param start_date: the start date of the targeted period
        :param end_date: the end date of the targeted period
        :return: the created (or updated) move
        """
        self.ensure_one()
        current_move = self._get_move_for_period(end_date)
        if current_move is None:
            current_move = self.env['account.move'].create({
                'ref': '%s: %s --> %s' % (self.name, str(start_date), str(end_date)),
                'date': end_date,
                'journal_id': self.journal_id.id,
                'transfer_model_id': self.id,
            })

        line_values = self._get_auto_transfer_move_line_values(start_date, end_date)
        if line_values:
            line_ids_values = [(0, 0, value) for value in line_values]
            # unlink all old line ids
            current_move.line_ids.unlink()
            # recreate line ids
            current_move.write({'line_ids': line_ids_values})
        return current_move

    def _get_move_for_period(self, end_date):
        """ Get the generated move for a given period
        :param end_date: the end date of the wished period, do not need the start date as the move will always be
        generated with end date of a period as date
        :return: a recordset containing the move found if any, else None
        """
        self.ensure_one()
        # Move will always be generated with end_date of a period as date
        domain = [
            ('date', '=', end_date),
            ('state', '=', 'draft'),
            ('transfer_model_id', '=', self.id)
        ]
        current_moves = self.env['account.move'].search(domain, limit=1, order="date desc")
        return current_moves[0] if current_moves else None

    def _determine_start_date(self):
        """ Determine the automatic transfer start date which is the last created move if any or the start date of the model  """
        self.ensure_one()
        # Get last generated move date if any (to know when to start)
        last_move_domain = [('transfer_model_id', '=', self.id), ('state', '=', 'posted'), ('company_id', '=', self.company_id.id)]
        move_ids = self.env['account.move'].search(last_move_domain, order='date desc', limit=1)
        return move_ids[0].date if move_ids else self.date_start

    def _get_next_move_date(self, date):
        """ Compute the following date of automated transfer move, based on a date and the frequency """
        self.ensure_one()
        if self.frequency == 'month':
            delta = relativedelta(months=1)
        elif self.frequency == 'quarter':
            delta = relativedelta(months=3)
        else:
            delta = relativedelta(years=1)
        return date + delta - relativedelta(days=1)

    def _get_auto_transfer_move_line_values(self, start_date, end_date):
        """ Get all the transfer move lines values for a given period
        :param start_date: the start date of the period
        :param end_date: the end date of the period
        :return: a list of dict representing the values of lines to create
        :rtype: list
        """
        self.ensure_one()
        values = []
        # Get the balance of all moves from all selected accounts, grouped by accounts
        filtered_lines = self.line_ids.filtered(lambda x: x.analytic_account_ids or x.partner_ids)
        if filtered_lines:
            values += filtered_lines._get_transfer_move_lines_values(start_date, end_date)

        non_filtered_lines = self.line_ids - filtered_lines
        if non_filtered_lines:
            values += self._get_non_filtered_auto_transfer_move_line_values(non_filtered_lines, start_date, end_date)

        return values

    def _get_non_filtered_auto_transfer_move_line_values(self, lines, start_date, end_date):
        """
        Get all values to create move lines corresponding to the transfers needed by all lines without analytic
        account or partner for a given period. It contains the move lines concerning destination accounts and
        the ones concerning the origin accounts. This process all the origin accounts one after one.
        :param lines: the move model lines to handle
        :param start_date: the start date of the period
        :param end_date: the end date of the period
        :return: a list of dict representing the values to use to create the needed move lines
        :rtype: list
        """
        self.ensure_one()
        domain = self._get_move_lines_base_domain(start_date, end_date)
        for account in self.line_ids.analytic_account_ids:
            domain.append(('analytic_distribution_stored_char', 'not ilike', f'%"{account.id}":%'))
        domain = expression.AND([domain, [('partner_id', 'not in', self.line_ids.partner_ids.ids), ]])
        total_balance_by_accounts = self.env['account.move.line']._read_group(domain, ['balance', 'account_id'],
                                                                             ['account_id'])

        # balance = debit - credit
        # --> balance > 0 means a debit so it should be credited on the source account
        # --> balance < 0 means a credit so it should be debited on the source account
        values_list = []
        for total_balance_account in total_balance_by_accounts:
            initial_amount = abs(total_balance_account['balance'])
            source_account_is_debit = total_balance_account['balance'] >= 0
            account_id = total_balance_account['account_id'][0]
            account = self.env['account.account'].browse(account_id)
            if not float_is_zero(initial_amount, precision_digits=9):
                move_lines_values, amount_left = self._get_non_analytic_transfer_values(account, lines, end_date,
                                                                                        initial_amount,
                                                                                        source_account_is_debit)

                # the line which credit/debit the source account
                substracted_amount = initial_amount - amount_left
                source_move_line = {
                    'name': _('Automatic Transfer (-%s%%)', self.total_percent),
                    'account_id': account_id,
                    'date_maturity': end_date,
                    'credit' if source_account_is_debit else 'debit': substracted_amount
                }
                values_list += move_lines_values
                values_list.append(source_move_line)
        return values_list

    def _get_non_analytic_transfer_values(self, account, lines, write_date, amount, is_debit):
        """
        Get all values to create destination account move lines corresponding to the transfers needed by all lines
        without analytic account for a given account.
        :param account: the origin account to handle
        :param write_date: the write date of the move lines
        :param amount: the total amount to take care on the origin account
        :type amount: float
        :param is_debit: True if origin account has a debit balance, False if it's a credit
        :type is_debit: bool
        :return: a tuple containing the move lines values in a list and the amount left on the origin account after
        processing as a float
        :rtype: tuple
        """
        # if total ventilated is 100%
        #   then the last line should not compute in % but take the rest
        # else
        #   it should compute in % (as the rest will stay on the source account)
        self.ensure_one()
        amount_left = amount

        take_the_rest = self.total_percent == 100.0
        amount_of_lines = len(lines)
        values_list = []

        for i, line in enumerate(lines):
            if take_the_rest and i == amount_of_lines - 1:
                line_amount = amount_left
                amount_left = 0
            else:
                line_amount = (line.percent / 100.0) * amount
                amount_left -= line_amount

            move_line = line._get_destination_account_transfer_move_line_values(account, line_amount, is_debit,
                                                                                write_date)
            values_list.append(move_line)

        return values_list, amount_left


class TransferModelLine(models.Model):
    _name = "account.transfer.model.line"
    _description = "Account Transfer Model Line"
    _order = "sequence, id"

    transfer_model_id = fields.Many2one('account.transfer.model', string="Transfer Model", required=True)
    account_id = fields.Many2one('account.account', string="Destination Account", required=True,
                                 domain="[('is_off_balance', '=', False)]")
    percent = fields.Float(string="Percent", required=True, default=100, help="Percentage of the sum of lines from the origin accounts will be transferred to the destination account")
    analytic_account_ids = fields.Many2many('account.analytic.account', string='Analytic Filter', help="Adds a condition to only transfer the sum of the lines from the origin accounts that match these analytic accounts to the destination account")
    partner_ids = fields.Many2many('res.partner', string='Partner Filter', help="Adds a condition to only transfer the sum of the lines from the origin accounts that match these partners to the destination account")
    percent_is_readonly = fields.Boolean(compute="_compute_percent_is_readonly")
    sequence = fields.Integer("Sequence")

    _sql_constraints = [
        (
            'unique_account_by_transfer_model', 'UNIQUE(transfer_model_id, account_id)',
            'Only one account occurrence by transfer model')
    ]

    @api.onchange('analytic_account_ids', 'partner_ids')
    def set_percent_if_analytic_account_ids(self):
        """
        Set percent to 100 if at least analytic account id is set.
        """
        for record in self:
            if record.analytic_account_ids or record.partner_ids:
                record.percent = 100

    def _get_transfer_move_lines_values(self, start_date, end_date):
        """
        Get values to create the move lines to perform all needed transfers between accounts linked to current recordset
        for a given period
        :param start_date: the start date of the targeted period
        :param end_date: the end date of the targeted period
        :return: a list containing all the values needed to create the needed transfers
        :rtype: list
        """
        transfer_values = []
        # Avoid to transfer two times the same entry
        already_handled_move_line_ids = []
        for transfer_model_line in self:
            domain = transfer_model_line._get_move_lines_domain(start_date, end_date, already_handled_move_line_ids)
            total_balances_by_account = self.env['account.move.line']._read_group(domain, ['ids:array_agg(id)', 'balance', 'account_id'], ['account_id'])
            for total_balance_account in total_balances_by_account:
                already_handled_move_line_ids += total_balance_account['ids']
                balance = total_balance_account['balance']
                if not float_is_zero(balance, precision_digits=9):
                    amount = abs(balance)
                    source_account_is_debit = balance > 0
                    account_id = total_balance_account['account_id'][0]
                    account = self.env['account.account'].browse(account_id)
                    transfer_values += transfer_model_line._get_transfer_values(account, amount, source_account_is_debit,
                                                                            end_date)
        return transfer_values

    def _get_move_lines_domain(self, start_date, end_date, avoid_move_line_ids=None):
        """
        Determine the domain to get all account move lines posted in a given period corresponding to self move model
        line.
        :param start_date: the start date of the targeted period
        :param end_date: the end date of the targeted period
        :param avoid_move_line_ids: the account.move.line ids that should be excluded from the domain
        :return: the computed domain
        :rtype: list
        """
        self.ensure_one()
        move_lines_domain = self.transfer_model_id._get_move_lines_base_domain(start_date, end_date)
        if avoid_move_line_ids:
            move_lines_domain.append(('id', 'not in', avoid_move_line_ids))
        domain_account = []
        for account in self.analytic_account_ids:
            domain_account.append([('analytic_distribution_stored_char', '=ilike', f'%"{account.id}":%')])
        domain_account = expression.OR(domain_account) if domain_account else []
        for domain in domain_account:
            move_lines_domain.append(domain)
        if self.partner_ids:
            move_lines_domain.append(('partner_id', 'in', self.partner_ids.ids))
        return move_lines_domain

    def _get_transfer_values(self, account, amount, is_debit, write_date):
        """
        Get values to create the move lines to perform a transfer between self account and given account
        :param account: the account
        :param amount: the amount that is being transferred
        :type amount: float
        :param is_debit: True if the transferred amount is a debit, False if credit
        :type is_debit: bool
        :param write_date: the date to use for the move line writing
        :return: a list containing the values to create the needed move lines
        :rtype: list
        """
        self.ensure_one()
        return [
            self._get_destination_account_transfer_move_line_values(account, amount, is_debit, write_date),
            self._get_origin_account_transfer_move_line_values(account, amount, is_debit, write_date)
        ]

    def _get_origin_account_transfer_move_line_values(self, origin_account, amount, is_debit,
                                                      write_date):
        """
        Get values to create the move line in the origin account side for a given transfer of a given amount from origin
        account to a given destination account.
        :param origin_account: the origin account
        :param amount: the amount that is being transferred
        :type amount: float
        :param is_debit: True if the transferred amount is a debit, False if credit
        :type is_debit: bool
        :param write_date: the date to use for the move line writing
        :return: a dict containing the values to create the move line
        :rtype: dict
        """
        anal_accounts = self.analytic_account_ids and ', '.join(self.analytic_account_ids.mapped('name'))
        partners = self.partner_ids and ', '.join(self.partner_ids.mapped('name'))
        if anal_accounts and partners:
            name = _("Automatic Transfer (entries with analytic account(s): %s and partner(s): %s)") % (anal_accounts, partners)
        elif anal_accounts:
            name = _("Automatic Transfer (entries with analytic account(s): %s)") % (anal_accounts,)
        elif partners:
            name = _("Automatic Transfer (entries with partner(s): %s)") % (partners,)
        else:
            name = _("Automatic Transfer (to account %s)", self.account_id.code)
        return {
            'name': name,
            'account_id': origin_account.id,
            'date_maturity': write_date,
            'credit' if is_debit else 'debit': amount
        }

    def _get_destination_account_transfer_move_line_values(self, origin_account, amount, is_debit,
                                                           write_date):
        """
        Get values to create the move line in the destination account side for a given transfer of a given amount from
        given origin account to destination account.
        :param origin_account: the origin account
        :param amount: the amount that is being transferred
        :type amount: float
        :param is_debit: True if the transferred amount is a debit, False if credit
        :type is_debit: bool
        :param write_date: the date to use for the move line writing
        :return: a dict containing the values to create the move line
        :rtype dict:
        """
        anal_accounts = self.analytic_account_ids and ', '.join(self.analytic_account_ids.mapped('name'))
        partners = self.partner_ids and ', '.join(self.partner_ids.mapped('name'))
        if anal_accounts and partners:
            name = _("Automatic Transfer (from account %s with analytic account(s): %s and partner(s): %s)") % (origin_account.code, anal_accounts, partners)
        elif anal_accounts:
            name = _("Automatic Transfer (from account %s with analytic account(s): %s)") % (origin_account.code, anal_accounts)
        elif partners:
            name = _("Automatic Transfer (from account %s with partner(s): %s)") % (origin_account.code, partners,)
        else:
            name = _("Automatic Transfer (%s%% from account %s)") % (self.percent, origin_account.code)
        return {
            'name': name,
            'account_id': self.account_id.id,
            'date_maturity': write_date,
            'debit' if is_debit else 'credit': amount
        }

    @api.depends('analytic_account_ids', 'partner_ids')
    def _compute_percent_is_readonly(self):
        for record in self:
            record.percent_is_readonly = record.analytic_account_ids or record.partner_ids
