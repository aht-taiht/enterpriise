# -*- coding: utf-8 -*-

import collections

from odoo import models, fields, api, _
from odoo.exceptions import UserError, ValidationError

ColumnMetadata = collections.namedtuple('ColumnMetadata', 'grouping domain prev next initial values format')


class ConsolidationJournal(models.Model):
    _name = "consolidation.journal"
    _description = "Consolidation Journal"
    _order = 'company_period_id asc, id asc'

    name = fields.Char(string='Name', required=True)
    period_id = fields.Many2one('consolidation.period', string="Analysis Period", ondelete="cascade")
    chart_id = fields.Many2one('consolidation.chart', string="Chart", required=True, ondelete='cascade')
    company_period_id = fields.Many2one('consolidation.company_period', string="Company Period", required=False,
                                        copy=False)
    state = fields.Selection(related="period_id.state", readonly=True)
    # CHART currency id
    currency_id = fields.Many2one('res.currency', related="period_id.chart_id.currency_id", readonly=True)
    composition_id = fields.Many2one('consolidation.period.composition', string="Consolidation Period",
                                     required=False, copy=False)
    line_ids = fields.One2many('consolidation.journal.line', 'journal_id', 'Consolidation items')

    auto_generated = fields.Boolean(default=False, string="Automatically Generated", readonly=True, copy=False)
    balance = fields.Monetary(compute="_compute_balance", string="Balance", readonly=True)

    # Originating company period or composition fields
    originating_currency_id = fields.Many2one('res.currency', compute="_compute_originating_fields", readonly=True)
    rate_consolidation = fields.Float(compute="_compute_originating_fields", string='Consolidation Rate', readonly=True)
    currencies_are_different = fields.Boolean(compute="_compute_currencies_are_different", readonly=True)

    # CONSTRAINTS
    @api.constrains('company_period_id', 'composition_id')
    def _check_unique_origin(self):
        """
        Check that the journal have only been generated by a company period OR a composition OR neither.
        """
        for record in self:
            if record.company_period_id and record.composition_id:
                raise ValidationError(_('A journal entry should only be linked to a company period OR to a analysis period of another consolidation !'))

    @api.constrains('period_id')
    def _check_not_locked_period(self):
        """
        Prevent the addition of journals to a already closed analysis period.
        """
        for record in self:
            if record.period_id and record.period_id.state == 'closed':
                raise ValidationError(_('You cannot add journals to a closed period !'))

    @api.constrains('period_id', 'chart_id')
    def _check_chart_id(self):
        for record in self:
            if record.period_id and record.chart_id != record.period_id.chart_id:
                raise ValidationError(_("When setting a period on a consolidation journal, the selected consolidation chart for the journal cannot be different from the one of the chosen period."))

    # COMPUTEDS
    @api.depends('line_ids')
    def _compute_balance(self):
        """
        Compute the total balance of the journal
        """
        JournalLine = self.env['consolidation.journal.line']
        journal_lines = JournalLine.read_group([('journal_id', 'in', self.ids)], ['amount:sum', 'journal_id'],
                                               ['journal_id'])
        amounts = {a['journal_id'][0]: a['amount'] for a in journal_lines}
        for record in self:
            record.balance = amounts.get(record.id, 0)

    @api.depends('company_period_id', 'composition_id')
    def _compute_originating_fields(self):
        """
        Compute the fields which are base on the origin of the journal (composition_id or company_period_id) :
        rate_consolidation and originating_currency_id.
        :return:
        """
        for record in self:
            if record.company_period_id:
                record.originating_currency_id = record.company_period_id.currency_company_id
                record.rate_consolidation = record.company_period_id.rate_consolidation
            else:
                record.originating_currency_id = record.composition_id.using_chart_currency_id
                record.rate_consolidation = record.composition_id.rate_consolidation

    @api.depends('originating_currency_id', 'currency_id')
    def _compute_currencies_are_different(self):
        """
        Compute if the currencies (the one from the origin and the one from the record itself) are different.
        """
        for record in self:
            record.currencies_are_different = record.currency_id != record.originating_currency_id

    @api.onchange('period_id')
    def _onchange_period_id(self):
        if self.period_id:
            self.chart_id = self.period_id.chart_id

    # ACTIONS
    def action_generate_journal_lines(self):
        """
        Re(generate) all the journals of the recordset. It won't affect journals linked to closed analysis periods.
        """
        self.check_access_rule('write')
        self.check_access_rights('write')
        for record in self:
            if record.state == 'closed':
                continue
            record.line_ids.with_context(allow_unlink=True).unlink()
            origin = record.company_period_id or record.composition_id
            # compute journal lines in sudo since it needs to browse several companies
            journal_line_values = origin.sudo()._get_journal_lines_values()
            record.write({'line_ids': [(0, 0, value) for value in journal_line_values]})


