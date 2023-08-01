# -*- coding: utf-8 -*-
# pylint: disable=C0326
from odoo import fields, Command
from odoo.tests import tagged
from odoo.addons.account.tests.common import AccountTestInvoicingCommon


@tagged('post_install', '-at_install')
class TestDeferredManagement(AccountTestInvoicingCommon):
    @classmethod
    def setUpClass(cls, chart_template_ref=None):
        super().setUpClass(chart_template_ref=chart_template_ref)
        cls.expense_accounts = [cls.env['account.account'].create({
            'name': f'Expense {i}',
            'code': f'EXP{i}',
            'account_type': 'expense',
        }) for i in range(3)]
        cls.revenue_accounts = [cls.env['account.account'].create({
            'name': f'Revenue {i}',
            'code': f'REV{i}',
            'account_type': 'income',
        }) for i in range(3)]

        cls.company = cls.company_data['company']
        cls.company.deferred_journal_id = cls.company_data['default_journal_misc'].id
        cls.company.deferred_expense_account_id = cls.company_data['default_account_deferred_expense'].id
        cls.company.deferred_revenue_account_id = cls.company_data['default_account_deferred_revenue'].id

        cls.expense_lines = [
            [cls.expense_accounts[0], 1000, '2023-01-01', '2023-04-30'],  # 4 full months (=250/month)
            [cls.expense_accounts[0], 1050, '2023-01-16', '2023-04-30'],  # 3 full months + 15 days (=300/month)
            [cls.expense_accounts[1], 1225, '2023-01-01', '2023-04-15'],  # 3 full months + 15 days (=350/month)
            [cls.expense_accounts[2], 1680, '2023-01-21', '2023-04-14'],  # 2 full months + 10 days + 14 days (=600/month)
            [cls.expense_accounts[2],  225, '2023-04-01', '2023-04-15'],  # 15 days (=450/month)
        ]
        cls.revenue_lines = [
            [cls.revenue_accounts[0], 1000, '2023-01-01', '2023-04-30'],  # 4 full months (=250/month)
            [cls.revenue_accounts[0], 1050, '2023-01-16', '2023-04-30'],  # 3 full months + 15 days (=300/month)
            [cls.revenue_accounts[1], 1225, '2023-01-01', '2023-04-15'],  # 3 full months + 15 days (=350/month)
            [cls.revenue_accounts[2], 1680, '2023-01-21', '2023-04-14'],  # 2 full months + 10 days + 14 days (=600/month)
            [cls.revenue_accounts[2],  225, '2023-04-01', '2023-04-15'],  # 15 days (=450/month)
        ]

    def create_invoice(self, move_type, journal, partner, invoice_lines, date=None, post=True):
        move = self.env['account.move'].create({
            'move_type': move_type,
            'partner_id': partner.id,
            'date': date or '2023-01-01',
            'invoice_date': date or '2023-01-01',
            'journal_id': journal.id,
            'invoice_line_ids': [
                Command.create({
                    'product_id': self.product_a.id,
                    'quantity': 1,
                    'account_id': account.id,
                    'price_unit': price_unit,
                    'deferred_start_date': start_date,
                    'deferred_end_date': end_date,
                }) for account, price_unit, start_date, end_date in invoice_lines
            ]
        })
        if post:
            move.action_post()
        return move

    def test_deferred_management_get_diff_dates(self):
        def assert_get_diff_dates(start, end, expected):
            diff = self.env['account.move']._get_deferred_diff_dates(fields.Date.to_date(start), fields.Date.to_date(end))
            self.assertAlmostEqual(diff, expected, 3)

        assert_get_diff_dates('2023-01-01', '2023-01-01', 0)
        assert_get_diff_dates('2023-01-01', '2023-01-02', 1/30)
        assert_get_diff_dates('2023-01-01', '2023-01-20', 19/30)
        assert_get_diff_dates('2023-01-01', '2023-01-31', 29/30)
        assert_get_diff_dates('2023-01-01', '2023-01-30', 29/30)
        assert_get_diff_dates('2023-01-01', '2023-02-01', 1)
        assert_get_diff_dates('2023-01-01', '2023-02-28', 1 + 29/30)
        assert_get_diff_dates('2023-02-01', '2023-02-28', 29/30)
        assert_get_diff_dates('2023-02-10', '2023-02-28', 20/30)
        assert_get_diff_dates('2023-01-01', '2023-02-15', 1 + 14/30)
        assert_get_diff_dates('2023-01-01', '2023-03-31', 2 + 29/30)
        assert_get_diff_dates('2023-01-01', '2023-04-01', 3)
        assert_get_diff_dates('2023-01-01', '2023-04-30', 3 + 29/30)
        assert_get_diff_dates('2023-01-10', '2023-04-30', 3 + 20/30)
        assert_get_diff_dates('2023-01-10', '2023-04-09', 2 + 29/30)
        assert_get_diff_dates('2023-01-10', '2023-04-10', 3)
        assert_get_diff_dates('2023-01-10', '2023-04-11', 3 + 1/30)
        assert_get_diff_dates('2023-02-20', '2023-04-10', 1 + 20/30)
        assert_get_diff_dates('2023-01-31', '2023-04-30', 3)
        assert_get_diff_dates('2023-02-28', '2023-04-10', 1 + 10/30)
        assert_get_diff_dates('2023-03-01', '2023-04-10', 1 + 9/30)
        assert_get_diff_dates('2023-04-10', '2023-03-01', 1 + 9/30)
        assert_get_diff_dates('2023-01-01', '2023-12-31', 11 + 29/30)
        assert_get_diff_dates('2023-01-01', '2024-01-01', 12)
        assert_get_diff_dates('2023-01-01', '2024-07-01', 18)
        assert_get_diff_dates('2023-01-01', '2024-07-10', 18 + 9/30)

    def test_get_ends_of_month(self):
        def assertEndsOfMonths(start_date, end_date, expected):
            self.assertEqual(
                self.env['account.move.line']._get_deferred_ends_of_month(
                    fields.Date.to_date(start_date),
                    fields.Date.to_date(end_date)
                ),
                [fields.Date.to_date(date) for date in expected]
            )

        assertEndsOfMonths('2023-01-01', '2023-01-01', ['2023-01-31'])
        assertEndsOfMonths('2023-01-01', '2023-01-02', ['2023-01-31'])
        assertEndsOfMonths('2023-01-01', '2023-01-20', ['2023-01-31'])
        assertEndsOfMonths('2023-01-01', '2023-01-30', ['2023-01-31'])
        assertEndsOfMonths('2023-01-01', '2023-01-31', ['2023-01-31'])
        assertEndsOfMonths('2023-01-01', '2023-02-01', ['2023-01-31', '2023-02-28'])
        assertEndsOfMonths('2023-01-01', '2023-02-28', ['2023-01-31', '2023-02-28'])
        assertEndsOfMonths('2023-02-01', '2023-02-28', ['2023-02-28'])
        assertEndsOfMonths('2023-02-10', '2023-02-28', ['2023-02-28'])
        assertEndsOfMonths('2023-01-01', '2023-02-15', ['2023-01-31', '2023-02-28'])
        assertEndsOfMonths('2023-01-01', '2023-03-31', ['2023-01-31', '2023-02-28', '2023-03-31'])
        assertEndsOfMonths('2023-01-01', '2023-04-01', ['2023-01-31', '2023-02-28', '2023-03-31', '2023-04-30'])
        assertEndsOfMonths('2023-01-01', '2023-04-30', ['2023-01-31', '2023-02-28', '2023-03-31', '2023-04-30'])
        assertEndsOfMonths('2023-01-10', '2023-04-30', ['2023-01-31', '2023-02-28', '2023-03-31', '2023-04-30'])
        assertEndsOfMonths('2023-01-10', '2023-04-09', ['2023-01-31', '2023-02-28', '2023-03-31', '2023-04-30'])

    def test_deferred_expense_generate_entries_method(self):
        # The deferred entries are NOT generated when the invoice is validated if the method is set to 'manual'.
        self.company.generate_deferred_entries_method = 'manual'
        move2 = self.create_invoice('in_invoice', self.company_data['default_journal_purchase'], self.partner_a, [self.expense_lines[0]], post=True)
        self.assertEqual(len(move2.deferred_move_ids), 0)

        # Test that the deferred entries are generated when the invoice is validated.
        self.company.generate_deferred_entries_method = 'on_validation'
        move = self.create_invoice('in_invoice', self.company_data['default_journal_purchase'], self.partner_a, [self.expense_lines[0]], post=True)
        self.assertEqual(len(move.deferred_move_ids), 5)  # 1 for the invoice deferred + 4 for the deferred entries
        # See test_deferred_expense_credit_note for the values

    def test_deferred_expense_reset_to_draft(self):
        """
        Test that the deferred entries are deleted/reverted when the invoice is reset to draft.
        """
        self.company.generate_deferred_entries_method = 'on_validation'
        move = self.create_invoice('in_invoice', self.company_data['default_journal_purchase'], self.partner_a, [(self.expense_accounts[0], 1680, '2023-01-21', '2023-04-14')], date='2023-03-15')
        self.assertEqual(len(move.deferred_move_ids), 5)
        move.button_draft()
        self.assertFalse(move.deferred_move_ids)

        # With a lock date, we should reverse the moves that cannot be deleted
        move.action_post()  # Post the move to create the deferred entries with 'on_validation' method
        self.assertEqual(len(move.deferred_move_ids), 5)
        move.company_id.fiscalyear_lock_date = fields.Date.to_date('2023-02-15')
        move.button_draft()
        # January deferred entry is in lock period, so it is reversed, not deleted, thus we have only one
        self.assertEqual(len(move.deferred_move_ids), 1)

    def assert_invoice_lines(self, move, expected_values, source_account, deferred_account):
        deferred_moves = move.deferred_move_ids.sorted('date')
        for deferred_move, expected_value in zip(deferred_moves, expected_values):
            expected_date, expense_line_debit, expense_line_credit, deferred_line_debit, deferred_line_credit = expected_value
            self.assertRecordValues(deferred_move, [{
                'state': 'posted',
                'move_type': 'entry',
                'date': fields.Date.to_date(expected_date),
            }])
            expense_line = deferred_move.line_ids.filtered(lambda line: line.account_id == source_account)
            self.assertRecordValues(expense_line, [
                {'debit': expense_line_debit, 'credit': expense_line_credit},
            ])
            deferred_line = deferred_move.line_ids.filtered(lambda line: line.account_id == deferred_account)
            self.assertEqual(deferred_line.debit, deferred_line_debit)
            self.assertEqual(deferred_line.credit, deferred_line_credit)

    def test_default_tax_on_account_not_on_deferred_entries(self):
        """
        Test that the default taxes on an account are not calculated on deferral entries, since this would impact the
        tax report.
        """
        revenue_account_with_taxes = self.env['account.account'].create({
            'name': 'Revenue with Taxes',
            'code': 'REVWTAXES',
            'account_type': 'income',
            'tax_ids': [Command.set(self.tax_sale_a.ids)]
        })

        move = self.create_invoice(
            'out_invoice',
            self.company_data['default_journal_sale'],
            self.partner_a,
            [[revenue_account_with_taxes, 1000, '2023-01-01', '2023-04-30']],
            date='2022-12-10'
        )

        expected_line_values = [
            # Date         [Line expense] [Line deferred]
            ('2022-12-31',  1000,      0,      0,   1000),
            ('2023-01-31',     0,    250,    250,      0),
            ('2023-02-28',     0,    250,    250,      0),
            ('2023-03-31',     0,    250,    250,      0),
        ]

        self.assert_invoice_lines(
            move,
            expected_line_values,
            revenue_account_with_taxes,
            self.company_data['default_account_deferred_revenue']
        )

        for deferred_move in move.deferred_move_ids:
            # There are no extra lines besides the two lines we checked before
            self.assertEqual(len(deferred_move.line_ids), 2)


    def test_deferred_values(self):
        """
        Test that the debit/credit values are correctly computed, even after a credit note is issued.
        """
        self.company.generate_deferred_entries_method = 'on_validation'

        expected_line_values1 = [
            # Date         [Line expense] [Line deferred]
            ('2022-12-31',     0,   1000,    1000,     0),
            ('2023-01-31',   250,      0,       0,   250),
            ('2023-02-28',   250,      0,       0,   250),
            ('2023-03-31',   250,      0,       0,   250),
        ]
        expected_line_values2 = [
            # Date         [Line expense] [Line deferred]
            ('2022-12-31',  1000,      0,      0,   1000),
            ('2023-01-31',     0,    250,    250,      0),
            ('2023-02-28',     0,    250,    250,      0),
            ('2023-03-31',     0,    250,    250,      0),
        ]

        # Vendor bill and credit note
        move = self.create_invoice('in_invoice', self.company_data['default_journal_purchase'], self.partner_a, [self.expense_lines[0]], post=True, date='2022-12-10')
        self.assert_invoice_lines(move, expected_line_values1, self.expense_accounts[0], self.company_data['default_account_deferred_expense'])
        reverse_move = move._reverse_moves()
        self.assert_invoice_lines(reverse_move, expected_line_values2, self.expense_accounts[0], self.company_data['default_account_deferred_expense'])

        # Customer invoice and credit note
        move2 = self.create_invoice('out_invoice', self.company_data['default_journal_sale'], self.partner_a, [self.revenue_lines[0]], post=True, date='2022-12-10')
        self.assert_invoice_lines(move2, expected_line_values2, self.revenue_accounts[0], self.company_data['default_account_deferred_revenue'])
        reverse_move2 = move2._reverse_moves()
        self.assert_invoice_lines(reverse_move2, expected_line_values1, self.revenue_accounts[0], self.company_data['default_account_deferred_revenue'])

    def test_deferred_expense_avoid_useless_deferred_entries(self):
        """
        If we have an invoice with a start date in the beginning of the month, and an end date in the end of the month,
        we should not create the deferred entries because the original invoice will be totally deferred
        on the last day of the month, but the full amount will be accounted for on the same day too, thus
        cancelling each other. Therefore we should not create the deferred entries.
        """
        self.company.generate_deferred_entries_method = 'on_validation'
        move = self.create_invoice('in_invoice', self.company_data['default_journal_purchase'], self.partner_a, [(self.expense_accounts[0], 1680, '2023-01-01', '2023-01-31')], date='2023-01-01')
        self.assertEqual(len(move.deferred_move_ids), 0)

    def test_taxes_deferred_after_date_added(self):
        """
        Test that applicable taxes get deferred also when the dates of the base line are filled in after a first save.
        """
        self.company.generate_deferred_entries_method = 'on_validation'

        expected_line_values = [
            # Date         [Line expense] [Line deferred]
            ('2022-12-31',     0,   1000,    1000,     0),
            ('2022-12-31',     0,    100,     100,     0),
            ('2023-01-31',   250,      0,       0,   250),
            ('2023-01-31',    25,      0,       0,    25),
            ('2023-02-28',   250,      0,       0,   250),
            ('2023-02-28',    25,      0,       0,    25),
            ('2023-03-31',   250,      0,       0,   250),
            ('2023-03-31',    25,      0,       0,    25),
        ]

        partially_deductible_tax = self.env['account.tax'].create({
            'name': 'Partially deductible Tax',
            'amount': 20,
            'amount_type': 'percent',
            'type_tax_use': 'purchase',
            'invoice_repartition_line_ids': [
                Command.create({'repartition_type': 'base'}),
                Command.create({
                    'factor_percent': 50,
                    'repartition_type': 'tax',
                    'use_in_tax_closing': False
                }),
                Command.create({
                    'factor_percent': 50,
                    'repartition_type': 'tax',
                    'account_id': self.company_data['default_account_tax_purchase'].id,
                    'use_in_tax_closing': True
                }),
            ],
            'refund_repartition_line_ids': [
                Command.create({'repartition_type': 'base'}),
                Command.create({
                    'factor_percent': 50,
                    'repartition_type': 'tax',
                    'use_in_tax_closing': False
                }),
                Command.create({
                    'factor_percent': 50,
                    'repartition_type': 'tax',
                    'account_id': self.company_data['default_account_tax_purchase'].id,
                    'use_in_tax_closing': True
                }),
            ],
        })

        move = self.env['account.move'].create({
            'move_type': 'in_invoice',
            'partner_id': self.partner_a.id,
            'date': '2022-12-10',
            'invoice_date': '2022-12-10',
            'journal_id': self.company_data['default_journal_purchase'].id,
            'invoice_line_ids': [
                Command.create({
                    'quantity': 1,
                    'account_id': self.expense_lines[0][0].id,
                    'price_unit': self.expense_lines[0][1],
                    'tax_ids': [Command.set(partially_deductible_tax.ids)],
                })
            ]
        })

        move.invoice_line_ids.write({
            'deferred_start_date': self.expense_lines[0][2],
            'deferred_end_date': self.expense_lines[0][3],
        })

        move.action_post()

        self.assert_invoice_lines(move, expected_line_values, self.expense_accounts[0], self.company_data['default_account_deferred_expense'])
