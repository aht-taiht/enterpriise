# -*- coding: utf-8 -*-
from odoo.addons.account_accountant.tests.test_bank_rec_widget_common import TestBankRecWidgetCommon
from odoo.exceptions import UserError
from odoo.tests import tagged
from odoo.tools import html2plaintext
from odoo import fields, Command

from freezegun import freeze_time
from unittest.mock import patch
import re

@tagged('post_install', '-at_install')
class TestBankRecWidget(TestBankRecWidgetCommon):

    @classmethod
    def setUpClass(cls, chart_template_ref=None):
        super().setUpClass(chart_template_ref=chart_template_ref)

        cls.early_payment_term = cls.env['account.payment.term'].create({
            'name': "early_payment_term",
            'company_id': cls.company_data['company'].id,
            'discount_percentage': 10,
            'discount_days': 10,
            'early_discount': True,
            'line_ids': [
                Command.create({
                    'value': 'percent',
                    'value_amount': 100,
                    'nb_days': 20,
                }),
            ],
        })

        cls.account_revenue1 = cls.company_data['default_account_revenue']
        cls.account_revenue2 = cls.copy_account(cls.account_revenue1)

    def assert_form_extra_text_value(self, wizard, regex):
        line = wizard.line_ids.filtered(lambda x: x.index == wizard.form_index)
        value = line.suggestion_html
        if regex:
            cleaned_value = html2plaintext(value).replace('\n', '')
            if not re.match(regex, cleaned_value):
                self.fail(f"The following 'form_extra_text':\n\n'{cleaned_value}'\n\n...doesn't match the provided regex:\n\n'{regex}'")
        else:
            self.assertFalse(value)

    def test_retrieve_partner_from_account_number(self):
        st_line = self._create_st_line(1000.0, partner_id=None, account_number="014 474 8555")
        bank_account = self.env['res.partner.bank'].create({
            'acc_number': '0144748555',
            'partner_id': self.partner_a.id,
        })
        self.assertEqual(st_line._retrieve_partner(), bank_account.partner_id)

        # Can't retrieve the partner since the bank account is used by multiple partners.
        self.env['res.partner.bank'].create({
            'acc_number': '0144748555',
            'partner_id': self.partner_b.id,
        })
        self.assertEqual(st_line._retrieve_partner(), self.env['res.partner'])

    def test_retrieve_partner_from_partner_name(self):
        """ Ensure the partner having a name fitting exactly the 'partner_name' is retrieved first.
        This test create two partners that will be ordered in the lexicographic order when performing
        a search. So:
        row1: "Turlututu tsoin tsoin"
        row2: "turlututu"

        Since "turlututu" matches exactly (case insensitive) the partner_name of the statement line,
        it should be suggested first.
        """
        _partner_a, partner_b = self.env['res.partner'].create([
            {'name': "Turlututu tsoin tsoin"},
            {'name': "turlututu"},
        ])

        st_line = self._create_st_line(1000.0, partner_id=None, partner_name="Turlututu")
        self.assertEqual(st_line._retrieve_partner(), partner_b)

    def test_res_partner_bank_find_create_when_archived(self):
        """ Test we don't get the "The combination Account Number/Partner must be unique." error with archived
        bank account.
        """
        partner = self.env['res.partner'].create({
            'name': "Zitycard",
            'bank_ids': [Command.create({
                'acc_number': "123456789",
                'active': False,
            })],
        })

        st_line = self._create_st_line(
            100.0,
            partner_name="Zeumat Zitycard",
            account_number="123456789",
        )
        inv_line = self._create_invoice_line(
            'out_invoice',
            partner_id=partner.id,
            invoice_line_ids=[{'price_unit': 100.0, 'tax_ids': []}],
        )
        wizard = self.env['bank.rec.widget'].with_context(default_st_line_id=st_line.id).new({})
        wizard._action_add_new_amls(inv_line)
        wizard._action_validate()

        # Should not trigger the error.
        self.env['res.partner.bank'].flush_model()

    def test_res_partner_bank_find_create_multi_company(self):
        """ Test we don't get the "The combination Account Number/Partner must be unique." error when the bank account
        already exists on another company.
        """
        partner = self.env['res.partner'].create({
            'name': "Zitycard",
            'bank_ids': [Command.create({'acc_number': "123456789"})],
        })
        partner.bank_ids.company_id = self.company_data_2['company']
        self.env.user.company_ids = self.env.company

        st_line = self._create_st_line(
            100.0,
            partner_name="Zeumat Zitycard",
            account_number="123456789",
        )
        inv_line = self._create_invoice_line(
            'out_invoice',
            partner_id=partner.id,
            invoice_line_ids=[{'price_unit': 100.0, 'tax_ids': []}],
        )
        wizard = self.env['bank.rec.widget'].with_context(default_st_line_id=st_line.id).new({})
        wizard._action_add_new_amls(inv_line)
        wizard._action_validate()

        # Should not trigger the error.
        self.env['res.partner.bank'].flush_model()

    def test_validation_base_case(self):
        st_line = self._create_st_line(
            1000.0,
            date='2017-01-01',
        )

        wizard = self.env['bank.rec.widget'].with_context(default_st_line_id=st_line.id).new({})
        line = wizard.line_ids.filtered(lambda x: x.flag == 'auto_balance')
        wizard._js_action_mount_line_in_edit(line.index)
        line.account_id = self.account_revenue1
        wizard._line_value_changed_account_id(line)
        self.assertRecordValues(wizard.line_ids, [
            # pylint: disable=C0326
            {'flag': 'liquidity',     'amount_currency': 1000.0,  'currency_id': self.company_data['currency'].id,    'balance': 1000.0},
            {'flag': 'manual',        'amount_currency': -1000.0, 'currency_id': self.company_data['currency'].id,    'balance': -1000.0},
        ])
        self.assertRecordValues(wizard, [{'state': 'valid'}])

        # The amount is the same, no message under the 'amount' field.
        self.assert_form_extra_text_value(wizard, False)

        wizard._action_validate()
        self.assertRecordValues(st_line.line_ids, [
            # pylint: disable=C0326
            {'account_id': st_line.journal_id.default_account_id.id,    'amount_currency': 1000.0,      'currency_id': self.company_data['currency'].id,    'balance': 1000.0,  'reconciled': False},
            {'account_id': self.account_revenue1.id,                    'amount_currency': -1000.0,     'currency_id': self.company_data['currency'].id,    'balance': -1000.0, 'reconciled': False},
        ])

        self.assertRecordValues(wizard.line_ids, [
            # pylint: disable=C0326
            {'flag': 'liquidity', 'account_id': st_line.journal_id.default_account_id.id,  'amount_currency': 1000.0,  'currency_id': self.company_data['currency'].id,    'balance': 1000.0},
            {'flag': 'aml',       'account_id': self.account_revenue1.id,                  'amount_currency': -1000.0, 'currency_id': self.company_data['currency'].id,    'balance': -1000.0},
        ])

    def test_validation_new_aml_same_foreign_currency(self):
        income_exchange_account = self.env.company.income_currency_exchange_account_id

        # 6000.0 curr2 == 1200.0 comp_curr (bank rate 5:1 instead of the odoo rate 4:1)
        st_line = self._create_st_line(
            1200.0,
            date='2017-01-01',
            foreign_currency_id=self.currency_data_2['currency'].id,
            amount_currency=6000.0,
        )
        # 6000.0 curr2 == 1000.0 comp_curr (rate 6:1)
        inv_line = self._create_invoice_line(
            'out_invoice',
            currency_id=self.currency_data_2['currency'].id,
            invoice_date='2016-01-01',
            invoice_line_ids=[{'price_unit': 6000.0}],
        )

        wizard = self.env['bank.rec.widget'].with_context(default_st_line_id=st_line.id).new({})
        wizard._action_add_new_amls(inv_line)
        self.assertRecordValues(wizard.line_ids, [
            # pylint: disable=C0326
            {'flag': 'liquidity',       'amount_currency': 1200.0,      'currency_id': self.company_data['currency'].id,    'balance': 1200.0},
            {'flag': 'new_aml',         'amount_currency': -6000.0,     'currency_id': self.currency_data_2['currency'].id, 'balance': -1000.0},
            {'flag': 'exchange_diff',   'amount_currency': 0.0,         'currency_id': self.currency_data_2['currency'].id, 'balance': -200.0},
        ])
        self.assertRecordValues(wizard, [{'state': 'valid'}])

        # The amount is the same, no message under the 'amount' field.
        self.assert_form_extra_text_value(wizard, False)

        wizard._action_validate()
        self.assertRecordValues(st_line.line_ids, [
            # pylint: disable=C0326
            {'account_id': st_line.journal_id.default_account_id.id,    'amount_currency': 1200.0,      'currency_id': self.company_data['currency'].id,    'balance': 1200.0,  'reconciled': False},
            {'account_id': inv_line.account_id.id,                      'amount_currency': -6000.0,     'currency_id': self.currency_data_2['currency'].id, 'balance': -1200.0, 'reconciled': True},
        ])
        self.assertRecordValues(st_line, [{'is_reconciled': True}])
        self.assertRecordValues(inv_line.move_id, [{'payment_state': 'paid'}])
        self.assertRecordValues(inv_line.matched_credit_ids.exchange_move_id.line_ids, [
            # pylint: disable=C0326
            {'account_id': inv_line.account_id.id,                      'amount_currency': 0.0,         'currency_id': self.currency_data_2['currency'].id, 'balance': 200.0,   'reconciled': True},
            {'account_id': income_exchange_account.id,                  'amount_currency': 0.0,         'currency_id': self.currency_data_2['currency'].id, 'balance': -200.0,  'reconciled': False},
        ])

        # Reset the wizard.
        wizard._js_action_reset()
        self.assertRecordValues(wizard.line_ids, [
            # pylint: disable=C0326
            {'flag': 'liquidity',       'amount_currency': 1200.0,      'currency_id': self.company_data['currency'].id,    'balance': 1200.0},
            {'flag': 'auto_balance',    'amount_currency': -6000.0,     'currency_id': self.currency_data_2['currency'].id, 'balance': -1200.0},
        ])

        # Create the same invoice with a higher amount to check the partial flow.
        # 9000.0 curr2 == 1500.0 comp_curr (rate 6:1)
        inv_line = self._create_invoice_line(
            'out_invoice',
            currency_id=self.currency_data_2['currency'].id,
            invoice_date='2016-01-01',
            invoice_line_ids=[{'price_unit': 9000.0}],
        )
        wizard._action_add_new_amls(inv_line)
        self.assertRecordValues(wizard.line_ids, [
            # pylint: disable=C0326
            {'flag': 'liquidity',       'amount_currency': 1200.0,      'currency_id': self.company_data['currency'].id,    'balance': 1200.0},
            {'flag': 'new_aml',         'amount_currency': -6000.0,     'currency_id': self.currency_data_2['currency'].id, 'balance': -1000.0},
            {'flag': 'exchange_diff',   'amount_currency': 0.0,         'currency_id': self.currency_data_2['currency'].id, 'balance': -200.0},
        ])

        # Check the message under the 'amount' field.
        line = wizard.line_ids.filtered(lambda x: x.flag == 'new_aml')
        wizard._js_action_mount_line_in_edit(line.index)
        self.assert_form_extra_text_value(
            wizard,
            r".+open amount of 9,000.000.+ reduced by 6,000.000.+ set the invoice as fully paid .",
        )
        self.assertRecordValues(line, [{
            'suggestion_amount_currency': -9000.0,
            'suggestion_balance': -1500.0,
        }])

        # Switch to a full reconciliation.
        wizard._js_action_apply_line_suggestion(line.index)
        self.assertRecordValues(wizard.line_ids, [
            # pylint: disable=C0326
            {'flag': 'liquidity',       'amount_currency': 1200.0,      'currency_id': self.company_data['currency'].id,    'balance': 1200.0},
            {'flag': 'new_aml',         'amount_currency': -9000.0,     'currency_id': self.currency_data_2['currency'].id, 'balance': -1500.0},
            {'flag': 'exchange_diff',   'amount_currency': 0.0,         'currency_id': self.currency_data_2['currency'].id, 'balance': -300.0},
            {'flag': 'auto_balance',    'amount_currency': 3000.0,      'currency_id': self.currency_data_2['currency'].id, 'balance': 600.0},
        ])

        # Check the message under the 'amount' field.
        line = wizard.line_ids.filtered(lambda x: x.flag == 'new_aml')
        wizard._js_action_mount_line_in_edit(line.index)
        self.assert_form_extra_text_value(
            wizard,
            r".+open amount of 9,000.000.+ paid .+ record a partial payment .",
        )
        self.assertRecordValues(line, [{
            'suggestion_amount_currency': -6000.0,
            'suggestion_balance': -1000.0,
        }])

        # Switch back to a partial reconciliation.
        wizard._js_action_apply_line_suggestion(line.index)
        self.assertRecordValues(wizard, [{'state': 'valid'}])

        # Reconcile
        wizard._action_validate()
        self.assertRecordValues(st_line.line_ids, [
            # pylint: disable=C0326
            {'account_id': st_line.journal_id.default_account_id.id,    'amount_currency': 1200.0,      'currency_id': self.company_data['currency'].id,    'balance': 1200.0,  'reconciled': False},
            {'account_id': inv_line.account_id.id,                      'amount_currency': -6000.0,     'currency_id': self.currency_data_2['currency'].id, 'balance': -1200.0, 'reconciled': True},
        ])
        self.assertRecordValues(st_line, [{'is_reconciled': True}])
        self.assertRecordValues(inv_line.move_id, [{
            'payment_state': 'partial',
            'amount_residual': 3000.0,
        }])
        self.assertRecordValues(inv_line.matched_credit_ids.exchange_move_id.line_ids, [
            # pylint: disable=C0326
            {'account_id': inv_line.account_id.id,                      'amount_currency': 0.0,         'currency_id': self.currency_data_2['currency'].id, 'balance': 200.0,   'reconciled': True},
            {'account_id': income_exchange_account.id,                  'amount_currency': 0.0,         'currency_id': self.currency_data_2['currency'].id, 'balance': -200.0,  'reconciled': False},
        ])

    def test_validation_expense_exchange_difference(self):
        expense_exchange_account = self.env.company.expense_currency_exchange_account_id
        foreign_currency = self.setup_multi_currency_data(default_values={
            'name': 'Diamond',
            'symbol': '💎',
            'currency_unit_label': 'Diamond',
            'currency_subunit_label': 'Carbon',
        }, rate2016=1.0, rate2017=0.25)['currency']
        # 1000.0 foreign_currency == 1000.0 comp_curr in 2016 (rate 1:1)
        st_line = self._create_st_line(
            1000.0,
            date='2016-01-01',
            foreign_currency_id=foreign_currency.id,
            amount_currency=1000.0,
        )
        # 1000.0 comp_curr is equals to 4000.0 curr2 in 2017 (rate 1:4)
        inv_line = self._create_invoice_line(
            'out_invoice',
            invoice_date='2017-01-01',
            invoice_line_ids=[{'price_unit': 4000.0}],
        )

        wizard = self.env['bank.rec.widget'].with_context(default_st_line_id=st_line.id).new({})
        wizard._action_add_new_amls(inv_line)
        self.assertRecordValues(wizard.line_ids, [
            # pylint: disable=C0326
            {'flag': 'liquidity',       'amount_currency': 1000.0,        'currency_id': self.company_data['currency'].id,    'balance': 1000.0},
            {'flag': 'new_aml',         'amount_currency': -4000.0,       'currency_id': self.company_data['currency'].id,    'balance': -4000.0},
            {'flag': 'exchange_diff',   'amount_currency': 3000.0,        'currency_id': self.company_data['currency'].id,    'balance': 3000.0},
        ])
        self.assertRecordValues(wizard, [{'state': 'valid'}])

        wizard._action_validate()
        self.assertRecordValues(st_line.line_ids, [
            # pylint: disable=C0326
            {'account_id': st_line.journal_id.default_account_id.id,  'amount_currency': 1000.0,       'currency_id': self.company_data['currency'].id,    'balance': 1000.0,   'reconciled': False},
            {'account_id': inv_line.account_id.id,                    'amount_currency': -1000.0,      'currency_id': self.company_data['currency'].id,    'balance': -1000.0,  'reconciled': True},
        ])
        self.assertRecordValues(st_line, [{'is_reconciled': True}])
        self.assertRecordValues(inv_line.move_id, [{'payment_state': 'paid'}])
        self.assertRecordValues(inv_line.matched_credit_ids.exchange_move_id.line_ids, [
            # pylint: disable=C0326
            {'account_id': inv_line.account_id.id,                 'amount_currency': -3000.0,        'currency_id': self.company_data['currency'].id, 'balance': -3000.0,  'reconciled': True},
            {'account_id': expense_exchange_account.id,            'amount_currency': 3000.0,         'currency_id': self.company_data['currency'].id, 'balance': 3000.0,   'reconciled': False},
        ])
        # Checks that the wizard still display the 3 initial lines
        self.assertRecordValues(wizard.line_ids, [
            # pylint: disable=C0326
            {'flag': 'liquidity',       'amount_currency': 1000.0,       'currency_id': self.company_data['currency'].id,    'balance': 1000.0},
            {'flag': 'aml',             'amount_currency': -4000.0,      'currency_id': self.company_data['currency'].id,    'balance': -4000.0},
            {'flag': 'aml',             'amount_currency': 3000.0,       'currency_id': self.company_data['currency'].id,    'balance': 3000.0},  # represents the exchange diff
        ])

    def test_validation_income_exchange_difference(self):
        income_exchange_account = self.env.company.income_currency_exchange_account_id
        foreign_currency = self.setup_multi_currency_data(default_values={
            'name': 'Diamond',
            'symbol': '💎',
            'currency_unit_label': 'Diamond',
            'currency_subunit_label': 'Carbon',
        }, rate2016=1.0, rate2017=4.0)['currency']
        # 1000.0 foreign_currency == 1000.0 comp_curr in 2016 (rate 1:1)
        st_line = self._create_st_line(
            1000.0,
            date='2016-01-01',
            foreign_currency_id=foreign_currency.id,
            amount_currency=1000.0,
        )
        # 1000.0 comp_curr is equals to 250.0 curr2 in 2017 (rate 4:1)
        inv_line = self._create_invoice_line(
            'out_invoice',
            invoice_date='2017-01-01',
            invoice_line_ids=[{'price_unit': 250.0}],
        )

        wizard = self.env['bank.rec.widget'].with_context(default_st_line_id=st_line.id).new({})
        wizard._action_add_new_amls(inv_line)
        self.assertRecordValues(wizard.line_ids, [
            # pylint: disable=C0326
            {'flag': 'liquidity',       'amount_currency': 1000.0,        'currency_id': self.company_data['currency'].id,    'balance': 1000.0},
            {'flag': 'new_aml',         'amount_currency': -250.0,        'currency_id': self.company_data['currency'].id,    'balance': -250.0},
            {'flag': 'exchange_diff',   'amount_currency': -750.0,        'currency_id': self.company_data['currency'].id,    'balance': -750.0},
        ])
        self.assertRecordValues(wizard, [{'state': 'valid'}])

        wizard._action_validate()
        self.assertRecordValues(st_line.line_ids, [
            # pylint: disable=C0326
            {'account_id': st_line.journal_id.default_account_id.id, 'amount_currency': 1000.0,       'currency_id': self.company_data['currency'].id,    'balance': 1000.0,   'reconciled': False},
            {'account_id': inv_line.account_id.id,                   'amount_currency': -1000.0,      'currency_id': self.company_data['currency'].id,    'balance': -1000.0,  'reconciled': True},
        ])
        self.assertRecordValues(st_line, [{'is_reconciled': True}])
        self.assertRecordValues(inv_line.move_id, [{'payment_state': 'paid'}])
        self.assertRecordValues(inv_line.matched_credit_ids.exchange_move_id.line_ids, [
            # pylint: disable=C0326
            {'account_id': inv_line.account_id.id,                 'amount_currency': 750.0,        'currency_id': self.company_data['currency'].id, 'balance': 750.0,   'reconciled': True},
            {'account_id': income_exchange_account.id,             'amount_currency': -750.0,       'currency_id': self.company_data['currency'].id, 'balance': -750.0,  'reconciled': False},
        ])
        # Checks that the wizard still display the 3 initial lines
        self.assertRecordValues(wizard.line_ids, [
            # pylint: disable=C0326
            {'flag': 'liquidity',       'amount_currency': 1000.0,       'currency_id': self.company_data['currency'].id,    'balance': 1000.0},
            {'flag': 'aml',             'amount_currency': -250.0,       'currency_id': self.company_data['currency'].id,    'balance': -250.0},
            {'flag': 'aml',             'amount_currency': -750.0,       'currency_id': self.company_data['currency'].id,    'balance': -750.0},  # represents the exchange diff
        ])

    def test_validation_exchange_diff_multiple(self):
        income_exchange_account = self.env.company.income_currency_exchange_account_id
        foreign_currency = self.setup_multi_currency_data(default_values={
            'name': 'Diamond',
            'symbol': '💎',
            'currency_unit_label': 'Diamond',
            'currency_subunit_label': 'Carbon',
        }, rate2016=6.0, rate2017=5.0)['currency']

        # 6000.0 curr2 == 1200.0 comp_curr (bank rate 5:1 instead of the odoo rate 6:1)
        st_line = self._create_st_line(
            1200.0,
            date='2016-01-01',
            foreign_currency_id=foreign_currency.id,
            amount_currency=6000.0,
        )
        # 1000.0 foreign_curr == 166.67 comp_curr (rate 6:1)
        inv_line_1 = self._create_invoice_line(
            'out_invoice',
            currency_id=foreign_currency.id,
            invoice_date='2016-01-01',
            invoice_line_ids=[{'price_unit': 1000.0}],
        )
        # 2000.00 foreign_curr == 400.0 comp_curr (rate 5:1)
        inv_line_2 = self._create_invoice_line(
            'out_invoice',
            currency_id=foreign_currency.id,
            invoice_date='2017-01-01',
            invoice_line_ids=[{'price_unit': 2000.0}],
        )
        # 3000.0 foreign_curr == 500.0 comp_curr (rate 6:1)
        inv_line_3 = self._create_invoice_line(
            'out_invoice',
            currency_id=foreign_currency.id,
            invoice_date='2016-01-01',
            invoice_line_ids=[{'price_unit': 3000.0}],
        )

        wizard = self.env['bank.rec.widget'].with_context(default_st_line_id=st_line.id).new({})
        wizard._action_add_new_amls(inv_line_1 + inv_line_2 + inv_line_3)
        self.assertRecordValues(wizard.line_ids, [
            # pylint: disable=C0326
            {'flag': 'liquidity',       'amount_currency': 1200.0,      'currency_id': self.company_data['currency'].id,  'balance': 1200.0},
            {'flag': 'new_aml',         'amount_currency': -1000.0,     'currency_id': foreign_currency.id,               'balance': -166.67},
            {'flag': 'exchange_diff',   'amount_currency': 0.0,         'currency_id': foreign_currency.id,               'balance': -33.33},
            {'flag': 'new_aml',         'amount_currency': -2000.0,     'currency_id': foreign_currency.id,               'balance': -400.0},
            {'flag': 'new_aml',         'amount_currency': -3000.0,     'currency_id': foreign_currency.id,               'balance': -500.0},
            {'flag': 'exchange_diff',   'amount_currency': 0.0,         'currency_id': foreign_currency.id,               'balance': -100.0},
        ])
        self.assertRecordValues(wizard, [{'state': 'valid'}])

        # The amount is the same, no message under the 'amount' field.
        self.assert_form_extra_text_value(wizard, False)

        wizard._action_validate()
        self.assertRecordValues(st_line.line_ids, [
            # pylint: disable=C0326
            {'account_id': st_line.journal_id.default_account_id.id,      'amount_currency': 1200.0,      'currency_id': self.company_data['currency'].id,  'balance': 1200.0,  'reconciled': False},
            {'account_id': inv_line_1.account_id.id,                      'amount_currency': -1000.0,     'currency_id': foreign_currency.id,               'balance': -200.0,  'reconciled': True},
            {'account_id': inv_line_2.account_id.id,                      'amount_currency': -2000.0,     'currency_id': foreign_currency.id,               'balance': -400.0,  'reconciled': True},
            {'account_id': inv_line_3.account_id.id,                      'amount_currency': -3000.0,     'currency_id': foreign_currency.id,               'balance': -600.0,  'reconciled': True},
        ])
        self.assertRecordValues(st_line, [{'is_reconciled': True}])
        self.assertRecordValues(inv_line_1.move_id, [{'payment_state': 'paid'}])
        self.assertRecordValues(inv_line_2.move_id, [{'payment_state': 'paid'}])
        self.assertRecordValues(inv_line_3.move_id, [{'payment_state': 'paid'}])
        self.assertRecordValues((inv_line_1 + inv_line_2 + inv_line_3).matched_credit_ids.exchange_move_id.line_ids, [
            # pylint: disable=C0326
            {'account_id': inv_line_1.account_id.id,    'amount_currency': 0.0, 'currency_id': foreign_currency.id, 'balance': 33.33,   'reconciled': True},
            {'account_id': income_exchange_account.id,  'amount_currency': 0.0, 'currency_id': foreign_currency.id, 'balance': -33.33,  'reconciled': False},
            {'account_id': inv_line_3.account_id.id,    'amount_currency': 0.0, 'currency_id': foreign_currency.id, 'balance': 100.0,   'reconciled': True},
            {'account_id': income_exchange_account.id,  'amount_currency': 0.0, 'currency_id': foreign_currency.id, 'balance': -100.0,  'reconciled': False},
        ])

    def test_validation_new_aml_one_foreign_currency_on_st_line(self):
        income_exchange_account = self.env.company.income_currency_exchange_account_id

        # 4800.0 curr2 == 1200.0 comp_curr (rate 4:1)
        st_line = self._create_st_line(
            1200.0,
            date='2017-01-01',
            foreign_currency_id=self.currency_data_2['currency'].id,
            amount_currency=4800.0,
        )
        # 800.0 comp_curr is equals to 4800.0 curr2 in 2016 (rate 6:1)
        inv_line = self._create_invoice_line(
            'out_invoice',
            invoice_date='2016-01-01',
            invoice_line_ids=[{'price_unit': 800.0}],
        )

        wizard = self.env['bank.rec.widget'].with_context(default_st_line_id=st_line.id).new({})
        wizard._action_add_new_amls(inv_line)
        self.assertRecordValues(wizard.line_ids, [
            # pylint: disable=C0326
            {'flag': 'liquidity',       'amount_currency': 1200.0,      'currency_id': self.company_data['currency'].id,    'balance': 1200.0},
            {'flag': 'new_aml',         'amount_currency': -800.0,      'currency_id': self.company_data['currency'].id,    'balance': -800.0},
            {'flag': 'exchange_diff',   'amount_currency': -400.0,      'currency_id': self.company_data['currency'].id,    'balance': -400.0},
        ])
        self.assertRecordValues(wizard, [{'state': 'valid'}])

        # The amount is the same, no message under the 'amount' field.
        self.assert_form_extra_text_value(wizard, False)

        wizard._action_validate()
        self.assertRecordValues(st_line.line_ids, [
            # pylint: disable=C0326
            {'account_id': st_line.journal_id.default_account_id.id,    'amount_currency': 1200.0,       'currency_id': self.company_data['currency'].id,    'balance': 1200.0,   'reconciled': False},
            {'account_id': inv_line.account_id.id,                      'amount_currency': -1200.0,      'currency_id': self.company_data['currency'].id,    'balance': -1200.0,  'reconciled': True},
        ])
        self.assertRecordValues(st_line, [{'is_reconciled': True}])
        self.assertRecordValues(inv_line.move_id, [{'payment_state': 'paid'}])
        self.assertRecordValues(inv_line.matched_credit_ids.exchange_move_id.line_ids, [
            # pylint: disable=C0326
            {'account_id': inv_line.account_id.id,                      'amount_currency': 400.0,          'currency_id': self.company_data['currency'].id, 'balance': 400.0,   'reconciled': True},
            {'account_id': income_exchange_account.id,                  'amount_currency': -400.0,         'currency_id': self.company_data['currency'].id, 'balance': -400.0,  'reconciled': False},
        ])

        # Checks that the wizard still display the 3 initial lines
        self.assertRecordValues(wizard.line_ids, [
            # pylint: disable=C0326
            {'flag': 'liquidity',       'amount_currency': 1200.0,      'currency_id': self.company_data['currency'].id,    'balance': 1200.0},
            {'flag': 'aml',             'amount_currency': -800.0,      'currency_id': self.company_data['currency'].id,    'balance': -800.0},
            {'flag': 'aml',             'amount_currency': -400.0,      'currency_id': self.company_data['currency'].id,    'balance': -400.0},  # represents the exchange diff
        ])

        # Reset the wizard.
        wizard._js_action_reset()
        self.assertRecordValues(wizard.line_ids, [
            # pylint: disable=C0326
            {'flag': 'liquidity',       'amount_currency': 1200.0,      'currency_id': self.company_data['currency'].id,    'balance': 1200.0},
            {'flag': 'auto_balance',    'amount_currency': -4800.0,     'currency_id': self.currency_data_2['currency'].id, 'balance': -1200.0},
        ])

        # Create the same invoice with a higher amount to check the partial flow.
        # 1200.0 comp_curr is equals to 7200.0 curr2 in 2016 (rate 6:1)
        inv_line = self._create_invoice_line(
            'out_invoice',
            invoice_date='2016-01-01',
            invoice_line_ids=[{'price_unit': 1200.0}],
        )
        wizard._action_add_new_amls(inv_line)
        self.assertRecordValues(wizard.line_ids, [
            # pylint: disable=C0326
            {'flag': 'liquidity',       'amount_currency': 1200.0,      'currency_id': self.company_data['currency'].id,    'balance': 1200.0},
            {'flag': 'new_aml',         'amount_currency': -800.0,      'currency_id': self.company_data['currency'].id,    'balance': -800.0},
            {'flag': 'exchange_diff',   'amount_currency': -400.0,      'currency_id': self.company_data['currency'].id,    'balance': -400.0},
        ])

        # Check the message under the 'amount' field.
        line = wizard.line_ids.filtered(lambda x: x.flag == 'new_aml')
        wizard._js_action_mount_line_in_edit(line.index)
        self.assert_form_extra_text_value(
            wizard,
            r".+open amount of .+1,200.00.+ reduced by .+800.00.+ set the invoice as fully paid .",
        )
        self.assertRecordValues(line, [{
            'suggestion_amount_currency': -1200.0,
            'suggestion_balance': -1200.0,
        }])

        # Switch to a full reconciliation.
        wizard._js_action_apply_line_suggestion(line.index)
        self.assertRecordValues(wizard.line_ids, [
            # pylint: disable=C0326
            {'flag': 'liquidity',       'amount_currency': 1200.0,      'currency_id': self.company_data['currency'].id,    'balance': 1200.0},
            {'flag': 'new_aml',         'amount_currency': -1200.0,     'currency_id': self.company_data['currency'].id,    'balance': -1200.0},
            {'flag': 'exchange_diff',   'amount_currency': -600.0,      'currency_id': self.company_data['currency'].id,    'balance': -600.0},
            {'flag': 'auto_balance',    'amount_currency': 2400.0,      'currency_id': self.currency_data_2['currency'].id, 'balance': 600.0},
        ])

        # Check the message under the 'amount' field.
        line = wizard.line_ids.filtered(lambda x: x.flag == 'new_aml')
        wizard._js_action_mount_line_in_edit(line.index)
        self.assert_form_extra_text_value(
            wizard,
            r".+open amount of .+1,200.00.+ paid .+ record a partial payment .",
        )
        self.assertRecordValues(line, [{
            'suggestion_amount_currency': -800.0,
            'suggestion_balance': -800.0,
        }])

        # Switch back to a partial reconciliation.
        wizard._js_action_apply_line_suggestion(line.index)
        self.assertRecordValues(wizard, [{'state': 'valid'}])

        # Reconcile
        wizard._action_validate()
        self.assertRecordValues(st_line.line_ids, [
            # pylint: disable=C0326
            {'account_id': st_line.journal_id.default_account_id.id,    'amount_currency': 1200.0,       'currency_id': self.company_data['currency'].id,    'balance': 1200.0,   'reconciled': False},
            {'account_id': inv_line.account_id.id,                      'amount_currency': -1200.0,      'currency_id': self.company_data['currency'].id,    'balance': -1200.0,  'reconciled': True},
        ])
        self.assertRecordValues(st_line, [{'is_reconciled': True}])
        self.assertRecordValues(inv_line.move_id, [{
            'payment_state': 'partial',
            'amount_residual': 400.0,
        }])
        self.assertRecordValues(inv_line.matched_credit_ids.exchange_move_id.line_ids, [
            # pylint: disable=C0326
            {'account_id': inv_line.account_id.id,                      'amount_currency': 400.0,          'currency_id': self.company_data['currency'].id, 'balance': 400.0,   'reconciled': True},
            {'account_id': income_exchange_account.id,                  'amount_currency': -400.0,         'currency_id': self.company_data['currency'].id, 'balance': -400.0,  'reconciled': False},
        ])

    def test_validation_new_aml_one_foreign_currency_on_inv_line(self):
        income_exchange_account = self.env.company.income_currency_exchange_account_id

        # 1200.0 comp_curr is equals to 4800.0 curr2 in 2017 (rate 4:1)
        st_line = self._create_st_line(
            1200.0,
            date='2017-01-01',
        )
        # 4800.0 curr2 == 800.0 comp_curr (rate 6:1)
        inv_line = self._create_invoice_line(
            'out_invoice',
            currency_id=self.currency_data_2['currency'].id,
            invoice_date='2016-01-01',
            invoice_line_ids=[{'price_unit': 4800.0}],
        )

        wizard = self.env['bank.rec.widget'].with_context(default_st_line_id=st_line.id).new({})
        wizard._action_add_new_amls(inv_line)
        self.assertRecordValues(wizard.line_ids, [
            # pylint: disable=C0326
            {'flag': 'liquidity',       'amount_currency': 1200.0,      'currency_id': self.company_data['currency'].id,    'balance': 1200.0},
            {'flag': 'new_aml',         'amount_currency': -4800.0,     'currency_id': self.currency_data_2['currency'].id, 'balance': -800.0},
            {'flag': 'exchange_diff',   'amount_currency': 0.0,         'currency_id': self.currency_data_2['currency'].id, 'balance': -400.0},
        ])
        self.assertRecordValues(wizard, [{'state': 'valid'}])

        # The amount is the same, no message under the 'amount' field.
        self.assert_form_extra_text_value(wizard, False)

        # Remove the line to see if the exchange difference is well removed.
        wizard._action_remove_new_amls(inv_line)
        self.assertRecordValues(wizard.line_ids, [
            # pylint: disable=C0326
            {'flag': 'liquidity',       'amount_currency': 1200.0,      'currency_id': self.company_data['currency'].id,    'balance': 1200.0},
            {'flag': 'auto_balance',    'amount_currency': -1200.0,     'currency_id': self.company_data['currency'].id,    'balance': -1200.0},
        ])
        self.assertRecordValues(wizard, [{'state': 'invalid'}])

        # Mount the line again and validate.
        wizard._action_add_new_amls(inv_line)
        wizard._action_validate()
        self.assertRecordValues(st_line.line_ids, [
            # pylint: disable=C0326
            {'account_id': st_line.journal_id.default_account_id.id,    'amount_currency': 1200.0,      'currency_id': self.company_data['currency'].id,    'balance': 1200.0,   'reconciled': False},
            {'account_id': inv_line.account_id.id,                      'amount_currency': -4800.0,     'currency_id': self.currency_data_2['currency'].id, 'balance': -1200.0,  'reconciled': True},
        ])
        self.assertRecordValues(st_line, [{'is_reconciled': True}])
        self.assertRecordValues(inv_line.move_id, [{'payment_state': 'paid'}])
        self.assertRecordValues(inv_line.matched_credit_ids.exchange_move_id.line_ids, [
            # pylint: disable=C0326
            {'account_id': inv_line.account_id.id,                      'amount_currency': 0.0,         'currency_id': self.currency_data_2['currency'].id, 'balance': 400.0,   'reconciled': True},
            {'account_id': income_exchange_account.id,                  'amount_currency': 0.0,         'currency_id': self.currency_data_2['currency'].id, 'balance': -400.0,  'reconciled': False},
        ])

        # Reset the wizard.
        wizard._js_action_reset()
        self.assertRecordValues(wizard.line_ids, [
            # pylint: disable=C0326
            {'flag': 'liquidity',       'amount_currency': 1200.0,      'currency_id': self.company_data['currency'].id,    'balance': 1200.0},
            {'flag': 'auto_balance',    'amount_currency': -1200.0,     'currency_id': self.company_data['currency'].id,    'balance': -1200.0},
        ])

        # Create the same invoice with a higher amount to check the partial flow.
        # 7200.0 curr2 == 1200.0 comp_curr (rate 6:1)
        inv_line = self._create_invoice_line(
            'out_invoice',
            currency_id=self.currency_data_2['currency'].id,
            invoice_date='2016-01-01',
            invoice_line_ids=[{'price_unit': 7200.0}],
        )
        wizard._action_add_new_amls(inv_line)
        self.assertRecordValues(wizard.line_ids, [
            # pylint: disable=C0326
            {'flag': 'liquidity',       'amount_currency': 1200.0,      'currency_id': self.company_data['currency'].id,    'balance': 1200.0},
            {'flag': 'new_aml',         'amount_currency': -4800.0,     'currency_id': self.currency_data_2['currency'].id, 'balance': -800.0},
            {'flag': 'exchange_diff',   'amount_currency': 0.0,         'currency_id': self.currency_data_2['currency'].id, 'balance': -400.0},
        ])

        # Check the message under the 'amount' field.
        line = wizard.line_ids.filtered(lambda x: x.flag == 'new_aml')
        wizard._js_action_mount_line_in_edit(line.index)
        self.assert_form_extra_text_value(
            wizard,
            r".+open amount of 7,200.000.+ reduced by 4,800.000.+ set the invoice as fully paid .",
        )
        self.assertRecordValues(line, [{
            'suggestion_amount_currency': -7200.0,
            'suggestion_balance': -1200.0,
        }])

        # Switch to a full reconciliation.
        wizard._js_action_apply_line_suggestion(line.index)
        self.assertRecordValues(wizard.line_ids, [
            # pylint: disable=C0326
            {'flag': 'liquidity',       'amount_currency': 1200.0,      'currency_id': self.company_data['currency'].id,    'balance': 1200.0},
            {'flag': 'new_aml',         'amount_currency': -7200.0,     'currency_id': self.currency_data_2['currency'].id, 'balance': -1200.0},
            {'flag': 'exchange_diff',   'amount_currency': 0.0,         'currency_id': self.currency_data_2['currency'].id, 'balance': -600.0},
            {'flag': 'auto_balance',    'amount_currency': 600.0,       'currency_id': self.company_data['currency'].id,    'balance': 600.0},
        ])

        # Check the message under the 'amount' field.
        line = wizard.line_ids.filtered(lambda x: x.flag == 'new_aml')
        wizard._js_action_mount_line_in_edit(line.index)
        self.assert_form_extra_text_value(
            wizard,
            r".+open amount of 7,200.000.+ paid .+ record a partial payment .",
        )
        self.assertRecordValues(line, [{
            'suggestion_amount_currency': -4800.0,
            'suggestion_balance': -800.0,
        }])

        # Switch back to a partial reconciliation.
        wizard._js_action_apply_line_suggestion(line.index)
        self.assertRecordValues(wizard, [{'state': 'valid'}])

        # Reconcile
        wizard._action_validate()
        self.assertRecordValues(st_line.line_ids, [
            # pylint: disable=C0326
            {'account_id': st_line.journal_id.default_account_id.id,    'amount_currency': 1200.0,      'currency_id': self.company_data['currency'].id,    'balance': 1200.0,  'reconciled': False},
            {'account_id': inv_line.account_id.id,                      'amount_currency': -4800.0,     'currency_id': self.currency_data_2['currency'].id, 'balance': -1200.0,  'reconciled': True},
        ])
        self.assertRecordValues(st_line, [{'is_reconciled': True}])
        self.assertRecordValues(inv_line.move_id, [{
            'payment_state': 'partial',
            'amount_residual': 2400.0,
        }])
        self.assertRecordValues(inv_line.matched_credit_ids.exchange_move_id.line_ids, [
            # pylint: disable=C0326
            {'account_id': inv_line.account_id.id,                      'amount_currency': 0.0,         'currency_id': self.currency_data_2['currency'].id, 'balance': 400.0,   'reconciled': True},
            {'account_id': income_exchange_account.id,                  'amount_currency': 0.0,         'currency_id': self.currency_data_2['currency'].id, 'balance': -400.0,  'reconciled': False},
        ])

    def test_validation_new_aml_multi_currencies(self):
        # 6300.0 curr2 == 1800.0 comp_curr (bank rate 3.5:1 instead of the odoo rate 4:1)
        st_line = self._create_st_line(
            1800.0,
            date='2017-01-01',
            foreign_currency_id=self.currency_data_2['currency'].id,
            amount_currency=6300.0,
        )
        # 21600.0 curr3 == 1800.0 comp_curr (rate 12:1)
        inv_line = self._create_invoice_line(
            'out_invoice',
            currency_id=self.currency_data_3['currency'].id,
            invoice_date='2016-01-01',
            invoice_line_ids=[{'price_unit': 21600.0}],
        )

        wizard = self.env['bank.rec.widget'].with_context(default_st_line_id=st_line.id).new({})
        wizard._action_add_new_amls(inv_line)
        self.assertRecordValues(wizard.line_ids, [
            # pylint: disable=C0326
            {'flag': 'liquidity',   'amount_currency': 1800.0,      'currency_id': self.company_data['currency'].id,    'balance': 1800.0},
            {'flag': 'new_aml',     'amount_currency': -21600.0,    'currency_id': self.currency_data_3['currency'].id, 'balance': -1800.0},
        ])
        self.assertRecordValues(wizard, [{'state': 'valid'}])

        # The amount is the same, no message under the 'amount' field.
        self.assert_form_extra_text_value(wizard, False)

        wizard._action_validate()
        self.assertRecordValues(st_line.line_ids, [
            # pylint: disable=C0326
            {'account_id': st_line.journal_id.default_account_id.id,    'amount_currency': 1800.0,      'currency_id': self.company_data['currency'].id,    'balance': 1800.0,  'reconciled': False},
            {'account_id': inv_line.account_id.id,                      'amount_currency': -21600.0,    'currency_id': self.currency_data_3['currency'].id, 'balance': -1800.0, 'reconciled': True},
        ])
        self.assertRecordValues(st_line, [{'is_reconciled': True}])
        self.assertRecordValues(inv_line.move_id, [{'payment_state': 'paid'}])

        # Reset the wizard.
        wizard._js_action_reset()
        self.assertRecordValues(wizard.line_ids, [
            # pylint: disable=C0326
            {'flag': 'liquidity',       'amount_currency': 1800.0,      'currency_id': self.company_data['currency'].id,    'balance': 1800.0},
            {'flag': 'auto_balance',    'amount_currency': -6300.0,     'currency_id': self.currency_data_2['currency'].id, 'balance': -1800.0},
        ])

        # Create the same invoice with a higher amount to check the partial flow.
        # 32400.0 curr3 == 2700.0 comp_curr (rate 12:1)
        inv_line = self._create_invoice_line(
            'out_invoice',
            currency_id=self.currency_data_3['currency'].id,
            invoice_date='2016-01-01',
            invoice_line_ids=[{'price_unit': 32400.0}],
        )
        wizard._action_add_new_amls(inv_line)
        self.assertRecordValues(wizard.line_ids, [
            # pylint: disable=C0326
            {'flag': 'liquidity',   'amount_currency': 1800.0,      'currency_id': self.company_data['currency'].id,    'balance': 1800.0},
            {'flag': 'new_aml',     'amount_currency': -21600.0,    'currency_id': self.currency_data_3['currency'].id, 'balance': -1800.0},
        ])

        # Check the message under the 'amount' field.
        line = wizard.line_ids.filtered(lambda x: x.flag == 'new_aml')
        wizard._js_action_mount_line_in_edit(line.index)
        self.assert_form_extra_text_value(
            wizard,
            r".+open amount of 32,400.000.+ reduced by 21,600.000.+ set the invoice as fully paid .",
        )
        self.assertRecordValues(line, [{
            'suggestion_amount_currency': -32400.0,
            'suggestion_balance': -2700.0,
        }])

        # Switch to a full reconciliation.
        wizard._js_action_apply_line_suggestion(line.index)
        self.assertRecordValues(wizard.line_ids, [
            # pylint: disable=C0326
            {'flag': 'liquidity',       'amount_currency': 1800.0,      'currency_id': self.company_data['currency'].id,    'balance': 1800.0},
            {'flag': 'new_aml',         'amount_currency': -32400.0,    'currency_id': self.currency_data_3['currency'].id, 'balance': -2700.0},
            {'flag': 'auto_balance',    'amount_currency': 3150.0,      'currency_id': self.currency_data_2['currency'].id, 'balance': 900.0},
        ])

        # Check the message under the 'amount' field.
        line = wizard.line_ids.filtered(lambda x: x.flag == 'new_aml')
        wizard._js_action_mount_line_in_edit(line.index)
        self.assert_form_extra_text_value(
            wizard,
            r".+open amount of 32,400.000.+ paid .+ record a partial payment .",
        )
        self.assertRecordValues(line, [{
            'suggestion_amount_currency': -21600.0,
            'suggestion_balance': -1800.0,
        }])

        # Switch back to a partial reconciliation.
        wizard._js_action_apply_line_suggestion(line.index)
        self.assertRecordValues(wizard, [{'state': 'valid'}])

        # Reconcile
        wizard._action_validate()
        self.assertRecordValues(st_line.line_ids, [
            # pylint: disable=C0326
            {'account_id': st_line.journal_id.default_account_id.id,    'amount_currency': 1800.0,      'currency_id': self.company_data['currency'].id,    'balance': 1800.0,  'reconciled': False},
            {'account_id': inv_line.account_id.id,                      'amount_currency': -21600.0,    'currency_id': self.currency_data_3['currency'].id, 'balance': -1800.0, 'reconciled': True},
        ])
        self.assertRecordValues(st_line, [{'is_reconciled': True}])
        self.assertRecordValues(inv_line.move_id, [{
            'payment_state': 'partial',
            'amount_residual': 10800.0,
        }])

    def test_validation_new_aml_multi_currencies_exchange_diff_custom_rates(self):
        self.company_data['default_journal_bank'].currency_id = self.currency_data['currency']

        self.env['res.currency.rate'].create([
            {
                'name': '2017-02-01',
                'rate': 1.0683,
                'currency_id': self.currency_data['currency'].id,
                'company_id': self.env.company.id,
            },
            {
                'name': '2017-03-01',
                'rate': 1.0812,
                'currency_id': self.currency_data['currency'].id,
                'company_id': self.env.company.id,
            },
        ])

        # 960.14 curr1 = 888.03 comp_curr
        st_line = self._create_st_line(
            -960.14,
            date='2017-03-01',
        )
        # 112.7 curr1 == 105.49 comp_curr
        inv_line1 = self._create_invoice_line(
            'in_invoice',
            currency_id=self.currency_data['currency'].id,
            invoice_date='2017-02-01',
            invoice_line_ids=[{'price_unit': 112.7}],
        )
        # 847.44 curr1 == 793.26 comp_curr
        inv_line2 = self._create_invoice_line(
            'in_invoice',
            currency_id=self.currency_data['currency'].id,
            invoice_date='2017-02-01',
            invoice_line_ids=[{'price_unit': 847.44}],
        )

        wizard = self.env['bank.rec.widget'].with_context(default_st_line_id=st_line.id).new({})
        wizard._action_add_new_amls(inv_line1)
        wizard._action_add_new_amls(inv_line2)

        self.assertRecordValues(wizard.line_ids, [
            # pylint: disable=C0326
            {'flag': 'liquidity',       'amount_currency': -960.14,     'balance': -888.03},
            {'flag': 'new_aml',         'amount_currency': 112.7,       'balance': 105.49},
            {'flag': 'exchange_diff',   'amount_currency': 0.0,         'balance': -1.25},
            {'flag': 'new_aml',         'amount_currency': 847.44,      'balance': 793.26},
            {'flag': 'exchange_diff',   'amount_currency': 0.0,         'balance': -9.47},
        ])
        wizard._action_remove_new_amls(inv_line1 + inv_line2)
        wizard._action_add_new_amls(inv_line2)
        wizard._action_add_new_amls(inv_line1)

        self.assertRecordValues(wizard.line_ids, [
            # pylint: disable=C0326
            {'flag': 'liquidity',       'amount_currency': -960.14,     'balance': -888.03},
            {'flag': 'new_aml',         'amount_currency': 847.44,      'balance': 793.26},
            {'flag': 'exchange_diff',   'amount_currency': 0.0,         'balance': -9.47},
            {'flag': 'new_aml',         'amount_currency': 112.7,       'balance': 105.49},
            {'flag': 'exchange_diff',   'amount_currency': 0.0,         'balance': -1.25},
        ])

    def test_validation_with_partner(self):
        partner = self.partner_a.copy()

        st_line = self._create_st_line(1000.0, partner_id=self.partner_a.id)

        # The wizard can be validated directly thanks to the receivable account set on the partner.
        wizard = self.env['bank.rec.widget'].with_context(default_st_line_id=st_line.id).new({})
        self.assertRecordValues(wizard, [{'state': 'valid'}])

        # Validate and check the statement line.
        wizard._action_validate()
        self.assertRecordValues(st_line, [{'partner_id': self.partner_a.id}])
        liquidity_line, _suspense_line, other_line = st_line._seek_for_lines()
        account = self.partner_a.property_account_receivable_id
        self.assertRecordValues(liquidity_line + other_line, [
            # pylint: disable=C0326
            {'account_id': liquidity_line.account_id.id,    'balance': 1000.0},
            {'account_id': account.id,                      'balance': -1000.0},
        ])
        self.assertRecordValues(wizard, [{'state': 'reconciled'}])

        # Match an invoice with a different partner.
        wizard._js_action_reset()
        inv_line = self._create_invoice_line(
            'out_invoice',
            partner_id=partner.id,
            invoice_line_ids=[{'price_unit': 1000.0}],
        )
        wizard._action_add_new_amls(inv_line)
        wizard._action_validate()
        liquidity_line, suspense_line, other_line = st_line._seek_for_lines()
        self.assertRecordValues(st_line, [{'partner_id': partner.id}])
        self.assertRecordValues(st_line.move_id, [{'partner_id': partner.id}])
        self.assertRecordValues(liquidity_line + other_line, [
            # pylint: disable=C0326
            {'account_id': liquidity_line.account_id.id,    'partner_id': partner.id,   'balance': 1000.0},
            {'account_id': inv_line.account_id.id,          'partner_id': partner.id,   'balance': -1000.0},
        ])
        self.assertRecordValues(wizard, [{'state': 'reconciled'}])

        # Reset the wizard and match invoices with different partners.
        wizard._js_action_reset()
        partner1 = self.partner_a.copy()
        inv_line1 = self._create_invoice_line(
            'out_invoice',
            partner_id=partner1.id,
            invoice_line_ids=[{'price_unit': 300.0}],
        )
        partner2 = self.partner_a.copy()
        inv_line2 = self._create_invoice_line(
            'out_invoice',
            partner_id=partner2.id,
            invoice_line_ids=[{'price_unit': 300.0}],
        )
        wizard._action_add_new_amls(inv_line1 + inv_line2)
        wizard._action_validate()
        liquidity_line, _suspense_line, other_line = st_line._seek_for_lines()
        self.assertRecordValues(st_line, [{'partner_id': False}])
        self.assertRecordValues(st_line.move_id, [{'partner_id': False}])
        self.assertRecordValues(liquidity_line + other_line, [
            # pylint: disable=C0326
            {'account_id': liquidity_line.account_id.id,    'partner_id': False,        'balance': 1000.0},
            {'account_id': inv_line1.account_id.id,         'partner_id': partner1.id,  'balance': -300.0},
            {'account_id': inv_line2.account_id.id,         'partner_id': partner2.id,  'balance': -300.0},
            {'account_id': account.id,                      'partner_id': False,        'balance': -400.0},
        ])
        self.assertRecordValues(wizard, [{'state': 'reconciled'}])

        # Clear the accounts set on the partner and reset the widget.
        # The wizard should be invalid since we are not able to set an open balance.
        partner.property_account_receivable_id = None
        wizard._js_action_reset()
        liquidity_line, suspense_line, other_line = st_line._seek_for_lines()
        self.assertRecordValues(wizard.line_ids, [
            # pylint: disable=C0326
            {'flag': 'liquidity',       'account_id': liquidity_line.account_id.id},
            {'flag': 'auto_balance',    'account_id': suspense_line.account_id.id},
        ])
        self.assertRecordValues(wizard, [{'state': 'invalid'}])

    def test_partner_receivable_payable_account(self):
        self.partner_a.write({'customer_rank': 1, 'supplier_rank': 0})  # always receivable
        self.partner_b.write({'customer_rank': 0, 'supplier_rank': 1})  # always payable
        partner_c = self.partner_b.copy({'customer_rank': 3, 'supplier_rank': 2})  # no preference

        positive_st_line = self._create_st_line(1000)
        journal_account = positive_st_line.journal_id.default_account_id

        wizard = self.env['bank.rec.widget'].with_context(default_st_line_id=positive_st_line.id).new({})
        suspense_line = wizard.line_ids.filtered(lambda l: l.flag != "liquidity")
        wizard._js_action_mount_line_in_edit(suspense_line.index)

        suspense_line.partner_id = self.partner_a
        wizard._line_value_changed_partner_id(suspense_line)
        self.assertRecordValues(wizard.line_ids, [
            # pylint: disable=C0326
            {'partner_id': False,             'account_id': journal_account.id},
            {'partner_id': self.partner_a.id, 'account_id': self.partner_a.property_account_receivable_id.id},
        ])

        suspense_line.partner_id = self.partner_b
        wizard._line_value_changed_partner_id(suspense_line)
        self.assertRecordValues(wizard.line_ids, [
            # pylint: disable=C0326
            {'partner_id': False,             'account_id': journal_account.id},
            {'partner_id': self.partner_b.id, 'account_id': self.partner_b.property_account_payable_id.id},
        ])

        suspense_line.partner_id = partner_c
        wizard._line_value_changed_partner_id(suspense_line)
        self.assertRecordValues(wizard.line_ids, [
            # pylint: disable=C0326
            {'partner_id': False,             'account_id': journal_account.id},
            {'partner_id': partner_c.id,      'account_id': partner_c.property_account_receivable_id.id},
        ])

        negative_st_line = self._create_st_line(-1000)
        wizard = self.env['bank.rec.widget'].with_context(default_st_line_id=negative_st_line.id).new({})
        suspense_line = wizard.line_ids.filtered(lambda l: l.flag != "liquidity")
        wizard._js_action_mount_line_in_edit(suspense_line.index)

        suspense_line.partner_id = self.partner_a
        wizard._line_value_changed_partner_id(suspense_line)
        self.assertRecordValues(wizard.line_ids, [
            # pylint: disable=C0326
            {'partner_id': False,             'account_id': journal_account.id},
            {'partner_id': self.partner_a.id, 'account_id': self.partner_a.property_account_receivable_id.id},
        ])

        suspense_line.partner_id = self.partner_b
        wizard._line_value_changed_partner_id(suspense_line)
        self.assertRecordValues(wizard.line_ids, [
            # pylint: disable=C0326
            {'partner_id': False,             'account_id': journal_account.id},
            {'partner_id': self.partner_b.id, 'account_id': self.partner_b.property_account_payable_id.id},
        ])

        suspense_line.partner_id = partner_c
        wizard._line_value_changed_partner_id(suspense_line)
        self.assertRecordValues(wizard.line_ids, [
            # pylint: disable=C0326
            {'partner_id': False,             'account_id': journal_account.id},
            {'partner_id': partner_c.id,      'account_id': partner_c.property_account_payable_id.id},
        ])

    def test_validation_using_custom_account(self):
        st_line = self._create_st_line(1000.0)

        # By default, the wizard can't be validated directly due to the suspense account.
        wizard = self.env['bank.rec.widget'].with_context(default_st_line_id=st_line.id).new({})
        self.assertRecordValues(wizard, [{'state': 'invalid'}])

        # Mount the auto-balance line in edit mode.
        line = wizard.line_ids.filtered(lambda x: x.flag == 'auto_balance')
        wizard._js_action_mount_line_in_edit(line.index)
        liquidity_line, suspense_line, _other_lines = st_line._seek_for_lines()
        self.assertRecordValues(line, [{
            'account_id': suspense_line.account_id.id,
            'balance': -1000.0,
        }])

        # Switch to a custom account.
        account = self.env['account.account'].create({
            'name': "test_validation_using_custom_account",
            'code': "424242",
            'account_type': "asset_current",
        })
        line.account_id = account
        wizard._line_value_changed_account_id(line)
        self.assertRecordValues(wizard.line_ids, [
            # pylint: disable=C0326
            {'flag': 'liquidity',   'account_id': liquidity_line.account_id.id, 'balance': 1000.0},
            {'flag': 'manual',      'account_id': account.id,                   'balance': -1000.0},
        ])

        # The wizard can be validated.
        self.assertRecordValues(wizard, [{'state': 'valid'}])

        # Validate and check the statement line.
        wizard._action_validate()
        liquidity_line, _suspense_line, other_line = st_line._seek_for_lines()
        self.assertRecordValues(liquidity_line + other_line, [
            # pylint: disable=C0326
            {'account_id': liquidity_line.account_id.id,    'balance': 1000.0},
            {'account_id': account.id,                      'balance': -1000.0},
        ])
        self.assertRecordValues(wizard, [{'state': 'reconciled'}])

    def test_validation_with_taxes(self):
        st_line = self._create_st_line(1000.0)

        tax_tags = self.env['account.account.tag'].create({
            'name': f'tax_tag_{i}',
            'applicability': 'taxes',
            'country_id': self.env.company.account_fiscal_country_id.id,
        } for i in range(4))

        tax_21 = self.env['account.tax'].create({
            'name': "tax_21",
            'amount': 21,
            'invoice_repartition_line_ids': [
                Command.create({
                    'factor_percent': 100,
                    'repartition_type': 'base',
                    'tag_ids': [Command.set(tax_tags[0].ids)],
                }),
                Command.create({
                    'factor_percent': 100,
                    'repartition_type': 'tax',
                    'tag_ids': [Command.set(tax_tags[1].ids)],
                }),
            ],
            'refund_repartition_line_ids': [
                Command.create({
                    'factor_percent': 100,
                    'repartition_type': 'base',
                    'tag_ids': [Command.set(tax_tags[2].ids)],
                }),
                Command.create({
                    'factor_percent': 100,
                    'repartition_type': 'tax',
                    'tag_ids': [Command.set(tax_tags[3].ids)],
                }),
            ],
        })

        wizard = self.env['bank.rec.widget'].with_context(default_st_line_id=st_line.id).new({})
        line = wizard.line_ids.filtered(lambda x: x.flag == 'auto_balance')
        wizard._js_action_mount_line_in_edit(line.index)
        line.tax_ids = [Command.link(tax_21.id)]
        wizard._line_value_changed_tax_ids(line)

        self.assertRecordValues(wizard.line_ids, [
            # pylint: disable=C0326
            {'flag': 'liquidity',   'balance': 1000.0,  'tax_tag_ids': []},
            {'flag': 'manual',      'balance': -826.45, 'tax_tag_ids': tax_tags[0].ids},
            {'flag': 'tax_line',    'balance': -173.55, 'tax_tag_ids': tax_tags[1].ids},
        ])

        # Edit the base line. The tax tags should be the refund ones.
        line = wizard.line_ids.filtered(lambda x: x.flag == 'manual')
        wizard._js_action_mount_line_in_edit(line.index)
        line.balance = 500.0
        wizard._line_value_changed_balance(line)

        self.assertRecordValues(wizard.line_ids, [
            # pylint: disable=C0326
            {'flag': 'liquidity',       'balance': 1000.0,      'tax_tag_ids': []},
            {'flag': 'manual',          'balance': 500.0,       'tax_tag_ids': tax_tags[2].ids},
            {'flag': 'tax_line',        'balance': 105.0,       'tax_tag_ids': tax_tags[3].ids},
            {'flag': 'auto_balance',    'balance': -1605.0,     'tax_tag_ids': []},
        ])

        # Edit the base line.
        line = wizard.line_ids.filtered(lambda x: x.flag == 'manual')
        wizard._js_action_mount_line_in_edit(line.index)
        line.balance = -500.0
        wizard._line_value_changed_balance(line)

        self.assertRecordValues(wizard.line_ids, [
            # pylint: disable=C0326
            {'flag': 'liquidity',       'balance': 1000.0,  'tax_tag_ids': []},
            {'flag': 'manual',          'balance': -500.0,  'tax_tag_ids': tax_tags[0].ids},
            {'flag': 'tax_line',        'balance': -105.0,  'tax_tag_ids': tax_tags[1].ids},
            {'flag': 'auto_balance',    'balance': -395.0,  'tax_tag_ids': []},
        ])

        # Edit the tax line.
        line = wizard.line_ids.filtered(lambda x: x.flag == 'tax_line')
        wizard._js_action_mount_line_in_edit(line.index)
        line.balance = -100.0
        wizard._line_value_changed_balance(line)

        self.assertRecordValues(wizard.line_ids, [
            # pylint: disable=C0326
            {'flag': 'liquidity',       'balance': 1000.0,  'tax_tag_ids': []},
            {'flag': 'manual',          'balance': -500.0,  'tax_tag_ids': tax_tags[0].ids},
            {'flag': 'tax_line',        'balance': -100.0,  'tax_tag_ids': tax_tags[1].ids},
            {'flag': 'auto_balance',    'balance': -400.0,  'tax_tag_ids': []},
        ])

        # Add a new tax.
        tax_10 = self.env['account.tax'].create({
            'name': "tax_10",
            'amount': 10,
        })

        line = wizard.line_ids.filtered(lambda x: x.flag == 'manual')
        wizard._js_action_mount_line_in_edit(line.index)
        line.tax_ids = [Command.link(tax_10.id)]
        wizard._line_value_changed_tax_ids(line)

        self.assertRecordValues(wizard.line_ids, [
            # pylint: disable=C0326
            {'flag': 'liquidity',       'balance': 1000.0},
            {'flag': 'manual',          'balance': -500.0},
            {'flag': 'tax_line',        'balance': -105.0},
            {'flag': 'tax_line',        'balance': -50.0},
            {'flag': 'auto_balance',    'balance': -345.0},
        ])

        # Remove the taxes.
        line = wizard.line_ids.filtered(lambda x: x.flag == 'manual')
        wizard._js_action_mount_line_in_edit(line.index)
        line.tax_ids = [Command.clear()]
        wizard._line_value_changed_tax_ids(line)

        self.assertRecordValues(wizard.line_ids, [
            # pylint: disable=C0326
            {'flag': 'liquidity',       'balance': 1000.0},
            {'flag': 'manual',          'balance': -500.0},
            {'flag': 'auto_balance',    'balance': -500.0},
        ])

        # Reset the amount.
        line = wizard.line_ids.filtered(lambda x: x.flag == 'manual')
        wizard._js_action_mount_line_in_edit(line.index)
        line.balance = -1000.0
        wizard._line_value_changed_balance(line)

        self.assertRecordValues(wizard.line_ids, [
            # pylint: disable=C0326
            {'flag': 'liquidity',       'balance': 1000.0},
            {'flag': 'manual',          'balance': -1000.0},
        ])

        # Add taxes. We should be back into the "price included taxes" mode.
        line = wizard.line_ids.filtered(lambda x: x.flag == 'manual')
        wizard._js_action_mount_line_in_edit(line.index)
        line.tax_ids = [Command.link(tax_21.id)]
        wizard._line_value_changed_tax_ids(line)

        self.assertRecordValues(wizard.line_ids, [
            # pylint: disable=C0326
            {'flag': 'liquidity',   'balance': 1000.0},
            {'flag': 'manual',      'balance': -826.45},
            {'flag': 'tax_line',    'balance': -173.55},
        ])

        line = wizard.line_ids.filtered(lambda x: x.flag == 'manual')
        wizard._js_action_mount_line_in_edit(line.index)
        line.tax_ids = [Command.link(tax_10.id)]
        wizard._line_value_changed_tax_ids(line)

        self.assertRecordValues(wizard.line_ids, [
            # pylint: disable=C0326
            {'flag': 'liquidity',   'balance': 1000.0},
            {'flag': 'manual',      'balance': -763.36},
            {'flag': 'tax_line',    'balance': -160.31},
            {'flag': 'tax_line',    'balance': -76.33},
        ])

        # Changing the account should recompute the taxes but preserve the "price included taxes" mode.
        line = wizard.line_ids.filtered(lambda x: x.flag == 'manual')
        wizard._js_action_mount_line_in_edit(line.index)
        line.account_id = self.account_revenue1
        wizard._line_value_changed_account_id(line)

        self.assertRecordValues(wizard.line_ids, [
            # pylint: disable=C0326
            {'flag': 'liquidity',   'balance': 1000.0},
            {'flag': 'manual',      'balance': -763.36},
            {'flag': 'tax_line',    'balance': -160.31},
            {'flag': 'tax_line',    'balance': -76.33},
        ])

        # The wizard can be validated.
        self.assertRecordValues(wizard, [{'state': 'valid'}])

        # Validate and check the statement line.
        wizard._action_validate()
        self.assertRecordValues(st_line.line_ids, [
            # pylint: disable=C0326
            {'balance': 1000.0},
            {'balance': -763.36},
            {'balance': -160.31},
            {'balance': -76.33},
        ])
        self.assertRecordValues(wizard, [{'state': 'reconciled'}])

    def test_validation_caba_tax_account(self):
        """ Cash basis taxes usually put their tax lines on a transition account, and the cash basis entries then move those amounts
        to the regular tax accounts. When using a cash basis tax in the bank reconciliation widget, their won't be any cash basis
        entry and the lines will directly be exigible, so we want to use the final tax account directly.
        """
        tax_account = self.company_data['default_account_tax_sale']

        caba_tax = self.env['account.tax'].create({
            'name': "CABA",
            'amount_type': 'percent',
            'amount': 20.0,
            'tax_exigibility': 'on_payment',
            'cash_basis_transition_account_id': self.safe_copy(tax_account).id,
            'invoice_repartition_line_ids': [
                (0, 0, {
                    'repartition_type': 'base',
                }),
                (0, 0, {
                    'repartition_type': 'tax',
                    'account_id': tax_account.id,
                }),
            ],
            'refund_repartition_line_ids': [
                (0, 0, {
                    'repartition_type': 'base',
                }),
                (0, 0, {
                    'repartition_type': 'tax',
                    'account_id': tax_account.id,
                }),
            ],
        })

        st_line = self._create_st_line(120.0)

        wizard = self.env['bank.rec.widget'].with_context(default_st_line_id=st_line.id).new({})
        line = wizard.line_ids.filtered(lambda x: x.flag == 'auto_balance')
        wizard._js_action_mount_line_in_edit(line.index)
        line.account_id = self.account_revenue1
        line.tax_ids = [Command.link(caba_tax.id)]
        wizard._line_value_changed_tax_ids(line)

        self.assertRecordValues(wizard.line_ids, [
            # pylint: disable=C0326
            {'flag': 'liquidity',   'balance': 120.0,  'account_id': st_line.journal_id.default_account_id.id},
            {'flag': 'manual',      'balance': -100.0, 'account_id': self.account_revenue1.id},
            {'flag': 'tax_line',    'balance': -20.0,  'account_id': tax_account.id},
        ])

        self.assertRecordValues(wizard, [{'state': 'valid'}])

        wizard._action_validate()
        self.assertRecordValues(st_line.line_ids, [
            # pylint: disable=C0326
            {'balance': 120.0,  'tax_ids': [],           'tax_line_id': False,       'account_id': st_line.journal_id.default_account_id.id},
            {'balance': -100.0, 'tax_ids': caba_tax.ids, 'tax_line_id': False,       'account_id': self.account_revenue1.id},
            {'balance': -20.0,  'tax_ids': [],           'tax_line_id': caba_tax.id, 'account_id': tax_account.id},
        ])
        self.assertRecordValues(wizard, [{'state': 'reconciled'}])

    def test_validation_changed_default_account(self):
        st_line = self._create_st_line(100.0, partner_id=self.partner_a.id)
        original_journal_account_id = st_line.journal_id.default_account_id
        # Change the default account of the journal (exceptional case)
        st_line.journal_id.default_account_id = self.company_data['default_journal_cash'].default_account_id
        wizard = self.env['bank.rec.widget'].with_context(default_st_line_id=st_line.id).new({})
        self.assertRecordValues(wizard, [{'state': 'valid'}])
        # Validate and check the statement line.
        wizard._action_validate()
        liquidity_line, _suspense_line, _other_line = st_line._seek_for_lines()
        self.assertRecordValues(liquidity_line, [
            {'account_id': original_journal_account_id.id, 'balance': 100.0},
        ])
        self.assertRecordValues(wizard, [{'state': 'reconciled'}])

    def test_apply_taxes_with_reco_model(self):
        st_line = self._create_st_line(1000.0)

        tax_21 = self.env['account.tax'].create({
            'name': "tax_21",
            'amount': 21,
        })

        reco_model = self.env['account.reconcile.model'].create({
            'name': "test_apply_taxes_with_reco_model",
            'rule_type': 'writeoff_button',
            'line_ids': [Command.create({
                'account_id': self.account_revenue1.id,
                'tax_ids': [Command.set(tax_21.ids)],
            })],
        })

        wizard = self.env['bank.rec.widget'].with_context(default_st_line_id=st_line.id).new({})
        wizard._action_select_reconcile_model(reco_model)

        self.assertRecordValues(wizard.line_ids, [
            # pylint: disable=C0326
            {'flag': 'liquidity',   'balance': 1000.0},
            {'flag': 'manual',      'balance': -826.45},
            {'flag': 'tax_line',    'balance': -173.55},
        ])

    def test_manual_edits_not_replaced(self):
        """ 2 partial payments should keep the edited balance """
        st_line = self._create_st_line(
            1200.0,
            date='2017-02-01',
        )
        inv_line_1 = self._create_invoice_line(
            'out_invoice',
            invoice_date='2016-01-01',
            invoice_line_ids=[{'price_unit': 3000.0}],
        )
        inv_line_2 = self._create_invoice_line(
            'out_invoice',
            invoice_date='2017-01-01',
            invoice_line_ids=[{'price_unit': 4000.0}],
        )

        wizard = self.env['bank.rec.widget'].with_context(default_st_line_id=st_line.id).new({})
        wizard._action_add_new_amls(inv_line_1)
        self.assertRecordValues(wizard.line_ids, [
            # pylint: disable=C0326
            {'flag': 'liquidity',    'balance': 1200.0},
            {'flag': 'new_aml',      'balance':-1200.0},
        ])

        line = wizard.line_ids.filtered(lambda x: x.flag == 'new_aml')
        wizard._js_action_mount_line_in_edit(line.index)
        line.balance = -600.0
        wizard._line_value_changed_balance(line)

        self.assertRecordValues(wizard.line_ids, [
            # pylint: disable=C0326
            {'flag': 'liquidity',    'balance': 1200.0},
            {'flag': 'new_aml',      'balance': -600.0},
            {'flag': 'auto_balance', 'balance': -600.0},
        ])

        wizard._action_add_new_amls(inv_line_2)

        self.assertRecordValues(wizard.line_ids, [
            # pylint: disable=C0326
            {'flag': 'liquidity',    'balance': 1200.0},
            {'flag': 'new_aml',      'balance': -600.0},
            {'flag': 'new_aml',      'balance': -600.0},
        ])

    def test_manual_edits_not_replaced_multicurrency(self):
        """ 2 partial payments should keep the edited amount_currency """
        st_line = self._create_st_line(
            1200.0,
            date='2018-01-01',
            foreign_currency_id=self.currency_data_2['currency'].id,
            amount_currency=6000.0,  # rate 5:1
        )

        inv_line_1 = self._create_invoice_line(
            'out_invoice',
            invoice_date='2016-01-01',
            currency_id=self.currency_data_2['currency'].id,
            invoice_line_ids=[{'price_unit': 6000.0}],  # 1000 company curr (rate 6:1)
        )
        inv_line_2 = self._create_invoice_line(
            'out_invoice',
            invoice_date='2017-01-01',
            currency_id=self.currency_data_2['currency'].id,
            invoice_line_ids=[{'price_unit': 4000.0}], # 1000 company curr (rate 4:1)
        )

        wizard = self.env['bank.rec.widget'].with_context(default_st_line_id=st_line.id).new({})
        wizard._action_add_new_amls(inv_line_1)
        self.assertRecordValues(wizard.line_ids, [
            # pylint: disable=C0326
            {'flag': 'liquidity',     'amount_currency': 1200.0, 'balance': 1200.0},
            {'flag': 'new_aml',       'amount_currency':-6000.0, 'balance':-1000.0},
            {'flag': 'exchange_diff', 'amount_currency':    0.0, 'balance': -200.0},
        ])

        line = wizard.line_ids.filtered(lambda x: x.flag == 'new_aml')
        wizard._js_action_mount_line_in_edit(line.index)
        line.amount_currency = -3000.0
        wizard._line_value_changed_amount_currency(line)

        self.assertRecordValues(wizard.line_ids, [
            # pylint: disable=C0326
            {'flag': 'liquidity',     'amount_currency': 1200.0, 'balance': 1200.0},
            {'flag': 'new_aml',       'amount_currency':-3000.0, 'balance': -500.0},
            {'flag': 'exchange_diff', 'amount_currency':    0.0, 'balance': -100.0},
            {'flag': 'auto_balance',  'amount_currency':-3000.0, 'balance': -600.0},
        ])

        wizard._action_add_new_amls(inv_line_2)

        self.assertRecordValues(wizard.line_ids, [
            # pylint: disable=C0326
            {'flag': 'liquidity',     'amount_currency': 1200.0, 'balance': 1200.0},
            {'flag': 'new_aml',       'amount_currency':-3000.0, 'balance': -500.0},
            {'flag': 'exchange_diff', 'amount_currency':    0.0, 'balance': -100.0},
            {'flag': 'new_aml',       'amount_currency':-3000.0, 'balance': -750.0},
            {'flag': 'exchange_diff', 'amount_currency':    0.0, 'balance':  150.0},
        ])

    def test_creating_manual_line_multi_currencies(self):
        # 6300.0 curr2 == 1800.0 comp_curr (bank rate 3.5:1 instead of the odoo rate 4:1)
        st_line = self._create_st_line(
            1800.0,
            date='2017-01-01',
            foreign_currency_id=self.currency_data_2['currency'].id,
            amount_currency=6300.0,
        )

        wizard = self.env['bank.rec.widget'].with_context(default_st_line_id=st_line.id).new({})
        self.assertRecordValues(wizard.line_ids, [
            # pylint: disable=C0326
            {'flag': 'liquidity',       'amount_currency': 1800.0,  'currency_id': self.company_data['currency'].id,    'balance': 1800.0},
            {'flag': 'auto_balance',    'amount_currency': -6300.0, 'currency_id': self.currency_data_2['currency'].id, 'balance': -1800.0},
        ])

        # Custom balance.
        line = wizard.line_ids.filtered(lambda x: x.flag == 'auto_balance')
        wizard._js_action_mount_line_in_edit(line.index)
        line.balance = -1500.0
        wizard._line_value_changed_balance(line)
        self.assertRecordValues(wizard.line_ids, [
            # pylint: disable=C0326
            {'flag': 'liquidity',       'amount_currency': 1800.0,  'currency_id': self.company_data['currency'].id,    'balance': 1800.0},
            {'flag': 'manual',          'amount_currency': -6300.0, 'currency_id': self.currency_data_2['currency'].id, 'balance': -1500.0},
            {'flag': 'auto_balance',    'amount_currency': 0.0,     'currency_id': self.currency_data_2['currency'].id, 'balance': -300.0},
        ])

        # Custom amount_currency.
        line = wizard.line_ids.filtered(lambda x: x.flag == 'manual')
        wizard._js_action_mount_line_in_edit(line.index)
        line.amount_currency = -4200.0
        wizard._line_value_changed_amount_currency(line)
        self.assertRecordValues(wizard.line_ids, [
            # pylint: disable=C0326
            {'flag': 'liquidity',       'amount_currency': 1800.0,  'currency_id': self.company_data['currency'].id,    'balance': 1800.0},
            {'flag': 'manual',          'amount_currency': -4200.0, 'currency_id': self.currency_data_2['currency'].id, 'balance': -1200.0},
            {'flag': 'auto_balance',    'amount_currency': -2100.0, 'currency_id': self.currency_data_2['currency'].id, 'balance': -600.0},
        ])

        # Custom currency_id.
        line = wizard.line_ids.filtered(lambda x: x.flag == 'manual')
        wizard._js_action_mount_line_in_edit(line.index)
        line.currency_id = self.currency_data['currency']
        wizard._line_value_changed_currency_id(line)
        self.assertRecordValues(wizard.line_ids, [
            # pylint: disable=C0326
            {'flag': 'liquidity',       'amount_currency': 1800.0,  'currency_id': self.company_data['currency'].id,    'balance': 1800.0},
            {'flag': 'manual',          'amount_currency': -4200.0, 'currency_id': self.currency_data['currency'].id,   'balance': -2100.0},
            {'flag': 'auto_balance',    'amount_currency': 1050.0,  'currency_id': self.currency_data_2['currency'].id, 'balance': 300.0},
        ])

        # Custom balance.
        line = wizard.line_ids.filtered(lambda x: x.flag == 'manual')
        wizard._js_action_mount_line_in_edit(line.index)
        line.balance = -1800.0
        wizard._line_value_changed_balance(line)
        self.assertRecordValues(wizard.line_ids, [
            # pylint: disable=C0326
            {'flag': 'liquidity',       'amount_currency': 1800.0,  'currency_id': self.company_data['currency'].id,    'balance': 1800.0},
            {'flag': 'manual',          'amount_currency': -4200.0, 'currency_id': self.currency_data['currency'].id,   'balance': -1800.0},
        ])

    def test_auto_reconcile_cron(self):
        self.env['account.reconcile.model'].search([('company_id', '=', self.company_data['company'].id)]).unlink()
        cron = self.env.ref('account_accountant.auto_reconcile_bank_statement_line')
        self.env['ir.cron.trigger'].search([('cron_id', '=', cron.id)]).unlink()

        st_line = self._create_st_line(1234.0, partner_id=self.partner_a.id, date='2017-01-01')
        self.assertEqual(len(self.env['ir.cron.trigger'].search([('cron_id', '=', cron.id)])), 1)

        self._create_invoice_line(
            'out_invoice',
            invoice_date='2017-01-01',
            invoice_line_ids=[{'price_unit': 1234.0}],
        )

        rule = self.env['account.reconcile.model'].create({
            'name': "test_auto_reconcile_cron",
            'rule_type': 'writeoff_suggestion',
            'auto_reconcile': False,
            'line_ids': [Command.create({'account_id': self.account_revenue1.id})],
        })

        # The CRON is not doing anything since the model is not auto reconcile.
        with freeze_time('2017-01-01'):
            self.env['account.bank.statement.line']._cron_try_auto_reconcile_statement_lines()
        self.assertRecordValues(st_line, [{'is_reconciled': False, 'cron_last_check': False}])
        self.assertEqual(len(self.env['ir.cron.trigger'].search([('cron_id', '=', cron.id)])), 1)

        rule.auto_reconcile = True

        # The CRON don't consider old statement lines.
        with freeze_time('2017-06-01'):
            self.env['account.bank.statement.line']._cron_try_auto_reconcile_statement_lines()
        self.assertRecordValues(st_line, [{'is_reconciled': False, 'cron_last_check': False}])
        self.assertEqual(len(self.env['ir.cron.trigger'].search([('cron_id', '=', cron.id)])), 1)

        # The CRON will auto-reconcile the line.
        with freeze_time('2017-01-02'):
            self.env['account.bank.statement.line']._cron_try_auto_reconcile_statement_lines()
        self.assertRecordValues(st_line, [{'is_reconciled': True, 'cron_last_check': fields.Datetime.from_string('2017-01-02 00:00:00')}])
        self.assertEqual(len(self.env['ir.cron.trigger'].search([('cron_id', '=', cron.id)])), 1)

        st_line1 = self._create_st_line(1234.0, partner_id=self.partner_a.id, date='2018-01-01')
        self.assertEqual(len(self.env['ir.cron.trigger'].search([('cron_id', '=', cron.id)])), 2)
        self._create_invoice_line(
            'out_invoice',
            invoice_date='2018-01-01',
            invoice_line_ids=[{'price_unit': 1234.0}],
        )
        st_line2 = self._create_st_line(1234.0, partner_id=self.partner_a.id, date='2018-01-01')
        self.assertEqual(len(self.env['ir.cron.trigger'].search([('cron_id', '=', cron.id)])), 3)
        self._create_invoice_line(
            'out_invoice',
            invoice_date='2018-01-01',
            invoice_line_ids=[{'price_unit': 1234.0}],
        )

        # Simulate the cron already tried to process 'st_line1' before.
        with freeze_time('2017-12-31'):
            st_line1.cron_last_check = fields.Datetime.now()

        # The statement line with no 'cron_last_check' must be processed before others.
        with freeze_time('2018-01-02'):
            self.env['account.bank.statement.line']._cron_try_auto_reconcile_statement_lines(batch_size=1)

        self.assertRecordValues(st_line1 + st_line2, [
            {'is_reconciled': False, 'cron_last_check': fields.Datetime.from_string('2017-12-31 00:00:00')},
            {'is_reconciled': True, 'cron_last_check': fields.Datetime.from_string('2018-01-02 00:00:00')},
        ])
        self.assertEqual(len(self.env['ir.cron.trigger'].search([('cron_id', '=', cron.id)])), 4)

        with freeze_time('2018-01-03'):
            self.env['account.bank.statement.line']._cron_try_auto_reconcile_statement_lines(batch_size=1)

        self.assertRecordValues(st_line1, [{'is_reconciled': True, 'cron_last_check': fields.Datetime.from_string('2018-01-03 00:00:00')}])
        self.assertEqual(len(self.env['ir.cron.trigger'].search([('cron_id', '=', cron.id)])), 4)

        st_line3 = self._create_st_line(1234.0, date='2018-01-01')
        self.assertEqual(len(self.env['ir.cron.trigger'].search([('cron_id', '=', cron.id)])), 5)
        self._create_invoice_line(
            'out_invoice',
            invoice_date='2018-01-01',
            invoice_line_ids=[{'price_unit': 1234.0}],
        )
        st_line4 = self._create_st_line(1234.0, date='2018-01-01')
        self.assertEqual(len(self.env['ir.cron.trigger'].search([('cron_id', '=', cron.id)])), 6)
        self._create_invoice_line(
            'out_invoice',
            invoice_date='2018-01-01',
            invoice_line_ids=[{'price_unit': 1234.0}],
        )

        # Make sure the CRON is no longer applicable.
        rule.match_partner = True
        rule.match_partner_ids = [Command.set(self.partner_a.ids)]
        with freeze_time('2018-01-01'):
            self.env['account.bank.statement.line']._cron_try_auto_reconcile_statement_lines(batch_size=1)

        self.assertRecordValues(st_line3 + st_line4, [
            {'is_reconciled': False, 'cron_last_check': fields.Datetime.from_string('2018-01-01 00:00:00')},
            {'is_reconciled': False, 'cron_last_check': False},
        ])
        self.assertEqual(len(self.env['ir.cron.trigger'].search([('cron_id', '=', cron.id)])), 7)

        # Make sure the statement lines are reconciled by the cron in the right order.
        self.assertRecordValues(st_line3 + st_line4, [
            {'is_reconciled': False, 'cron_last_check': fields.Datetime.from_string('2018-01-01 00:00:00')},
            {'is_reconciled': False, 'cron_last_check': False},
        ])

        # st_line4 is processed because cron_last_check is null.
        with freeze_time('2018-01-02'):
            self.env['account.bank.statement.line']._cron_try_auto_reconcile_statement_lines(batch_size=1)

        self.assertRecordValues(st_line3 + st_line4, [
            {'is_reconciled': False, 'cron_last_check': fields.Datetime.from_string('2018-01-01 00:00:00')},
            {'is_reconciled': False, 'cron_last_check': fields.Datetime.from_string('2018-01-02 00:00:00')},
        ])
        self.assertEqual(len(self.env['ir.cron.trigger'].search([('cron_id', '=', cron.id)])), 7)

        # st_line3 is processed because it has the oldest cron_last_check.
        with freeze_time('2018-01-03'):
            self.env['account.bank.statement.line']._cron_try_auto_reconcile_statement_lines(batch_size=1)

        self.assertRecordValues(st_line3 + st_line4, [
            {'is_reconciled': False, 'cron_last_check': fields.Datetime.from_string('2018-01-03 00:00:00')},
            {'is_reconciled': False, 'cron_last_check': fields.Datetime.from_string('2018-01-02 00:00:00')},
        ])
        self.assertEqual(len(self.env['ir.cron.trigger'].search([('cron_id', '=', cron.id)])), 7)

    def test_duplicate_amls_constraint(self):
        st_line = self._create_st_line(1000.0)
        inv_line = self._create_invoice_line(
            'out_invoice',
            invoice_line_ids=[{'price_unit': 1000.0}],
        )

        wizard = self.env['bank.rec.widget'].with_context(default_st_line_id=st_line.id).new({})
        wizard._action_add_new_amls(inv_line)
        self.assertTrue(len(wizard.line_ids), 2)

        wizard._action_add_new_amls(inv_line)
        self.assertTrue(len(wizard.line_ids), 2)

    @freeze_time('2017-01-01')
    def test_reconcile_model_with_payment_tolerance(self):
        self.env['account.reconcile.model'].search([('company_id', '=', self.company_data['company'].id)]).unlink()

        invoice_line = self._create_invoice_line(
            'out_invoice',
            invoice_date='2017-01-01',
            invoice_line_ids=[{'price_unit': 1000.0}],
        )
        st_line = self._create_st_line(998.0, partner_id=self.partner_a.id, date='2017-01-01', payment_ref=invoice_line.move_id.name)

        rule = self.env['account.reconcile.model'].create({
            'name': "test_reconcile_model_with_payment_tolerance",
            'rule_type': 'invoice_matching',
            'allow_payment_tolerance': True,
            'payment_tolerance_type': 'percentage',
            'payment_tolerance_param': 2.0,
            'line_ids': [Command.create({'account_id': self.account_revenue1.id})],
        })

        wizard = self.env['bank.rec.widget'].with_context(default_st_line_id=st_line.id).new({})
        wizard._action_trigger_matching_rules()
        self.assertRecordValues(wizard.line_ids, [
            # pylint: disable=C0326
            {'flag': 'liquidity',       'balance': 998.0,   'reconcile_model_id': False},
            {'flag': 'new_aml',         'balance': -1000.0, 'reconcile_model_id': rule.id},
            {'flag': 'manual',          'balance': 2.0,     'reconcile_model_id': rule.id},
        ])

    def test_early_payment_included_multi_currency(self):
        self.env['account.reconcile.model'].search([('company_id', '=', self.company_data['company'].id)]).unlink()
        self.early_payment_term.early_pay_discount_computation = 'included'
        income_exchange_account = self.env.company.income_currency_exchange_account_id
        expense_exchange_account = self.env.company.expense_currency_exchange_account_id

        inv_line1_with_epd = self._create_invoice_line(
            'out_invoice',
            currency_id=self.currency_data_2['currency'].id,
            partner_id=self.partner_a.id,
            invoice_payment_term_id=self.early_payment_term.id,
            invoice_date='2016-12-01',
            invoice_line_ids=[
                {
                    'price_unit': 4800.0,
                    'account_id': self.account_revenue1.id,
                    'tax_ids': [Command.set(self.company_data['default_tax_sale'].ids)],
                },
                {
                    'price_unit': 9600.0,
                    'account_id': self.account_revenue2.id,
                    'tax_ids': [Command.set(self.company_data['default_tax_sale'].ids)],
                },
            ],
        )
        inv_line1_with_epd_rec_lines = inv_line1_with_epd.move_id.line_ids\
            .filtered(lambda x: x.account_type == 'asset_receivable')\
            .sorted(lambda x: x.discount_date or x.date_maturity)
        self.assertRecordValues(
            inv_line1_with_epd_rec_lines,
            [
                {
                    'amount_currency': 16560.0,
                    'balance': 2760.0,
                    'discount_amount_currency': 14904.0,
                    'discount_balance': 2484.0,
                    'discount_date': fields.Date.from_string('2016-12-11'),
                    'date_maturity': fields.Date.from_string('2016-12-21'),
                },
            ],
        )

        inv_line2_with_epd = self._create_invoice_line(
            'out_invoice',
            currency_id=self.currency_data_2['currency'].id,
            partner_id=self.partner_a.id,
            invoice_payment_term_id=self.early_payment_term.id,
            invoice_date='2017-01-20',
            invoice_line_ids=[
                {
                    'price_unit': 480.0,
                    'account_id': self.account_revenue1.id,
                    'tax_ids': [Command.set(self.company_data['default_tax_sale'].ids)],
                },
                {
                    'price_unit': 960.0,
                    'account_id': self.account_revenue2.id,
                    'tax_ids': [Command.set(self.company_data['default_tax_sale'].ids)],
                },
            ],
        )
        inv_line2_with_epd_rec_lines = inv_line2_with_epd.move_id.line_ids\
            .filtered(lambda x: x.account_type == 'asset_receivable')\
            .sorted(lambda x: x.discount_date or x.date_maturity)
        self.assertRecordValues(
            inv_line2_with_epd_rec_lines,
            [
                {
                    'amount_currency': 1656.0,
                    'balance': 414.0,
                    'discount_amount_currency': 1490.4,
                    'discount_balance': 372.6,
                    'discount_date': fields.Date.from_string('2017-01-30'),
                    'date_maturity': fields.Date.from_string('2017-02-09'),
                },
            ],
        )

        # inv1: 16560.0 (no epd)
        # inv2: 1490.4 (epd)
        st_line = self._create_st_line(
            4512.0, # instead of 4512.6 (rate 1:4)
            date='2017-01-04',
            foreign_currency_id=self.currency_data_2['currency'].id,
            amount_currency=18050.4,
        )

        wizard = self.env['bank.rec.widget'].with_context(default_st_line_id=st_line.id).new({})

        # Add all lines from the first invoice plus the first one from the second one.
        wizard._action_add_new_amls(inv_line1_with_epd_rec_lines + inv_line2_with_epd_rec_lines)
        liquidity_acc = st_line.journal_id.default_account_id
        receivable_acc = self.company_data['default_account_receivable']
        early_pay_acc = self.env.company.account_journal_early_pay_discount_loss_account_id
        tax_acc = self.company_data['default_tax_sale'].invoice_repartition_line_ids.account_id
        self.assertRecordValues(wizard.line_ids, [
            # pylint: disable=C0326
            {'flag': 'liquidity',       'amount_currency': 4512.0,      'balance': 4512.0,      'account_id': liquidity_acc.id},
            {'flag': 'new_aml',         'amount_currency': -16560.0,    'balance': -2760.0,     'account_id': receivable_acc.id},
            {'flag': 'exchange_diff',   'amount_currency': 0.0,         'balance': -1379.45,    'account_id': income_exchange_account.id},
            {'flag': 'new_aml',         'amount_currency': -1656.0,     'balance': -414.0,      'account_id': receivable_acc.id},
            {'flag': 'exchange_diff',   'amount_currency': 0.0,         'balance': 0.06,        'account_id': expense_exchange_account.id},
            {'flag': 'early_payment',   'amount_currency': 144.0,       'balance': 36.0,        'account_id': early_pay_acc.id},
            {'flag': 'early_payment',   'amount_currency': 21.6,        'balance': 5.4,         'account_id': tax_acc.id},
            {'flag': 'early_payment',   'amount_currency': 0.0,         'balance': -0.01,       'account_id': income_exchange_account.id},
        ])

    def test_early_payment_excluded_multi_currency(self):
        self.env['account.reconcile.model'].search([('company_id', '=', self.company_data['company'].id)]).unlink()
        self.early_payment_term.early_pay_discount_computation = 'excluded'
        income_exchange_account = self.env.company.income_currency_exchange_account_id
        expense_exchange_account = self.env.company.expense_currency_exchange_account_id

        inv_line1_with_epd = self._create_invoice_line(
            'out_invoice',
            currency_id=self.currency_data_2['currency'].id,
            partner_id=self.partner_a.id,
            invoice_payment_term_id=self.early_payment_term.id,
            invoice_date='2016-12-01',
            invoice_line_ids=[
                {
                    'price_unit': 4800.0,
                    'account_id': self.account_revenue1.id,
                    'tax_ids': [Command.set(self.company_data['default_tax_sale'].ids)],
                },
                {
                    'price_unit': 9600.0,
                    'account_id': self.account_revenue2.id,
                    'tax_ids': [Command.set(self.company_data['default_tax_sale'].ids)],
                },
            ],
        )
        inv_line1_with_epd_rec_lines = inv_line1_with_epd.move_id.line_ids\
            .filtered(lambda x: x.account_type == 'asset_receivable')\
            .sorted(lambda x: x.discount_date or x.date_maturity)
        self.assertRecordValues(
            inv_line1_with_epd_rec_lines,
            [
                {
                    'amount_currency': 16560.0,
                    'balance': 2760.0,
                    'discount_amount_currency': 15120.0,
                    'discount_balance': 2520.0,
                    'discount_date': fields.Date.from_string('2016-12-11'),
                    'date_maturity': fields.Date.from_string('2016-12-21'),
                },
            ],
        )

        inv_line2_with_epd = self._create_invoice_line(
            'out_invoice',
            currency_id=self.currency_data_2['currency'].id,
            partner_id=self.partner_a.id,
            invoice_payment_term_id=self.early_payment_term.id,
            invoice_date='2017-01-20',
            invoice_line_ids=[
                {
                    'price_unit': 480.0,
                    'account_id': self.account_revenue1.id,
                    'tax_ids': [Command.set(self.company_data['default_tax_sale'].ids)],
                },
                {
                    'price_unit': 960.0,
                    'account_id': self.account_revenue2.id,
                    'tax_ids': [Command.set(self.company_data['default_tax_sale'].ids)],
                },
            ],
        )
        inv_line2_with_epd_rec_lines = inv_line2_with_epd.move_id.line_ids\
            .filtered(lambda x: x.account_type == 'asset_receivable')\
            .sorted(lambda x: x.discount_date or x.date_maturity)
        self.assertRecordValues(
            inv_line2_with_epd_rec_lines,
            [
                {
                    'amount_currency': 1656.0,
                    'balance': 414.0,
                    'discount_amount_currency': 1512.0,
                    'discount_balance': 378.0,
                    'discount_date': fields.Date.from_string('2017-01-30'),
                    'date_maturity': fields.Date.from_string('2017-02-09'),
                },
            ],
        )

        # inv1: 16560.0 (no epd)
        # inv2: 1512.0 (epd)
        st_line = self._create_st_line(
            4515.0, # instead of 4518.0 (rate 1:4)
            date='2017-01-04',
            foreign_currency_id=self.currency_data_2['currency'].id,
            amount_currency=18072.0,
        )

        wizard = self.env['bank.rec.widget'].with_context(default_st_line_id=st_line.id).new({})

        # Add all lines from the first invoice plus the first one from the second one.
        wizard._action_add_new_amls(inv_line1_with_epd_rec_lines + inv_line2_with_epd_rec_lines[:2])
        liquidity_acc = st_line.journal_id.default_account_id
        receivable_acc = self.company_data['default_account_receivable']
        early_pay_acc = self.env.company.account_journal_early_pay_discount_loss_account_id
        self.assertRecordValues(wizard.line_ids, [
            # pylint: disable=C0326
            {'flag': 'liquidity',       'amount_currency': 4515.0,      'balance': 4515.0,      'account_id': liquidity_acc.id},
            {'flag': 'new_aml',         'amount_currency': -16560.0,    'balance': -2760.0,     'account_id': receivable_acc.id},
            {'flag': 'exchange_diff',   'amount_currency': 0.0,         'balance': -1377.25,    'account_id': income_exchange_account.id},
            {'flag': 'new_aml',         'amount_currency': -1656.0,     'balance': -414.0,      'account_id': receivable_acc.id},
            {'flag': 'exchange_diff',   'amount_currency': 0.0,         'balance': 0.27,        'account_id': expense_exchange_account.id},
            {'flag': 'early_payment',   'amount_currency': 144.0,       'balance': 36.0,        'account_id': early_pay_acc.id},
            {'flag': 'early_payment',   'amount_currency': 0.0,         'balance': -0.02,       'account_id': income_exchange_account.id},
        ])

    def test_early_payment_mixed_multi_currency(self):
        self.env['account.reconcile.model'].search([('company_id', '=', self.company_data['company'].id)]).unlink()
        self.early_payment_term.early_pay_discount_computation = 'mixed'
        income_exchange_account = self.env.company.income_currency_exchange_account_id
        expense_exchange_account = self.env.company.expense_currency_exchange_account_id

        inv_line1_with_epd = self._create_invoice_line(
            'out_invoice',
            currency_id=self.currency_data_2['currency'].id,
            partner_id=self.partner_a.id,
            invoice_payment_term_id=self.early_payment_term.id,
            invoice_date='2016-12-01',
            invoice_line_ids=[
                {
                    'price_unit': 4800.0,
                    'account_id': self.account_revenue1.id,
                    'tax_ids': [Command.set(self.company_data['default_tax_sale'].ids)],
                },
                {
                    'price_unit': 9600.0,
                    'account_id': self.account_revenue2.id,
                    'tax_ids': [Command.set(self.company_data['default_tax_sale'].ids)],
                },
            ],
        )
        inv_line1_with_epd_rec_lines = inv_line1_with_epd.move_id.line_ids\
            .filtered(lambda x: x.account_type == 'asset_receivable')\
            .sorted(lambda x: x.discount_date or x.date_maturity)
        self.assertRecordValues(
            inv_line1_with_epd_rec_lines,
            [
                {
                    'amount_currency': 16344.0,
                    'balance': 2724.0,
                    'discount_amount_currency': 14904.0,
                    'discount_balance': 2484.0,
                    'discount_date': fields.Date.from_string('2016-12-11'),
                    'date_maturity': fields.Date.from_string('2016-12-21'),
                },
            ],
        )

        inv_line2_with_epd = self._create_invoice_line(
            'out_invoice',
            currency_id=self.currency_data_2['currency'].id,
            partner_id=self.partner_a.id,
            invoice_payment_term_id=self.early_payment_term.id,
            invoice_date='2017-01-20',
            invoice_line_ids=[
                {
                    'price_unit': 480.0,
                    'account_id': self.account_revenue1.id,
                    'tax_ids': [Command.set(self.company_data['default_tax_sale'].ids)],
                },
                {
                    'price_unit': 960.0,
                    'account_id': self.account_revenue2.id,
                    'tax_ids': [Command.set(self.company_data['default_tax_sale'].ids)],
                },
            ],
        )
        inv_line2_with_epd_rec_lines = inv_line2_with_epd.move_id.line_ids\
            .filtered(lambda x: x.account_type == 'asset_receivable')\
            .sorted(lambda x: x.discount_date or x.date_maturity)
        self.assertRecordValues(
            inv_line2_with_epd_rec_lines,
            [
                {
                    'amount_currency': 1634.4,
                    'balance': 408.6,
                    'discount_amount_currency': 1490.4,
                    'discount_balance': 372.6,
                    'discount_date': fields.Date.from_string('2017-01-30'),
                    'date_maturity': fields.Date.from_string('2017-02-09'),
                },
            ],
        )

        # inv1: 16344.0 (no epd)
        # inv2: 1490.4 (epd)
        st_line = self._create_st_line(
            4458.0, # instead of 4458.6 (rate 1:4)
            date='2017-01-04',
            foreign_currency_id=self.currency_data_2['currency'].id,
            amount_currency=17834.4,
        )

        wizard = self.env['bank.rec.widget'].with_context(default_st_line_id=st_line.id).new({})

        # Add all lines from the first invoice plus the first one from the second one.
        wizard._action_add_new_amls(inv_line1_with_epd_rec_lines + inv_line2_with_epd_rec_lines[:2])
        liquidity_acc = st_line.journal_id.default_account_id
        receivable_acc = self.company_data['default_account_receivable']
        early_pay_acc = self.env.company.account_journal_early_pay_discount_loss_account_id
        self.assertRecordValues(wizard.line_ids, [
            # pylint: disable=C0326
            {'flag': 'liquidity',       'amount_currency': 4458.0,      'balance': 4458.0,      'account_id': liquidity_acc.id},
            {'flag': 'new_aml',         'amount_currency': -16344.0,    'balance': -2724.0,     'account_id': receivable_acc.id},
            {'flag': 'exchange_diff',   'amount_currency': 0.0,         'balance': -1361.45,    'account_id': income_exchange_account.id},
            {'flag': 'new_aml',         'amount_currency': -1634.4,     'balance': -408.6,      'account_id': receivable_acc.id},
            {'flag': 'exchange_diff',   'amount_currency': 0.0,         'balance': 0.05,        'account_id': expense_exchange_account.id},
            {'flag': 'early_payment',   'amount_currency': 144.0,       'balance': 36.0,        'account_id': early_pay_acc.id},
        ])

    def test_early_payment_included_intracomm_bill(self):
        tax_tags = self.env['account.account.tag'].create({
            'name': f'tax_tag_{i}',
            'applicability': 'taxes',
            'country_id': self.env.company.account_fiscal_country_id.id,
        } for i in range(6))

        intracomm_tax = self.env['account.tax'].create({
            'name': 'tax20',
            'amount_type': 'percent',
            'amount': 20,
            'type_tax_use': 'purchase',
            'invoice_repartition_line_ids': [
                # pylint: disable=bad-whitespace
                Command.create({'repartition_type': 'base', 'factor_percent': 100.0,    'tag_ids': [Command.set(tax_tags[0].ids)]}),
                Command.create({'repartition_type': 'tax',  'factor_percent': 100.0,    'tag_ids': [Command.set(tax_tags[1].ids)]}),
                Command.create({'repartition_type': 'tax',  'factor_percent': -100.0,   'tag_ids': [Command.set(tax_tags[2].ids)]}),
            ],
            'refund_repartition_line_ids': [
                # pylint: disable=bad-whitespace
                Command.create({'repartition_type': 'base', 'factor_percent': 100.0,    'tag_ids': [Command.set(tax_tags[3].ids)]}),
                Command.create({'repartition_type': 'tax',  'factor_percent': 100.0,    'tag_ids': [Command.set(tax_tags[4].ids)]}),
                Command.create({'repartition_type': 'tax',  'factor_percent': -100.0,   'tag_ids': [Command.set(tax_tags[5].ids)]}),
            ],
        })

        early_payment_term = self.env['account.payment.term'].create({
            'name': "early_payment_term",
            'company_id': self.company_data['company'].id,
            'early_pay_discount_computation': 'included',
            'early_discount': True,
            'discount_percentage': 2,
            'discount_days': 7,
            'line_ids': [
                Command.create({
                    'value': 'percent',
                    'value_amount': 100.0,
                    'nb_days': 30,
                }),
            ],
        })

        bill = self.env['account.move'].create({
            'move_type': 'in_invoice',
            'partner_id': self.partner_a.id,
            'invoice_payment_term_id': early_payment_term.id,
            'invoice_date': '2019-01-01',
            'date': '2019-01-01',
            'invoice_line_ids': [
                Command.create({
                    'name': 'line',
                    'price_unit': 1000.0,
                    'tax_ids': [Command.set(intracomm_tax.ids)],
                }),
            ],
        })
        bill.action_post()

        st_line = self._create_st_line(
            -980.0,
            date='2017-01-01',
        )

        wizard = self.env['bank.rec.widget'].with_context(default_st_line_id=st_line.id).new({})
        wizard._action_add_new_amls(bill.line_ids.filtered(lambda x: x.account_type == 'liability_payable'))
        wizard._action_validate()

        self.assertRecordValues(st_line.line_ids.sorted('balance'), [
            # pylint: disable=bad-whitespace
            {'amount_currency': -980.0, 'tax_ids': [],                  'tax_tag_ids': [],              'tax_tag_invert': False},
            {'amount_currency': -20.0,  'tax_ids': intracomm_tax.ids,   'tax_tag_ids': tax_tags[3].ids, 'tax_tag_invert': True},
            {'amount_currency': -4.0,   'tax_ids': [],                  'tax_tag_ids': tax_tags[4].ids, 'tax_tag_invert': True},
            {'amount_currency': 4.0,    'tax_ids': [],                  'tax_tag_ids': tax_tags[5].ids, 'tax_tag_invert': True},
            {'amount_currency': 1000.0, 'tax_ids': [],                  'tax_tag_ids': [],              'tax_tag_invert': False},
        ])

    def test_tax_removal(self):
        tax_10 = self.env['account.tax'].create({
            'name': "tax_10",
            'amount': 10,
        })
        st_line = self._create_st_line(110.0)
        wizard = self.env['bank.rec.widget'].with_context(default_st_line_id=st_line.id).new({})
        suspense_line = wizard.line_ids.filtered(lambda l: l.flag == 'auto_balance')

        suspense_line.tax_ids = [Command.set(tax_10.ids)]
        wizard._line_value_changed_tax_ids(suspense_line)
        self.assertRecordValues(wizard.line_ids, [
            # pylint: disable=C0326
            { 'flag': 'liquidity', 'debit': 110.0, 'credit':   0.0 },
            { 'flag': 'manual',    'debit':   0.0, 'credit': 100.0 },
            { 'flag': 'tax_line',  'debit':   0.0, 'credit':  10.0 },
        ])

        suspense_line.tax_ids = [Command.clear()]
        wizard._line_value_changed_tax_ids(suspense_line)
        self.assertRecordValues(wizard.line_ids, [
            # pylint: disable=C0326
            { 'flag': 'liquidity', 'debit': 110.0, 'credit':   0.0 },
            { 'flag': 'manual',    'debit':   0.0, 'credit': 110.0 },
        ])

    def test_multi_currencies_with_custom_rate(self):
        self.company_data['default_journal_bank'].currency_id = self.currency_data['currency']
        st_line = self._create_st_line(1200.0) # rate 1:2
        self.assertRecordValues(st_line.move_id.line_ids, [
            # pylint: disable=C0326
            {'amount_currency': 1200.0,     'balance': 600.0},
            {'amount_currency': -1200.0,    'balance': -600.0},
        ])

        # invoice with currency_data and rate 1:2
        invoice_line1 = self._create_invoice_line(
            'out_invoice',
            currency_id=self.currency_data['currency'].id,
            invoice_date='2017-01-01',
            invoice_line_ids=[{'price_unit': 300.0}], # = 150 USD
        )

        # Remove all rates.
        self.currency_data['rates'].unlink()

        wizard = self.env['bank.rec.widget'].with_context(default_st_line_id=st_line.id).new({})
        self.assertRecordValues(wizard.line_ids, [
            # pylint: disable=C0326
            {'flag': 'liquidity',       'amount_currency': 1200.0,  'balance': 600.0},
            {'flag': 'auto_balance',    'amount_currency': -1200.0, 'balance': -600.0},
        ])

        # invoice with currency_data_2 and rate 1:6
        invoice_line2 = self._create_invoice_line(
            'out_invoice',
            currency_id=self.currency_data_2['currency'].id,
            invoice_date='2016-01-01',
            invoice_line_ids=[{'price_unit': 600.0}], # = 100 USD
        )
        # invoice with currency_data_2 and rate 1:4
        invoice_line3 = self._create_invoice_line(
            'out_invoice',
            currency_id=self.currency_data_2['currency'].id,
            invoice_date='2017-01-01',
            invoice_line_ids=[{'price_unit': 400.0}], # = 100 USD
        )

        # Remove all rates.
        self.currency_data_2['rates'].unlink()

        # Ensure no conversion rate has been made.
        wizard._action_add_new_amls(invoice_line1 + invoice_line2 + invoice_line3)
        self.assertRecordValues(wizard.line_ids, [
            # pylint: disable=C0326
            {'flag': 'liquidity',       'amount_currency': 1200.0,  'balance': 600.0},
            {'flag': 'new_aml',         'amount_currency': -300.0,  'balance': -150.0},
            {'flag': 'new_aml',         'amount_currency': -600.0,  'balance': -100.0},
            {'flag': 'new_aml',         'amount_currency': -400.0,  'balance': -100.0},
            {'flag': 'auto_balance',    'amount_currency': -500.0,  'balance': -250.0},
        ])

    def test_partial_reconciliation_suggestion_with_mixed_invoice_and_refund(self):
        """ Test the partial reconciliation suggestion is well recomputed when adding another
        line. For example, when adding 2 invoices having an higher amount then a refund. In that
        case, the partial on the second invoice should be removed since the difference is filled
        by the newly added refund.
        """
        st_line = self._create_st_line(
            1800.0,
            date='2017-01-01',
            foreign_currency_id=self.currency_data['currency'].id,
            amount_currency=3600.0,
        )

        inv1 = self._create_invoice_line(
            'out_invoice',
            currency_id=self.currency_data['currency'].id,
            invoice_date='2016-01-01',
            invoice_line_ids=[{'price_unit': 2400.0}],
        )
        inv2 = self._create_invoice_line(
            'out_invoice',
            currency_id=self.currency_data['currency'].id,
            invoice_date='2016-01-01',
            invoice_line_ids=[{'price_unit': 2400.0}],
        )
        refund = self._create_invoice_line(
            'out_refund',
            currency_id=self.currency_data['currency'].id,
            invoice_date='2016-01-01',
            invoice_line_ids=[{'price_unit': 1200.0}],
        )

        wizard = self.env['bank.rec.widget'].with_context(default_st_line_id=st_line.id).new({})
        wizard._action_add_new_amls(inv1 + inv2)
        self.assertRecordValues(wizard.line_ids, [
            # pylint: disable=C0326
            {'flag': 'liquidity',       'amount_currency': 1800.0,  'balance': 1800.0},
            {'flag': 'new_aml',         'amount_currency': -2400.0, 'balance': -800.0},
            {'flag': 'exchange_diff',   'amount_currency': 0.0,     'balance': -400.0},
            {'flag': 'new_aml',         'amount_currency': -1200.0, 'balance': -400.0},
            {'flag': 'exchange_diff',   'amount_currency': 0.0,     'balance': -200.0},
        ])
        wizard._action_add_new_amls(refund)
        self.assertRecordValues(wizard.line_ids, [
            # pylint: disable=C0326
            {'flag': 'liquidity',       'amount_currency': 1800.0,  'balance': 1800.0},
            {'flag': 'new_aml',         'amount_currency': -2400.0, 'balance': -800.0},
            {'flag': 'exchange_diff',   'amount_currency': 0.0,     'balance': -400.0},
            {'flag': 'new_aml',         'amount_currency': -2400.0, 'balance': -800.0},
            {'flag': 'exchange_diff',   'amount_currency': 0.0,     'balance': -400.0},
            {'flag': 'new_aml',         'amount_currency': 1200.0,  'balance': 400.0},
            {'flag': 'exchange_diff',   'amount_currency': 0.0,     'balance': 200.0},
        ])

    def test_auto_reconcile_cron_with_time_limit(self):
        self.env['account.reconcile.model'].search([('company_id', '=', self.company_data['company'].id)]).unlink()
        cron = self.env.ref('account_accountant.auto_reconcile_bank_statement_line')
        self.env['ir.cron.trigger'].search([('cron_id', '=', cron.id)]).unlink()

        st_line1 = self._create_st_line(1234.0, partner_id=self.partner_a.id, date='2017-01-01')
        self.assertEqual(len(self.env['ir.cron.trigger'].search([('cron_id', '=', cron.id)])), 1)
        st_line2 = self._create_st_line(5678.0, partner_id=self.partner_a.id, date='2017-01-02')
        self.assertEqual(len(self.env['ir.cron.trigger'].search([('cron_id', '=', cron.id)])), 2)

        self._create_invoice_line(
            'out_invoice',
            invoice_date='2017-01-01',
            invoice_line_ids=[{'price_unit': 1234.0}],
        )
        self._create_invoice_line(
            'out_invoice',
            invoice_date='2017-01-01',
            invoice_line_ids=[{'price_unit': 5678.0}],
        )
        self.env['account.reconcile.model'].create({
            'name': "test_auto_reconcile_cron_with_time_limit",
            'rule_type': 'writeoff_suggestion',
            'auto_reconcile': True,
            'line_ids': [Command.create({'account_id': self.account_revenue1.id})],
        })

        with freeze_time('2017-01-01 00:00:00') as frozen_time:
            def datetime_now_override():
                frozen_time.tick()
                return frozen_time()
            with patch('odoo.fields.Datetime.now', side_effect=datetime_now_override):
                # we simulate that the time limit is reached after first loop
                self.env['account.bank.statement.line']._cron_try_auto_reconcile_statement_lines(limit_time=1)
        # after first loop, only one statement should be reconciled
        self.assertRecordValues(st_line1, [{'is_reconciled': True, 'cron_last_check': fields.Datetime.from_string('2017-01-01 00:00:01')}])
        # the other one should be in queue for regular cron tigger
        self.assertRecordValues(st_line2, [{'is_reconciled': False, 'cron_last_check': False}])
        self.assertEqual(len(self.env['ir.cron.trigger'].search([('cron_id', '=', cron.id)])), 3)

    def test_auto_reconcile_cron_with_provided_statements_lines(self):
        self.env['account.reconcile.model'].search([('company_id', '=', self.company_data['company'].id)]).unlink()

        st_line1 = self._create_st_line(1234.0, partner_id=self.partner_a.id, date='2017-01-01')
        st_line2 = self._create_st_line(5678.0, partner_id=self.partner_a.id, date='2017-01-02')
        self._create_invoice_line(
            'out_invoice',
            invoice_date='2017-01-01',
            invoice_line_ids=[{'price_unit': 1234.0}],
        )
        self._create_invoice_line(
            'out_invoice',
            invoice_date='2017-01-01',
            invoice_line_ids=[{'price_unit': 5678.0}],
        )
        self.env['account.reconcile.model'].create({
            'name': "test_auto_reconcile_cron_with_time_limit",
            'rule_type': 'writeoff_suggestion',
            'auto_reconcile': True,
            'line_ids': [Command.create({'account_id': self.account_revenue1.id})],
        })
        with freeze_time('2017-01-01 00:00:00'):
            # we call auto reconcile on st_lines1 **only**
            st_line1._cron_try_auto_reconcile_statement_lines()
        self.assertRecordValues(st_line1, [{'is_reconciled': True, 'cron_last_check': fields.Datetime.from_string('2017-01-01 00:00:00')}])
        self.assertRecordValues(st_line2, [{'is_reconciled': False, 'cron_last_check': False}])

    @freeze_time('2019-01-01')
    def test_button_apply_reco_model(self):
        st_line = self._create_st_line(-1000.0, partner_id=self.partner_a.id)
        inv_line = self._create_invoice_line(
            'in_invoice',
            invoice_date=st_line.date,
            invoice_line_ids=[{'price_unit': 980.0}],
        )

        reco_model = self.env['account.reconcile.model'].create({
            'name': "test_apply_taxes_with_reco_model",
            'rule_type': 'writeoff_button',
            'line_ids': [Command.create({
                'account_id': self.account_revenue1.copy().id,
                'label': 'Bank Fees'
            })],
        })

        wizard = self.env['bank.rec.widget'].with_context(default_st_line_id=st_line.id).new({})
        wizard._action_trigger_matching_rules()

        self.assertRecordValues(wizard.line_ids, [
            # pylint: disable=C0326
            {'flag': 'liquidity',    'account_id': st_line.journal_id.default_account_id.id,        'balance': -1000.0},
            {'flag': 'new_aml',      'account_id': inv_line.account_id.id,                          'balance':   980.0},
            {'flag': 'auto_balance', 'account_id': self.company_data['default_account_payable'].id, 'balance':    20.0},
        ])

        wizard._action_select_reconcile_model(reco_model)

        self.assertRecordValues(wizard.line_ids, [
            # pylint: disable=C0326
            {'flag': 'liquidity',    'account_id': st_line.journal_id.default_account_id.id,        'balance': -1000.0},
            {'flag': 'new_aml',      'account_id': inv_line.account_id.id,                          'balance':   980.0},
            {'flag': 'manual',       'account_id': reco_model.line_ids[0].account_id.id,            'balance':    20.0},
        ])

    def test_exchange_diff_on_partial_aml_multi_currency(self):
        self.company_data['default_journal_bank'].currency_id = self.currency_data['currency']
        st_line = self._create_st_line(-36000.0) # rate 1:2
        inv_line = self._create_invoice_line(
            'in_invoice',
            invoice_date='2016-01-01', # rate 1:3
            currency_id=self.currency_data['currency'].id,
            invoice_line_ids=[{'price_unit': 38000.0}],
        )

        wizard = self.env['bank.rec.widget'].with_context(default_st_line_id=st_line.id).new({})
        wizard._action_add_new_amls(inv_line)

        self.assertRecordValues(wizard.line_ids, [
            # pylint: disable=C0326
            {'flag': 'liquidity',       'amount_currency': -36000.0,    'currency_id': self.currency_data['currency'].id,   'balance': -18000.0},
            {'flag': 'new_aml',         'amount_currency': 36000.0,     'currency_id': self.currency_data['currency'].id,   'balance': 12000.0},
            {'flag': 'exchange_diff',   'amount_currency': 0.0,         'currency_id': self.currency_data['currency'].id,   'balance': 6000.0},
        ])

    def test_exchange_diff_on_partial_aml_multi_currency_close_amount(self):
        self.currency_data['rates'].rate = 0.9839
        self.company_data['default_journal_bank'].currency_id = self.currency_data['currency']

        st_line = self._create_st_line(-37436.50)
        self.assertRecordValues(st_line.line_ids, [
            # pylint: disable=C0326
            {'amount_currency': -37436.50,  'balance': -38049.09},
            {'amount_currency': 37436.50,   'balance': 38049.09},
        ])

        inv_line = self._create_invoice_line(
            'in_invoice',
            invoice_date=st_line.date,
            currency_id=self.currency_data['currency'].id,
            invoice_line_ids=[{'price_unit': 37436.52}],
        )
        self.assertRecordValues(inv_line, [{
            'amount_currency': -37436.52,
            'balance': -38049.11,
        }])

        wizard = self.env['bank.rec.widget'].with_context(default_st_line_id=st_line.id).new({})
        wizard._action_add_new_amls(inv_line)

        self.assertRecordValues(wizard.line_ids, [
            # pylint: disable=C0326
            {'flag': 'liquidity',       'amount_currency': -37436.50,   'currency_id': self.currency_data['currency'].id,   'balance': -38049.09},
            {'flag': 'new_aml',         'amount_currency': 37436.50,    'currency_id': self.currency_data['currency'].id,   'balance': 38049.09},
        ])

    def test_matching_zero_amount_misc_entry(self):
        """ Check for division by zero with foreign currencies and some 0 making a broken rate. """
        self.company_data['default_journal_bank'].currency_id = self.currency_data['currency']
        st_line = self._create_st_line(0.0, amount_currency=10.0, foreign_currency_id=self.company_data['currency'].id)

        entry = self.env['account.move'].create({
            'date': '2019-01-01',
            'line_ids': [
                Command.create({
                    'account_id': self.company_data['default_account_receivable'].id,
                    'currency_id': self.currency_data['currency'].id,
                    'debit': 1.0,
                    'credit': 0.0,
                }),
                Command.create({
                    'account_id': self.company_data['default_account_revenue'].id,
                    'currency_id': self.currency_data['currency'].id,
                    'debit': 0.0,
                    'credit': 1.0,
                }),
            ]
        })
        entry.action_post()

        wizard = self.env['bank.rec.widget'].with_context(default_st_line_id=st_line.id).new({})
        aml = entry.line_ids.filtered('debit')
        wizard._action_add_new_amls(aml)
        self.assertRecordValues(wizard.line_ids, [
            # pylint: disable=C0326
            {'flag': 'liquidity',       'balance': 10.0},
            {'flag': 'new_aml',         'balance': -1.0},
            {'flag': 'exchange_diff',   'balance': 1.0},
            {'flag': 'auto_balance',    'balance': -10.0},
        ])
