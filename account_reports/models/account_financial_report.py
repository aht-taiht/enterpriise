# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.
import copy
from odoo import models, fields, api, _
from odoo.tools.safe_eval import safe_eval
from odoo.tools.misc import formatLang
from odoo.tools import float_is_zero, ustr
from datetime import datetime
from dateutil.relativedelta import relativedelta
from odoo.exceptions import UserError, ValidationError
from odoo.osv import expression
from odoo.tools.pycompat import izip


class ReportAccountFinancialReport(models.Model):
    _name = "account.financial.html.report"
    _description = "Account Report"
    _inherit = "account.report"

    name = fields.Char(translate=True)
    debit_credit = fields.Boolean('Show Credit and Debit Columns')
    line_ids = fields.One2many('account.financial.html.report.line', 'financial_report_id', string='Lines')
    date_range = fields.Boolean('Based on date ranges', default=True, help='specify if the report use date_range or single date')
    comparison = fields.Boolean('Allow comparison', default=True, help='display the comparison filter')
    cash_basis = fields.Boolean('Allow cash basis mode', help='display the option to switch to cash basis mode')
    analytic = fields.Boolean('Allow analytic filters', help='display the analytic filters')
    hierarchy_option = fields.Boolean('Enable the hierarchy option', help='Display the hierarchy choice in the report options')
    show_journal_filter = fields.Boolean('Allow filtering by journals', help='display the journal filter in the report')
    unfold_all_filter = fields.Boolean('Show unfold all filter', help='display the unfold all options in report')
    company_id = fields.Many2one('res.company', string='Company')
    generated_menu_id = fields.Many2one(
        string='Menu Item', comodel_name='ir.ui.menu', copy=False,
        help="The menu item generated for this report, or None if there isn't any."
    )
    parent_id = fields.Many2one('ir.ui.menu', related="generated_menu_id.parent_id")
    tax_report = fields.Boolean('Tax Report', help="Set to True to automatically filter out journal items that have the boolean field 'tax_exigible' set to False")
    applicable_filters_ids = fields.Many2many('ir.filters', domain="[('model_id', '=', 'account.move.line')]",
                                              help='Filters that can be used to filter and group lines in this report.')

    def _get_column_name(self, field_content, field):
        comodel_name = self.env['account.move.line']._fields[field].comodel_name
        if not comodel_name:
            return field_content
        grouping_record = self.env[comodel_name].browse(field_content)
        return grouping_record.name_get()[0][1] if grouping_record and grouping_record.exists() else _('Undefined')

    def _get_columns_name_hierarchy(self, options):
        '''Calculates a hierarchy of column headers meant to be easily used in QWeb.

        This returns a list of lists. An example for 1 period and a
        filter that groups by company and partner:

        [
          [{'colspan': 2, 'name': 'As of 02/28/2018'}],
          [{'colspan': 2, 'name': 'YourCompany'}],
          [{'colspan': 1, 'name': 'ASUSTeK'}, {'colspan': 1, 'name': 'Agrolait'}],
        ]

        The algorithm used to generate this loops through each group
        id in options['groups'].get('ids') (group_ids). E.g. for
        group_ids:

        [(1, 8, 8),
         (1, 17, 9),
         (1, None, 9),
         (1, None, 13),
         (1, None, None)]

        These groups are always ordered. The algorithm loops through
        every first elements of each tuple, then every second element
        of each tuple etc. It generates a header element every time
        it:

        - notices a change compared to the last element (e.g. when processing 17
          it will create a dict for 8) or,
        - when a split in the row above happened

        '''
        if not options.get('groups', {}).get('ids'):
            return False

        periods = [{'string': self.format_date(options), 'class': 'number'}] + options['comparison']['periods']

        # generate specific groups for each period
        groups = []
        for period in periods:
            for group in options['groups'].get('ids'):
                groups.append((period,) + tuple(group))

        # add sentinel group that won't be rendered, this way we don't
        # need special code to handle the last group of every row
        groups.append(('sentinel',) * (len(options['groups'].get('fields', [])) + 1))

        column_hierarchy = []

        # row_splits ensures that we do not span over a split in the row above.
        # E.g. the following is *not* allowed (there should be 2 product sales):
        # | Agrolait | Camptocamp |
        # |  20000 Product Sales  |
        row_splits = []

        for field_index, field in enumerate(['period'] + options['groups'].get('fields')):
            current_colspan = 0
            current_group = False
            last_group = False

            # every report has an empty, unnamed header as the leftmost column
            current_hierarchy_line = [{'name': '', 'colspan': 1}]

            for group_index, group_ids in enumerate(groups):
                current_group = group_ids[field_index]
                if last_group is False:
                    last_group = current_group

                if last_group != current_group or group_index in row_splits:
                    current_hierarchy_line.append({
                        # field_index - 1 because ['period'] is not part of options['groups']['fields']
                        'name': last_group.get('string') if field == 'period' else self._get_column_name(last_group, options['groups']['fields'][field_index - 1]),
                        'colspan': current_colspan
                    })
                    last_group = current_group
                    current_colspan = 0
                    row_splits.append(group_index)

                current_colspan += 1

            column_hierarchy.append(current_hierarchy_line)

        return column_hierarchy

    def _get_columns_name(self, options):
        columns = [{'name': ''}]
        if self.debit_credit and not options.get('comparison', {}).get('periods', False):
            columns += [{'name': _('Debit'), 'class': 'number'}, {'name': _('Credit'), 'class': 'number'}]
        columns += [{'name': self.format_date(options), 'class': 'number'}]
        if options.get('comparison') and options['comparison'].get('periods'):
            for period in options['comparison']['periods']:
                columns += [{'name': period.get('string'), 'class': 'number'}]
            if options['comparison'].get('number_period') == 1 and not options.get('groups'):
                columns += [{'name': '%', 'class': 'number'}]

        if options.get('groups', {}).get('ids'):
            columns_for_groups = []
            for column in columns[1:]:
                for ids in options['groups'].get('ids'):
                    group_column_name = ''
                    for index, id in enumerate(ids):
                        column_name = self._get_column_name(id, options['groups']['fields'][index])
                        group_column_name += ' ' + column_name
                    columns_for_groups.append({'name': column.get('name') + group_column_name, 'class': 'number'})
            columns = columns[:1] + columns_for_groups

        return columns

    def _get_filter_journals(self):
        if self == self.env.ref('account_reports.account_financial_report_cashsummary0'):
            return self.env['account.journal'].search([('company_id', 'in', self.env.user.company_ids.ids or [self.env.user.company_id.id]), ('type', 'in', ['bank', 'cash'])], order="company_id, name")
        return super(ReportAccountFinancialReport, self)._get_filter_journals()

    def _build_options(self, previous_options=None):
        options = super(ReportAccountFinancialReport, self)._build_options(previous_options=previous_options)

        if self.filter_ir_filters:
            options['ir_filters'] = []

            previously_selected_id = False
            if previous_options and previous_options.get('ir_filters'):
                previously_selected_id = [f for f in previous_options['ir_filters'] if f.get('selected')]
                if previously_selected_id:
                    previously_selected_id = previously_selected_id[0]['id']
                else:
                    previously_selected_id = False

            for ir_filter in self.filter_ir_filters:
                options['ir_filters'].append({
                    'id': ir_filter.id,
                    'name': ir_filter.name,
                    'domain': ir_filter.domain,
                    'context': ir_filter.context,
                    'selected': ir_filter.id == previously_selected_id,
                })

        return options

    @api.model
    def _get_options(self, previous_options=None):
        if self.date_range:
            self.filter_date = {'date_from': '', 'date_to': '', 'filter': 'this_year'}
            if self.comparison:
                self.filter_comparison = {'date_from': '', 'date_to': '', 'filter': 'no_comparison', 'number_period': 1}
        else:
            self.filter_date = {'date': '', 'filter': 'today'}
            if self.comparison:
                self.filter_comparison = {'date': '', 'filter': 'no_comparison', 'number_period': 1}
        self.filter_cash_basis = False if self.cash_basis else None
        if self.unfold_all_filter:
            self.filter_unfold_all = False
        if self.show_journal_filter:
            self.filter_journals = True
        self.filter_all_entries = False
        self.filter_analytic = self.analytic or None
        if self.analytic:
            self.filter_analytic_accounts = [] if self.env.user.id in self.env.ref('analytic.group_analytic_accounting').users.ids else None
            self.filter_analytic_tags = [] if self.env.user.id in self.env.ref('analytic.group_analytic_tags').users.ids else None
            #don't display the analytic filtering options if no option would be shown
            if self.filter_analytic_accounts is None and self.filter_analytic_tags is None:
                self.filter_analytic = None
        self.filter_hierarchy = True if self.hierarchy_option else None
        self.filter_ir_filters = self.applicable_filters_ids or None

        return super(ReportAccountFinancialReport, self)._get_options(previous_options)

    def _create_action_and_menu(self, parent_id):
        # create action and menu with corresponding external ids, in order to
        # remove those entries when deinstalling the corresponding module
        module = self._context.get('install_module', 'account_reports')
        IMD = self.env['ir.model.data']
        for report in self:
            if not report.generated_menu_id:
                action_vals = {
                    'name': report._get_report_name(),
                    'tag': 'account_report',
                    'context': {
                        'model': 'account.financial.html.report',
                        'id': report.id,
                    },
                }
                action_xmlid = "%s.%s" % (module, 'account_financial_html_report_action_' + str(report.id))
                data = dict(xml_id=action_xmlid, values=action_vals, noupdate=True)
                action = self.env['ir.actions.client']._load_records([data])

                menu_vals = {
                    'name': report._get_report_name(),
                    'parent_id': parent_id or IMD.xmlid_to_res_id('account.menu_finance_reports'),
                    'action': 'ir.actions.client,%s' % (action.id,),
                }
                menu_xmlid = "%s.%s" % (module, 'account_financial_html_report_menu_' + str(report.id))
                data = dict(xml_id=menu_xmlid, values=menu_vals, noupdate=True)
                menu = self.env['ir.ui.menu']._load_records([data])

                self.write({'generated_menu_id': menu.id})

    @api.model
    def create(self, vals):
        parent_id = vals.pop('parent_id', False)
        res = super(ReportAccountFinancialReport, self).create(vals)
        res._create_action_and_menu(parent_id)
        return res

    @api.multi
    def write(self, vals):
        parent_id = vals.pop('parent_id', False)
        res = super(ReportAccountFinancialReport, self).write(vals)
        if parent_id:
            # this keeps external ids "alive" when upgrading the module
            for report in self:
                report._create_action_and_menu(parent_id)
        return res

    @api.multi
    def unlink(self):
        for report in self:
            default_parent_id = self.env['ir.model.data'].xmlid_to_res_id('account.menu_finance_reports')
            menu = self.env['ir.ui.menu'].search([('parent_id', '=', default_parent_id), ('name', '=', report.name)])
            if menu:
                menu.action.unlink()
                menu.unlink()
        return super(ReportAccountFinancialReport, self).unlink()

    def _get_currency_table(self):
        used_currency = self.env.user.company_id.currency_id.with_context(company_id=self.env.user.company_id.id)
        currency_table = {}
        for company in self.env['res.company'].search([]):
            if company.currency_id != used_currency:
                currency_table[company.currency_id.id] = used_currency.rate / company.currency_id.rate
        return currency_table

    def _get_groups(self, domain, group_by):
        '''This returns a list of lists of record ids. Every list represents a
           domain to be used in a column in the report. The ids in the list are
           in the same order as `group_by`. Only groups containing an
           account.move.line are returned.

           E.g. with group_by=['partner_id', 'journal_id']:
           # partner_id  journal_id
           [(7,2),
            (7,5),
            (8,8)]
        '''
        if any([field not in self.env['account.move.line'] for field in group_by]):
            raise ValueError(_('Groupby should be a field from account.move.line'))
        domain = [domain] if domain else [()]
        group_by = ', '.join(['"account_move_line".%s' % field for field in group_by])
        all_report_lines = self.env['account.financial.html.report.line'].search([('id', 'child_of', self.line_ids.ids)])
        all_domains = expression.OR([safe_eval(dom) for dom in all_report_lines.mapped('domain') if dom])
        all_domains = expression.AND([all_domains] + domain)
        tables, where_clause, where_params = self.env['account.move.line']._query_get(domain=all_domains)
        sql = 'SELECT %s FROM %s WHERE %s GROUP BY %s ORDER BY %s' % (group_by, tables, where_clause, group_by, group_by)
        self.env.cr.execute(sql, where_params)
        return self.env.cr.fetchall()

    def _get_filter_info(self, options):
        if not options['ir_filters']:
            return False, False

        selected_ir_filter = [f for f in options['ir_filters'] if f.get('selected')]
        if selected_ir_filter:
            selected_ir_filter = selected_ir_filter[0]
        else:
            return False, False

        domain = safe_eval(selected_ir_filter['domain'])
        group_by = safe_eval(selected_ir_filter['context']).get('group_by', [])
        return domain, group_by

    @api.multi
    def _get_lines(self, options, line_id=None):
        line_obj = self.line_ids
        if line_id:
            line_obj = self.env['account.financial.html.report.line'].search([('id', '=', line_id)])
        if options.get('comparison') and options.get('comparison').get('periods'):
            line_obj = line_obj.with_context(periods=options['comparison']['periods'])
        if options.get('ir_filters'):
            line_obj = line_obj.with_context(periods=options.get('ir_filters'))

        currency_table = self._get_currency_table()
        domain, group_by = self._get_filter_info(options)

        if group_by:
            options['groups'] = {}
            options['groups']['fields'] = group_by
            options['groups']['ids'] = self._get_groups(domain, group_by)

        amount_of_periods = len((options.get('comparison') or {}).get('periods') or []) + 1
        amount_of_group_ids = len(options.get('groups', {}).get('ids') or []) or 1
        linesDicts = [[{} for _ in range(0, amount_of_group_ids)] for _ in range(0, amount_of_periods)]

        res = line_obj.with_context(
            cash_basis=options.get('cash_basis'),
            filter_domain=domain,
        )._get_lines(self, currency_table, options, linesDicts)
        return res

    def _get_report_name(self):
        return self.name

    @api.multi
    def _get_copied_name(self):
        '''Return a copied name of the account.financial.html.report record by adding the suffix (copy) at the end
        until the name is unique.

        :return: an unique name for the copied account.financial.html.report
        '''
        self.ensure_one()
        name = self.name + ' ' + _('(copy)')
        while self.search_count([('name', '=', name)]) > 0:
            name += ' ' + _('(copy)')
        return name

    @api.multi
    @api.returns('self', lambda value: value.id)
    def copy(self, default=None):
        '''Copy the whole financial report hierarchy by duplicating each line recursively.

        :param default: Default values.
        :return: The copied account.financial.html.report record.
        '''
        self.ensure_one()
        if default is None:
            default = {}
        default.update({'name': self._get_copied_name()})
        copied_report_id = super(ReportAccountFinancialReport, self).copy(default=default)
        for line in self.line_ids:
            line._copy_hierarchy(report_id=self, copied_report_id=copied_report_id)
        return copied_report_id


