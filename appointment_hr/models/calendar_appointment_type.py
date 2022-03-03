# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

import pytz

from datetime import timedelta
from odoo import api, fields, models, _, Command
from odoo.exceptions import ValidationError
from odoo.osv.expression import AND


class CalendarAppointmentType(models.Model):
    _name = "calendar.appointment.type"
    _inherit = "calendar.appointment.type"

    @api.model
    def default_get(self, default_fields):
        result = super().default_get(default_fields)

        if result.get('category') == 'work_hours' and result.get('staff_user_ids') == [Command.set(self.env.user.ids)]:
            if not self.env.user.employee_id:
                raise ValueError(_("An employee should be set on the current user to create an appointment type tied to the working schedule."))
        return result

    category = fields.Selection(
        selection_add=[('work_hours', 'Work Hours')],
        help="""Used to define this appointment type's category.
        Can be one of:
            - Website: the default category, the people can access and shedule the appointment with users from the website
            - Custom: the user will create and share to another user a custom appointment type with hand-picked time slots
            - Work Hours: a special type of appointment type that is used by one user and which takes the working hours of this
                user as availabilities. This one uses recurring slot that englobe the entire week to display all possible slots
                based on its working hours and availabilities """)
    work_hours_activated = fields.Boolean('Limit to Work Hours',
        help="When this option is activated the slots computation takes into account the working hours of the users.")

    @api.constrains('category', 'staff_user_ids')
    def _check_staff_user_configuration_work_hours(self):
        for appointment_type in self:
            if appointment_type.category == 'work_hours':
                appointment_domain = [('category', '=', 'work_hours'), ('staff_user_ids', 'in', appointment_type.staff_user_ids.ids)]
                if appointment_type.ids:
                    appointment_domain = AND([appointment_domain, [('id', 'not in', appointment_type.ids)]])
                if self.search_count(appointment_domain) > 0:
                    raise ValidationError(_("Only one work hours appointment type is allowed for a specific employee."))

    def _slot_availability_is_user_available(self, slot, staff_user, availability_values):
        """ This method verifies if the employee is available on the given slot.

        In addition to checks done in ``super()`` it checks whether the slot has
        conflicts with the working schedule of the employee linked to the user
        (if such an employee exists in the current company). An employee will
        not be considered available if the slot is not entirely comprised in its
        working schedule (using a certain tolerance).
        """
        slot_start_dt_utc, slot_end_dt_utc = slot['UTC'][0], slot['UTC'][1]
        is_available = super()._slot_availability_is_user_available(slot, staff_user, availability_values)
        if not is_available or not self.work_hours_activated:
            return is_available

        workhours = availability_values.get('work_schedules')
        if workhours and workhours.get(staff_user.partner_id):
            is_available = self._slot_availability_is_user_working(
                slot_start_dt_utc,
                slot_end_dt_utc,
                workhours[staff_user.partner_id]
            )

        return is_available

    def _slot_availability_is_user_working(self, start_dt, end_dt, intervals):
        """ Check if the slot is contained in the given work hours (defined by
        intervals). Those are linked to a given employee (user with working hours
        activated).

        TDE NOTE: internal method ``is_work_available`` of ``_slots_available``
        made as explicit method in 15.0 but left untouched. To clean in 15.3+.

        :param datetime start_dt: beginning of slot boundary. Not timezoned UTC;
        :param datetime end_dt: end of slot boundary. Not timezoned UTC;
        :param intervals: list of tuples defining working hours boundaries. If no
          intervals are given we consider employee does not work during this slot.
          See ``Resource._work_intervals_batch()`` for more details;

        :return bool: whether employee is available for this slot;
        """
        def find_start_index():
            """ find the highest index of intervals for which the start_date
            (element [0]) is before (or at) start_dt """
            def recursive_find_index(lower_bound, upper_bound):
                if upper_bound - lower_bound <= 1:
                    if intervals[upper_bound][0] <= start_dt:
                        return upper_bound
                    return lower_bound
                index = (upper_bound + lower_bound) // 2
                if intervals[index][0] <= start_dt:
                    return recursive_find_index(index, upper_bound)
                return recursive_find_index(lower_bound, index)

            if start_dt <= intervals[0][0] - tolerance:
                return -1
            if end_dt >= intervals[-1][1] + tolerance:
                return -1
            return recursive_find_index(0, len(intervals) - 1)

        if not intervals:
            return False

        tolerance = timedelta(minutes=1)
        start_index = find_start_index()
        if start_index != -1:
            for index in range(start_index, len(intervals)):
                if intervals[index][1] >= end_dt - tolerance:
                    return True
                if len(intervals) == index + 1 or intervals[index + 1][0] - intervals[index][1] > tolerance:
                    return False
        return False

    def _slot_availability_prepare_values(self, staff_users, start_dt, end_dt):
        """ Override to add batch-fetch of working hours information.

        :return: update ``super()`` values with work hours for computation, formatted like
          {
            'work_schedules': dict giving working hours based on user_partner_id
              (see ``_slot_availability_prepare_values_workhours()``);
          }
        """
        values = super()._slot_availability_prepare_values(staff_users, start_dt, end_dt)
        values.update(
            self._slot_availability_prepare_values_workhours(staff_users, start_dt, end_dt)
        )
        return values

    @api.model
    def _slot_availability_prepare_values_workhours(self, staff_users, start_dt, end_dt):
        """ This method computes the work intervals of staff users between start_dt
        and end_dt of slot. This means they have an employee using working hours.

        :param <res.users> staff_users: prepare values to check availability
          of those users against given appointment boundaries. At this point
          timezone should be correctly set in context of those users;
        :param datetime start_dt: beginning of appointment check boundary. Timezoned to UTC;
        :param datetime end_dt: end of appointment check boundary. Timezoned to UTC;

        :return: dict with unique key 'work_schedules' being a dict of working
          intervals based on employee partners:
          {
            'user_partner_id.id': [tuple(work interval), tuple(work_interval), ...],
            'user_partner_id.id': work_intervals,
            ...
          }
          Calendar field is required on resource and therefore on employee so each
          employee should be correctly taken into account;
        """
        calendar_to_employees = {}

        # Compute work schedules for users having employees with a resource.calendar
        available_employees_tz = [
            user.employee_id.with_context(tz=user.tz)
            for user in staff_users.sudo()
            if user.employee_id and user.employee_id.resource_id.calendar_id
        ]

        for employee in available_employees_tz:
            calendar = employee.resource_id.calendar_id
            if calendar not in calendar_to_employees:
                calendar_to_employees[calendar] = employee
            else:
                calendar_to_employees[calendar] += employee

        # Compute work schedules for users having employees
        work_schedules = {}
        for calendar, employees in calendar_to_employees.items():
            work_intervals = calendar._work_intervals_batch(
                start_dt, end_dt,
                resources=employees.resource_id
            )
            work_schedules.update(dict(
                (employee.user_partner_id,
                 [(interval[0].astimezone(pytz.UTC).replace(tzinfo=None),
                   interval[1].astimezone(pytz.UTC).replace(tzinfo=None)
                  )
                  for interval in work_intervals[employee.resource_id.id]
                 ]
                )
                for employee in employees
            ))

        return {'work_schedules': work_schedules}
