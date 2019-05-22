# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

import itertools
import pytz

from dateutil.relativedelta import relativedelta

from odoo import api, fields, models, _
from odoo.addons.resource.models.resource import Intervals
from odoo.exceptions import ValidationError


class HrWorkEnrty(models.Model):
    _name = 'hr.work.entry'
    _description = 'hr.work.entry'
    _order = 'display_warning desc,state,date_start'

    name = fields.Char(required=True)
    active = fields.Boolean(default=True)
    employee_id = fields.Many2one('hr.employee', required=True, domain=[('contract_ids.state', 'in', ('open', 'pending'))])
    date_start = fields.Datetime(required=True, string='From')
    date_stop = fields.Datetime(string='To')
    duration = fields.Float(compute='_compute_duration', inverse='_inverse_duration', store=True, string="Period")
    contract_id = fields.Many2one('hr.contract', string="Contract", required=True)
    work_entry_type_id = fields.Many2one('hr.work.entry.type')
    color = fields.Integer(related='work_entry_type_id.color', readonly=True)
    state = fields.Selection([
        ('draft', 'Draft'),
        ('confirmed', 'Confirmed'),
        ('validated', 'Validated'),
        ('cancelled', 'Cancelled')
    ], default='draft')
    display_warning = fields.Boolean(string="Error")
    leave_id = fields.Many2one('hr.leave', string='Time Off')
    company_id = fields.Many2one('res.company', string='Company', readonly=True, required=True,
        default=lambda self: self.env.company)

    _sql_constraints = [
        ('_unique', 'unique (date_start, date_stop, employee_id, work_entry_type_id, active)', "Work entry already exists for this attendance"),
        ('_work_entry_has_end', 'check (date_stop IS NOT NULL OR duration <> 0)', 'Work entry must end. Please define an end date or a duration.'),
        ('_work_entry_start_before_end', 'check (date_stop is null OR (date_stop > date_start))', 'Starting time should be before end time.')
    ]

    @api.onchange('duration')
    def _onchange_duration(self):
        self._inverse_duration()

    def _get_duration(self, date_start, date_stop):
        if not date_start or not date_stop:
            return 0
        dt = date_stop - date_start
        return dt.days * 24 + dt.seconds / 3600 # Number of hours

    @api.depends('date_stop', 'date_start')
    def _compute_duration(self):
        for work_entry in self:
            work_entry.duration = work_entry._get_duration(work_entry.date_start, work_entry.date_stop)

    def _inverse_duration(self):
        for work_entry in self:
            if work_entry.date_start and work_entry.duration:
                work_entry.date_stop = work_entry.date_start + relativedelta(hours=work_entry.duration)

    def write(self, vals):
        if 'state' in vals:
            if vals['state'] == 'draft':
                vals['active'] = True
            if vals['state'] == 'cancelled':
                vals['active'] = False
                self.mapped('leave_id').action_refuse()
        return super(HrWorkEnrty, self).write(vals)

    @api.multi
    def _check_if_error(self):
        if not self:
            return False
        undefined_type = self.filtered(lambda b: not b.work_entry_type_id)
        undefined_type.write({'display_warning': True})
        conflict = self._mark_conflicting_work_entries(min(self.mapped('date_start')), max(self.mapped('date_stop')))
        conflict_with_leaves = self._compute_conflicts_leaves_to_approve()
        return undefined_type or conflict or conflict_with_leaves

    @api.model
    def _mark_conflicting_work_entries(self, start, stop):
        """
        Set `display_warning` to True for overlapping work entries
        between two dates.
        Return True if overlapping work entries were detected.
        """
        # Use the postgresql range type `tsrange` which is a range of timestamp
        # It supports the intersection operator (&&) useful to detect overlap.
        # use '()' to exlude the lower and upper bounds of the range.
        # Filter on date_start and date_stop (both indexed) in the EXISTS clause to
        # limit the resulting set size and fasten the query.
        query = """
            SELECT b1.id
            FROM hr_work_entry b1
            WHERE
            b1.date_start <= %s
            AND b1.date_stop >= %s
            AND active = TRUE
            AND EXISTS (
                SELECT 1
                FROM hr_work_entry b2
                WHERE
                    b2.date_start <= %s
                    AND b2.date_stop >= %s
                    AND active = TRUE
                    AND tsrange(b1.date_start, b1.date_stop, '()') && tsrange(b2.date_start, b2.date_stop, '()')
                    AND b1.id <> b2.id
                    AND b1.employee_id = b2.employee_id
            );
        """
        self.env.cr.execute(query, (stop, start, stop, start))
        conflicts = [res.get('id') for res in self.env.cr.dictfetchall()]
        self.browse(conflicts).write({
            'display_warning': True,
        })
        return bool(conflicts)

    @api.multi
    def _compute_conflicts_leaves_to_approve(self):
        if not self:
            return False

        query = """
            SELECT
                b.id AS work_entry_id,
                l.id AS leave_id
            FROM hr_work_entry b
            INNER JOIN hr_leave l ON b.employee_id = l.employee_id
            WHERE
                b.id IN %s AND
                l.date_from <= b.date_stop AND
                l.date_to >= b.date_start AND
                l.state IN ('confirm', 'validate1');
        """
        self.env.cr.execute(query, [tuple(self.ids)])
        conflicts = self.env.cr.dictfetchall()
        for res in conflicts:
            self.browse(res.get('work_entry_id')).write({
                'display_warning': True,
                'leave_id': res.get('leave_id')
            })
        return bool(conflicts)

    def _safe_duplicate_create(self, vals_list, date_start, date_stop):
        """
        Create work_entries between date_start and date_stop according to vals_list.
        Skip the values in vals_list if a work_entry already exists for the given
        date_start, date_stop, employee_id, work_entry_type_id
        :return: new record id if it didn't exist.
        """
        # The search_read should be fast as date_start and date_stop are indexed from the
        # unique sql constraint
        month_recs = self.search_read([('date_start', '>=', date_start), ('date_stop', '<=', date_stop)],
                                      ['employee_id', 'date_start', 'date_stop', 'work_entry_type_id'])
        existing_entries = {(
            r['date_start'],
            r['date_stop'],
            r['employee_id'][0],
            r['work_entry_type_id'][0] if r['work_entry_type_id'] else False,
        ) for r in month_recs}
        assert all(v['date_start'].tzinfo is None for v in vals_list)
        assert all(v['date_stop'].tzinfo is None for v in vals_list)
        new_vals = [v for v in vals_list if (v['date_start'], v['date_stop'], v['employee_id'], v['work_entry_type_id']) not in existing_entries]
        # Remove duplicates from vals_list, shouldn't be necessary from saas-12.2
        unique_new_vals = set()
        for values in new_vals:
            unique_new_vals.add(tuple(values.items()))
        new_vals = [dict(values) for values in unique_new_vals]
        return self.create(new_vals)

    def action_leave(self):
        leave = self.leave_id
        return {
            'type': 'ir.actions.act_window',
            'view_type': 'form',
            'view_mode': 'form',
            'res_id': leave.id,
            'res_model': 'hr.leave',
            'views': [[False, 'form']],
        }

    def _split_by_day(self):
        """
        Split the work_entry by days and unlink the original work_entry.
        @return recordset
        """
        def _split_range_by_day(start, end):
            days = []
            current_start = start
            current_end = start.replace(hour=23, minute=59, second=59)
            while current_end < end:
                days.append((current_start, current_end))
                current_start = current_end + relativedelta(seconds=1)
                current_end = current_end + relativedelta(days=1)

            days.append((current_start, end))

            # filter to avoid dummy intervals starting and ending at the same time
            return [(start, end) for start, end in days if start != end]

        new_work_entries = self.env['hr.work.entry']
        work_entries_to_unlink = self.env['hr.work.entry']

        for work_entry in self:
            if work_entry.date_start.date() == work_entry.date_stop.date():
                new_work_entries |= work_entry
            else:
                values = {
                    'name': work_entry.name,
                    'employee_id': work_entry.employee_id.id,
                    'work_entry_type_id': work_entry.work_entry_type_id.id,
                    'contract_id': work_entry.contract_id.id,
                }
                work_entry_state = work_entry.state
                work_entries_to_unlink |= work_entry
                for start, stop in _split_range_by_day(work_entry.date_start, work_entry.date_stop):
                    values['date_start'] = start
                    values['date_stop'] = stop
                    new_work_entry = self.create(values)
                    # Write the state after the creation due to the ir.rule on work_entry state
                    new_work_entry.state = work_entry_state
                    new_work_entries |= new_work_entry

        work_entries_to_unlink.unlink()
        return new_work_entries

    @api.multi
    def _duplicate_to_calendar(self):
        """
            Duplicate data to keep the complexity in work_entry and not mess up payroll, etc.
        """
        attendance_type = self.env.ref('hr_payroll.work_entry_type_attendance')
        attendance_work_entries = self.filtered(lambda b:
            not b.work_entry_type_id.is_leave and
            # Normal work_entry are global to all employees -> avoid duplicating it
            not b.work_entry_type_id == attendance_type)
        leave_work_entries = self.filtered(lambda b: b.work_entry_type_id.is_leave)

        work_entries_to_duplicate = self.env['hr.work.entry']
        for work_entry in attendance_work_entries:
            work_entry = work_entry._split_by_day()
            work_entries_to_duplicate |= work_entry

        work_entries_to_duplicate._duplicate_to_calendar_attendance()
        leave_work_entries._duplicate_to_calendar_leave()

    @api.multi
    def _duplicate_to_calendar_leave(self):
        vals_list = []
        for work_entry in self:
            if not work_entry.leave_id:
                vals_list += [{
                    'name': work_entry.name,
                    'date_from': work_entry.date_start,
                    'date_to': work_entry.date_stop,
                    'calendar_id': work_entry.employee_id.resource_calendar_id.id,
                    'resource_id': work_entry.employee_id.resource_id.id,
                    'work_entry_type_id': work_entry.work_entry_type_id.id,
                }]
        if vals_list:
            self.env['resource.calendar.leaves'].create(vals_list)

    @api.multi
    def _duplicate_to_calendar_attendance(self):
        mapped_data = {
            work_entry: [
                work_entry.date_start,
                work_entry.date_stop,
            ] for work_entry in self
        }

        if any(data[0].date() != data[1].date() for data in mapped_data.values()):
            raise ValidationError(_("You can't validate a work_entry that covers several days."))

        vals_list = []
        for work_entry in self:
            start, end = mapped_data.get(work_entry)

            vals_list += [{
                'name': work_entry.name,
                'dayofweek': str(start.weekday()),
                'date_from': start.date(),
                'date_to': end.date(),
                'hour_from': start.hour + start.minute / 60,
                'hour_to': end.hour + end.minute / 60,
                'calendar_id': work_entry.contract_id.resource_calendar_id.id,
                'day_period': 'morning' if end.hour <= 12 else 'afternoon',
                'resource_id': work_entry.employee_id.resource_id.id,
                'work_entry_type_id': work_entry.work_entry_type_id.id,
            }]
        self.env['resource.calendar.attendance'].create(vals_list)

    @api.multi
    def action_validate(self):
        work_entries = self.filtered(lambda work_entry: work_entry.state != 'validated')
        work_entries.write({'display_warning': False})
        if not work_entries._check_if_error():
            work_entries.write({'state': 'validated'})
            work_entries._duplicate_to_calendar()
            return True
        return False


