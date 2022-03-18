# -*- coding: utf-8 -*-

from freezegun import freeze_time
from odoo.addons.account.tests.common import AccountTestInvoicingCommon
from odoo.addons.l10n_be_reports.models.res_partner import format_if_float
from odoo.tests import tagged
from odoo import fields, Command


@tagged('post_install_l10n', 'post_install', '-at_install')
@freeze_time('2022-03-01')
class TestResPartner(AccountTestInvoicingCommon):

    @classmethod
    def setUpClass(cls, chart_template_ref='l10n_be.l10nbe_chart_template'):
        super().setUpClass(chart_template_ref=chart_template_ref)

        cls.invoice = cls.init_invoice('in_invoice')

        cls.partner_a.write({
            'street': 'Rue du Jacobet, 9',
            'zip': '7100',
            'city': 'La Louvière',
            'country_id': cls.env.ref('base.be').id,
            'vat': 'BE0475646428',
            'is_company': True,
            'category_id': [Command.link(cls.env.ref('l10n_be_reports.res_partner_tag_281_50').id)]
        })
        cls.partner_b.write({
            'name': 'SPRL Popiul',
            'street': 'Rue Arthur Libert',
            'street2': 'Longueville 8',
            'zip': '1325',
            'city': 'Chaumont-Gistoux',
            'country_id': cls.env.ref('base.be').id,
            'vat': 'BE0807677428',
            'is_company': True,
            'category_id': [Command.link(cls.env.ref('l10n_be_reports.res_partner_tag_281_50').id)]
        })

        cls.wizard_values = {
            'reference_year': '2000',
            'is_test': False,
            'type_sending': '0',
            'type_treatment': '0',
        }

        cls.tag_281_50_commissions = cls.env.ref('l10n_be_reports.account_tag_281_50_commissions')
        cls.tag_281_50_fees = cls.env.ref('l10n_be_reports.account_tag_281_50_fees')
        cls.tag_281_50_atn = cls.env.ref('l10n_be_reports.account_tag_281_50_atn')
        cls.tag_281_50_exposed_expenses = cls.env.ref('l10n_be_reports.account_tag_281_50_exposed_expenses')

        cls.env.company.vat = 'BE0477472701'
        cls.env.company.phone = '+3222903490'
        cls.env.company.street = 'Rue du Laid Burniat 5'
        cls.env.company.zip = '1348'
        cls.env.company.city = 'Ottignies-Louvain-la-Neuve '
        cls.env.company.country_id = cls.env.ref('base.be').id

        cls.product_a.property_account_expense_id.tag_ids |= cls.tag_281_50_commissions
        cls.product_b.property_account_expense_id.tag_ids |= cls.tag_281_50_fees

        cls.move_a = cls.create_and_post_bill(cls.partner_a, cls.product_a, 1000.0, '2000-05-12')

        cls.debtor = cls.env.company.partner_id
        cls.sender = cls.env.company.partner_id

    @classmethod
    def create_and_post_bill(cls, partner_id, product_id, amount, date):
        invoice = cls.env['account.move'].create({
            'move_type': 'in_invoice',
            'partner_id': partner_id.id,
            'invoice_date': fields.Date.from_string(date),
            'currency_id': cls.currency_data['currency'].id,
            'invoice_line_ids': [
                Command.create({
                    'product_id': product_id.id,
                    'account_id': product_id.property_account_expense_id.id,
                    'partner_id': partner_id.id,
                    'product_uom_id': product_id.uom_id.id,
                    'quantity': 1.0,
                    'discount': 0.0,
                    'price_unit': amount,
                    'amount_currency': 0.0,
                    'debit': amount,
                    'credit': 0.0,
                }),
            ]
        })
        invoice.action_post()
        return invoice

    @classmethod
    def pay_bill(cls, bill, amount, date):
        payment = cls.env['account.payment'].create({
            'payment_type': 'outbound',
            'amount': amount,
            'currency_id': bill.currency_id.id,
            'journal_id': cls.company_data['default_journal_bank'].id,
            'date': fields.Date.from_string(date),
            'partner_id': bill.partner_id.id,
            'payment_method_id': cls.env.ref('account.account_payment_method_manual_out').id,
            'partner_type': 'supplier',
        })
        payment.action_post()
        bill_payable_move_lines = bill.line_ids.filtered(lambda x: x.account_internal_type == 'payable')
        bill_payable_move_lines += payment.line_ids.filtered(lambda x: x.account_internal_type == 'payable')
        bill_payable_move_lines.reconcile()

    def test_281_50_xml_generation_1_partner_eligible_no_payment(self):
        """check the values generated and injected in the xml are as expected
        Simple case: 1 partner, invoice for 1.000,00 currency in an account tagged as commission, no payment
        """
        partner_325_form = self.partner_a._generate_form_325_values(self.debtor, self.sender, self.wizard_values)
        resulting_xml = self.debtor._generate_325_form_xml(partner_325_form)
        expected_281_50_xml = b"""<?xml version='1.0' encoding='utf-8'?>
                    <Verzendingen>
                        <Verzending>
                            <v0002_inkomstenjaar>2000</v0002_inkomstenjaar>
                            <v0010_bestandtype>BELCOTAX</v0010_bestandtype>
                            <v0011_aanmaakdatum>01-03-2022</v0011_aanmaakdatum>
                            <v0014_naam>company_1_data</v0014_naam>
                            <v0015_adres>Rue du Laid Burniat 5</v0015_adres>
                            <v0016_postcode>1348</v0016_postcode>
                            <v0017_gemeente>Ottignies-Louvain-la-Neuve </v0017_gemeente>
                            <v0018_telefoonnummer>+3222903490</v0018_telefoonnummer>
                            <v0021_contactpersoon>Because I am accountman!</v0021_contactpersoon>
                            <v0022_taalcode>2</v0022_taalcode>
                            <v0023_emailadres>accountman@test.com</v0023_emailadres>
                            <v0024_nationaalnr>0477472701</v0024_nationaalnr>
                            <v0025_typeenvoi>0</v0025_typeenvoi>
                            <Aangiften>
                                <Aangifte>
                                    <a1002_inkomstenjaar>2000</a1002_inkomstenjaar>
                                    <a1005_registratienummer>0477472701</a1005_registratienummer>
                                    <a1011_naamnl1>company_1_data</a1011_naamnl1>
                                    <a1013_adresnl>Rue du Laid Burniat 5</a1013_adresnl>
                                    <a1014_postcodebelgisch>1348</a1014_postcodebelgisch>
                                    <a1015_gemeente>Ottignies-Louvain-la-Neuve </a1015_gemeente>
                                    <a1016_landwoonplaats>00000</a1016_landwoonplaats>
                                    <a1020_taalcode>1</a1020_taalcode>
                                    <Opgaven>
                                        <Opgave32550>
                                            <Fiche28150>
                                                <f2002_inkomstenjaar>2000</f2002_inkomstenjaar>
                                                <f2005_registratienummer>0477472701</f2005_registratienummer>
                                                <f2008_typefiche>28150</f2008_typefiche>
                                                <f2009_volgnummer>1</f2009_volgnummer>
                                                <f2013_naam>partner_a</f2013_naam>
                                                <f2015_adres>Rue du Jacobet, 9</f2015_adres>
                                                <f2016_postcodebelgisch>7100</f2016_postcodebelgisch>
                                                <f2017_gemeente>La Louvi\xc3\xa8re</f2017_gemeente>
                                                <f2018_landwoonplaats>00000</f2018_landwoonplaats>
                                                <f2028_typetraitement>0</f2028_typetraitement>
                                                <f2029_enkelopgave325>0</f2029_enkelopgave325>
                                                <f2105_birthplace>0</f2105_birthplace>
                                                <f2112_buitenlandspostnummer/>
                                                <f2114_voornamen/>
                                                <f50_2030_aardpersoon>2</f50_2030_aardpersoon>
                                                <f50_2031_nihil>1</f50_2031_nihil>
                                                <f50_2059_totaalcontrole>200000</f50_2059_totaalcontrole>
                                                <f50_2060_commissies>100000</f50_2060_commissies>
                                                <f50_2061_erelonenofvacatie>0</f50_2061_erelonenofvacatie>
                                                <f50_2062_voordelenaardbedrag>0</f50_2062_voordelenaardbedrag>
                                                <f50_2063_kosten>0</f50_2063_kosten>
                                                <f50_2064_totaal>100000</f50_2064_totaal>
                                                <f50_2065_werkelijkbetaaldb>0</f50_2065_werkelijkbetaaldb>
                                                <f50_2066_sportremuneration>0</f50_2066_sportremuneration>
                                                <f50_2067_managerremuneration>0</f50_2067_managerremuneration>
                                                <f50_2099_comment/>
                                                <f50_2103_advantagenature/>
                                                <f50_2107_uitgeoefendberoep/>
                                                <f50_2109_fiscaalidentificat/>
                                                <f50_2110_kbonbr>0475646428</f50_2110_kbonbr>
                                            </Fiche28150>
                                        </Opgave32550>
                                    </Opgaven>
                                    <r8002_inkomstenjaar>2000</r8002_inkomstenjaar>
                                    <r8005_registratienummer>0477472701</r8005_registratienummer>
                                    <r8010_aantalrecords>3</r8010_aantalrecords>
                                    <r8011_controletotaal>1</r8011_controletotaal>
                                    <r8012_controletotaal>200000</r8012_controletotaal>
                                </Aangifte>
                            </Aangiften>
                            <r9002_inkomstenjaar>2000</r9002_inkomstenjaar>
                            <r9010_aantallogbestanden>3</r9010_aantallogbestanden>
                            <r9011_totaalaantalrecords>5</r9011_totaalaantalrecords>
                            <r9012_controletotaal>1</r9012_controletotaal>
                            <r9013_controletotaal>200000</r9013_controletotaal>
                        </Verzending>
                    </Verzendingen>"""
        self.assertXmlTreeEqual(
            self.get_xml_tree_from_string(resulting_xml),
            self.get_xml_tree_from_string(expected_281_50_xml),
        )

    def test_281_50_xml_generation_1_partner_eligible(self):
        """check the values generated and injected in the xml are as expected
        Simple case: 1 partner, invoice for 1.000,00 currency in an account tagged as commission and a full payment
        """
        # make a payment to the vendor partner_a and reconcile it with the bill
        self.pay_bill(bill=self.move_a, amount=1000, date='2000-05-12')

        partner_325_form = self.partner_a._generate_form_325_values(self.debtor, self.sender, self.wizard_values)
        resulting_xml = self.debtor._generate_325_form_xml(partner_325_form)
        expected_281_50_xml = b"""<?xml version='1.0' encoding='utf-8'?>
                    <Verzendingen>
                        <Verzending>
                            <v0002_inkomstenjaar>2000</v0002_inkomstenjaar>
                            <v0010_bestandtype>BELCOTAX</v0010_bestandtype>
                            <v0011_aanmaakdatum>01-03-2022</v0011_aanmaakdatum>
                            <v0014_naam>company_1_data</v0014_naam>
                            <v0015_adres>Rue du Laid Burniat 5</v0015_adres>
                            <v0016_postcode>1348</v0016_postcode>
                            <v0017_gemeente>Ottignies-Louvain-la-Neuve </v0017_gemeente>
                            <v0018_telefoonnummer>+3222903490</v0018_telefoonnummer>
                            <v0021_contactpersoon>Because I am accountman!</v0021_contactpersoon>
                            <v0022_taalcode>2</v0022_taalcode>
                            <v0023_emailadres>accountman@test.com</v0023_emailadres>
                            <v0024_nationaalnr>0477472701</v0024_nationaalnr>
                            <v0025_typeenvoi>0</v0025_typeenvoi>
                            <Aangiften>
                                <Aangifte>
                                    <a1002_inkomstenjaar>2000</a1002_inkomstenjaar>
                                    <a1005_registratienummer>0477472701</a1005_registratienummer>
                                    <a1011_naamnl1>company_1_data</a1011_naamnl1>
                                    <a1013_adresnl>Rue du Laid Burniat 5</a1013_adresnl>
                                    <a1014_postcodebelgisch>1348</a1014_postcodebelgisch>
                                    <a1015_gemeente>Ottignies-Louvain-la-Neuve </a1015_gemeente>
                                    <a1016_landwoonplaats>00000</a1016_landwoonplaats>
                                    <a1020_taalcode>1</a1020_taalcode>
                                    <Opgaven>
                                        <Opgave32550>
                                            <Fiche28150>
                                                <f2002_inkomstenjaar>2000</f2002_inkomstenjaar>
                                                <f2005_registratienummer>0477472701</f2005_registratienummer>
                                                <f2008_typefiche>28150</f2008_typefiche>
                                                <f2009_volgnummer>1</f2009_volgnummer>
                                                <f2013_naam>partner_a</f2013_naam>
                                                <f2015_adres>Rue du Jacobet, 9</f2015_adres>
                                                <f2016_postcodebelgisch>7100</f2016_postcodebelgisch>
                                                <f2017_gemeente>La Louvi\xc3\xa8re</f2017_gemeente>
                                                <f2018_landwoonplaats>00000</f2018_landwoonplaats>
                                                <f2028_typetraitement>0</f2028_typetraitement>
                                                <f2029_enkelopgave325>0</f2029_enkelopgave325>
                                                <f2105_birthplace>0</f2105_birthplace>
                                                <f2112_buitenlandspostnummer/>
                                                <f2114_voornamen/>
                                                <f50_2030_aardpersoon>2</f50_2030_aardpersoon>
                                                <f50_2031_nihil>0</f50_2031_nihil>
                                                <f50_2059_totaalcontrole>300000</f50_2059_totaalcontrole>
                                                <f50_2060_commissies>100000</f50_2060_commissies>
                                                <f50_2061_erelonenofvacatie>0</f50_2061_erelonenofvacatie>
                                                <f50_2062_voordelenaardbedrag>0</f50_2062_voordelenaardbedrag>
                                                <f50_2063_kosten>0</f50_2063_kosten>
                                                <f50_2064_totaal>100000</f50_2064_totaal>
                                                <f50_2065_werkelijkbetaaldb>100000</f50_2065_werkelijkbetaaldb>
                                                <f50_2066_sportremuneration>0</f50_2066_sportremuneration>
                                                <f50_2067_managerremuneration>0</f50_2067_managerremuneration>
                                                <f50_2099_comment/>
                                                <f50_2103_advantagenature/>
                                                <f50_2107_uitgeoefendberoep/>
                                                <f50_2109_fiscaalidentificat/>
                                                <f50_2110_kbonbr>0475646428</f50_2110_kbonbr>
                                            </Fiche28150>
                                        </Opgave32550>
                                    </Opgaven>
                                    <r8002_inkomstenjaar>2000</r8002_inkomstenjaar>
                                    <r8005_registratienummer>0477472701</r8005_registratienummer>
                                    <r8010_aantalrecords>3</r8010_aantalrecords>
                                    <r8011_controletotaal>1</r8011_controletotaal>
                                    <r8012_controletotaal>300000</r8012_controletotaal>
                                </Aangifte>
                            </Aangiften>
                            <r9002_inkomstenjaar>2000</r9002_inkomstenjaar>
                            <r9010_aantallogbestanden>3</r9010_aantallogbestanden>
                            <r9011_totaalaantalrecords>5</r9011_totaalaantalrecords>
                            <r9012_controletotaal>1</r9012_controletotaal>
                            <r9013_controletotaal>300000</r9013_controletotaal>
                        </Verzending>
                    </Verzendingen>"""
        self.assertXmlTreeEqual(
            self.get_xml_tree_from_string(resulting_xml),
            self.get_xml_tree_from_string(expected_281_50_xml),
        )

    def test_281_50_xml_generation_2_partners_eligible(self):
        """check the values generated and injected in the xml are as expected
        2 partners, each invoiced for 1.000,00 currency
        partner_a for an account tagged as commission and a full payment
        partner_b for an account tagged as commission, no payment
        """
        self.create_and_post_bill(self.partner_b, self.product_b, 1000.0, '2000-05-12')

        # make a payment to the vendor partner_a and reconcile it with the bill
        self.pay_bill(bill=self.move_a, amount=1000, date='2000-05-12')

        partners = self.partner_a + self.partner_b
        partner_325_form = partners._generate_form_325_values(self.debtor, self.sender, self.wizard_values)
        resulting_xml = self.debtor._generate_325_form_xml(partner_325_form)
        expected_281_50_xml = b"""<?xml version='1.0' encoding='utf-8'?>
                    <Verzendingen>
                        <Verzending>
                            <v0002_inkomstenjaar>2000</v0002_inkomstenjaar>
                            <v0010_bestandtype>BELCOTAX</v0010_bestandtype>
                            <v0011_aanmaakdatum>01-03-2022</v0011_aanmaakdatum>
                            <v0014_naam>company_1_data</v0014_naam>
                            <v0015_adres>Rue du Laid Burniat 5</v0015_adres>
                            <v0016_postcode>1348</v0016_postcode>
                            <v0017_gemeente>Ottignies-Louvain-la-Neuve </v0017_gemeente>
                            <v0018_telefoonnummer>+3222903490</v0018_telefoonnummer>
                            <v0021_contactpersoon>Because I am accountman!</v0021_contactpersoon>
                            <v0022_taalcode>2</v0022_taalcode>
                            <v0023_emailadres>accountman@test.com</v0023_emailadres>
                            <v0024_nationaalnr>0477472701</v0024_nationaalnr>
                            <v0025_typeenvoi>0</v0025_typeenvoi>
                            <Aangiften>
                                <Aangifte>
                                    <a1002_inkomstenjaar>2000</a1002_inkomstenjaar>
                                    <a1005_registratienummer>0477472701</a1005_registratienummer>
                                    <a1011_naamnl1>company_1_data</a1011_naamnl1>
                                    <a1013_adresnl>Rue du Laid Burniat 5</a1013_adresnl>
                                    <a1014_postcodebelgisch>1348</a1014_postcodebelgisch>
                                    <a1015_gemeente>Ottignies-Louvain-la-Neuve </a1015_gemeente>
                                    <a1016_landwoonplaats>00000</a1016_landwoonplaats>
                                    <a1020_taalcode>1</a1020_taalcode>
                                    <Opgaven>
                                        <Opgave32550>
                                            <Fiche28150>
                                                <f2002_inkomstenjaar>2000</f2002_inkomstenjaar>
                                                <f2005_registratienummer>0477472701</f2005_registratienummer>
                                                <f2008_typefiche>28150</f2008_typefiche>
                                                <f2009_volgnummer>1</f2009_volgnummer>
                                                <f2013_naam>SPRL Popiul</f2013_naam>
                                                <f2015_adres>Rue Arthur Libert, Longueville 8</f2015_adres>
                                                <f2016_postcodebelgisch>1325</f2016_postcodebelgisch>
                                                <f2017_gemeente>Chaumont-Gistoux</f2017_gemeente>
                                                <f2018_landwoonplaats>00000</f2018_landwoonplaats>
                                                <f2028_typetraitement>0</f2028_typetraitement>
                                                <f2029_enkelopgave325>0</f2029_enkelopgave325>
                                                <f2105_birthplace>0</f2105_birthplace>
                                                <f2112_buitenlandspostnummer/>
                                                <f2114_voornamen/>
                                                <f50_2030_aardpersoon>2</f50_2030_aardpersoon>
                                                <f50_2031_nihil>1</f50_2031_nihil>
                                                <f50_2059_totaalcontrole>200000</f50_2059_totaalcontrole>
                                                <f50_2060_commissies>0</f50_2060_commissies>
                                                <f50_2061_erelonenofvacatie>100000</f50_2061_erelonenofvacatie>
                                                <f50_2062_voordelenaardbedrag>0</f50_2062_voordelenaardbedrag>
                                                <f50_2063_kosten>0</f50_2063_kosten>
                                                <f50_2064_totaal>100000</f50_2064_totaal>
                                                <f50_2065_werkelijkbetaaldb>0</f50_2065_werkelijkbetaaldb>
                                                <f50_2066_sportremuneration>0</f50_2066_sportremuneration>
                                                <f50_2067_managerremuneration>0</f50_2067_managerremuneration>
                                                <f50_2099_comment/>
                                                <f50_2103_advantagenature/>
                                                <f50_2107_uitgeoefendberoep/>
                                                <f50_2109_fiscaalidentificat/>
                                                <f50_2110_kbonbr>0807677428</f50_2110_kbonbr>
                                            </Fiche28150>
                                            <Fiche28150>
                                                <f2002_inkomstenjaar>2000</f2002_inkomstenjaar>
                                                <f2005_registratienummer>0477472701</f2005_registratienummer>
                                                <f2008_typefiche>28150</f2008_typefiche>
                                                <f2009_volgnummer>2</f2009_volgnummer>
                                                <f2013_naam>partner_a</f2013_naam>
                                                <f2015_adres>Rue du Jacobet, 9</f2015_adres>
                                                <f2016_postcodebelgisch>7100</f2016_postcodebelgisch>
                                                <f2017_gemeente>La Louvi\xc3\xa8re</f2017_gemeente>
                                                <f2018_landwoonplaats>00000</f2018_landwoonplaats>
                                                <f2028_typetraitement>0</f2028_typetraitement>
                                                <f2029_enkelopgave325>0</f2029_enkelopgave325>
                                                <f2105_birthplace>0</f2105_birthplace>
                                                <f2112_buitenlandspostnummer/>
                                                <f2114_voornamen/>
                                                <f50_2030_aardpersoon>2</f50_2030_aardpersoon>
                                                <f50_2031_nihil>0</f50_2031_nihil>
                                                <f50_2059_totaalcontrole>300000</f50_2059_totaalcontrole>
                                                <f50_2060_commissies>100000</f50_2060_commissies>
                                                <f50_2061_erelonenofvacatie>0</f50_2061_erelonenofvacatie>
                                                <f50_2062_voordelenaardbedrag>0</f50_2062_voordelenaardbedrag>
                                                <f50_2063_kosten>0</f50_2063_kosten>
                                                <f50_2064_totaal>100000</f50_2064_totaal>
                                                <f50_2065_werkelijkbetaaldb>100000</f50_2065_werkelijkbetaaldb>
                                                <f50_2066_sportremuneration>0</f50_2066_sportremuneration>
                                                <f50_2067_managerremuneration>0</f50_2067_managerremuneration>
                                                <f50_2099_comment/>
                                                <f50_2103_advantagenature/>
                                                <f50_2107_uitgeoefendberoep/>
                                                <f50_2109_fiscaalidentificat/>
                                                <f50_2110_kbonbr>0475646428</f50_2110_kbonbr>
                                            </Fiche28150>
                                        </Opgave32550>
                                    </Opgaven>
                                    <r8002_inkomstenjaar>2000</r8002_inkomstenjaar>
                                    <r8005_registratienummer>0477472701</r8005_registratienummer>
                                    <r8010_aantalrecords>4</r8010_aantalrecords>
                                    <r8011_controletotaal>3</r8011_controletotaal>
                                    <r8012_controletotaal>500000</r8012_controletotaal>
                                </Aangifte>
                            </Aangiften>
                            <r9002_inkomstenjaar>2000</r9002_inkomstenjaar>
                            <r9010_aantallogbestanden>3</r9010_aantallogbestanden>
                            <r9011_totaalaantalrecords>6</r9011_totaalaantalrecords>
                            <r9012_controletotaal>3</r9012_controletotaal>
                            <r9013_controletotaal>500000</r9013_controletotaal>
                        </Verzending>
                    </Verzendingen>"""
        self.assertXmlTreeEqual(
            self.get_xml_tree_from_string(resulting_xml),
            self.get_xml_tree_from_string(expected_281_50_xml),
        )

    def test_281_50_partner_remuneration_should_include_amount_directly_put_as_expense(self):
        expense_account_atn_281_50 = self.copy_account(self.company_data['default_account_expense'])
        expense_account_atn_281_50.tag_ids = self.tag_281_50_atn

        statement = self.env['account.bank.statement'].create({
            'name': '281.50 test',
            'date': fields.Date.from_string('2000-05-12'),
            'balance_end_real': -1000.0,
            'journal_id': self.company_data['default_journal_bank'].id,
            'line_ids': [
                (0, 0, {
                    'payment_ref': 'line2',
                    'partner_id': self.partner_b.id,
                    'amount': -1000.0,
                    'date': fields.Date.from_string('2000-05-12'),
                }),
            ],
        })
        statement.button_post()
        statement.line_ids.reconcile([{
            'balance': 1000.0,
            'account_id': expense_account_atn_281_50.id,
            'name': "Payment sent without any invoice for atn reason",
        }])

        partner_325_form = self.partner_b._generate_form_325_values(self.debtor, self.sender, self.wizard_values)
        atn_calculated_amount = partner_325_form.get('Fiches28150')[0].get('F50_2062')
        paid_amount_to_this_partner = partner_325_form.get('Fiches28150')[0].get('F50_2065')

        self.assertEqual(atn_calculated_amount, 1000.0)
        self.assertEqual(paid_amount_to_this_partner, 1000.0)

    def test_281_50_partner_remuneration_shouldnt_include_commission_from_previous_year(self):
        previous_year_bill = self.create_and_post_bill(self.partner_b, self.product_b, 500.0, '1999-05-12')
        self.pay_bill(bill=previous_year_bill, amount=250, date='1999-05-12')

        # make a payment to the vendor partner_b and reconcile it with the bill for the previous year
        self.pay_bill(bill=previous_year_bill, amount=250, date='2000-05-12')

        partner_325_form = self.partner_b._generate_form_325_values(self.debtor, self.sender, self.wizard_values)
        commission_calculated_amount = partner_325_form.get('Fiches28150')[0].get('F50_2060')
        paid_amount_to_this_partner = partner_325_form.get('Fiches28150')[0].get('F50_2065')

        self.assertEqual(commission_calculated_amount, 0.0)
        self.assertEqual(paid_amount_to_this_partner, 250.0)

    def test_281_50_wizard_should_return_action_to_download_file(self):
        # press button "both pdf and xml"
        action = self.env['l10n_be_reports.281_50_wizard'].create(self.wizard_values).action_generate_281_50_form()
        self.assertEqual({
            'type': 'ir.actions.act_url',
            'name': 'Download 281.50 Form',
            'url': f"/web/content/res.partner/{self.debtor.id}/form_file/281_50_forms_2000.zip?download=true"
        }, action)
