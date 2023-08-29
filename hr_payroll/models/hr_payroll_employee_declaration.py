# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

import logging

from collections import defaultdict

from odoo import models, fields, api, _

_logger = logging.getLogger(__name__)


class HrPayrollEmployeeDeclaration(models.Model):
    _name = 'hr.payroll.employee.declaration'
    _description = 'Payroll Employee Declaration'
    _rec_name = 'employee_id'

    res_model = fields.Char(
        'Declaration Model Name', required=True, index=True)
    res_id = fields.Many2oneReference(
        'Declaration Model Id', index=True, model_field='res_model', required=True)
    employee_id = fields.Many2one('hr.employee')
    company_id = fields.Many2one('res.company', default=lambda self: self.env.company, required=True)
    pdf_file = fields.Binary('PDF File', readonly=True, attachment=False)
    pdf_filename = fields.Char()
    pdf_to_generate = fields.Boolean()
    state = fields.Selection([
        ('draft', 'Draft'),
        ('pdf_to_generate', 'Queued PDF generation'),
        ('pdf_generated', 'Generated PDF'),
    ], compute='_compute_state', store=True)

    @api.depends('pdf_to_generate', 'pdf_file')
    def _compute_state(self):
        for declaration in self:
            if declaration.pdf_to_generate:
                declaration.state = 'pdf_to_generate'
            elif declaration.pdf_file:
                declaration.state = 'pdf_generated'
            else:
                declaration.state = 'draft'

    def _generate_pdf(self):
        report_sudo = self.env["ir.actions.report"].sudo()
        declarations_by_sheet = defaultdict(lambda: self.env['hr.payroll.employee.declaration'])
        for declaration in self:
            declarations_by_sheet[(declaration.res_model, declaration.res_id)] += declaration


        for (res_model, res_id), declarations in declarations_by_sheet.items():
            sheet = self.env[res_model].browse(res_id)
            report_id = sheet._get_pdf_report().id
            rendering_data = sheet._get_rendering_data(declarations.employee_id)
            rendering_data = sheet._post_process_rendering_data_pdf(rendering_data)

            pdf_files = []
            sheet_count = len(rendering_data)
            counter = 1
            for employee, employee_data in rendering_data.items():
                _logger.info('Printing %s (%s/%s)', sheet._description, counter, sheet_count)
                counter += 1
                sheet_filename = sheet._get_pdf_filename(employee)
                sheet_file, dummy = report_sudo.with_context(lang=employee.lang)._render_qweb_pdf(
                    report_id,
                    [employee.id], data={'report_data': employee_data, 'employee': employee})
                pdf_files.append((employee, sheet_filename, sheet_file))
            if pdf_files:
                sheet._process_files(pdf_files)

    @api.model_create_multi
    def create(self, vals_list):
        declarations = super().create(vals_list)
        if any(declaration.pdf_to_generate for declaration in declarations):
            self.env.ref('hr_payroll.ir_cron_generate_payslip_pdfs')._trigger()
        return declarations

    def write(self, vals):
        res = super().write(vals)
        if vals.get('pdf_to_generate'):
            self.env.ref('hr_payroll.ir_cron_generate_payslip_pdfs')._trigger()
        return res

    def action_generate_pdf(self):
        if self:
            self.write({'pdf_to_generate': True})
            self.env.ref('hr_payroll.ir_cron_generate_payslip_pdfs')._trigger()
            message = _("PDF generation started. It will be available shortly.")
        else:
            message = _("Please select the declarations for which you want to generate a PDF.")
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'type': 'success',
                'message': message,
                'next': {
                    'type': 'ir.actions.client',
                    'tag': 'reload'
                }
            }
        }