class AccountFinancialReportLine(models.Model):
    _name = "account.financial.html.report.line"
    _description = "Account Report Line"
    _order = "sequence"
    _parent_store = True

    name = fields.Char('Section Name', translate=True)
    code = fields.Char('Code')
    financial_report_id = fields.Many2one('account.financial.html.report', 'Financial Report')
    parent_id = fields.Many2one('account.financial.html.report.line', string='Parent', ondelete='cascade')
    children_ids = fields.One2many('account.financial.html.report.line', 'parent_id', string='Children')
    parent_path = fields.Char(index=True)
    sequence = fields.Integer()

    domain = fields.Char(default=None)
    formulas = fields.Char()
    groupby = fields.Char("Group by", default=False)
    figure_type = fields.Selection([('float', 'Float'), ('percents', 'Percents'), ('no_unit', 'No Unit')],
                                   'Type', default='float', required=True)
    print_on_new_page = fields.Boolean('Print On New Page', help='When checked this line and everything after it will be printed on a new page.')
    green_on_positive = fields.Boolean('Is growth good when positive', default=True)
    level = fields.Integer(required=True)
    special_date_changer = fields.Selection([
        ('from_beginning', 'From the beginning'),
        ('to_beginning_of_period', 'At the beginning of the period'),
        ('normal', 'Use given dates'),
        ('strict_range', 'Force given dates for all accounts and account types'),
        ('from_fiscalyear', 'From the beginning of the fiscal year'),
    ], default='normal')
    show_domain = fields.Selection([('always', 'Always'), ('never', 'Never'), ('foldable', 'Foldable')], default='foldable')
    hide_if_zero = fields.Boolean(default=False)
    action_id = fields.Many2one('ir.actions.actions')

    _sql_constraints = [
        ('code_uniq', 'unique (code)', "A report line with the same code already exists."),
    ]

    @api.one
    @api.constrains('code')
    def _code_constrains(self):
        if self.code and self.code.strip().lower() in __builtins__.keys():
            raise ValidationError('The code "%s" is invalid on line with name "%s"' % (self.code, self.name))

    @api.multi
    def _get_copied_code(self):
        '''Look for an unique copied code.

        :return: an unique code for the copied account.financial.html.report.line
        '''
        self.ensure_one()
        code = self.code + '_COPY'
        while self.search_count([('code', '=', code)]) > 0:
            code += '_COPY'
        return code

    @api.multi
    def _copy_hierarchy(self, report_id=None, copied_report_id=None, parent_id=None, code_mapping=None):
        ''' Copy the whole hierarchy from this line by copying each line children recursively and adapting the
        formulas with the new copied codes.

        :param report_id: The financial report that triggered the duplicate.
        :param copied_report_id: The copy of old_report_id.
        :param parent_id: The parent line in the hierarchy (a copy of the original parent line).
        :param code_mapping: A dictionary keeping track of mapping old_code -> new_code
        '''
        self.ensure_one()
        if code_mapping is None:
            code_mapping = {}
        # If the line points to the old report, replace with the new one.
        # Otherwise, cut the link to another financial report.
        if report_id and copied_report_id and self.financial_report_id.id == report_id.id:
            financial_report_id = copied_report_id.id
        else:
            financial_report_id = None
        copy_line_id = self.copy({
            'financial_report_id': financial_report_id,
            'parent_id': parent_id and parent_id.id,
            'code': self.code and self._get_copied_code(),
        })
        # Keep track of old_code -> new_code in a mutable dict
        if self.code:
            code_mapping[self.code] = copy_line_id.code
        # Copy children
        for line in self.children_ids:
            line._copy_hierarchy(parent_id=copy_line_id, code_mapping=code_mapping)
        # Update formulas
        if self.formulas:
            copied_formulas = self.formulas
            for k, v in code_mapping.items():
                for field in ['debit', 'credit', 'balance', 'amount_residual']:
                    suffix = '.' + field
                    copied_formulas = copied_formulas.replace(k + suffix, v + suffix)
            copy_line_id.formulas = copied_formulas

    def _query_get_select_sum(self, currency_table):
        """ Little function to help building the SELECT statement when computing the report lines.

            @param currency_table: dictionary containing the foreign currencies (key) and their factor (value)
                compared to the current user's company currency
            @returns: the string and parameters to use for the SELECT
        """
        extra_params = []
        select = '''
            COALESCE(SUM(\"account_move_line\".balance), 0) AS balance,
            COALESCE(SUM(\"account_move_line\".amount_residual), 0) AS amount_residual,
            COALESCE(SUM(\"account_move_line\".debit), 0) AS debit,
            COALESCE(SUM(\"account_move_line\".credit), 0) AS credit
        '''
        if currency_table:
            select = 'COALESCE(SUM(CASE '
            for currency_id, rate in currency_table.items():
                extra_params += [currency_id, rate]
                select += 'WHEN \"account_move_line\".company_currency_id = %s THEN \"account_move_line\".balance * %s '
            select += 'ELSE \"account_move_line\".balance END), 0) AS balance, COALESCE(SUM(CASE '
            for currency_id, rate in currency_table.items():
                extra_params += [currency_id, rate]
                select += 'WHEN \"account_move_line\".company_currency_id = %s THEN \"account_move_line\".amount_residual * %s '
            select += 'ELSE \"account_move_line\".amount_residual END), 0) AS amount_residual, COALESCE(SUM(CASE '
            for currency_id, rate in currency_table.items():
                extra_params += [currency_id, rate]
                select += 'WHEN \"account_move_line\".company_currency_id = %s THEN \"account_move_line\".debit * %s '
            select += 'ELSE \"account_move_line\".debit END), 0) AS debit, COALESCE(SUM(CASE '
            for currency_id, rate in currency_table.items():
                extra_params += [currency_id, rate]
                select += 'WHEN \"account_move_line\".company_currency_id = %s THEN \"account_move_line\".credit * %s '
            select += 'ELSE \"account_move_line\".credit END), 0) AS credit'

        if self.env.context.get('cash_basis'):
            for field in ['debit', 'credit', 'balance']:
                #replace the columns selected but not the final column name (... AS <field>)
                number_of_occurence = len(select.split(field)) - 1
                select = select.replace(field, field + '_cash_basis', number_of_occurence - 1)
        return select, extra_params

    def _get_with_statement(self, financial_report):
        """ This function allow to define a WITH statement as prologue to the usual queries returned by query_get().
            It is useful if you need to shadow a table entirely and let the query_get work normally although you're
            fetching rows from your temporary table (built in the WITH statement) instead of the regular tables.

            @returns: the WITH statement to prepend to the sql query and the parameters used in that WITH statement
            @rtype: tuple(char, list)
        """
        sql = ''
        params = []

        #Cashflow Statement
        #------------------
        #The cash flow statement has a dedicated query because because we want to make a complex selection of account.move.line,
        #but keep simple to configure the financial report lines.
        #So we have the following query, aliasing the account.move.line table to consider only the journal entries where, at
        #least, one line is touching a liquidity account. Counterparts are either shown directly if they're not reconciled (or
        #not reconciliable), either replaced by the accounts of the entries they're reconciled with.
        if financial_report == self.env.ref('account_reports.account_financial_report_cashsummary0'):
            # Get available fields.
            replace_columns = {
                'date': 'ref.date',
                'debit_cash_basis': 'CASE WHEN \"account_move_line\".debit > 0 THEN ref.matched_percentage * \"account_move_line\".debit ELSE 0 END AS debit_cash_basis',
                'credit_cash_basis': 'CASE WHEN \"account_move_line\".credit > 0 THEN ref.matched_percentage * \"account_move_line\".credit ELSE 0 END AS credit_cash_basis',
                'balance_cash_basis': 'ref.matched_percentage * \"account_move_line\".balance AS balance_cash_basis'
            }
            columns = []
            columns_2 = []
            for name, field in self.env['account.move.line']._fields.items():
                if not(field.store and field.type not in ('one2many', 'many2many')):
                    continue
                columns.append('\"account_move_line\".%s' % name)
                if name in replace_columns:
                    columns_2.append(replace_columns.get(name))
                else:
                    columns_2.append('\"account_move_line\".%s' % name)
            select_clause_1 = ', '.join(columns)
            select_clause_2 = ', '.join(columns_2)

            # Get moves having a line using a bank account in one of the selected journals.
            if self.env.context.get('journal_ids'):
                bank_journals = self.env['account.journal'].browse(self.env.context.get('journal_ids'))
            else:
                bank_journals = self.env['account.journal'].search([('type', 'in', ('bank', 'cash'))])
            bank_accounts = bank_journals.mapped('default_debit_account_id') + bank_journals.mapped('default_credit_account_id')

            self._cr.execute('SELECT DISTINCT(move_id) FROM account_move_line WHERE account_id IN %s', [tuple(bank_accounts.ids)])
            bank_move_ids = tuple([r[0] for r in self.env.cr.fetchall()])

            # Avoid crash if there's no bank moves to consider
            if not bank_move_ids:
                return '''
                WITH account_move_line AS (
                    SELECT ''' + select_clause_1 + '''
                    FROM account_move_line
                    WHERE False)''', []

            # Fake domain to always get the join to the account_move_line__move_id table.
            fake_domain = [('move_id.id', '!=', None)]
            sub_tables, sub_where_clause, sub_where_params = self.env['account.move.line']._query_get(domain=fake_domain)
            tables, where_clause, where_params = self.env['account.move.line']._query_get(domain=fake_domain + safe_eval(self.domain))

            sql = '''
                WITH account_move_line AS (
                    WITH payment_table AS (
                        SELECT
                            aml.id,
                            "account_move_line".move_id,
                            "account_move_line".date,
                            CASE WHEN aml.balance = 0 THEN
                                0 ELSE part.amount / ABS("account_move_line__move_id".amount)
                            END AS matched_percentage
                        FROM account_partial_reconcile part
                        LEFT JOIN account_move_line aml ON aml.id = part.debit_move_id
                        LEFT JOIN account_account acc ON aml.account_id = acc.id
                        LEFT JOIN account_move am ON aml.move_id = am.id, ''' + sub_tables + '''
                        WHERE part.credit_move_id = "account_move_line".id
                        AND acc.reconcile
                        AND aml.move_id IN %s
                        AND ''' + sub_where_clause + '''

                        UNION ALL

                        SELECT
                            aml.id,
                            "account_move_line".move_id,
                            "account_move_line".date,
                            CASE WHEN aml.balance = 0 THEN
                                0 ELSE part.amount / ABS("account_move_line__move_id".amount)
                            END AS matched_percentage
                        FROM account_partial_reconcile part
                        LEFT JOIN account_move_line aml ON aml.id = part.credit_move_id
                        LEFT JOIN account_account acc ON aml.account_id = acc.id
                        LEFT JOIN account_move am ON aml.move_id = am.id, ''' + sub_tables + '''
                        WHERE part.debit_move_id = "account_move_line".id
                        AND acc.reconcile
                        AND aml.move_id IN %s
                        AND ''' + sub_where_clause + '''
                    )

                    SELECT ''' + select_clause_2 + '''
                    FROM ''' + tables + '''
                    RIGHT JOIN payment_table ref ON ("account_move_line".move_id = ref.move_id)
                    LEFT JOIN account_account acc ON "account_move_line".account_id = acc.id
                    WHERE acc.internal_type = 'other'
                    AND "account_move_line".move_id NOT IN %s
                    AND ''' + where_clause + '''

                    UNION ALL

                    SELECT ''' + select_clause_1 + '''
                    FROM ''' + tables + '''
                    WHERE "account_move_line".move_id IN %s
                    AND ''' + where_clause + '''
                )
            '''
            params = [tuple(bank_move_ids)] + sub_where_params + [tuple(bank_move_ids)] + sub_where_params\
                     + [tuple(bank_move_ids)] + where_params + [tuple(bank_move_ids)] + where_params
        elif self.env.context.get('cash_basis'):
            #Cash basis option
            #-----------------
            #In cash basis, we need to show amount on income/expense accounts, but only when they're paid AND under the payment date in the reporting, so
            #we have to make a complex query to join aml from the invoice (for the account), aml from the payments (for the date) and partial reconciliation
            #(for the reconciled amount).
            user_types = self.env['account.account.type'].search([('type', 'in', ('receivable', 'payable'))])
            if not user_types:
                return sql, params

            # Get all columns from account_move_line using the psql metadata table in order to make sure all columns from the account.move.line model
            # are present in the shadowed table.
            sql = "SELECT column_name FROM information_schema.columns WHERE table_name='account_move_line'"
            self.env.cr.execute(sql)
            columns = []
            columns_2 = []
            replace_columns = {'date': 'ref.date',
                                'debit_cash_basis': 'CASE WHEN aml.debit > 0 THEN ref.matched_percentage * aml.debit ELSE 0 END AS debit_cash_basis',
                                'credit_cash_basis': 'CASE WHEN aml.credit > 0 THEN ref.matched_percentage * aml.credit ELSE 0 END AS credit_cash_basis',
                                'balance_cash_basis': 'ref.matched_percentage * aml.balance AS balance_cash_basis'}
            for field in self.env.cr.fetchall():
                field = field[0]
                columns.append("\"account_move_line\".\"%s\"" % (field,))
                if field in replace_columns:
                    columns_2.append(replace_columns.get(field))
                else:
                    columns_2.append('aml.\"%s\"' % (field,))
            select_clause_1 = ', '.join(columns)
            select_clause_2 = ', '.join(columns_2)

            #we use query_get() to filter out unrelevant journal items to have a shadowed table as small as possible
            tables, where_clause, where_params = self.env['account.move.line']._query_get(domain=self._get_aml_domain())
            sql = """WITH account_move_line AS (
              SELECT """ + select_clause_1 + """
               FROM """ + tables + """
               WHERE (\"account_move_line\".journal_id IN (SELECT id FROM account_journal WHERE type in ('cash', 'bank'))
                 OR \"account_move_line\".move_id NOT IN (SELECT DISTINCT move_id FROM account_move_line WHERE user_type_id IN %s))
                 AND """ + where_clause + """
              UNION ALL
              (
               WITH payment_table AS (
                 SELECT aml.move_id, \"account_move_line\".date, CASE WHEN aml.balance = 0 THEN 0 ELSE part.amount / ABS(am.amount) END as matched_percentage
                   FROM account_partial_reconcile part LEFT JOIN account_move_line aml ON aml.id = part.debit_move_id LEFT JOIN account_move am ON aml.move_id = am.id, """ + tables + """
                   WHERE part.credit_move_id = "account_move_line".id
                    AND "account_move_line".user_type_id IN %s
                    AND """ + where_clause + """
                 UNION ALL
                 SELECT aml.move_id, \"account_move_line\".date, CASE WHEN aml.balance = 0 THEN 0 ELSE part.amount / ABS(am.amount) END as matched_percentage
                   FROM account_partial_reconcile part LEFT JOIN account_move_line aml ON aml.id = part.credit_move_id LEFT JOIN account_move am ON aml.move_id = am.id, """ + tables + """
                   WHERE part.debit_move_id = "account_move_line".id
                    AND "account_move_line".user_type_id IN %s
                    AND """ + where_clause + """
               )
               SELECT """ + select_clause_2 + """
                FROM account_move_line aml
                RIGHT JOIN payment_table ref ON aml.move_id = ref.move_id
                WHERE journal_id NOT IN (SELECT id FROM account_journal WHERE type in ('cash', 'bank'))
                  AND aml.move_id IN (SELECT DISTINCT move_id FROM account_move_line WHERE user_type_id IN %s)
              )
            ) """
            params = [tuple(user_types.ids)] + where_params + [tuple(user_types.ids)] + where_params + [tuple(user_types.ids)] + where_params + [tuple(user_types.ids)]
        return sql, params

    def _compute_line(self, currency_table, financial_report, group_by=None, domain=[]):
        """ Computes the sum that appeas on report lines when they aren't unfolded. It is using _query_get() function
            of account.move.line which is based on the context, and an additional domain (the field domain on the report
            line) to build the query that will be used.

            @param currency_table: dictionary containing the foreign currencies (key) and their factor (value)
                compared to the current user's company currency
            @param financial_report: browse_record of the financial report we are willing to compute the lines for
            @param group_by: used in case of conditionnal sums on the report line
            @param domain: domain on the report line to consider in the query_get() call

            @returns : a dictionnary that has for each aml in the domain a dictionnary of the values of the fields
        """
        domain = domain and safe_eval(ustr(domain))
        for index, condition in enumerate(domain):
            if condition[0].startswith('tax_ids.'):
                new_condition = (condition[0].partition('.')[2], condition[1], condition[2])
                taxes = self.env['account.tax'].with_context(active_test=False).search([new_condition])
                domain[index] = ('tax_ids', 'in', taxes.ids)
        tables, where_clause, where_params = self.env['account.move.line']._query_get(domain=self._get_aml_domain())
        if financial_report.tax_report:
            where_clause += ''' AND "account_move_line".tax_exigible = 't' '''

        line = self
        financial_report = False

        while(not financial_report):
            financial_report = line.financial_report_id
            if not line.parent_id:
                break
            line = line.parent_id

        sql, params = self._get_with_statement(financial_report)

        select, select_params = self._query_get_select_sum(currency_table)
        where_params = params + select_params + where_params

        if (self.env.context.get('sum_if_pos') or self.env.context.get('sum_if_neg')) and group_by:
            sql = sql + "SELECT account_move_line." + group_by + " as " + group_by + "," + select + " FROM " + tables + " WHERE " + where_clause + " GROUP BY account_move_line." + group_by
            self.env.cr.execute(sql, where_params)
            res = {'balance': 0, 'debit': 0, 'credit': 0, 'amount_residual': 0}
            for row in self.env.cr.dictfetchall():
                if (row['balance'] > 0 and self.env.context.get('sum_if_pos')) or (row['balance'] < 0 and self.env.context.get('sum_if_neg')):
                    for field in ['debit', 'credit', 'balance', 'amount_residual']:
                        res[field] += row[field]
            res['currency_id'] = self.env.user.company_id.currency_id.id
            return res

        sql = sql + "SELECT " + select + " FROM " + tables + " WHERE " + where_clause
        self.env.cr.execute(sql, where_params)
        results = self.env.cr.dictfetchall()[0]
        results['currency_id'] = self.env.user.company_id.currency_id.id
        return results

    @api.multi
    def _compute_date_range(self):
        '''Compute the current report line date range according to the dates passed through the context
        and its specified special_date_changer.

        :return: The date_from, date_to, strict_range values to consider for the report line.
        '''
        date_from = self._context.get('date_from', False)
        date_to = self._context.get('date_to', False)

        strict_range = self.special_date_changer == 'strict_range'
        if self.special_date_changer == 'from_beginning':
            date_from = False
        if self.special_date_changer == 'to_beginning_of_period' and date_from:
            date_tmp = fields.Date.from_string(self._context['date_from']) - relativedelta(days=1)
            date_to = date_tmp.strftime('%Y-%m-%d')
            date_from = False
        if self.special_date_changer == 'from_fiscalyear' and date_to:
            date_tmp = fields.Date.from_string(date_to)
            date_tmp = self.env.user.company_id.compute_fiscalyear_dates(date_tmp)['date_from']
            date_from = date_tmp.strftime('%Y-%m-%d')
            strict_range = True
        return date_from, date_to, strict_range

    @api.multi
    def report_move_lines_action(self):
        domain = safe_eval(self.domain)
        if 'date_from' in self.env.context.get('context', {}):
            if self.env.context['context'].get('date_from'):
                domain = expression.AND([domain, [('date', '>=', self.env.context['context']['date_from'])]])
            if self.env.context['context'].get('date_to'):
                domain = expression.AND([domain, [('date', '<=', self.env.context['context']['date_to'])]])
            if self.env.context['context'].get('state', 'all') == 'posted':
                domain = expression.AND([domain, [('move_id.state', '=', 'posted')]])
            if self.env.context['context'].get('company_ids'):
                domain = expression.AND([domain, [('company_id', 'in', self.env.context['context']['company_ids'])]])
        return {'type': 'ir.actions.act_window',
                'name': 'Journal Items (%s)' % self.name,
                'res_model': 'account.move.line',
                'view_mode': 'tree,form',
                'domain': domain,
                }

    @api.one
    @api.constrains('groupby')
    def _check_same_journal(self):
        if self.groupby and self.groupby not in self.env['account.move.line']:
            raise ValidationError(_("Groupby should be a journal item field"))

    def _get_sum(self, currency_table, financial_report, field_names=None):
        ''' Returns the sum of the amls in the domain '''
        if not field_names:
            field_names = ['debit', 'credit', 'balance', 'amount_residual']
        res = dict((fn, 0.0) for fn in field_names)
        if self.domain:
            date_from, date_to, strict_range = \
                self._compute_date_range()
            res = self.with_context(strict_range=strict_range, date_from=date_from, date_to=date_to)._compute_line(currency_table, financial_report, group_by=self.groupby, domain=self._get_aml_domain())
        return res

    @api.one
    def _get_balance(self, linesDict, currency_table, financial_report, field_names=None):
        if not field_names:
            field_names = ['debit', 'credit', 'balance']
        res = dict((fn, 0.0) for fn in field_names)
        c = FormulaContext(self.env['account.financial.html.report.line'], linesDict, currency_table, financial_report, self)
        if self.formulas:
            for f in self.formulas.split(';'):
                [field, formula] = f.split('=')
                field = field.strip()
                if field in field_names:
                    try:
                        res[field] = safe_eval(formula, c, nocopy=True)
                    except ValueError as err:
                        if 'division by zero' in err.args[0]:
                            res[field] = 0
                        else:
                            raise err
        return res

    def _get_rows_count(self):
        groupby = self.groupby or 'id'
        if groupby not in self.env['account.move.line']:
            raise ValueError(_('Groupby should be a field from account.move.line'))

        date_from, date_to, strict_range = self._compute_date_range()
        tables, where_clause, where_params = self.env['account.move.line'].with_context(strict_range=strict_range,
                                                                                        date_from=date_from,
                                                                                        date_to=date_to)._query_get(domain=self._get_aml_domain())

        query = 'SELECT count(distinct(account_move_line.' + groupby + ')) FROM ' + tables + 'WHERE' + where_clause
        self.env.cr.execute(query, where_params)
        return self.env.cr.dictfetchall()[0]['count']

    def _get_value_from_context(self):
        if self.env.context.get('financial_report_line_values'):
            return self.env.context.get('financial_report_line_values').get(self.code, 0)
        return 0

    def _format(self, value):
        if self.env.context.get('no_format'):
            return value
        value['no_format_name'] = value['name']
        if self.figure_type == 'float':
            currency_id = self.env.user.company_id.currency_id
            if currency_id.is_zero(value['name']):
                # don't print -0.0 in reports
                value['name'] = abs(value['name'])
            value['name'] = formatLang(self.env, value['name'], currency_obj=currency_id)
            return value
        if self.figure_type == 'percents':
            value['name'] = str(round(value['name'] * 100, 1)) + '%'
            return value
        value['name'] = round(value['name'], 1)
        return value

    def _get_gb_name(self, gb_id):
        if self.groupby and self.env['account.move.line']._fields[self.groupby].relational:
            relation = self.env['account.move.line']._fields[self.groupby].comodel_name
            gb = self.env[relation].browse(gb_id)
            return gb.name_get()[0][1] if gb and gb.exists() else _('Undefined')
        return gb_id

    def _build_cmp(self, balance, comp):
        if comp != 0:
            res = round((balance - comp) / comp * 100, 1)
            # In case the comparison is made on a negative figure, the color should be the other
            # way around. For example:
            #                       2018         2017           %
            # Product Sales      1000.00     -1000.00     -200.0%
            #
            # The percentage is negative, which is mathematically correct, but my sales increased
            # => it should be green, not red!
            if (res > 0) != (self.green_on_positive and comp > 0):
                return {'name': str(res) + '%', 'class': 'number color-red'}
            else:
                return {'name': str(res) + '%', 'class': 'number color-green'}
        else:
            return {'name': _('n/a')}

    def _split_formulas(self):
        result = {}
        if self.formulas:
            for f in self.formulas.split(';'):
                [column, formula] = f.split('=')
                column = column.strip()
                result.update({column: formula})
        return result

    def _get_aml_domain(self):
        return (safe_eval(self.domain) or []) + (self._context.get('filter_domain') or []) + (self._context.get('group_domain') or [])

    def _get_group_domain(self, group, groups):
        return [(field, '=', grp) for field, grp in izip(groups['fields'], group)]

    def _eval_formula(self, financial_report, debit_credit, currency_table, linesDict_per_group, groups=False):
        groups = groups or {'fields': [], 'ids': [()]}
        debit_credit = debit_credit and financial_report.debit_credit
        formulas = self._split_formulas()

        line_res_per_group = []

        if not groups['ids']:
            return [{'line': {'balance': False}}]

        # this computes the results of the line itself
        for group_index, group in enumerate(groups['ids']):
            self_for_group = self.with_context(group_domain=self._get_group_domain(group, groups))
            linesDict = linesDict_per_group[group_index]
            line = False

            if self.code and self.code in linesDict:
                line = linesDict[self.code]
            elif formulas and formulas['balance'].strip() == 'count_rows' and self.groupby:
                line_res_per_group.append({'line': {'balance': self_for_group._get_rows_count()}})
            elif formulas and formulas['balance'].strip() == 'from_context':
                line_res_per_group.append({'line': {'balance': self_for_group._get_value_from_context()}})
            else:
                line = FormulaLine(self_for_group, currency_table, financial_report, linesDict=linesDict)

            if line:
                res = {}
                res['balance'] = line.balance
                if debit_credit:
                    res['credit'] = line.credit
                    res['debit'] = line.debit
                line_res_per_group.append(res)

        # don't need any groupby lines for count_rows and from_context formulas
        if all('line' in val for val in line_res_per_group):
            return line_res_per_group

        columns = []
        # this computes children lines in case the groupby field is set
        if self.domain and self.groupby and self.show_domain != 'never':
            if self.groupby not in self.env['account.move.line']:
                raise ValueError(_('Groupby should be a field from account.move.line'))

            groupby = [self.groupby or 'id']
            if groups:
                groupby = groups['fields'] + groupby
            groupby = ', '.join(['"account_move_line".%s' % field for field in groupby])

            aml_obj = self.env['account.move.line']
            tables, where_clause, where_params = aml_obj._query_get(domain=self._get_aml_domain())
            sql, params = self._get_with_statement(financial_report)
            if financial_report.tax_report:
                where_clause += ''' AND "account_move_line".tax_exigible = 't' '''

            select, select_params = self._query_get_select_sum(currency_table)
            params += select_params
            sql = sql + "SELECT " + groupby + ", " + select + " FROM " + tables + " WHERE " + where_clause + " GROUP BY " + groupby + " ORDER BY " + groupby

            params += where_params
            self.env.cr.execute(sql, params)
            results = self.env.cr.fetchall()
            for group_index, group in enumerate(groups['ids']):
                linesDict = linesDict_per_group[group_index]
                results_for_group = [result for result in results if group == result[:len(group)]]
                if results_for_group:
                    results_for_group = [r[len(group):] for r in results_for_group]
                    results_for_group = dict([(k[0], {'balance': k[1], 'amount_residual': k[2], 'debit': k[3], 'credit': k[4]}) for k in results_for_group])
                    c = FormulaContext(self.env['account.financial.html.report.line'].with_context(group_domain=self._get_group_domain(group, groups)),
                                       linesDict, currency_table, financial_report, only_sum=True)
                    if formulas:
                        for key in results_for_group:
                            c['sum'] = FormulaLine(results_for_group[key], currency_table, financial_report, type='not_computed')
                            c['sum_if_pos'] = FormulaLine(results_for_group[key]['balance'] >= 0.0 and results_for_group[key] or {'balance': 0.0},
                                                          currency_table, financial_report, type='not_computed')
                            c['sum_if_neg'] = FormulaLine(results_for_group[key]['balance'] <= 0.0 and results_for_group[key] or {'balance': 0.0},
                                                          currency_table, financial_report, type='not_computed')
                            for col, formula in formulas.items():
                                if col in results_for_group[key]:
                                    results_for_group[key][col] = safe_eval(formula, c, nocopy=True)
                    to_del = []
                    for key in results_for_group:
                        if self.env.user.company_id.currency_id.is_zero(results_for_group[key]['balance']):
                            to_del.append(key)
                    for key in to_del:
                        del results_for_group[key]
                    results_for_group.update({'line': line_res_per_group[group_index]})
                    columns.append(results_for_group)
                else:
                    columns.append({'line': {'balance': False}})

        return columns or [{'line': res} for res in line_res_per_group]

    def _put_columns_together(self, data, domain_ids):
        res = dict((domain_id, []) for domain_id in domain_ids)
        for period in data:
            debit_credit = False
            if 'debit' in period['line']:
                debit_credit = True
            for domain_id in domain_ids:
                if debit_credit:
                    res[domain_id].append(period.get(domain_id, {'debit': 0})['debit'])
                    res[domain_id].append(period.get(domain_id, {'credit': 0})['credit'])
                res[domain_id].append(period.get(domain_id, {'balance': 0})['balance'])
        return res

    def _divide_line(self, line):
        line1 = {
            'id': line['id'],
            'name': line['name'],
            'class': line['class'],
            'level': line['level'],
            'columns': [{'name': ''}] * len(line['columns']),
            'unfoldable': line['unfoldable'],
            'unfolded': line['unfolded'],
            'page_break': line['page_break'],
        }
        line2 = {
            'id': line['id'],
            'name': _('Total') + ' ' + line['name'],
            'class': 'total',
            'level': line['level'] + 1,
            'columns': line['columns'],
        }
        return [line1, line2]

    @api.multi
    def _get_lines(self, financial_report, currency_table, options, linesDicts):
        final_result_table = []
        comparison_table = [options.get('date')]
        comparison_table += options.get('comparison') and options['comparison'].get('periods', []) or []
        currency_precision = self.env.user.company_id.currency_id.rounding

        # build comparison table
        for line in self:
            res = []
            debit_credit = len(comparison_table) == 1
            domain_ids = {'line'}
            k = 0

            for period in comparison_table:
                date_from = period.get('date_from', False)
                date_to = period.get('date_to', False) or period.get('date', False)
                date_from, date_to, strict_range = line.with_context(date_from=date_from, date_to=date_to)._compute_date_range()

                r = line.with_context(date_from=date_from,
                                      date_to=date_to,
                                      strict_range=strict_range)._eval_formula(financial_report,
                                                                               debit_credit,
                                                                               currency_table,
                                                                               linesDicts[k],
                                                                               groups=options.get('groups'))
                debit_credit = False
                res.extend(r)
                for column in r:
                    domain_ids.update(column)
                k += 1

            res = line._put_columns_together(res, domain_ids)
            if line.hide_if_zero and all([float_is_zero(k, precision_rounding=currency_precision) for k in res['line']]):
                continue

            # Post-processing ; creating line dictionnary, building comparison, computing total for extended, formatting
            vals = {
                'id': line.id,
                'name': line.name,
                'level': line.level,
                'class': '',
                'columns': [{'name': l} for l in res['line']],
                'unfoldable': len(domain_ids) > 1 and line.show_domain != 'always',
                'unfolded': line.id in options.get('unfolded_lines', []) or line.show_domain == 'always',
                'page_break': line.print_on_new_page,
            }

            if financial_report.tax_report and line.domain and not line.action_id:
                vals['caret_options'] = 'tax.report.line'

            if line.action_id:
                vals['action_id'] = line.action_id.id
            domain_ids.remove('line')
            lines = [vals]
            groupby = line.groupby or 'aml'
            if line.id in options.get('unfolded_lines', []) or line.show_domain == 'always':
                if line.groupby:
                    domain_ids = sorted(list(domain_ids), key=lambda k: line._get_gb_name(k))
                for domain_id in domain_ids:
                    name = line._get_gb_name(domain_id)
                    vals = {
                        'id': domain_id,
                        'name': name and len(name) >= 45 and name[0:40] + '...' or name,
                        'level': 4,
                        'parent_id': line.id,
                        'columns': [{'name': l} for l in res[domain_id]],
                        'caret_options': groupby == 'account_id' and 'account.account' or groupby,
                    }
                    if line.financial_report_id.name == 'Aged Receivable':
                        vals['trust'] = self.env['res.partner'].browse([domain_id]).trust
                    lines.append(vals)
                if domain_ids and self.env.user.company_id.totals_below_sections:
                    lines.append({
                        'id': 'total_' + str(line.id),
                        'name': _('Total') + ' ' + line.name,
                        'class': 'o_account_reports_domain_total',
                        'parent_id': line.id,
                        'columns': copy.deepcopy(lines[0]['columns']),
                    })

            for vals in lines:
                if len(comparison_table) == 2 and not options.get('groups'):
                    vals['columns'].append(line._build_cmp(vals['columns'][0]['name'], vals['columns'][1]['name']))
                    for i in [0, 1]:
                        vals['columns'][i] = line._format(vals['columns'][i])
                else:
                    vals['columns'] = [line._format(v) for v in vals['columns']]
                if not line.formulas:
                    vals['columns'] = [{'name': ''} for k in vals['columns']]

            if len(lines) == 1:
                new_lines = line.children_ids._get_lines(financial_report, currency_table, options, linesDicts)
                if new_lines and line.formulas:
                    if self.env.user.company_id.totals_below_sections:
                        divided_lines = self._divide_line(lines[0])
                        result = [divided_lines[0]] + new_lines + [divided_lines[-1]]
                    else:
                        result = [lines[0]] + new_lines
                else:
                    result = lines + new_lines
            else:
                result = lines
            final_result_table += result

        return final_result_table


