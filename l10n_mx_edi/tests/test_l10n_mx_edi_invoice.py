# coding: utf-8

import base64
import os

from lxml import etree, objectify

from odoo.tools import misc

from . import common


class TestL10nMxEdiInvoice(common.InvoiceTransactionCase):
    def setUp(self):
        super(TestL10nMxEdiInvoice, self).setUp()
        self.cert = misc.file_open(os.path.join(
            'l10n_mx_edi', 'demo', 'pac_credentials', 'certificate.cer')).read()
        self.cert_key = misc.file_open(os.path.join(
            'l10n_mx_edi', 'demo', 'pac_credentials', 'certificate.key')).read()
        self.cert_password = '12345678a'
        self.l10n_mx_edi_basic_configuration()
        xml_expected = misc.file_open(os.path.join(
            'l10n_mx_edi', 'tests', 'expected_cfdi.xml')).read()
        self.xml_expected = objectify.fromstring(xml_expected)
        self.company_partner = self.env.ref('base.main_partner')

    def l10n_mx_edi_basic_configuration(self):
        self.company.write({
            'currency_id': self.mxn.id,
        })
        self.company.partner_id.write({
            'vat': 'AAA010101AAA',
            'country_id': self.env.ref('base.mx').id,
            'state_id': self.env.ref('base.state_mx_jal').id,
            'street_name': 'Company Street Juan & José & "Niño"',
            'street2': 'Company Street 2',
            'street_number': 'Company Internal Number',
            'street_number2': 'Company Internal Number # 2',
            'l10n_mx_edi_colony': 'Company Colony',
            'l10n_mx_edi_locality': 'Company Locality',
            'city': 'Company City',
            'zip': '37200',
            'property_account_position_id': self.fiscal_position.id,
        })
        self.account_settings.create({
            'l10n_mx_edi_pac': 'finkok',
            'l10n_mx_edi_pac_test_env': True,
            'l10n_mx_edi_certificate_ids': [{
                'content': base64.encodestring(self.cert),
                'key': base64.encodestring(self.cert_key),
                'password': self.cert_password,
            }]
        }).execute()
        self.set_currency_rates(mxn_rate=21, usd_rate=1)

    def get_xml_attach(self, invoice, limit=1):
        # TODO: Create a method to get XML attachment from account.invoice
        domain = [
            ('res_id', '=', invoice.id),
            ('res_model', '=', invoice._name),
            ('name', '=', invoice.l10n_mx_edi_cfdi_name)]
        xml_attach = self.env['ir.attachment'].search(domain, limit=limit)
        return xml_attach

    def test_l10n_mx_edi_invoice_basic(self):
        # -----------------------
        # Testing sign process
        # -----------------------
        invoice = self.create_invoice()
        invoice.journal_id.l10n_mx_address_issued_id = self.company_partner.id
        invoice.move_name = '999'
        invoice.action_invoice_open()
        self.assertEqual(invoice.state, "open")
        self.assertEqual(invoice.l10n_mx_edi_pac_status, "signed")
        xml = self.get_invoice_xml(invoice)
        self.xml_merge_dynamic_items(xml, self.xml_expected)
        self.assertEqualXML(xml, self.xml_expected)
        xml_attach = base64.decodestring(self.get_xml_attach(invoice).datas)
        self.assertEqual(xml_attach.splitlines()[0].lower(),
                         '<?xml version="1.0" encoding="utf-8"?>'.lower())

        # -----------------------
        # Testing re-sign process (recovery a previous signed xml)
        # -----------------------
        invoice.l10n_mx_edi_pac_status = "retry"
        self.assertEqual(invoice.l10n_mx_edi_pac_status, "retry")
        invoice.l10n_mx_edi_update_pac_status()
        self.assertEqual(invoice.l10n_mx_edi_pac_status, "signed")
        xml_attachs = self.get_xml_attach(invoice, limit=None)
        self.assertEqual(len(xml_attachs), 2)
        xml_1 = objectify.fromstring(base64.decodestring(xml_attachs[0].datas))
        xml_2 = objectify.fromstring(base64.decodestring(xml_attachs[1].datas))
        # TODO: Supports this case. Currently the xml date is changed.
        # self.assertEqualXML(xml_1, xml_2)

        # -----------------------
        # Testing cancel PAC process
        # -----------------------
        invoice.journal_id.update_posted = True
        invoice.action_invoice_cancel()
        self.assertEqual(invoice.state, "cancel")
        self.assertEqual(invoice.l10n_mx_edi_pac_status, 'cancelled')
        invoice.l10n_mx_edi_pac_status = "signed"

        # -----------------------
        # Testing cancel SAT process
        # -----------------------
        invoice.l10n_mx_edi_update_sat_status()
        self.assertNotEqual(invoice.l10n_mx_edi_sat_status, "cancelled")

        # Use a real UUID cancelled
        xml_tfd = invoice._l10n_mx_edi_get_xml_tfd(xml)
        xml_tfd.attrib['UUID'] = '0F481E0F-47A5-4647-B06B-8B471671F377'
        xml.Emisor.attrib['rfc'] = 'VAU111017CG9'
        xml.Receptor.attrib['rfc'] = 'IAL691030TK3'
        xml.attrib['total'] = '1.16'
        xml_attach = self.get_xml_attach(invoice)
        xml_attach.datas = base64.encodestring(etree.tostring(xml))
        invoice.l10n_mx_edi_update_sat_status()
        self.assertEqual(invoice.l10n_mx_edi_sat_status, "cancelled")

    def test_l10n_mx_edi_invoice_basic_sf(self):
        self.account_settings.create({'l10n_mx_edi_pac': 'solfact'}).execute()
        self.test_l10n_mx_edi_invoice_basic()

    def test_multi_currency(self):
        invoice = self.create_invoice()
        usd_rate = 20.0

        # -----------------------
        # Testing company.mxn.rate=1 and invoice.usd.rate=1/value
        # -----------------------
        self.set_currency_rates(mxn_rate=1, usd_rate=1/usd_rate)
        values = invoice._l10n_mx_edi_create_cfdi_values()
        self.assertEqual(values['rate'], usd_rate)

        # -----------------------
        # Testing company.mxn.rate=value and invoice.usd.rate=1
        # -----------------------
        self.set_currency_rates(mxn_rate=usd_rate, usd_rate=1)
        values = invoice._l10n_mx_edi_create_cfdi_values()
        self.assertEqual(values['rate'], usd_rate)

        # -----------------------
        # Testing using MXN currency for invoice and company
        # -----------------------
        invoice.currency_id = self.mxn.id
        values = invoice._l10n_mx_edi_create_cfdi_values()
        self.assertEqual(values['rate'], 1)