class ConsolidationJournalLine(models.Model):
    _name = "consolidation.journal.line"
    _description = "Consolidation journal line"

    note = fields.Text(string='Description', required=False)
    journal_id = fields.Many2one('consolidation.journal', string="Journal", ondelete='restrict', required=True)
    account_id = fields.Many2one('consolidation.account', string="Consolidated Account", required=True)
    group_id = fields.Many2one('consolidation.group', related="account_id.group_id",
                                 string="Group", store=True)
    period_id = fields.Many2one('consolidation.period', related="journal_id.period_id",
                                string="Period", store=True)
    auto_generated = fields.Boolean(related="journal_id.auto_generated")
    currency_amount = fields.Monetary(string="Currency Amount", currency_field='chart_currency_id')
    journal_originating_currency_id = fields.Many2one('res.currency', related="journal_id.originating_currency_id",
                                                      readonly=True)
    amount = fields.Monetary(string="Amount", currency_field='chart_currency_id')
    chart_currency_id = fields.Many2one('res.currency', related="account_id.chart_id.currency_id", readonly=True)

    # GENERATED FROM when the journal is generated by a company period (AUDIT)
    move_line_ids = fields.Many2many('account.move.line')

    @api.constrains('account_id', 'journal_id')
    def _check_conditional_unicity(self):
        """
        Check that the journal line is unique by account and autogenerated journal
        EXCEPT if the account is in historical currency mode.
        """
        existings = {}
        for record in self:
            if record.journal_id and record.account_id and record.journal_id.auto_generated and record.account_id.currency_mode != 'hist':
                domain = [('account_id', '=', record.account_id.id), ('journal_id', '=', record.journal_id.id)]
                if record.id:
                    domain.append(('id', '!=', record.id))
                if existings.get((record.journal_id, record.account_id), False) or record.search(domain):
                    raise ValidationError(_('Only one entry by account should be created for a generated journal entry !'))
                existings[(record.journal_id, record.account_id)] = True

    # ORM OVERRIDES
    def write(self, vals):
        if self.journal_id and self.journal_id.auto_generated:
            raise UserError(_("You can't edit an auto-generated journal entry."))
        return super().write(vals)

    @api.ondelete(at_uninstall=False)
    def _unlink_except_autogenerated(self):
        if not self.env.context.get('allow_unlink', False) and self.journal_id and self.journal_id.auto_generated:
            raise UserError(_("You can't delete an auto-generated journal entry."))

    # GRID OVERRIDES

    def adjust_grid(self, row_domain, column_field, column_value, cell_field, change):
        """
        Called by the grid view when editing a cell value. If journal is editable, it creates a new journal line linked
        to the journal (column) and the account (row) with the difference and a auto generated text as description.
        :param row_domain: the domain corresponding to the row
        :param column_field: the column field
        :param column_value: the column value
        :param cell_field: the cell field
        :param change: the change applied to the cell (ex: was -10 and now is 10 : change contains 20)
        :return: created lines
        :rtype: account.consolidation.journal.line
        """
        if not self._journal_is_editable(row_domain, column_field, column_value):
            raise UserError(_("You can't edit an auto-generated journal entry."))

        row = self.search(row_domain)[0]
        return self.create([{
            column_field: column_value,
            'account_id': row.account_id.id,
            'note': 'Trial balance adjustment',
            cell_field: change
        }])

    def _grid_column_info(self, name, range):
        """
        Get the information of a given column.
        :param name: the field name linked to that column
        :param range: the range of the column
        :type name: str
        :type range: None | dict
        :return: a ColumnMetadata object representing the information of that column.
        :rtype: ColumnMetadata
        """
        period_id = self.env.context.get('default_period_id', False)
        if name == 'journal_id' and period_id:
            # filter journals displayed in columns on period id
            domain = [('period_id', '=', period_id)]
            journals = self.env['consolidation.journal'].search(domain).name_get()
            return ColumnMetadata(
                grouping=name,
                domain=[],
                prev=False,
                next=False,
                initial=False,
                values=[{
                    'values': {name: v},
                    'domain': [(name, '=', v[0])],
                    'is_current': False
                } for v in journals],
                format=lambda a: a and a[0],
            )
        return super()._grid_column_info(name, range)

    def _grid_format_cell(self, group, cell_field, readonly_field):
        """
        Format a cell in the grid.
        :param group: group of models linked to the cell
        :param cell_field: the model field used as measure in the cell
        :param readonly_field: readonly field associated to the cell (if any)
        :return: a dict containing the size of the cell, the domain, the value and a boolean which is True if the model
        is readonly, False otherwise.
        :rtype: dict
        """
        res = self.search(group['__domain'])
        return {
            'size': group['__count'],
            'domain': group['__domain'],
            'value': group[cell_field],
            'readonly': any(res.mapped('auto_generated'))
        }

    def _grid_make_empty_cell(self, row_domain, column_domain, view_domain):
        """
        Format a cell when no model found to display data. In this grid, we just need to set the readonly flag to False
        if the generated journal is not editable.
        :param row_domain: the domain of the row where the empty cell needs to be created
        :param column_domain: the domain of the column where the empty cell needs to be created
        :param view_domain: the domain of the view where the empty cell needs to be created
        :return: a dict containing the size of the cell, the domain, the value and a boolean which is True if the model
        is readonly, False otherwise.
        :rtype: dict
        """
        cell = super()._grid_make_empty_cell(row_domain, column_domain, view_domain)
        cell['readonly'] = False
        if len(column_domain) == 1:
            domain_clause = column_domain[0]
            if domain_clause[0] == 'journal_id':
                journal_domain = [('id', domain_clause[1], domain_clause[2])]
                cell['readonly'] = self.env['consolidation.journal'].search(journal_domain, limit=1).auto_generated
        return cell

    # PROTECTEDS

    def _journal_is_editable(self, row_domain, column_field, column_value):
        """
        Determine if a journal is editable based on a cell, even if no journal line object is linked to it.
        :param row_domain: the row's domain
        :type row_domain: list
        :param column_field: the column field
        :type column_field: str
        :param column_value: the value for column_field determining the column
        :return: True if editable, False otherwise
        :rtype: bool
        """
        if column_field == 'journal_id':
            res = self.env['consolidation.journal'].search([('id', '=', column_value)])
            return len(res) == 1 and not res[0].auto_generated
        return True
