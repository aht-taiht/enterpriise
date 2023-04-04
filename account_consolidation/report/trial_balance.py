# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import models, api, _
from .builder.comparison import ComparisonBuilder
from .builder.default import DefaultBuilder
from .handler.journals import JournalsHandler
from .handler.periods import PeriodsHandler


class AccountConsolidationTrialBalanceReport(models.Model):
    _inherit = "account.report"

    @api.model
    def _get_report_name(self):
        period_id = self._get_selected_period_id()
        return self.env['consolidation.period'].browse(period_id)['display_name'] or _("Trial Balance")

    def _set_context(self, options):
        ctx = super(AccountConsolidationTrialBalanceReport, self)._set_context(options)
        active_id = options.get('active_id')
        if active_id:
            ctx.update({'active_id': active_id})
        return ctx

    def get_report_filename(self, options):
        self = self.with_context(self._set_context(options))
        return super(AccountConsolidationTrialBalanceReport, self).get_report_filename(options)


class TrialBalanceCustomHandler(models.AbstractModel):
    _name = 'consolidation.trial.balance.report.handler'
    _inherit = 'account.report.custom.handler'
    _description = 'Trial Balance Custom Handler'

    def _dynamic_lines_generator(self, report, options, all_column_groups_expression_totals):
        options['column_headers'] = self._get_column_headers(options)

        lines = self._get_lines(options)
        new_lines = []

        for line in lines:
            new_lines.append((0, line))

        return new_lines

    def _custom_options_initializer(self, report, options, previous_options=None):
        super()._custom_options_initializer(report, options, previous_options=previous_options)
        options.pop('date', None)
        options['unfold_all'] = previous_options.get('unfold_all') if previous_options else True
        options['consolidation_hierarchy'] = True
        options['consolidation_show_zero_balance_accounts'] = previous_options.get('consolidation_show_zero_balance_accounts') if previous_options else True
        options['force_periods'] = (previous_options or {}).get('force_periods', False)

        if not self.env.context.get('active_id') and (previous_options or {}).get('active_id'):
            self = self.with_context(active_id=previous_options['active_id'])

        options['buttons'] = self._consolidated_balance_init_buttons(options)

        base_period = self._get_selected_period()
        handlers = [
            ('periods', PeriodsHandler(self.env)),
            ('consolidation_journals', JournalsHandler(self.env))
        ]

        for value in handlers:
            key, handler = value

            previous_handler_value = previous_options.get(key) if previous_options else None
            options[key] = handler.handle(previous_handler_value, base_period, options)

    def _get_column_headers(self, options):
        AnalysisPeriod = self.env['consolidation.period']
        all_period_ids = PeriodsHandler.get_selected_values(options) + [self._get_selected_period_id()]
        selected_periods = AnalysisPeriod.browse(all_period_ids)
        columns = []
        if len(selected_periods) == 1:
            columns += self._get_journals_headers(options)
        else:
            periods_columns = [{'name': period.display_name, 'class': 'number'} for period in selected_periods]
            # Add the percentage column
            if len(selected_periods) == 2:
                columns += periods_columns + [{'name': '%', 'class': 'number'}]
            else:
                columns += periods_columns
        return [columns]

    def _get_journals_headers(self, options):
        journal_ids = JournalsHandler.get_selected_values(options)
        journals = self.env['consolidation.journal'].browse(journal_ids)
        journal_columns = [self._get_journal_col(j, options) for j in journals]
        return journal_columns + [{'name': _('Total'), 'class': 'number'}]

    def _get_journal_col(self, journal, options):
        journal_name = journal.name
        if journal.company_period_id:
            journal_name = journal.company_period_id.company_name
        if self.env.context.get('print_mode') or options.get('xlsx_mode'):
            return {'name': journal_name}
        if journal.currencies_are_different and journal.company_period_id:
            cp = journal.company_period_id
            from_currency = cp.currency_chart_id.symbol
            to_currency = journal.originating_currency_id.symbol

            return {
                'name': journal.name,
                'consolidation_rate': journal.rate_consolidation,
                'from_currency': from_currency,
                'currency_rate_avg': cp.currency_rate_avg,
                'currency_rate_end': cp.currency_rate_end,
                'to_currency': to_currency,
                'class': 'number',
                'template': 'account_consolidation.cell_template_consolidation_report',
            }

        return {
            'name': journal.name,
            'consolidation_rate': journal.rate_consolidation,
            'class': 'number',
            'template': 'account_consolidation.cell_template_consolidation_report',
        }

    def _consolidated_balance_init_buttons(self, options):
        ap_is_closed = False
        ap_id = self._get_selected_period_id()
        if ap_id:
            ap = self.env['consolidation.period'].browse(ap_id)
            ap_is_closed = ap.state == 'closed'
        buttons = [
            {'name': _('PDF'), 'sequence': 1, 'action': 'export_file', 'action_param': 'export_to_pdf', 'file_export_type': _('PDF')},
            {'name': _('XLSX'), 'sequence': 2, 'action': 'export_file', 'action_param': 'export_to_xlsx', 'file_export_type': _('XLSX')}
        ]
        if not ap_is_closed:
            buttons.append({'name': _('Edit'), 'sequence': 10, 'action': 'action_open_view_grid'})

        return buttons

    @api.model
    def _get_lines(self, options, line_id=None):
        selected_aps = self._get_period_ids(options)
        selected_ap = self._get_selected_period()

        # comparison
        if len(selected_aps) > 1:
            builder = ComparisonBuilder(self.env, selected_ap._format_value)
        else:
            journal_ids = JournalsHandler.get_selected_values(options)
            journals = self.env['consolidation.journal'].browse(journal_ids)
            builder = DefaultBuilder(self.env, selected_ap._format_value, journals)
        return builder.get_lines(selected_aps, options, line_id)

    ####################################################
    # PERIODS
    ####################################################
    def _get_default_analysis_period(self):
        """
        Get the default analysis period, which is the last one when we order by id desc.
        :return: the if of this analysis period
        :rtype: int
        """
        return self.env['consolidation.period'].search([], limit=1, order="id desc").id

    def _get_period_ids(self, options):
        """
        Get all the period ids (the base period and the comparison ones if any)
        :param options: the options dict
        :type options: dict
        :return: a list containing the period ids
        :rtype: list
        """
        forced_periods = options.get('force_periods', False)
        return forced_periods or PeriodsHandler.get_selected_values(options) + [self._get_selected_period_id()]

    def _get_selected_period_id(self):
        """
        Get the selected period id (the base period)
        :return: the id of the selected period
        :rtype: int
        """
        default_analysis_period = self.env.context.get('default_period_id', self.env.context.get('active_id', None))
        return default_analysis_period or self._get_default_analysis_period()

    def _get_selected_period(self):
        """
        Get the selected period (the base period)
        :return: the recordset containing the selected period
        """
        return self.env['consolidation.period'].browse(self._get_selected_period_id())

    ####################################################
    # ACTIONS
    ####################################################
    def action_open_view_grid(self, options):
        period_id = self._get_selected_period_id()
        name = self.env['consolidation.period'].browse(period_id).display_name or _("Trial Balance")
        return {
            'type': 'ir.actions.act_window',
            'name': _("Edit %s", name),
            'res_model': 'consolidation.journal.line',
            'view_mode': 'grid,graph,form',
            'view_type': 'grid',
            'views': [
                [self.env.ref('account_consolidation.view_trial_balance_report_grid').id, 'grid'],
                [self.env.ref('account_consolidation.view_trial_balance_report_graph').id, 'graph'],
                [self.env.ref('account_consolidation.consolidation_journal_line_form').id, 'form']
            ],
            'context': {
                'default_period_id': period_id
            },
            'domain': [('period_id', '=', period_id)]
        }

    def action_open_audit(self, options, params=None):
        account_id = self.env['account.report']._parse_line_id(params['lineId'])[0][0]
        journal_id = params['id']
        journal = self.env['consolidation.journal'].browse(journal_id)
        company_period = journal.company_period_id
        journal_lines = self.env['consolidation.journal.line'].search([
            ('account_id', '=', int(account_id)),
            ('journal_id', '=', journal_id)
        ])
        if len(journal_lines) == 0:
            return None
        action = self.env["ir.actions.actions"]._for_xml_id("account_consolidation.view_account_move_line_filter")
        action.update({
            'context': {
                'search_default_consolidation_journal_line_ids': journal_lines.ids,
                'search_default_group_by_account': 1,
                'group_by': 'account_id',
                'search_default_posted': 1,
                'consolidation_rate': company_period.rate_consolidation if company_period else 0,
                'currencies_are_different': company_period.currencies_are_different if company_period else False,
                'currencies': {
                    'chart': company_period.currency_chart_id.symbol if company_period else None,
                    'company': company_period.currency_company_id.symbol if company_period else None,
                }
            },
            'views': [(self.env.ref('account_consolidation.view_move_line_tree_grouped_general').id, 'list')]
        })
        return action

    def export_file(self, options, file_generator):
        options.update({
            'force_periods': self._get_period_ids(options),
            'active_id': self.env.context.get('active_id'),
        })

        return self.env['account.report'].browse(options['report_id']).export_file(options, file_generator)
