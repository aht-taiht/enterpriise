# -*- coding: utf-8 -*-
from odoo.tests import tagged
from odoo.tests.common import Form, SingleTransactionCase
from odoo.tools import DEFAULT_SERVER_DATE_FORMAT, date_utils
from odoo.tools.misc import formatLang

import datetime
import copy
import logging

from dateutil.relativedelta import relativedelta

_logger = logging.getLogger(__name__)


@tagged('post_install', '-at_install')
class TestAccountReports(SingleTransactionCase):

    # -------------------------------------------------------------------------
    # DATA GENERATION
    # -------------------------------------------------------------------------
    
    @classmethod
    def setUpClass(cls):
        super(TestAccountReports, cls).setUpClass()

        chart_template = cls.env.ref('l10n_generic_coa.configurable_chart_template', raise_if_not_found=False)
        if not chart_template:
            _logger.warn('Reports Tests skipped because l10n_generic_coa is not installed')
            cls.skipTest("l10n_generic_coa not installed")

        # Create companies.
        cls.company_parent = cls.env['res.company'].create({
            'name': 'company_parent',
            'currency_id': cls.env.ref('base.USD').id,
        })
        cls.company_child_eur = cls.env['res.company'].create({
            'name': 'company_child_eur',
            'currency_id': cls.env.ref('base.EUR').id,
            'parent_id': cls.company_parent.id,
        })

        # EUR = 2 USD
        cls.eur_to_usd = cls.env['res.currency.rate'].create({
            'name': '2016-01-01',
            'rate': 2.0,
            'currency_id': cls.env.ref('base.EUR').id,
            'company_id': cls.company_parent.id,
        })

        # Create user.
        user = cls.env['res.users'].create({
            'name': 'Because I am reportman!',
            'login': 'reportman',
            'groups_id': [(6, 0, cls.env.user.groups_id.ids)],
            'company_id': cls.company_parent.id,
            'company_ids': [(6, 0, (cls.company_parent + cls.company_child_eur).ids)],
        })
        user.partner_id.email = 'reportman@test.com'

        # Shadow the current environment/cursor with one having the report user.
        cls.env = cls.env(user=user)
        cls.cr = cls.env.cr

        # Get the new chart of accounts using the new environment.
        chart_template = cls.env.ref('l10n_generic_coa.configurable_chart_template')

        partner_a = cls.env['res.partner'].create({'name': 'partner_a', 'company_id': False})
        partner_b = cls.env['res.partner'].create({'name': 'partner_b', 'company_id': False})
        partner_c = cls.env['res.partner'].create({'name': 'partner_c', 'company_id': False})
        partner_d = cls.env['res.partner'].create({'name': 'partner_d', 'company_id': False})

        # Init data for company_parent.
        chart_template.try_loading_for_current_company()

        cls.dec_year_minus_2 = datetime.datetime.strptime('2016-12-01', DEFAULT_SERVER_DATE_FORMAT).date()
        cls.jan_year_minus_1 = datetime.datetime.strptime('2017-01-01', DEFAULT_SERVER_DATE_FORMAT).date()
        cls.feb_year_minus_1 = datetime.datetime.strptime('2017-02-01', DEFAULT_SERVER_DATE_FORMAT).date()
        cls.mar_year_minus_1 = datetime.datetime.strptime('2017-03-01', DEFAULT_SERVER_DATE_FORMAT).date()
        cls.apr_year_minus_1 = datetime.datetime.strptime('2017-04-01', DEFAULT_SERVER_DATE_FORMAT).date()

        # December
        inv_dec_1 = cls._create_invoice(cls.env, 1200.0, partner_a, 'out_invoice', cls.dec_year_minus_2)
        cls._create_payment(cls.env, cls.jan_year_minus_1, inv_dec_1, 600.0)
        inv_dec_2 = cls._create_invoice(cls.env, 1200.0, partner_b, 'in_invoice', cls.dec_year_minus_2)
        cls._create_payment(cls.env, cls.dec_year_minus_2, inv_dec_2, 1200.0)
        inv_dec_3 = cls._create_invoice(cls.env, 1200.0, partner_c, 'in_invoice', cls.dec_year_minus_2)
        inv_dec_4 = cls._create_invoice(cls.env, 1200.0, partner_d, 'in_invoice', cls.dec_year_minus_2)

        # January
        inv_jan_1 = cls._create_invoice(cls.env, 100.0, partner_a, 'out_invoice', cls.jan_year_minus_1)
        inv_jan_2 = cls._create_invoice(cls.env, 100.0, partner_b, 'out_invoice', cls.jan_year_minus_1)
        cls._create_payment(cls.env, cls.jan_year_minus_1, inv_jan_2, 100.0)
        inv_jan_3 = cls._create_invoice(cls.env, 100.0, partner_c, 'in_invoice', cls.jan_year_minus_1)
        cls._create_payment(cls.env, cls.feb_year_minus_1, inv_jan_3, 50.0)
        inv_jan_4 = cls._create_invoice(cls.env, 100.0, partner_d, 'out_invoice', cls.jan_year_minus_1)

        # February
        inv_feb_1 = cls._create_invoice(cls.env, 200.0, partner_a, 'in_invoice', cls.feb_year_minus_1)
        inv_feb_2 = cls._create_invoice(cls.env, 200.0, partner_b, 'out_invoice', cls.feb_year_minus_1)
        inv_feb_3 = cls._create_invoice(cls.env, 200.0, partner_c, 'out_invoice', cls.feb_year_minus_1)
        cls._create_payment(cls.env, cls.mar_year_minus_1, inv_feb_3, 100.0)
        inv_feb_4 = cls._create_invoice(cls.env, 200.0, partner_d, 'in_invoice', cls.feb_year_minus_1)
        cls._create_payment(cls.env, cls.feb_year_minus_1, inv_feb_4, 200.0)

        # March
        inv_mar_1 = cls._create_invoice(cls.env, 300.0, partner_a, 'in_invoice', cls.mar_year_minus_1)
        cls._create_payment(cls.env, cls.mar_year_minus_1, inv_mar_1, 300.0)
        inv_mar_2 = cls._create_invoice(cls.env, 300.0, partner_b, 'in_invoice', cls.mar_year_minus_1)
        inv_mar_3 = cls._create_invoice(cls.env, 300.0, partner_c, 'out_invoice', cls.mar_year_minus_1)
        cls._create_payment(cls.env, cls.apr_year_minus_1, inv_mar_3, 150.0)
        inv_mar_4 = cls._create_invoice(cls.env, 300.0, partner_d, 'out_invoice', cls.mar_year_minus_1)

        # Init data for company_child_eur.
        # Data are the same as the company_parent with doubled amount.
        # However, due to the foreign currency (2 EUR = 1 USD), the amounts are divided by two during the foreign
        # currency conversion.
        user.company_id = cls.company_child_eur
        chart_template.try_loading_for_current_company()

        # Currency has been reset to USD during the installation of the chart template.
        cls.company_child_eur.currency_id = cls.env.ref('base.EUR')

        # December
        inv_dec_5 = cls._create_invoice(cls.env, 2400.0, partner_a, 'out_invoice', cls.dec_year_minus_2)
        cls._create_payment(cls.env, cls.jan_year_minus_1, inv_dec_5, 1200.0)
        inv_dec_6 = cls._create_invoice(cls.env, 2400.0, partner_b, 'in_invoice', cls.dec_year_minus_2)
        cls._create_payment(cls.env, cls.dec_year_minus_2, inv_dec_6, 2400.0)
        inv_dec_7 = cls._create_invoice(cls.env, 2400.0, partner_c, 'in_invoice', cls.dec_year_minus_2)
        inv_dec_8 = cls._create_invoice(cls.env, 2400.0, partner_d, 'in_invoice', cls.dec_year_minus_2)

        # January
        inv_jan_5 = cls._create_invoice(cls.env, 200.0, partner_a, 'out_invoice', cls.jan_year_minus_1)
        inv_jan_6 = cls._create_invoice(cls.env, 200.0, partner_b, 'out_invoice', cls.jan_year_minus_1)
        cls._create_payment(cls.env, cls.jan_year_minus_1, inv_jan_6, 200.0)
        inv_jan_7 = cls._create_invoice(cls.env, 200.0, partner_c, 'in_invoice', cls.jan_year_minus_1)
        cls._create_payment(cls.env, cls.feb_year_minus_1, inv_jan_7, 100.0)
        inv_jan_8 = cls._create_invoice(cls.env, 200.0, partner_d, 'out_invoice', cls.jan_year_minus_1)

        # February
        inv_feb_5 = cls._create_invoice(cls.env, 400.0, partner_a, 'in_invoice', cls.feb_year_minus_1)
        inv_feb_6 = cls._create_invoice(cls.env, 400.0, partner_b, 'out_invoice', cls.feb_year_minus_1)
        inv_feb_7 = cls._create_invoice(cls.env, 400.0, partner_c, 'out_invoice', cls.feb_year_minus_1)
        cls._create_payment(cls.env, cls.mar_year_minus_1, inv_feb_7, 200.0)
        inv_feb_8 = cls._create_invoice(cls.env, 400.0, partner_d, 'in_invoice', cls.feb_year_minus_1)
        cls._create_payment(cls.env, cls.feb_year_minus_1, inv_feb_8, 400.0)

        # Mars
        inv_mar_5 = cls._create_invoice(cls.env, 600.0, partner_a, 'in_invoice', cls.mar_year_minus_1)
        cls._create_payment(cls.env, cls.mar_year_minus_1, inv_mar_5, 600.0)
        inv_mar_6 = cls._create_invoice(cls.env, 600.0, partner_b, 'in_invoice', cls.mar_year_minus_1)
        inv_mar_7 = cls._create_invoice(cls.env, 600.0, partner_c, 'out_invoice', cls.mar_year_minus_1)
        cls._create_payment(cls.env, cls.apr_year_minus_1, inv_mar_7, 300.0)
        inv_mar_8 = cls._create_invoice(cls.env, 600.0, partner_d, 'out_invoice', cls.mar_year_minus_1)

        user.company_id = cls.company_parent

    @staticmethod
    def _create_invoice(env, amount, partner, invoice_type, date):
        ''' Helper to create an account.invoice on the fly with only one line.
        N.B: The taxes are also applied.
        :param amount:          The amount of the unique account.invoice.line.
        :param partner:         The partner.
        :param invoice_type:    The invoice type.
        :param date:            The invoice date as a datetime object.
        :return:                An account.invoice record.
        '''
        self_ctx = env['account.invoice'].with_context(type=invoice_type)
        journal_id = self_ctx._default_journal().id
        self_ctx = self_ctx.with_context(journal_id=journal_id)
        view = 'account.invoice_form' if 'out' in invoice_type else 'account.invoice_supplier_form'

        with Form(self_ctx, view=view) as invoice_form:
            invoice_form.partner_id = partner
            invoice_form.date_invoice = date
            with invoice_form.invoice_line_ids.new() as invoice_line_form:
                invoice_line_form.name = 'test'
                invoice_line_form.price_unit = amount
        invoice = invoice_form.save()
        invoice.action_invoice_open()
        return invoice

    @staticmethod
    def _create_payment(env, date, invoices, amount=None):
        ''' Helper to create an account.payment on the fly for some invoices.
        :param date:        The payment date.
        :param invoices:    The invoices on which the payment is done.
        :param amount:      The payment amount.
        :return:            An account.payment record.
        '''
        self_ctx = env['account.register.payments'].with_context(active_model='account.invoice', active_ids=invoices.ids)
        with Form(self_ctx) as payment_form:
            payment_form.payment_date = date
            if amount:
                payment_form.amount = amount
        register_payment = payment_form.save()
        register_payment.create_payments()
        return register_payment

    # -------------------------------------------------------------------------
    # TESTS METHODS
    # -------------------------------------------------------------------------
    
    def _init_options(self, report, filter, date_from=None, date_to=None):
        ''' Create new options at a certain date.        
        :param report:      The report.
        :param filter:      One of the following values: ('today', 'custom', 'this_month', 'this_quarter', 'this_year', 'last_month', 'last_quarter', 'last_year').
        :param date_from:   A datetime object or False.
        :param date_to:     A datetime object.
        :return:            The newly created options.
        '''
        filter_date = {
            'date_from': date_from and date_from.strftime(DEFAULT_SERVER_DATE_FORMAT),
            'date_to': date_to and date_to.strftime(DEFAULT_SERVER_DATE_FORMAT),
            'filter': filter,
        }
        report.filter_date = filter_date
        options = report._get_options(None)
        report._apply_date_filter(options)
        return options

    def _update_comparison_filter(self, options, report, comparison_type, number_period, date_from=None, date_to=None):
        ''' Modify the existing options to set a new filter_comparison.
        :param options:         The report options.
        :param report:          The report.
        :param comparison_type: One of the following values: ('no_comparison', 'custom', 'previous_period', 'previous_year').
        :param number_period:   The number of period to compare.
        :param date_from:       A datetime object for the 'custom' comparison_type.
        :param date_to:         A datetime object the 'custom' comparison_type.
        :return:                The newly created options.
        '''
        filter_comparison = {
            'date_from': date_from and date_from.strftime(DEFAULT_SERVER_DATE_FORMAT),
            'date_to': date_to and date_to.strftime(DEFAULT_SERVER_DATE_FORMAT),
            'filter': comparison_type,
            'number_period': number_period,
        }
        new_options = copy.deepcopy(options)
        new_options['comparison'] = filter_comparison
        report._apply_date_filter(new_options)
        return new_options

    def _update_multi_selector_filter(self, options, option_key, selected_ids):
        ''' Modify a selector in the options to select .
        :param options:         The report options.
        :param option_key:      The key to the option.
        :param selected_ids:    The ids to be selected.
        :return:                The newly created options.
        '''
        new_options = copy.deepcopy(options)
        for c in new_options[option_key]:
            c['selected'] = c['id'] in selected_ids
        return new_options

    def assertLinesValues(self, lines, columns, expected_values):
        ''' Helper to compare the lines returned by the _get_lines method
        with some expected results.
        :param lines:               See _get_lines.
        :params columns:            The columns index.
        :param expected_values:     A list of iterables.
        '''
        user_currency = self.env.user.company_id.currency_id

        # Compare the table length to see if any line is missing
        self.assertEquals(len(lines), len(expected_values))

        # Compare cell by cell the current value with the expected one.
        i = 0
        for line in lines:
            j = 0
            compared_values = [[], []]
            for index in columns:
                expected_value = expected_values[i][j]

                if index == 0:
                    current_value = line['name']
                else:
                    colspan = line.get('colspan', 1)
                    line_index = index - colspan
                    if line_index < 0:
                        current_value = ''
                    else:
                        current_value = line['columns'][line_index].get('name', '')

                if type(expected_value) in (int, float) and type(current_value) == str:
                    expected_value = formatLang(self.env, expected_value, currency_obj=user_currency)

                compared_values[0].append(current_value)
                compared_values[1].append(expected_value)

                j += 1
            self.assertEqual(compared_values[0], compared_values[1])
            i += 1

    # -------------------------------------------------------------------------
    # TESTS: General Ledger
    # -------------------------------------------------------------------------
    
    def test_general_ledger_folded_unfolded(self):
        ''' Test folded/unfolded lines. '''
        # Init options.
        report = self.env['account.general.ledger']
        options = self._init_options(report, 'custom', *date_utils.get_month(self.mar_year_minus_1))
        report = report.with_context(report._set_context(options))

        lines = report._get_lines(options)
        self.assertLinesValues(
            lines,
            #   Name                                    Debit           Credit          Balance
            [   0,                                      5,              6,              7],
            [
                # Accounts.
                ('101200 Account Receivable',           2875.00,        800.00,         2075.00),
                ('101300 Tax Paid',                     705.00,         0.00,           705.00),
                ('101401 Bank',                         800.00,         1750.00,        -950.00),
                ('111100 Account Payable',              1750.00,        5405.00,        -3655.00),
                ('111200 Tax Received',                 0.00,           375.00,         -375.00),
                ('200000 Product Sales',                0.00,           1300.00,        -1300.00),
                ('220000 Expenses',                     1100.00,        0.00,           1100.00),
                ('999999 Undistributed Profits/Losses', 3600.00,        1200.00,        2400.00),
                # Report Total.
                ('Total',                               10830.00,       10830.00,       0.00),
            ],
        )

        # Mark the '101200 Account Receivable' line to be unfolded.
        line_id = lines[0]['id']
        options['unfolded_lines'] = [line_id]
        report = report.with_context(report._set_context(options))

        self.assertLinesValues(
            report._get_lines(options, line_id=line_id),
            #   Name                                    Date            Partner         Currency    Debit           Credit          Balance
            [   0,                                      1,              3,              4,          5,              6,              7],
            [
                # Account.
                ('101200 Account Receivable',           '',             '',             '',         2875.00,        800.00,         2075.00),
                # Initial Balance.
                ('Initial Balance',                     '',             '',             '',         2185.00,        700.00,         1485.00),
                # Account Move Lines.
                ('BNK1/2017/0004',                      '03/01/2017',   'partner_c',    '',         '',             100.00,         1385.00),
                ('INV/2017/0006',                       '03/01/2017',   'partner_c',    '',         345.00,         '',             1730.00),
                ('INV/2017/0007',                       '03/01/2017',   'partner_d',    '',         345.00,         '',             2075.00),
                # Account Total.
                ('Total ',                              '',             '',             '',         2875.00,        800.00,         2075.00),
            ],
        )

    def test_general_ledger_cash_basis(self):
        ''' Test folded/unfolded lines with the cash basis option. '''
        # Check the cash basis option.
        report = self.env['account.general.ledger']
        options = self._init_options(report, 'custom', *date_utils.get_month(self.mar_year_minus_1))
        options['cash_basis'] = True
        report = report.with_context(report._set_context(options))

        lines = report._get_lines(options)
        self.assertLinesValues(
            lines,
            #   Name                                    Debit           Credit          Balance
            [   0,                                      5,              6,              7],
            [
                # Accounts.
                ('101200 Account Receivable',           800.00,         800.00,         0.00),
                ('101300 Tax Paid',                     228.26,         0.00,           228.26),
                ('101401 Bank',                         800.00,         1750.00,        -950.00),
                ('111100 Account Payable',              1750.00,        1750.00,        0.00),
                ('111200 Tax Received',                 0.00,           104.35,         -104.35),
                ('200000 Product Sales',                0.00,           695.65,         -695.65),
                ('220000 Expenses',                     478.26,         0.00,           478.26),
                # Report Total.
                ('Total',                               4056.52,        5100.00,        -1043.48),
            ],
        )

        # Mark the '101200 Account Receivable' line to be unfolded.
        line_id = lines[0]['id']
        options['unfolded_lines'] = [line_id]
        report = report.with_context(report._set_context(options))

        self.assertLinesValues(
            report._get_lines(options, line_id=line_id),
            #   Name                                    Date            Partner         Currency    Debit           Credit          Balance
            [   0,                                      1,              3,              4,          5,              6,              7],
            [
                # Account.
                ('101200 Account Receivable',           '',             '',             '',         800.00,         800.00,         0.00),
                # Initial Balance.
                ('Initial Balance',                     '',             '',             '',         700.00,         700.00,         0.00),
                # Account Move Lines.
                ('INV/2017/0005',                       '02/01/2017',   'partner_c',    '',         100.00,             '',       100.00),
                ('BNK1/2017/0004',                      '03/01/2017',   'partner_c',    '',             '',         100.00,         0.00),
                # Account Total.
                ('Total ',                              '',             '',             '',         800.00,         800.00,         0.00),
            ],
        )

    def test_general_ledger_multi_company(self):
        ''' Test folded/unfolded lines in a multi-company environment. '''
        # Select both company_parent/company_child_eur companies.
        report = self.env['account.general.ledger']
        options = self._init_options(report, 'custom', *date_utils.get_month(self.mar_year_minus_1))
        options = self._update_multi_selector_filter(options, 'multi_company', (self.company_parent + self.company_child_eur).ids)
        report = report.with_context(report._set_context(options))

        lines = report._get_lines(options)
        self.assertLinesValues(
            lines,
            #   Name                                    Debit           Credit          Balance
            [   0,                                      5,              6,              7],
            [
                # Accounts.
                ('101200 Account Receivable',           2875.00,        800.00,         2075.00),
                ('101200 Account Receivable',           2875.00,        800.00,         2075.00),
                ('101300 Tax Paid',                     705.00,         0.00,           705.00),
                ('101300 Tax Paid',                     705.00,         0.00,           705.00),
                ('101401 Bank',                         800.00,         1750.00,        -950.00),
                ('101401 Bank',                         800.00,         1750.00,        -950.00),
                ('111100 Account Payable',              1750.00,        5405.00,        -3655.00),
                ('111100 Account Payable',              1750.00,        5405.00,        -3655.00),
                ('111200 Tax Received',                 0.00,           375.00,         -375.00),
                ('111200 Tax Received',                 0.00,           375.00,         -375.00),
                ('200000 Product Sales',                0.00,           1300.00,        -1300.00),
                ('200000 Product Sales',                0.00,           1300.00,        -1300.00),
                ('220000 Expenses',                     1100.00,        0.00,           1100.00),
                ('220000 Expenses',                     1100.00,        0.00,           1100.00),
                ('999999 Undistributed Profits/Losses', 3600.00,        1200.00,        2400.00),
                ('999999 Undistributed Profits/Losses', 3600.00,        1200.00,        2400.00),
                # Report Total.
                ('Total',                               21660.00,       21660.00,       0.00),
            ],
        )

        # Mark the '101200 Account Receivable' line (for the company_child_eur company) to be unfolded.
        line_id = lines[1]['id']
        options['unfolded_lines'] = [line_id]
        report = report.with_context(report._set_context(options))

        self.assertLinesValues(
            report._get_lines(options, line_id=line_id),
            #   Name                                    Date            Partner         Currency    Debit           Credit          Balance
            [   0,                                      1,              3,              4,          5,              6,              7],
            [
                # Account.
                ('101200 Account Receivable',           '',             '',             '',         2875.00,        800.00,         2075.00),
                # Initial Balance.
                ('Initial Balance',                     '',             '',             '',         2185.00,        700.00,         1485.00),
                # Account Move Lines.
                ('BNK1/2017/0004',                      '03/01/2017',   'partner_c',    '',         '',             100.00,         1385.00),
                ('INV/2017/0006',                       '03/01/2017',   'partner_c',    '',         345.00,         '',             1730.00),
                ('INV/2017/0007',                       '03/01/2017',   'partner_d',    '',         345.00,         '',             2075.00),
                # Account Total.
                ('Total ',                              '',             '',             '',         2875.00,        800.00,         2075.00),
            ],
        )

    def test_general_ledger_load_more(self):
        ''' Test the load more feature. '''
        receivable_account = self.env['account.account'].search(
            [('company_id', '=', self.company_parent.id), ('internal_type', '=', 'receivable')])
        line_id = 'account_%s' % receivable_account.id

        # Mark the '101200 Account Receivable' line to be unfolded.
        report = self.env['account.general.ledger']
        options = self._init_options(report, 'custom', *date_utils.get_month(self.mar_year_minus_1))
        options['unfolded_lines'] = [line_id]
        report = report.with_context(report._set_context(options))

        # Force the load more to expand lines one by one.
        report.MAX_LINES = 1

        self.assertLinesValues(
            report._get_lines(options, line_id=line_id),
            #   Name                                    Date            Partner         Currency    Debit           Credit          Balance
            [   0,                                      1,              3,              4,          5,              6,              7],
            [
                # Account.
                ('101200 Account Receivable',           '',             '',             '',         2875.00,        800.00,         2075.00),
                # Initial Balance.
                ('Initial Balance',                     '',             '',             '',         2185.00,        700.00,         1485.00),
                # Account Move Lines.
                ('BNK1/2017/0004',                      '03/01/2017',   'partner_c',    '',         '',             100.00,         1385.00),
                # Load more.
                ('Load more... (2 remaining)',          '',             '',             '',         '',             '',             ''),
                # Account Total.
                ('Total ',                              '',             '',             '',         2875.00,        800.00,         2075.00),
            ],
        )

        # Store the load more values inside the options.
        options['lines_offset'] = 1
        options['lines_progress'] = 1385.00
        report = report.with_context(report._set_context(options))
        report.MAX_LINES = 1

        self.assertLinesValues(
            report._get_lines(options, line_id=line_id),
            #   Name                                    Date            Partner         Currency    Debit           Credit          Balance
            [   0,                                      1,              3,              4,          5,              6,              7],
            [
                # Account Move Lines.
                ('INV/2017/0006',                       '03/01/2017',   'partner_c',    '',         345.00,         '',             1730.00),
                # Load more.
                ('Load more... (1 remaining)',          '',             '',             '',         '',             '',             ''),
            ],
        )

        # Update the load more values inside the options.
        options['lines_offset'] = 2
        options['lines_progress'] = 1730.00
        report = report.with_context(report._set_context(options))
        report.MAX_LINES = 1

        self.assertLinesValues(
            report._get_lines(options, line_id=line_id),
            #   Name                                    Date            Partner         Currency    Debit           Credit          Balance
            [   0,                                      1,              3,              4,          5,              6,              7],
            [
                # Account Move Lines.
                ('INV/2017/0007',                       '03/01/2017',   'partner_d',    '',         345.00,         '',             2075.00),
            ],
        )

    def test_general_ledger_tax_declaration(self):
        ''' Test the tax declaration. '''
        journal = self.env['account.journal'].search(
            [('company_id', '=', self.company_parent.id), ('type', '=', 'sale')])

        # Select only the 'Customer Invoices' journal.
        report = self.env['account.general.ledger']
        options = self._init_options(report, 'custom', *date_utils.get_month(self.mar_year_minus_1))
        options = self._update_multi_selector_filter(options, 'journals', journal.ids)
        report = report.with_context(report._set_context(options))

        self.assertLinesValues(
            report._get_lines(options),
            #   Name                                    Debit           Credit          Balance
            [   0,                                      5,              6,              7],
            [
                # Accounts.
                ('101200 Account Receivable',           2875.00,        0.00,           2875.00),
                ('111200 Tax Received',                 0.00,           375.00,         -375.00),
                ('200000 Product Sales',                0.00,           1300.00,        -1300.00),
                ('999999 Undistributed Profits/Losses', 0.00,           1200.00,        -1200.00),
                # Report Total.
                ('Total',                               2875.00,        2875.00,        0.00),
                # Tax Declaration.
                ('Tax Declaration',                     '',             '',             ''),
                ('Name',                                'Base Amount',  'Tax Amount',   ''),
                ('Tax 15.00% (15.0)',                   600.00,         375.00,         ''),
            ],
        )