class FormulaLine(object):
    def __init__(self, obj, currency_table, financial_report, type='balance', linesDict=None):
        if linesDict is None:
            linesDict = {}
        fields = dict((fn, 0.0) for fn in ['debit', 'credit', 'balance'])
        if type == 'balance':
            fields = obj._get_balance(linesDict, currency_table, financial_report)[0]
            linesDict[obj.code] = self
        elif type in ['sum', 'sum_if_pos', 'sum_if_neg']:
            if type == 'sum_if_neg':
                obj = obj.with_context(sum_if_neg=True)
            if type == 'sum_if_pos':
                obj = obj.with_context(sum_if_pos=True)
            if obj._name == 'account.financial.html.report.line':
                fields = obj._get_sum(currency_table, financial_report)
                self.amount_residual = fields['amount_residual']
            elif obj._name == 'account.move.line':
                self.amount_residual = 0.0
                field_names = ['debit', 'credit', 'balance', 'amount_residual']
                res = obj.env['account.financial.html.report.line']._compute_line(currency_table, financial_report)
                for field in field_names:
                    fields[field] = res[field]
                self.amount_residual = fields['amount_residual']
        elif type == 'not_computed':
            for field in fields:
                fields[field] = obj.get(field, 0)
            self.amount_residual = obj.get('amount_residual', 0)
        elif type == 'null':
            self.amount_residual = 0.0
        self.balance = fields['balance']
        self.credit = fields['credit']
        self.debit = fields['debit']


