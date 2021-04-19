# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

import base64

from collections import defaultdict
from datetime import date
from lxml import etree

from dateutil.relativedelta import relativedelta
from odoo import api, fields, models, _
from odoo.modules.module import get_resource_path
from odoo.exceptions import UserError
from odoo.tools import format_date


class L10nBe273S(models.Model):
    _name = 'l10n_be.273s'
    _description = '273S Sheet'
    _order = 'period'

    @api.model
    def default_get(self, field_list=None):
        if self.env.company.country_id.code != "BE":
            raise UserError(_('You must be logged in a Belgian company to use this feature'))
        return super().default_get(field_list)

    year = fields.Integer(required=True, default=lambda self: fields.Date.today().year)
    month = fields.Selection([
        ('1', 'January'),
        ('2', 'February'),
        ('3', 'March'),
        ('4', 'April'),
        ('5', 'May'),
        ('6', 'June'),
        ('7', 'July'),
        ('8', 'August'),
        ('9', 'September'),
        ('10', 'October'),
        ('11', 'November'),
        ('12', 'December'),
    ], required=True, default=lambda self: str((fields.Date.today() + relativedelta(months=-1)).month))
    period = fields.Date(
        'Period', compute='_compute_period', store=True)
    company_id = fields.Many2one('res.company', default=lambda self: self.env.company)
    currency_id = fields.Many2one('res.currency', related='company_id.currency_id')
    state = fields.Selection([
        ('draft', 'Draft'),
        ('waiting', 'Waiting'),
        ('done', 'Done')
    ], default='draft', compute="_compute_state", store=True)

    pdf_file = fields.Binary(string="PDF File")
    pdf_filename = fields.Char("PDF Filename")

    xml_file = fields.Binary(string="XML File")
    xml_filename = fields.Char("XML Filename")
    xml_validation_state = fields.Selection([
        ('normal', 'N/A'),
        ('done', 'Valid'),
        ('invalid', 'Invalid'),
    ], default='normal', compute='_compute_validation_state', store=True)
    error_message = fields.Char('Error Message', compute='_compute_validation_state', store=True)

    def name_get(self):
        return [(
            record.id,
            format_date(self.env, record.period, date_format="MMMM y", lang_code=self.env.user.lang)
        ) for record in self]

    @api.depends('year', 'month')
    def _compute_period(self):
        for record in self:
            record.period = date(record.year, int(record.month), 1)

    @api.depends('xml_file', 'pdf_file', 'xml_validation_state')
    def _compute_state(self):
        for record in self:
            state = 'draft'
            if record.xml_file and record.pdf_file and record.xml_validation_state:
                state = 'done'
            elif record.xml_file or record.pdf_file:
                state = 'waiting'
            record.state = state

    @api.depends('xml_file')
    def _compute_validation_state(self):
        xsd_schema_file_path = get_resource_path(
            'l10n_be_hr_payroll',
            'data',
            'withholdingTaxDeclarationOriginal_202012.xsd',
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

    def _get_rendering_data(self):
        date_from = self.period + relativedelta(day=1)
        date_to = self.period + relativedelta(day=31)
        payslips = self.env['hr.payslip'].search([
            ('state', 'in', ['done', 'paid']),
            ('company_id', '=', self.company_id.id),
            ('date_from', '>=', date_from),
            ('date_to', '<=', date_to)])
        employees = payslips.mapped('employee_id').filtered(lambda e: not e._is_niss_valid())
        if employees:
            raise UserError(_('Invalid NISS number for those employees:\n %s', '\n'.join(employees.mapped('name'))))

        # The first threshold is at 16320 € of gross IP, so we only consider the rate at 7.5 %. 
        # YTI TODO: Handle different thresholds in master
        gross_amount = sum(p._get_salary_line_total('IP') for p in payslips)
        tax_amount = - sum(p._get_salary_line_total('IP.DED') for p in payslips)

        mapped_ip = defaultdict(lambda: [0, 0])
        for payslip in payslips.sudo():
            ip_amount = payslip._get_salary_line_total('IP')
            if ip_amount:
                mapped_ip[payslip.employee_id][0] += payslip._get_salary_line_total('IP')
                mapped_ip[payslip.employee_id][1] += payslip._get_salary_line_total('IP.DED')

        currency = self.env.company.currency_id

        return {
            'unique_reference': self.id,
            'company_info': {
                'identification': "BE%s" % (self.company_id.l10n_be_company_number),
                'name': self.company_id.name,
                'address': self.company_id.partner_id._display_address(),
                'phone': self.company_id.phone,
                'email': self.company_id.email,
            },
            'period': fields.Date.today(),
            'declaration': {
                'gross_amount': round(gross_amount / 2, 2) * 2,  # To avoid 1 cent diff (eg: 286079.05)
                'deductable_costs':  {
                    'fixed': gross_amount / 2,
                    'actual': 0,
                },
                'taxable_amount': gross_amount / 2,
                'rate': 15.0,
                'tax_amount': tax_amount,
            },
            'beneficiaries': [
                {
                    'identification': {
                        'nature': "Citizen",
                        'name': employee.name,
                        'street': employee.address_home_id.street,
                        'city': employee.address_home_id.city,
                        'zip': employee.address_home_id.zip,
                        'country': employee.address_home_id.country_id.code,
                        'nationality': employee.country_id.code,
                        'identification': employee.niss.replace('-', '').replace('.', ''),
                    },
                    'gross_amount': ip_values[0],
                    'deductable_costs': {
                        'fixed': ip_values[0] / 2,
                        'actual': 0,
                    },
                    'tax_amount': ip_values[1],
                } for employee, ip_values in mapped_ip.items()],
            'to_eurocent': lambda amount: '%s' % int(amount * 100),
            'to_monetary': lambda amount: '%.2f %s' % (amount, currency.symbol),
        }

    def action_generate_pdf(self):
        self.ensure_one()
        export_273S_pdf, dummy = self.env.ref('l10n_be_hr_payroll.action_report_ip_273S').sudo()._render_qweb_pdf(res_ids=self.ids, data=self._get_rendering_data())
        self.pdf_filename = '%s-273S_report.pdf' % (self.period.strftime('%B%Y'))
        self.pdf_file = base64.encodebytes(export_273S_pdf)

    def action_generate_xml(self):
        self.ensure_one()
        self.xml_filename = '%s-273S_report.xml' % (self.period.strftime('%B%Y'))
        xml_str = self.env.ref('l10n_be_hr_payroll.273S_xml_report')._render(self._get_rendering_data())

        # Prettify xml string
        root = etree.fromstring(xml_str, parser=etree.XMLParser(remove_blank_text=True))
        xml_formatted_str = etree.tostring(root, pretty_print=True, encoding='utf-8', xml_declaration=True)

        self.xml_file = base64.encodebytes(xml_formatted_str)

    def action_validate(self):
        self.ensure_one()
