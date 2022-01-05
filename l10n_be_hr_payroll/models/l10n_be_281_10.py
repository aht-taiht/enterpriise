# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

import base64
import io
import logging
import zipfile

from collections import defaultdict
from datetime import date
from lxml import etree
from odoo import api, fields, models, _
from odoo.exceptions import UserError
from odoo.modules.module import get_resource_path

_logger = logging.getLogger(__name__)

# Sources:
# - Technical Doc https://finances.belgium.be/fr/E-services/Belcotaxonweb/documentation-technique
# - "Avis aux débiteurs" https://finances.belgium.be/fr/entreprises/personnel_et_remuneration/avis_aux_debiteurs#q2

COUNTRY_CODES = {
    'BE': '00000',
    'ES': '00109',
    'FR': '00111',
    'GR': '00112',
    'LU': '00113',
    'DE': '00103',
    'RO': '00124',
    'IT': '00128',
    'NL': '00129',
    'TR': '00262',
    'US': '00402',
    'MA': 'O0354',
}


class L10nBe28110(models.Model):
    _name = 'l10n_be.281_10'
    _description = 'HR Payroll 281.10 Wizard'
    _order = 'reference_year'

    def _get_years(self):
        return [(str(i), i) for i in range(fields.Date.today().year, 2009, -1)]

    @api.model
    def default_get(self, field_list):
        if self.env.company.country_id.code != "BE":
            raise UserError(_('You must be logged in a Belgian company to use this feature'))
        return super().default_get(field_list)

    company_id = fields.Many2one('res.company', default=lambda self: self.env.company)
    state = fields.Selection([('generate', 'generate'), ('get', 'get')], default='generate')
    reference_year = fields.Selection(
        selection='_get_years', string='Reference Year', required=True,
        default=lambda x: str(fields.Date.today().year - 1))
    is_test = fields.Boolean(string="Is It a test ?", default=False)
    type_sending = fields.Selection([
        ('0', 'Original send'),
        ('1', 'Send grouped corrections'),
        ], string="Sending Type", default='0', required=True)
    type_treatment = fields.Selection([
        ('0', 'Original'),
        ('1', 'Modification'),
        ('2', 'Add'),
        ('3', 'Cancel'),
        ], string="Treatment Type", default='0', required=True)
    pdf_file = fields.Binary('PDF File', readonly=True, attachment=False)
    xml_file = fields.Binary('XML File', readonly=True, attachment=False)
    pdf_filename = fields.Char()
    xml_filename = fields.Char()
    documents_enabled = fields.Boolean(compute='_compute_documents_enabled')
    xml_validation_state = fields.Selection([
        ('normal', 'N/A'),
        ('done', 'Valid'),
        ('invalid', 'Invalid'),
    ], default='normal', compute='_compute_validation_state', store=True)
    error_message = fields.Char('Error Message', compute='_compute_validation_state', store=True)

    @api.depends('xml_file')
    def _compute_validation_state(self):
        xsd_schema_file_path = get_resource_path(
            'l10n_be_hr_payroll',
            'data',
            '161-xsd-2021-20211223.xsd',
        )
        xsd_root = etree.parse(xsd_schema_file_path)
        schema = etree.XMLSchema(xsd_root)

        no_xml_file_records = self.filtered(lambda record: not record.xml_file)
        no_xml_file_records.update({
            'xml_validation_state': 'normal',
            'error_message': False})
        for record in self - no_xml_file_records:
            xml_root = etree.fromstring(base64.b64decode(record.xml_file))
            try:
                schema.assertValid(xml_root)
                record.xml_validation_state = 'done'
            except etree.DocumentInvalid as err:
                record.xml_validation_state = 'invalid'
                record.error_message = str(err)

    def name_get(self):
        return [(
            record.id,
            '%s%s' % (record.reference_year, _('- Test') if record.is_test else '')
        ) for record in self]

    @api.model
    def _check_employees_configuration(self, employees):
        invalid_employees = employees.filtered(lambda e: not (e.company_id and e.company_id.street and e.company_id.zip and e.company_id.city and e.company_id.phone and e.company_id.vat))
        if invalid_employees:
            raise UserError(_("The company is not correctly configured on your employees. Please be sure that the following pieces of information are set: street, zip, city, phone and vat") + '\n' + '\n'.join(invalid_employees.mapped('name')))

        invalid_employees = employees.filtered(
            lambda e: not e.address_home_id or not e.address_home_id.street or not e.address_home_id.zip or not e.address_home_id.city or not e.address_home_id.country_id)
        if invalid_employees:
            raise UserError(_("The following employees don't have a valid private address (with a street, a zip, a city and a country):\n%s", '\n'.join(invalid_employees.mapped('name'))))

        if not all(emp.contract_ids and emp.contract_id for emp in employees):
            raise UserError(_('Some employee has no contract.'))

        invalid_employees = employees.filtered(lambda e: not e._is_niss_valid())
        if invalid_employees:
            raise UserError(_('Invalid NISS number for those employees:\n %s', '\n'.join(invalid_employees.mapped('name'))))

        invalid_country_codes = employees.address_home_id.country_id.filtered(lambda c: c.code not in COUNTRY_CODES)
        if invalid_country_codes:
            raise UserError(_('Unsupported country code %s. Please contact an administrator.', ', '.join(invalid_country_codes.mapped('code'))))

    @api.model
    def _get_lang_code(self, lang):
        if lang == 'nl_NL':
            return 1
        elif lang == 'fr_FR':
            return 2
        elif lang == 'de_DE':
            return 3
        return 2

    @api.model
    def _get_country_code(self, country):
        return COUNTRY_CODES[country.code]

    @api.model
    def _get_atn_nature(self, payslips):
        result = ''
        if any(payslip.vehicle_id for payslip in payslips):
            result += 'F'
        if any(payslip.contract_id.has_laptop for payslip in payslips):
            result += 'H'
        if any(payslip.contract_id.internet for payslip in payslips):
            result += 'I'
        if any(payslip.contract_id.mobile for payslip in payslips):
            result += 'K'
        return result

    def _get_rendering_data(self):
        main_data = {
            'v0002_inkomstenjaar': self.reference_year,
            'v0010_bestandtype': 'BELCOTST' if self.is_test else 'BELCOTAX',
            'v0011_aanmaakdatum': fields.Date.today().strftime('%d-%m-%Y'),
            'v0014_naam': self.company_id.name,
            'v0015_adres': self.company_id.street,
            'v0016_postcode': self.company_id.zip,
            'v0017_gemeente': self.company_id.city,
            'v0018_telefoonnummer': self.company_id.phone,
            'v0021_contactpersoon': self.env.user.name,
            'v0022_taalcode': self._get_lang_code(self.env.user.employee_id.address_home_id.lang),
            'v0023_emailadres': self.env.user.email,
            'v0024_nationaalnr': self.company_id.vat.replace('BE', ''),
            'v0025_typeenvoi': self.type_sending,

            'a1002_inkomstenjaar': self.reference_year,
            'a1005_registratienummer': self.company_id.vat.replace('BE', ''),
            'a1011_naamnl1': self.company_id.name,
            'a1013_adresnl': self.company_id.street,
            'a1015_gemeente': self.company_id.zip,
            'a1020_taalcode': 1,
        }

        employees_data = []

        all_payslips = self.env['hr.payslip'].search([
            ('date_to', '<=', date(int(self.reference_year), 12, 31)),
            ('date_from', '>=', date(int(self.reference_year), 1, 1)),
            ('state', 'in', ['done', 'paid']),
        ])
        all_employees = all_payslips.mapped('employee_id')
        self._check_employees_configuration(all_employees)

        employee_payslips = defaultdict(lambda: self.env['hr.payslip'])
        for payslip in all_payslips:
            employee_payslips[payslip.employee_id] |= payslip

        line_codes = [
            'NET', 'PAY_SIMPLE', 'PPTOTAL', 'M.ONSS', 'ATN.INT', 'ATN.MOB', 'ATN.LAP',
            'ATN.CAR', 'REP.FEES', 'PUB.TRANS', 'EmpBonus.1', 'GROSS'
        ]
        all_line_values = all_payslips._get_line_values(line_codes)

        belgium = self.env.ref('base.be')
        sequence = 0

        warrant_structure = self.env.ref('l10n_be_hr_payroll.hr_payroll_structure_cp200_structure_warrant')
        holiday_n_structure = self.env.ref('l10n_be_hr_payroll.hr_payroll_structure_cp200_employee_departure_n_holidays')
        holiday_n1_structure = self.env.ref('l10n_be_hr_payroll.hr_payroll_structure_cp200_employee_departure_n1_holidays')

        for employee in employee_payslips:
            is_belgium = employee.address_home_id.country_id == belgium
            payslips = employee_payslips[employee]
            sequence += 1

            mapped_total = {
                code: sum(all_line_values[code][p.id]['total'] for p in payslips)
                for code in line_codes}

            total_gross = mapped_total['GROSS']
            warrant_gross = sum(all_line_values['GROSS'][p.id]['total'] for p in payslips if p.struct_id == warrant_structure)
            holiday_gross = sum(all_line_values['GROSS'][p.id]['total'] for p in payslips if p.struct_id in holiday_n_structure + holiday_n1_structure)
            common_gross = total_gross - warrant_gross - holiday_gross

            sheet_values = {
                'employee': employee,
                'employee_id': employee.id,
                'f2002_inkomstenjaar': self.reference_year,
                'f2005_registratienummer': self.company_id.vat.replace('BE', ''),
                'f2008_typefiche': '28110',
                'f2009_volgnummer': sequence,
                'f2011_nationaalnr': employee.niss,
                'f2013_naam': employee.name,
                'f2015_adres': employee.address_home_id.street,
                'f2016_postcodebelgisch': employee.address_home_id.zip if is_belgium else '0',
                'employee_city': employee.address_home_id.city,
                'f2018_landwoonplaats': '0' if is_belgium else self._get_country_code(employee.address_home_id.country_id),
                'f2027_taalcode': self._get_lang_code(employee.address_home_id.lang),
                'f2028_typetraitement': self.type_treatment,
                'f2029_enkelopgave325': 0,
                'f2112_buitenlandspostnummer': employee.address_home_id.zip if not is_belgium else '0',
                'f2114_voornamen': employee.name,
                'f10_2031_compensationwithstandards': 0,
                'f10_2033_compensationwithdocuments': 0,
                'f10_2034_ex': 0,
                'f10_2035_verantwoordingsstukken': 0,
                'f10_2036_inwonersdeenfr': 0,
                'f10_2037_vergoedingkosten': 0,
                'f10_2038_seasonalworker': 0,
                'f10_2039_optiebuitvennoots': '0',
                'f10_2040_individualconvention': 0,
                'f10_2041_overheidspersoneel': 0,
                'f10_2042_sailorcode': 0,
                'f10_2045_code': 0,
                # 'f10_2055_datumvanindienstt': employee.first_contract_date.strftime('%d/%m/%Y') if employee.first_contract_date.year == self.reference_year else '',
                'f10_2055_datumvanindienstt': employee.first_contract_date.strftime('%d/%m/%Y') if employee.first_contract_date else '',
                'f10_2056_datumvanvertrek': employee.end_notice_period.strftime('%d/%m/%Y') if employee.end_notice_period else '',
                'f10_2058_km': employee.has_bicycle and employee.km_home_work or 0.0,
                # f10_2059_totaalcontrole
                'f10_2060_gewonebezoldiginge': round(common_gross, 2),
                'f10_2061_bedragoveruren300horeca': 0,
                # f10_2062_totaal
                'f10_2063_vervroegdvakantieg': round(holiday_gross, 2),
                'f10_2064_afzbelachterstall': 0,
                'f10_2065_opzeggingsreclasseringsverg': 0,
                'f10_2066_impulsfund': 0,
                'f10_2067_rechtvermindering66_81': 0,
                'f10_2068_rechtvermindering57_75': 0,
                'f10_2069_fidelitystamps': 0,
                'f10_2070_decemberremuneration': 0,
                'f10_2071_totalevergoeding': 0,
                'f10_2072_pensioentoezetting':  0,
                'f10_2073_tipamount': 0,
                'f10_2074_bedrijfsvoorheffing': round(mapped_total['PPTOTAL'], 2),  # 2.074 = 2.131 + 2.133. YTI Is it ok to include PROF_TAX / should include Double holidays?
                'f10_2075_bijzonderbijdrage': round(-mapped_total['M.ONSS'], 2),
                'f10_2076_voordelenaardbedrag': round(sum(mapped_total[code] for code in ['ATN.INT', 'ATN.MOB', 'ATN.LAP', 'ATN.CAR']), 2),
                # f10_2077_totaal
                'f10_2078_compensationamountwithoutstandards': round(mapped_total['REP.FEES'], 2),
                'f10_2080_detacheringsvergoed': 0,
                'f10_2081_gewonebijdragenenpremies': 0,
                'f10_2082_bedrag': round(warrant_gross, 2),
                'f10_2083_bedrag': 0,
                'f10_2084_mobiliteitsvergoedi': 0,
                'f10_2085_forfbezoldiging': 0,
                'f10_2086_openbaargemeenschap': round(mapped_total['PUB.TRANS'], 2),
                'f10_2087_bedrag': 0,
                'f10_2088_andervervoermiddel': 0,
                'f10_2090_outborderdays': 0,
                'f10_2092_othercode1': 0,
                'f10_2094_othercode2': 0,
                'f10_2095_aantaluren': 0,
                'f10_2096_othercode3': 0,
                'f10_2097_aantaluren': 0,
                'f10_2098_othercode4': 0,
                'f10_2099_aard': self._get_atn_nature(payslips),
                'f10_2102_kas': 0,
                'f10_2103_kasvrijaanvullendpensioen': 0,
                'f10_2106_percentages': '53.5' if round(warrant_gross, 2) else '', # YTI FIXME: Retrieve actual percentage
                'f10_2109_fiscaalidentificat': employee.identification_id if employee.country_id != belgium else '',
                'f10_2110_aantaloveruren360': 0,
                'f10_2111_achterstalloveruren300horeca': 0,
                'f10_2113_forfaitrsz': 0,
                'f10_2115_bonus': round(mapped_total['EmpBonus.1'], 2),
                'f10_2116_badweatherstamps': 0,
                'f10_2117_nonrecurrentadvantages': 0,
                'f10_2118_amountovertime180secondsemester': 0,
                'f10_2119_sportremuneration': 0,
                'f10_2120_sportvacancysavings': 0,
                'f10_2121_sportoutdated': 0,
                'f10_2122_sportindemnificationofretraction': 0,
                'f10_2123_managerremuneration': 0,
                'f10_2124_managervacancysavings': 0,
                'f10_2125_manageroutdated': 0,
                'f10_2126_managerindemnificationofretraction': 0,
                'f10_2127_nonrecurrentadvantagesoutdated': 0,
                'f10_2128_vrijaanvullendpensioenwerknemers': 0,
                'f10_2130_privatepc': 0,
                'f10_2131_bedrijfsvoorheffingvanwerkgever': round(mapped_total['PPTOTAL'], 2),
                'f10_2132_amountovertime180firstsemester': 0,
                'f10_2133_bedrijfsvoorheffingbuitenlvenverbondenwerkgever': 0,
                'f10_2134_totaalbedragmobiliteitsbudget': 0,
                'f10_2135_amountpaidforvolontarysuplementaryhourscovid': 0,
                'f10_2136_amountcontractofstudent': 0,
                'f10_2137_amountstudent2020oruntilthirdquarter2021': 0,
                'f10_2138_chequesofconsumptions': 0,
                'f10_2141_occasionalworkhoreca': 0,
                'f10_2142_aantaloveruren180': 0,
                'f10_2143_bedragoveruren360horeca': 0,
                'f10_2165_achterstalloveruren360horeca': 0,
                'f10_2166_flexi_job': 0,
                'f10_2167_aantaloveruren300horeca': 0,
                'f10_2168_achterstallaantaloveruren300horeca': 0,
                'f10_2169_aantaloveruren360horeca': 0,
                'f10_2170_achterstallaantaloveruren360horeca': 0,
                'f10_2177_winstpremies': 0,
                'f10_2179_startersjob': 0,
                'f10_2180_onkostenbrandweerenambulanciers': 0,
                'f10_2181_remunerationetrang': 0,
                'f10_2182_aandelenetrang': 0,
                'f10_2183_bonuspremieoaandelenoptiesetrang': 0,
                'f10_2184_anderevaaetrang': 0,
                'f10_2185_amountother1': 0,
                'f10_2186_amountother2': 0,
                'f10_2187_amountother3': 0,
                'f10_2188_amountother4': 0,
                'f10_2190_covidovertimeremunerationfirstsemester': 0,
                'f10_2191_covidovertimeremunerationsecondsemester': 0,
                'f10_2192_covidovertimehoursfirstsemester': 0,
                'f10_2193_covidovertimehourssecondsemester': 0,
                'f10_2194_covidovertimehourstotal': 0,
                'f10_2195_covidovertimehours2020': 0,
                'f10_2196_covidovertimeremuneration2020': 0,
                'f10_2198_coronabonus': 0,
            }
            # Somme de 2.060 + 2.076 + 2069 + 2.082 + 2.083
            sheet_values['f10_2062_totaal'] = round(sum(sheet_values[code] for code in [
                'f10_2060_gewonebezoldiginge',
                'f10_2076_voordelenaardbedrag',
                'f10_2069_fidelitystamps',
                'f10_2082_bedrag',
                'f10_2083_bedrag']), 2)

            # Somme de 2.086 + 2.087 + 2.088
            sheet_values['f10_2077_totaal'] = round(sum(sheet_values[code] for code in [
                'f10_2086_openbaargemeenschap',
                'f10_2087_bedrag',
                'f10_2088_andervervoermiddel']), 2)

            # Somme de 2060 à 2088, f10_2062_totaal et f10_2077_totaal inclus
            sheet_values['f10_2059_totaalcontrole'] = round(sum(sheet_values[code] for code in [
                'f10_2060_gewonebezoldiginge',
                'f10_2061_bedragoveruren300horeca',
                'f10_2062_totaal',
                'f10_2064_afzbelachterstall',
                'f10_2065_opzeggingsreclasseringsverg',
                'f10_2066_impulsfund',
                'f10_2067_rechtvermindering66_81',
                'f10_2068_rechtvermindering57_75',
                'f10_2069_fidelitystamps',
                'f10_2070_decemberremuneration',
                'f10_2071_totalevergoeding',
                'f10_2072_pensioentoezetting',
                'f10_2074_bedrijfsvoorheffing',
                'f10_2075_bijzonderbijdrage',
                'f10_2076_voordelenaardbedrag',
                'f10_2077_totaal',
                'f10_2080_detacheringsvergoed',
                'f10_2081_gewonebijdragenenpremies',
                'f10_2082_bedrag',
                'f10_2083_bedrag',
                'f10_2084_mobiliteitsvergoedi',
                'f10_2085_forfbezoldiging',
                'f10_2086_openbaargemeenschap',
                'f10_2087_bedrag',
                'f10_2088_andervervoermiddel']), 2)

            employees_data.append(sheet_values)

        sheets_count = len(employees_data)
        sum_2009 = round(sum(sheet_values['f2009_volgnummer'] for sheet_values in employees_data), 2)
        sum_2059 = round(sum(sheet_values['f10_2059_totaalcontrole'] for sheet_values in employees_data), 2)
        sum_2074 = round(sum(sheet_values['f10_2074_bedrijfsvoorheffing'] for sheet_values in employees_data), 2)
        total_data = {
            'r8002_inkomstenjaar': self.reference_year,
            'r8010_aantalrecords': sheets_count,
            'r8011_controletotaal': sum_2009,
            'r8012_controletotaal': sum_2059,
            'r8013_totaalvoorheffingen': sum_2074,
            'r9002_inkomstenjaar': self.reference_year,
            'r9010_aantallogbestanden': sheets_count,
            'r9011_totaalaantalrecords': sheets_count,
            'r9012_controletotaal': sum_2009,
            'r9013_controletotaal': sum_2059,
            'r9014_controletotaal': sum_2074,
        }

        return {'data': main_data, 'employees_data': employees_data, 'total_data': total_data}

    def _action_generate_pdf(self, post_process=False):
        rendering_data = self._get_rendering_data()
        for sheet_values in rendering_data['employees_data']:
            for key, value in sheet_values.items():
                if not value:
                    sheet_values[key] = 'Néant'
        template_sudo = self.env.ref('l10n_be_hr_payroll.action_report_employee_281_10').sudo()

        pdf_files = []
        sheet_count = len(rendering_data['employees_data'])
        counter = 1
        for sheet in rendering_data['employees_data']:
            _logger.info('Printing 281.10 sheet (%s/%s)', counter, sheet_count)
            counter += 1
            sheet_filename = '%s-%s-281_10' % (sheet['f2002_inkomstenjaar'], sheet['f2013_naam'])
            sheet_file, dummy = template_sudo._render_qweb_pdf(sheet['employee_id'], data={**sheet, **rendering_data['data']})
            pdf_files.append((sheet['employee'], sheet_filename, sheet_file))

        if pdf_files:
            filename, binary = self._process_files(pdf_files, default_filename='281.10 PDF - %s.zip' % fields.Date.today(), post_process=post_process)
            if not post_process:
                self.pdf_filename = filename
                self.pdf_file = binary

        self.state = 'get'

    def action_generate_pdf(self):
        return self._action_generate_pdf()

    def _post_process_files(self, files):
        return

    def _process_files(self, files, default_filename='281.zip', post_process=False):
        """Groups files into a single file
        :param files: list of tuple (employee, filename, data)
        :return: tuple filename, encoded data
        """
        if post_process:
            self._post_process_files(files)
            return False, False

        if len(files) == 1:
            dummy, filename, data = files[0]
            return filename, base64.encodebytes(data)

        stream = io.BytesIO()
        with zipfile.ZipFile(stream, 'w') as doc_zip:
            for dummy, filename, data in files:
                doc_zip.writestr(filename, data, compress_type=zipfile.ZIP_DEFLATED)

        filename = default_filename
        return filename, base64.encodebytes(stream.getvalue())

    def action_generate_xml(self):
        self.ensure_one()
        self.xml_filename = '%s-281_10_report.xml' % (self.reference_year)
        xml_str = self.env.ref('l10n_be_hr_payroll.281_10_xml_report')._render(self._get_rendering_data())

        # Prettify xml string
        root = etree.fromstring(xml_str, parser=etree.XMLParser(remove_blank_text=True))
        xml_formatted_str = etree.tostring(root, pretty_print=True, encoding='utf-8', xml_declaration=True)

        self.xml_file = base64.encodebytes(xml_formatted_str)
        self.state = 'get'
