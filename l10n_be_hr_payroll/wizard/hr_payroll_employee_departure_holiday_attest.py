# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

from dateutil.relativedelta import relativedelta

from odoo import api, fields, models, _
from odoo.exceptions import UserError


class HrPayslipEmployeeDepartureHoliday(models.TransientModel):
    _name = 'hr.payslip.employee.depature.holiday.attests'
    _description = 'Manage the Employee Departure Holiday Attests'

    @api.model
    def default_get(self, field_list=None):
        if self.env.company.country_id.code != "BE":
            raise UserError(_('You must be logged in a Belgian company to use this feature'))
        return super().default_get(field_list)

    employee_id = fields.Many2one('hr.employee', string='Employee', default=lambda self: self.env.context.get('active_id'))

    payslip_n_ids = fields.Many2many(
        'hr.payslip', string='Payslips N',
        compute='_compute_history', readonly=False, store=False)
    payslip_n1_ids = fields.Many2many(
        'hr.payslip', string='Payslips N-1',
        compute='_compute_history', readonly=False, store=False)

    net_n = fields.Monetary(
        'Gross Annual Remuneration Current Year',
        compute='_compute_net_n', store=True, readonly=False)
    net_n1 = fields.Monetary(
        'Gross Annual Remuneration Previous Year',
        compute='_compute_net_n1', store=True, readonly=False)
    currency_id = fields.Many2one(related='employee_id.contract_id.currency_id')

    time_off_n_ids = fields.Many2many(
        'hr.leave', string='Time Off N', compute='_compute_history', readonly=False, store=False)
    time_off_allocation_n_ids = fields.Many2many(
        'hr.leave.allocation', string='Allocations N',
        compute='_compute_history', readonly=False, store=False)

    time_off_taken = fields.Float(
        'Time off taken during current year',
        compute='_compute_time_off_taken', store=True, readonly=False)
    time_off_allocated = fields.Float(
        'Time off allocated during current year',
        compute='_compute_time_off_allocated', store=True, readonly=False)

    unpaid_time_off_n = fields.Float('Days Unpaid time off current year', help="Number of days of unpaid time off taken during current year")
    unpaid_time_off_n1 = fields.Float('Days Unpaid time off previous year', help="Number of days of unpaid time off taken during previous year")

    unpaid_average_remunaration_n = fields.Monetary('Average remuneration by month current year', help="Average remuneration for the 12 months preceding unpaid leave")
    unpaid_average_remunaration_n1 = fields.Monetary('Average remuneration by month previous year', help="Average remuneration for the 12 months preceding unpaid leave")

    fictitious_remuneration_n = fields.Monetary('Remuneration fictitious current year', compute='_compute_fictitious_remuneration_n')
    fictitious_remuneration_n1 = fields.Monetary('Remuneration fictitious previous year', compute='_compute_fictitious_remuneration_n1')

    @api.depends('employee_id')
    def _compute_history(self):
        for record in self:
            if record.employee_id and (not record.employee_id.start_notice_period or not record.employee_id.end_notice_period):
                raise UserError(_("Notice period not set for %s. Please, set the departure notice period first.", record.employee_id.name))

            if not record.employee_id:
                record.update({
                    'time_off_n_ids': [(5, 0, 0)],
                    'time_off_allocation_n_ids': [(5, 0, 0)],
                    'payslip_n_ids': [(5, 0, 0)],
                    'payslip_n1_ids': [(5, 0, 0)],
                })
            else:
                current_year = record.employee_id.end_notice_period.replace(month=1, day=1)
                previous_year = current_year + relativedelta(years=-1)
                next_year = current_year + relativedelta(years=+1)

                structure_warrant = self.env.ref('l10n_be_hr_payroll.hr_payroll_structure_cp200_structure_warrant')
                structure_termination = self.env.ref('l10n_be_hr_payroll.hr_payroll_structure_cp200_employee_termination_fees')
                structure_double_holidays = self.env.ref('l10n_be_hr_payroll.hr_payroll_structure_cp200_double_holiday')
                structure_termination = self.env.ref('l10n_be_hr_payroll.hr_payroll_structure_cp200_employee_termination_fees')
                structure_holidays_n = self.env.ref('l10n_be_hr_payroll.hr_payroll_structure_cp200_employee_departure_n_holidays')
                structure_holidays_n1 = self.env.ref('l10n_be_hr_payroll.hr_payroll_structure_cp200_employee_departure_n1_holidays')

                payslip_n_ids = self.env['hr.payslip'].search([
                    ('employee_id', '=', record.employee_id.id),
                    ('date_to', '>=', current_year),
                    ('state', 'in', ['done', 'paid', 'verify']),
                    ('struct_id', 'not in', (structure_warrant + structure_termination + structure_double_holidays + structure_termination + structure_holidays_n + structure_holidays_n1).ids)])
                payslip_n1_ids = self.env['hr.payslip'].search([
                    ('employee_id', '=', record.employee_id.id),
                    ('date_to', '>=', previous_year),
                    ('date_from', '<', current_year),
                    ('state', 'in', ['done', 'paid']),
                    ('struct_id', 'not in', (structure_warrant + structure_termination + structure_double_holidays + structure_termination + structure_holidays_n + structure_holidays_n1).ids)])

                record.payslip_n_ids = [(4, p._origin.id) for p in payslip_n_ids]
                record.payslip_n1_ids = [(4, p._origin.id) for p in payslip_n1_ids]

                time_off_n_ids = self.env['hr.leave'].search([
                    ('employee_id', '=', record.employee_id.id),
                    ('date_to', '>=', current_year),
                    ('date_from', '<', next_year),
                    ('state', '=', 'validate')])

                time_off_allocation_n_ids = self.env['hr.leave.allocation'].search([
                    ('employee_id', '=', record.employee_id.id),
                    ('create_date', '>=', current_year),
                    ('state', '=', 'validate')])

                record.time_off_n_ids = [(4, t.id) for t in time_off_n_ids]
                record.time_off_allocation_n_ids = [(4, t.id) for t in time_off_allocation_n_ids]

    @api.depends('payslip_n_ids')
    def _compute_net_n(self):
        for wizard in self:
            if wizard.payslip_n_ids:
                wizard.net_n = sum(p._origin._get_salary_line_total('SALARY') for p in wizard.payslip_n_ids)
            else:
                wizard.net_n = 0

    @api.depends('payslip_n1_ids')
    def _compute_net_n1(self):
        for wizard in self:
            if wizard.payslip_n1_ids:
                wizard.net_n1 = sum(p._origin._get_salary_line_total('SALARY') for p in wizard.payslip_n1_ids)
            else:
                wizard.net_n1 = 0

    @api.depends('time_off_n_ids')
    def _compute_time_off_taken(self):
        for wizard in self:
            if wizard.time_off_n_ids:
                wizard.time_off_taken = sum(time_off.number_of_days for time_off in wizard.time_off_n_ids)
            else:
                wizard.time_off_taken = 0

    @api.depends('time_off_allocation_n_ids')
    def _compute_time_off_allocated(self):
        for wizard in self:
            if wizard.time_off_allocation_n_ids:
                wizard.time_off_allocated = sum(allocation.number_of_days for allocation in wizard.time_off_allocation_n_ids)
            else:
                wizard.time_off_allocated = 0

    @api.depends('unpaid_average_remunaration_n', 'unpaid_time_off_n')
    def _compute_fictitious_remuneration_n(self):
        for attest in self:
            attest.fictitious_remuneration_n = (
                attest.unpaid_time_off_n * attest.unpaid_average_remunaration_n * 3 / (13 * 5))

    @api.depends('unpaid_average_remunaration_n1', 'unpaid_time_off_n1')
    def _compute_fictitious_remuneration_n1(self):
        for attest in self:
            attest.fictitious_remuneration_n1 = (
                attest.unpaid_time_off_n1 * attest.unpaid_average_remunaration_n1 * 3 / (13 * 5))

    def compute_termination_holidays(self):
        struct_n1_id = self.env.ref('l10n_be_hr_payroll.hr_payroll_structure_cp200_employee_departure_n1_holidays')
        struct_n_id = self.env.ref('l10n_be_hr_payroll.hr_payroll_structure_cp200_employee_departure_n_holidays')

        termination_payslip_n = self.env['hr.payslip'].create({
            'name': '%s - %s' % (struct_n_id.payslip_name, self.employee_id.display_name),
            'employee_id': self.employee_id.id,
        })
        termination_payslip_n._onchange_employee()
        if not termination_payslip_n.contract_id:
            termination_payslip_n.contract_id = self.employee_id.contract_id
        termination_payslip_n.struct_id = struct_n_id.id
        termination_payslip_n.worked_days_line_ids = [(5, 0, 0)]

        monthly_payslips = self.env['hr.payslip'].search([
            ('employee_id', '=', self.employee_id.id),
            ('state', 'in', ['done', 'paid']),
            ('struct_id', '=', self.env.ref('l10n_be_hr_payroll.hr_payroll_structure_cp200_employee_salary').id)
        ], order="date_from desc").filtered(
            lambda p: 'OUT' not in p.worked_days_line_ids.mapped('code'))

        if monthly_payslips:
            annual_gross = monthly_payslips[0]._get_salary_line_total('GROSS') * 12
        else:
            annual_gross = 0

        self.env['hr.payslip.input'].create([{
            'payslip_id': termination_payslip_n.id,
            'sequence': 2,
            'input_type_id': self.env.ref('l10n_be_hr_payroll.cp200_other_input_gross_ref').id,
            'amount': self.net_n + self.fictitious_remuneration_n,
            'contract_id': termination_payslip_n.contract_id.id
        }, {
            'payslip_id': termination_payslip_n.id,
            'sequence': 3,
            'input_type_id': self.env.ref('l10n_be_hr_payroll.cp200_other_input_allocation').id,
            'amount': 0,
            'contract_id': termination_payslip_n.contract_id.id
        }, {
            'payslip_id': termination_payslip_n.id,
            'sequence': 4,
            'input_type_id': self.env.ref('l10n_be_hr_payroll.cp200_other_input_time_off_taken').id,
            'amount': 0,
            'contract_id': termination_payslip_n.contract_id.id
        }, {
            'payslip_id': termination_payslip_n.id,
            'sequence': 5,
            'input_type_id': self.env.ref('l10n_be_hr_payroll.cp200_other_input_annual_taxable_amount').id,
            'amount': annual_gross,
            'contract_id': termination_payslip_n.contract_id.id
        }])
        termination_payslip_n.compute_sheet()
        termination_payslip_n.name = '%s - %s' % (struct_n_id.payslip_name, self.employee_id.display_name)

        termination_payslip_n1 = self.env['hr.payslip'].create({
            'name': '%s - %s' % (struct_n1_id.payslip_name, self.employee_id.display_name),
            'employee_id': self.employee_id.id,
        })
        termination_payslip_n1._onchange_employee()
        if not termination_payslip_n1.contract_id:
            termination_payslip_n1.contract_id = self.employee_id.contract_id
        termination_payslip_n1.struct_id = struct_n1_id.id
        termination_payslip_n1.worked_days_line_ids = [(5, 0, 0)]
        self.env['hr.payslip.input'].create([{
            'payslip_id': termination_payslip_n1.id,
            'sequence': 1,
            'input_type_id': self.env.ref('l10n_be_hr_payroll.cp200_other_input_gross_ref').id,
            'amount': self.net_n1 + self.fictitious_remuneration_n1,
            'contract_id': termination_payslip_n1.contract_id.id
        }, {
            'payslip_id': termination_payslip_n1.id,
            'sequence': 3,
            'input_type_id': self.env.ref('l10n_be_hr_payroll.cp200_other_input_allocation').id,
            'amount': self.time_off_allocated,
            'contract_id': termination_payslip_n1.contract_id.id
        }, {
            'payslip_id': termination_payslip_n1.id,
            'sequence': 4,
            'input_type_id': self.env.ref('l10n_be_hr_payroll.cp200_other_input_time_off_taken').id,
            'amount': self.time_off_taken,
            'contract_id': termination_payslip_n1.contract_id.id
        }, {
            'payslip_id': termination_payslip_n1.id,
            'sequence': 5,
            'input_type_id': self.env.ref('l10n_be_hr_payroll.cp200_other_input_annual_taxable_amount').id,
            'amount': annual_gross,
            'contract_id': termination_payslip_n1.contract_id.id
        }])
        termination_payslip_n1.compute_sheet()
        termination_payslip_n1.name = '%s - %s' % (struct_n1_id.payslip_name, self.employee_id.display_name)

        return {
            'name': _('Termination'),
            'domain': [('id', 'in', [termination_payslip_n.id, termination_payslip_n1.id])],
            'res_model': 'hr.payslip',
            'view_id': False,
            'view_mode': 'tree,form',
            'type': 'ir.actions.act_window',
        }
