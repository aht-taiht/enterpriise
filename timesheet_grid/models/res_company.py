# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

from datetime import date, datetime, timedelta, time
from dateutil.relativedelta import relativedelta

from odoo import api, fields, models


class Company(models.Model):
    _inherit = 'res.company'

    # reminder for employees
    timesheet_mail_employee_allow = fields.Boolean("Employee Reminder", default=True,
        help="If checked, send an email to all users who have not recorded their timesheet")
    timesheet_mail_employee_delay = fields.Integer("Number of days", default=3)
    timesheet_mail_employee_interval = fields.Selection([
        ('weeks', 'after end of week'),
        ('months', 'after end of month')
    ], string='Frequency', required=True, default="weeks")
    timesheet_mail_employee_nextdate = fields.Datetime('Next scheduled date for employee reminder', readonly=True)

    # reminder for manager
    timesheet_mail_manager_allow = fields.Boolean("Manager Reminder", default=True,
        help="If checked, send an email to all managers who have not validated their timesheet")
    timesheet_mail_manager_delay = fields.Integer("Number of days", default=7)
    timesheet_mail_manager_interval = fields.Selection([
        ('weeks', 'after end of week'),
        ('months', 'after end of month')
    ], string='Frequency', required=True, default="weeks")
    timesheet_mail_manager_nextdate = fields.Datetime('Next scheduled date for manager reminder', readonly=True)

    @api.model
    def create(self, values):
        company = super(Company, self).create(values)
        company._timesheet_postprocess(values)
        return company

    def write(self, values):
        result = super(Company, self).write(values)
        self._timesheet_postprocess(values)
        return result

    def _timesheet_postprocess(self, values):
        if any(field_name in values for field_name in ['timesheet_mail_employee_delay', 'timesheet_mail_employee_interval']):
            self._calculate_timesheet_mail_employee_nextdate()
        if any(field_name in values for field_name in ['timesheet_mail_manager_delay', 'timesheet_mail_manager_interval']):
            self._calculate_timesheet_mail_manager_nextdate()

    def _calculate_timesheet_mail_employee_nextdate(self):
        for company in self:
            now = datetime.now()
            if company.timesheet_mail_employee_interval == 'weeks':
                nextdate = now + relativedelta(weeks=1, days=-now.weekday() + company.timesheet_mail_employee_delay - 1)
            if company.timesheet_mail_employee_interval == 'months':
                nextdate = now + relativedelta(day=1, months=1, days=company.timesheet_mail_employee_delay - 1)
            company.timesheet_mail_employee_nextdate = fields.Datetime.to_string(nextdate)

    def _calculate_timesheet_mail_manager_nextdate(self):
        for company in self:
            now = datetime.now()
            if company.timesheet_mail_manager_interval == 'weeks':
                nextdate = now + relativedelta(weeks=1, days=-now.weekday() + company.timesheet_mail_manager_delay - 1)
            if company.timesheet_mail_manager_interval == 'months':
                nextdate = now + relativedelta(day=1, months=1, days=company.timesheet_mail_manager_delay - 1)
            company.timesheet_mail_manager_nextdate = fields.Datetime.to_string(nextdate)

    @api.model
    def _cron_timesheet_reminder_employee(self):
        """ Send an email reminder to the user having at least one timesheet since the last 3 month. From those ones, we exclude
            ones having complete their timesheet (meaning timesheeted the same hours amount than their working calendar).
        """
        today_min = fields.Datetime.to_string(datetime.combine(date.today(), time.min))
        today_max = fields.Datetime.to_string(datetime.combine(date.today(), time.max))
        companies = self.search([('timesheet_mail_employee_allow', '=', True), ('timesheet_mail_employee_nextdate', '<', today_max), ('timesheet_mail_employee_nextdate', '>=', today_min)])
        for company in companies:
            # get the employee that have at least a timesheet for the last 3 months
            users = self.env['account.analytic.line'].search([
                ('date', '>=', fields.Date.to_string(date.today() - relativedelta(months=3))),
                ('date', '<=', fields.Date.today()),
                ('company_id', '=', company.id),
            ]).mapped('user_id')

            # calculate the period
            if company.timesheet_mail_employee_interval == 'months':
                date_start = date.today() + relativedelta(day=1, days=-1)
            else:
                date_start = date.today() - timedelta(days=datetime.now().weekday()+1)

            date_start = fields.Date.to_string(date_start)
            date_stop = fields.Date.to_string(fields.Datetime.from_string(company.timesheet_mail_employee_nextdate).date())

            # get the related employees timesheet status for the cron period
            employees = self.env['hr.employee'].search([('user_id', 'in', users.ids)])
            work_hours_struct = employees.get_timesheet_and_working_hours(date_start, date_stop)

            for employee in employees:
                if employee.user_id and work_hours_struct[employee.id]['timesheet_hours'] < work_hours_struct[employee.id]['working_hours']:
                    self._cron_timesheet_send_reminder(
                        employee,
                        'timesheet_grid.mail_template_timesheet_reminder_user',
                        'hr_timesheet.act_hr_timesheet_line',
                        additionnal_values=work_hours_struct[employee.id],
                    )

        # compute the next execution date
        companies._calculate_timesheet_mail_employee_nextdate()

    @api.model
    def _cron_timesheet_reminder_manager(self):
        """ Send a email reminder to all users having the group 'timesheet manager'. """
        today_min = fields.Datetime.to_string(datetime.combine(date.today(), time.min))
        today_max = fields.Datetime.to_string(datetime.combine(date.today(), time.max))
        companies = self.search([('timesheet_mail_employee_allow', '=', True), ('timesheet_mail_manager_nextdate', '<', today_max), ('timesheet_mail_manager_nextdate', '>=', today_min)])
        for company in companies:
            # calculate the period
            if company.timesheet_mail_manager_interval == 'months':
                date_start = date.today() + relativedelta(day=1, days=-1)
            else:
                date_start = date.today() - timedelta(days=datetime.now().weekday()+1)

            date_start = fields.Date.to_string(date_start)
            date_stop = fields.Date.to_string(fields.Datetime.from_string(company.timesheet_mail_employee_nextdate).date())

            values = {
                'date_start': date_start,
                'date_stop': date_stop,
            }
            users = self.env['res.users'].search([('groups_id', 'in', [self.env.ref('hr_timesheet.group_timesheet_manager').id])])
            self._cron_timesheet_send_reminder(
                self.env['hr.employee'].search([('user_id', 'in', users.ids)]),
                'timesheet_grid.mail_template_timesheet_reminder_manager',
                'timesheet_grid.action_timesheet_previous_week',
                additionnal_values=values)

        # compute the next execution date
        companies._calculate_timesheet_mail_manager_nextdate()

    @api.model
    def _cron_timesheet_send_reminder(self, employees, template_xmlid, action_xmlid, additionnal_values=None):
        """ Send the email reminder to specified users
            :param user_ids : list of user identifier to send the reminder
            :param template_xmlid : xml id of the reminder mail template
        """
        action_url = '%s/web#menu_id=%s&action=%s' % (
            self.env['ir.config_parameter'].sudo().get_param('web.base.url'),
            self.env.ref('hr_timesheet.timesheet_menu_root').id,
            self.env.ref(action_xmlid).id,
        )

        # send mail template to users having email address
        template = self.env.ref(template_xmlid)
        template_ctx = {'action_url': action_url}
        if additionnal_values:
            template_ctx.update(additionnal_values)

        for employee in employees.filtered('user_id'):
            template.with_context(lang=employee.user_id.lang, **template_ctx).send_mail(employee.id)
