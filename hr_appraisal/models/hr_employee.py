# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

import datetime
from dateutil.relativedelta import relativedelta

from odoo import api, fields, models, _
from odoo.exceptions import UserError


class HrEmployee(models.Model):
    _inherit = "hr.employee"

    next_appraisal_date = fields.Date(string='Next Appraisal Date', groups="hr.group_hr_user",
        help="The date of the next appraisal is computed by the appraisal plan's dates (first appraisal + periodicity).",
        default=lambda self: self._default_next_appraisal_date())
    last_appraisal_date = fields.Date(string='Last Appraisal Date', groups="hr.group_hr_user",
        help="The date of the last appraisal")
    appraisal_by_manager = fields.Boolean(string='Managers', groups="hr.group_hr_user", default=lambda self: self.env.user.company_id.appraisal_by_manager)
    appraisal_manager_ids = fields.Many2many('hr.employee', 'emp_appraisal_manager_rel', 'hr_appraisal_id', groups="hr.group_hr_user", domain="['|', ('company_id', '=', False), ('company_id', '=', company_id)]")
    appraisal_by_colleagues = fields.Boolean(string='Colleagues', groups="hr.group_hr_user", default=lambda self: self.env.user.company_id.appraisal_by_colleagues)
    appraisal_colleagues_ids = fields.Many2many('hr.employee', 'emp_appraisal_colleagues_rel', 'hr_appraisal_id', groups="hr.group_hr_user", domain="['|', ('company_id', '=', False), ('company_id', '=', company_id)]")
    appraisal_self = fields.Boolean(string='Employee', groups="hr.group_hr_user",
        default=lambda self: self.env.user.company_id.appraisal_by_employee)
    appraisal_employee = fields.Char(string='Name', compute='_compute_name', groups="hr.group_hr_user")
    appraisal_by_collaborators = fields.Boolean(string='Collaborators', groups="hr.group_hr_user",
        default=lambda self: self.env.user.company_id.appraisal_by_collaborators)
    appraisal_collaborators_ids = fields.Many2many('hr.employee', 'emp_appraisal_subordinates_rel', 'hr_appraisal_id', groups="hr.group_hr_user", domain="['|', ('company_id', '=', False), ('company_id', '=', company_id)]")
    periodic_appraisal_created = fields.Boolean(string='Periodic Appraisal has been created', groups="hr.group_hr_user", default=False)  # Flag for the cron
    related_partner_id = fields.Many2one('res.partner', compute='_compute_related_partner', groups="hr.group_hr_user")
    last_duration_reminder_send = fields.Integer(string='Duration after last appraisal when we send last reminder mail',
        groups="hr.group_hr_user", default=0)

    def _default_next_appraisal_date(self):
        current_date = datetime.date.today()
        months = int(self.env['ir.config_parameter'].sudo().get_param('hr_appraisal.appraisal_max_period', default=18))
        return current_date + relativedelta(months=months)

    def _compute_name(self):
        for employee in self:
            employee.appraisal_employee = employee.name

    def _compute_related_partner(self):
        for rec in self:
            rec.related_partner_id = rec.user_id.partner_id

    @api.onchange('appraisal_by_manager')
    def onchange_appraisal_by_manager(self):
        if not self.appraisal_manager_ids:
            self._onchange_manager_appraisal()

    @api.onchange('parent_id')
    def _onchange_manager_appraisal(self):
        if self.appraisal_by_manager and self.parent_id:
            self.appraisal_manager_ids = [self.parent_id.id]
        else:
            self.appraisal_manager_ids = False

    @api.onchange('appraisal_by_colleagues')
    def onchange_appraisal_by_colleagues(self):
        if not self.appraisal_colleagues_ids:
            self.onchange_colleagues()

    @api.onchange('department_id', 'parent_id')
    def onchange_colleagues(self):
        if self.appraisal_by_colleagues and self.department_id and self.parent_id:
            self.appraisal_colleagues_ids = self.search([('department_id', '=', self.department_id.id), ('id', '!=', self._origin.id), ('parent_id', '=', self.parent_id.id)])
        else:
            self.appraisal_colleagues_ids = False

    @api.onchange('appraisal_by_collaborators')
    def onchange_appraisal_by_collaborators(self):
        if not self.appraisal_collaborators_ids:
            self.onchange_subordinates()

    @api.onchange('child_ids')
    def onchange_subordinates(self):
        if self.appraisal_by_collaborators:
            self.appraisal_collaborators_ids = self.child_ids
        else:
            self.appraisal_collaborators_ids = False

    def write(self, vals):
        if vals.get('next_appraisal_date') and fields.Date.from_string(vals.get('next_appraisal_date')) < datetime.date.today():
            raise UserError(_("The date of the next appraisal cannot be in the past"))
        return super(HrEmployee, self).write(vals)

    def _get_employees_to_send_reminder_appraisal(self, months, reminder):
        company_id = reminder.company_id.id
        current_date = datetime.date.today()
        if reminder.event == 'last_appraisal':
            return self.search([
                ('last_appraisal_date', '>', current_date - relativedelta(months=months+1)),
                ('last_appraisal_date', '<', current_date - relativedelta(months=months)),
                ('last_duration_reminder_send', '<', months),
                ('company_id', '=', company_id),
            ])
        return self.search([
            ('create_date', '>', current_date - relativedelta(months=months+1)),
            ('create_date', '<', current_date - relativedelta(months=months)),
            ('last_appraisal_date', '=', False),
            ('last_duration_reminder_send', '<', months),
            ('company_id', '=', company_id),
        ])

    def _get_employees_to_appraise(self, months):
        current_date = datetime.date.today()
        return self.search([
            ('periodic_appraisal_created', '=', False),
            ('next_appraisal_date', '<=', current_date + relativedelta(days=8)),
            '|', ('last_appraisal_date', '=', False), ('last_appraisal_date', '<=', current_date + relativedelta(months=-months, days=8)),
        ])
    
    @api.model
    def run_employee_appraisal(self):  # cronjob
        current_date = datetime.date.today()
        months = int(self.env['ir.config_parameter'].sudo().get_param('hr_appraisal.appraisal_max_period'))

        # Set periodic_appraisal_created for the next appraisal if the date is passed:
        for employee in self.search([('last_appraisal_date', '<', current_date - relativedelta(months=months))]):
            employee.write({
                'periodic_appraisal_created': False
            })
        # Create periodic appraisal if appraisal date is in less than a week and the appraisal for this period has not been created yet:
        employees_to_appraise = self._get_employees_to_appraise(months)
        appraisal_values = [{
            'employee_id': employee.id,
            'company_id': employee.company_id.id,
            'date_close': fields.Date.to_string(current_date + relativedelta(months=months)),
            'manager_ids': [(4, manager.id) for manager in employee.appraisal_manager_ids],
            'manager_body_html': employee.company_id.appraisal_by_manager_body_html,
            'colleagues_ids': [(4, colleagues.id) for colleagues in employee.appraisal_colleagues_ids],
            'colleagues_body_html': employee.company_id.appraisal_by_colleagues_body_html,
            'employee_body_html': employee.company_id.appraisal_by_employee_body_html,
            'collaborators_ids': [(4, subordinates.id) for subordinates in employee.appraisal_collaborators_ids],
            'collaborators_body_html': employee.company_id.appraisal_by_collaborators_body_html,
        } for employee in employees_to_appraise]
        self.env['hr.appraisal'].create(appraisal_values)
        employees_to_appraise.write({'periodic_appraisal_created': True})

        self.env['hr.appraisal.reminder']._run_employee_appraisal_reminder()
