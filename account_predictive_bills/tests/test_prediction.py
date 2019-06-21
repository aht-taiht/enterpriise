# -*- encoding: utf-8 -*-

from odoo.addons.account.tests.account_test_classes import AccountingTestCase
from odoo.tests import tagged
from odoo.tests.common import Form


@tagged('post_install', '-at_install')
class TestBillsPrediction(AccountingTestCase):

    def _create_one_line_bill(self, vendor, description, expected_account, account_to_set=None):
        with Form(self.env['account.invoice'].with_context(type='in_invoice'), view='account.invoice_supplier_form') as invoice_form:
            invoice_form.partner_id = vendor

            with invoice_form.invoice_line_ids.new() as invoice_line_form:
                invoice_line_form.quantity = 1
                invoice_line_form.price_unit = 42
                invoice_line_form.name = description

                self.assertEquals(invoice_line_form.account_id, expected_account, "Account %s should have been predicted instead of %s" % (expected_account.code, invoice_line_form.account_id.code))

                if account_to_set:
                    invoice_line_form.account_id = account_to_set
                    # We check that the account doesn't get another value due to onchange calling itself
                    self.assertEquals(invoice_line_form.account_id, account_to_set, "Account %s has been assigned manually, but has been changed to account %s" % (account_to_set.code, invoice_line_form.account_id.code))

            rslt = invoice_form.save()
            rslt.action_invoice_open()
            return rslt

    def _create_test_partners(self, nber):
        rslt = self.env['res.partner']
        for i in range(0, nber):
            with Form(self.env['res.partner']) as partner_form:
                partner_form.name = 'Test partner %d' % i
                rslt += partner_form.save()
        return rslt

    def _create_test_accounts(self, code_name_list):
        rslt = self.env['account.account']
        for (code, name) in code_name_list:
            with Form(self.env['account.account']) as account_form:
                account_form.code = code
                account_form.name = name
                account_form.user_type_id = self.env.ref('account.data_account_type_expenses')
                rslt += account_form.save()
        return rslt

    def test_account_prediction_flow(self):
        vendors = self._create_test_partners(7)
        accounts = self._create_test_accounts([('test1', 'Test Maintenance and Repair'),
                                               ('test2', 'Test Purchase of services, studies and preparatory work'),
                                               ('test3', 'Test Various Rents'),
                                               ('test4', 'Test Rental Charges'),
                                               ('test5', 'Test Purchase of commodity')])
        default_account = self.env['account.journal'].search([('type', '=', 'purchase')], limit=1).default_debit_account_id
        self._create_one_line_bill(vendors[0], "Maintenance and repair", accounts[0])
        self._create_one_line_bill(vendors[5], "Subsidies obtained", default_account, account_to_set=accounts[1])
        self._create_one_line_bill(vendors[6], "Prepare subsidies file", accounts[1])
        self._create_one_line_bill(vendors[1], "Rents January", accounts[2])
        self._create_one_line_bill(vendors[2], "Coca-cola", default_account, account_to_set=accounts[4])
        self._create_one_line_bill(vendors[1], "Rent February", accounts[2])
        self._create_one_line_bill(vendors[3], "Electricity Bruxelles", default_account, account_to_set=accounts[3])
        self._create_one_line_bill(vendors[3], "Electricity Grand-Rosière", accounts[3])
        self._create_one_line_bill(vendors[2], "Purchase of coca-cola", accounts[4])
        self._create_one_line_bill(vendors[4], "Crate of coca-cola", accounts[4])
        self._create_one_line_bill(vendors[1], "March: office", accounts[2])