class FormulaContext(dict):
    def __init__(self, reportLineObj, linesDict, currency_table, financial_report, curObj=None, only_sum=False, *data):
        self.reportLineObj = reportLineObj
        self.curObj = curObj
        self.linesDict = linesDict
        self.currency_table = currency_table
        self.only_sum = only_sum
        self.financial_report = financial_report
        return super(FormulaContext, self).__init__(data)

    def __getitem__(self, item):
        formula_items = ['sum', 'sum_if_pos', 'sum_if_neg']
        if item in set(__builtins__.keys()) - set(formula_items):
            return super(FormulaContext, self).__getitem__(item)

        if self.only_sum and item not in formula_items:
            return FormulaLine(self.curObj, self.currency_table, self.financial_report, type='null')
        if self.get(item):
            return super(FormulaContext, self).__getitem__(item)
        if self.linesDict.get(item):
            return self.linesDict[item]
        if item == 'sum':
            res = FormulaLine(self.curObj, self.currency_table, self.financial_report, type='sum')
            self['sum'] = res
            return res
        if item == 'sum_if_pos':
            res = FormulaLine(self.curObj, self.currency_table, self.financial_report, type='sum_if_pos')
            self['sum_if_pos'] = res
            return res
        if item == 'sum_if_neg':
            res = FormulaLine(self.curObj, self.currency_table, self.financial_report, type='sum_if_neg')
            self['sum_if_neg'] = res
            return res
        if item == 'NDays':
            d1 = fields.Date.from_string(self.curObj.env.context['date_from'])
            d2 = fields.Date.from_string(self.curObj.env.context['date_to'])
            res = (d2 - d1).days
            self['NDays'] = res
            return res
        if item == 'count_rows':
            return self.curObj._get_rows_count()
        if item == 'from_context':
            return self.curObj._get_value_from_context()
        line_id = self.reportLineObj.search([('code', '=', item)], limit=1)
        if line_id:
            date_from, date_to, strict_range = line_id._compute_date_range()
            res = FormulaLine(line_id.with_context(strict_range=strict_range, date_from=date_from, date_to=date_to), self.currency_table, self.financial_report, linesDict=self.linesDict)
            self.linesDict[item] = res
            return res
        return super(FormulaContext, self).__getitem__(item)


