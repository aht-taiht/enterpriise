# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.
import odoo.tests

from datetime import datetime
from odoo import fields
from odoo.addons.payment.tests.common import PaymentAcquirerCommon


class SepaDirectDebitCommon(PaymentAcquirerCommon):

    def setUp(self):
        super(SepaDirectDebitCommon, self).setUp()

        self.company = self.env.ref('base.main_company')
        self.company.sdd_creditor_identifier = 'BE30ZZZ300D000000042'
        self.EUR = self.env.ref('base.EUR').id
        bank_ing = self.env['res.bank'].create({'name': 'ING', 'bic': 'BBRUBEBB'})
        
        self.sepa_bank_account = self.env['res.partner.bank'].create({
            'acc_number': 'NL91 ABNA 0417 1643 00',
            'partner_id': self.company.partner_id.id,
            'bank_id': bank_ing.id,
        })

        assert self.sepa_bank_account.acc_type == 'iban'

        self.sepa_journal = self.env['account.journal'].create({
            'name': 'Bank SEPA',
            'type': 'bank',
            'code': 'BNKSEPA',
            'inbound_payment_method_ids': [(4, self.env.ref('account_sepa_direct_debit.payment_method_sdd').id)],
            'bank_account_id': self.sepa_bank_account.id,
        })

        self.sepa = self.env.ref('payment.payment_acquirer_sepa_direct_debit')
        self.sepa.write({
            'journal_id': self.sepa_journal.id,
            'state': 'enabled',
            'sepa_direct_debit_sms_enabled': True,
        })

        # create the partner bank account
        partner_bank = self.env['res.partner.bank'].create({
            'acc_number': 'BE17412614919710',
            'partner_id': self.buyer_id,
            'company_id': self.company.id,
        })

        self.mandate = self.env['sdd.mandate'].create({
            'partner_id': self.buyer_id,
            'company_id': self.company.id,
            'partner_bank_id': partner_bank.id,
            'start_date': fields.date.today(),
            'payment_journal_id': self.sepa_journal.id,
            'verified': True,
            'state': 'active',
        })

    def reconcile(self, payment):
        bank_journal = payment.journal_id
        move_line = payment.line_ids.filtered(lambda aml: aml.account_id == bank_journal.payment_debit_account_id)

        bank_stmt = self.env['account.bank.statement'].create({
            'journal_id': bank_journal.id,
            'date': payment.date,
            'name': payment.name,
        })
        bank_stmt_line = self.env['account.bank.statement.line'].create({
            'statement_id': bank_stmt.id,
            'partner_id': self.buyer_id,
            'foreign_currency_id': move_line.currency_id.id,
            'amount_currency': abs(move_line.amount_currency),
            'amount': abs(move_line.balance),
            'date': payment.date,
            'payment_ref': payment.name,
        })
        bank_stmt.button_post()
        bank_stmt_line.reconcile([{'id': move_line.id}])

        self.assertTrue(payment.is_matched, 'payment should be reconciled')


@odoo.tests.tagged('post_install', '-at_install')
class TestSepaDirectDebit(SepaDirectDebitCommon):

    def test_sepa_direct_debit_s2s_process(self):
        payment_token = self.env['payment.token'].create({
            'acquirer_id': self.sepa.id,
            'partner_id': self.buyer_id,
            'sdd_mandate_id': self.mandate.id,
            'acquirer_ref': self.mandate.name,
        })

        tx = self.env['payment.transaction'].create({
            'reference': 'test_ref_%s' % fields.datetime.now(),
            'currency_id': self.EUR,
            'partner_id': self.buyer_id,
            'amount': 10.0,
            'acquirer_id': self.sepa.id,
            'payment_token_id': payment_token.id,
            'type': 'server2server',
            'date': datetime.now(),
        })

        # 1. capture transaction
        tx.sepa_direct_debit_s2s_do_transaction()

        self.assertEqual(tx.payment_token_id.verified, True)
        self.assertEqual(tx.state, 'pending', 'payment transaction should be pending')
        self.assertEqual(tx.payment_id.state, 'posted', 'account payment should be posted')
        self.assertEqual(tx.payment_id.sdd_mandate_id.id, self.mandate.id)

        # 2. reconcile
        self.reconcile(tx.payment_id)

        self.assertEqual(tx.state, 'done', 'payment transaction should be done')