class HrWorkEntryType(models.Model):
    _name = 'hr.work.entry.type'
    _description = 'hr.work.entry.type'

    name = fields.Char(required=True)
    code = fields.Char(required=True)
    color = fields.Integer(default=0)
    sequence = fields.Integer(default=25)
    active = fields.Boolean(
        'Active', default=True,
        help="If the active field is set to false, it will allow you to hide the work entry type without removing it.")
    is_leave = fields.Boolean(default=False, string="Time Off")
    is_unforeseen = fields.Boolean(default=False, string="Unforeseen Absence")
    leave_type_ids = fields.One2many('hr.leave.type', 'work_entry_type_id', string='Time Off Type')

    _sql_constraints = [
        ('unique_work_entry_code', 'UNIQUE(code)', 'The same code cannot be associated to multiple work entry types.'),
        ('is_unforeseen_is_leave', 'check (is_unforeseen = FALSE OR (is_leave = TRUE and is_unforeseen = TRUE))', 'A unforeseen absence must be a leave.')
    ]


class Contacts(models.Model):
    """ Personnal calendar filter """

    _name = 'hr.user.work.entry.employee'
    _description = 'Work Entries Employees'

    user_id = fields.Many2one('res.users', 'Me', required=True, default=lambda self: self.env.user)
    employee_id = fields.Many2one('hr.employee', 'Employee', required=True)
    active = fields.Boolean('Active', default=True)

    _sql_constraints = [
        ('user_id_employee_id_unique', 'UNIQUE(user_id,employee_id)', 'You cannot have twice the same employee.')
    ]