class IrModuleModule(models.Model):
    _inherit = "ir.module.module"

    @api.multi
    def _update_translations(self, filter_lang=None):
        """ Create missing translations after loading the one of account.financial.html.report

        Use the translations of the account.financial.html.report to translate the linked
        ir.actions.client and ir.ui.menu generated at the creation of the report
        """
        res = super(IrModuleModule, self)._update_translations(filter_lang=filter_lang)

        # generated missing action translations for translated reports
        self.env.cr.execute("""
           INSERT INTO ir_translation (lang, type, name, res_id, src, value, module, state)
           SELECT l.code, 'model', 'ir.actions.client,name', a.id, t.src, t.value, t.module, t.state
             FROM account_financial_html_report r
             JOIN ir_act_client a ON (r.name = a.name)
             JOIN ir_translation t ON (t.res_id = r.id AND t.name = 'account.financial.html.report,name')
             JOIN res_lang l on  (l.code = t.lang)
            WHERE NOT EXISTS (
                  SELECT 1 FROM ir_translation tt
                  WHERE (tt.name = 'ir.actions.client,name'
                    AND tt.lang = l.code
                    AND type='model'
                    AND tt.res_id = a.id)
                  )
        """)

        # generated missing menu translations for translated reports
        self.env.cr.execute("""
           INSERT INTO ir_translation (lang, type, name, res_id, src, value, module, state)
           SELECT l.code, 'model', 'ir.ui.menu,name', m.id, t.src, t.value, t.module, t.state
             FROM account_financial_html_report r
             JOIN ir_ui_menu m ON (r.name = m.name)
             JOIN ir_translation t ON (t.res_id = r.id AND t.name = 'account.financial.html.report,name')
             JOIN res_lang l on  (l.code = t.lang)
            WHERE NOT EXISTS (
                  SELECT 1 FROM ir_translation tt
                  WHERE (tt.name = 'ir.ui.menu,name'
                    AND tt.lang = l.code
                    AND type='model'
                    AND tt.res_id = m.id)
                  )
        """)

        return res
