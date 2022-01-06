# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

from pytz import utc
from collections import defaultdict
from datetime import timedelta, datetime
from dateutil.relativedelta import relativedelta

from odoo import api, fields, models, _
from odoo.exceptions import UserError
from odoo.addons.resource.models.resource import Intervals, sum_intervals, string_to_datetime

PROJECT_TASK_WRITABLE_FIELDS = {
    'planned_date_begin',
    'planned_date_end',
}


class Task(models.Model):
    _inherit = "project.task"

    planned_date_begin = fields.Datetime("Start date", tracking=True, task_dependency_tracking=True, help="Scheduled date of the task, which will appear in the Gantt view.")
    planned_date_end = fields.Datetime("End date", tracking=True, task_dependency_tracking=True)
    partner_mobile = fields.Char(related='partner_id.mobile', readonly=False)
    partner_zip = fields.Char(related='partner_id.zip', readonly=False)
    partner_street = fields.Char(related='partner_id.street', readonly=False)
    project_color = fields.Integer('Project color', related='project_id.color')

    # Task Dependencies fields
    display_warning_dependency_in_gantt = fields.Boolean(compute="_compute_display_warning_dependency_in_gantt")
    planning_overlap = fields.Integer(compute='_compute_planning_overlap', search='_search_planning_overlap')

    # User names in popovers
    user_names = fields.Char(compute='_compute_user_names')

    # Allocated hours
    allocated_hours = fields.Float("Allocated Hours", compute='_compute_allocated_hours', store=True)
    allocation_type = fields.Selection([
        ('working_hours', 'Working Hours'),
        ('duration', 'Duration'),
    ], default='duration', compute='_compute_allocation_type')
    duration = fields.Float(compute='_compute_duration')

    _sql_constraints = [
        ('planned_dates_check', "CHECK ((planned_date_begin <= planned_date_end))", "The planned start date must be before the planned end date."),
    ]

    # action_gantt_reschedule utils
    _WEB_GANTT_RESCHEDULE_WORK_INTERVALS_CACHE_KEY = 'work_intervals'
    _WEB_GANTT_RESCHEDULE_RESOURCE_VALIDITY_CACHE_KEY = 'resource_validity'

    @property
    def SELF_WRITABLE_FIELDS(self):
        return super().SELF_WRITABLE_FIELDS | PROJECT_TASK_WRITABLE_FIELDS

    def default_get(self, fields_list):
        result = super().default_get(fields_list)
        planned_date_begin = result.get('planned_date_begin', False)
        planned_date_end = result.get('planned_date_end', False)
        if planned_date_begin and planned_date_end and not self.env.context.get('fsm_mode', False):
            user_id = result.get('user_id', None)
            planned_date_begin, planned_date_end = self._calculate_planned_dates(planned_date_begin, planned_date_end, user_id)
            result.update(planned_date_begin=planned_date_begin, planned_date_end=planned_date_end)
        return result

    def action_unschedule_task(self):
        self.write({
            'planned_date_begin': False,
            'planned_date_end': False
        })

    @api.depends('stage_id')
    def _compute_display_warning_dependency_in_gantt(self):
        for task in self:
            task.display_warning_dependency_in_gantt = not task.is_closed

    @api.depends('planned_date_begin', 'planned_date_end', 'user_ids')
    def _compute_planning_overlap(self):
        if self.ids:
            query = """
                SELECT
                    T1.id, COUNT(T2.id)
                FROM
                    (
                        SELECT
                            T.id as id,
                            T.project_id,
                            T.planned_date_begin as planned_date_begin,
                            T.planned_date_end as planned_date_end,
                            T.active as active
                        FROM project_task T
                        LEFT OUTER JOIN project_project P ON P.id = T.project_id
                        WHERE T.id IN %s
                            AND T.active = 't'
                            AND T.planned_date_begin IS NOT NULL
                            AND T.planned_date_end IS NOT NULL
                            AND T.project_id IS NOT NULL
                    ) T1
                INNER JOIN project_task_user_rel U1
                    ON T1.id = U1.task_id
                INNER JOIN project_task T2
                    ON T1.id != T2.id
                        AND T2.active = 't'
                        AND T2.planned_date_begin IS NOT NULL
                        AND T2.planned_date_end IS NOT NULL
                        AND T2.project_id IS NOT NULL
                        AND (T1.planned_date_begin::TIMESTAMP, T1.planned_date_end::TIMESTAMP)
                            OVERLAPS (T2.planned_date_begin::TIMESTAMP, T2.planned_date_end::TIMESTAMP)
                INNER JOIN project_task_user_rel U2
                    ON T2.id = U2.task_id
                    AND U2.user_id = U1.user_id
                GROUP BY T1.id
            """
            self.env.cr.execute(query, (tuple(self.ids),))
            raw_data = self.env.cr.dictfetchall()
            overlap_mapping = dict(map(lambda d: d.values(), raw_data))
            for task in self:
                task.planning_overlap = overlap_mapping.get(task.id, 0)
        else:
            self.planning_overlap = False

    @api.model
    def _search_planning_overlap(self, operator, value):
        if operator not in ['=', '>'] or not isinstance(value, int) or value != 0:
            raise NotImplementedError(_('Operation not supported, you should always compare planning_overlap to 0 value with = or > operator.'))

        query = """
            SELECT T1.id
            FROM project_task T1
            INNER JOIN project_task T2 ON T1.id <> T2.id
            INNER JOIN project_task_user_rel U1 ON T1.id = U1.task_id
            INNER JOIN project_task_user_rel U2 ON T2.id = U2.task_id
                AND U1.user_id = U2.user_id
            WHERE
                T1.planned_date_begin < T2.planned_date_end
                AND T1.planned_date_end > T2.planned_date_begin
                AND T1.planned_date_begin IS NOT NULL
                AND T1.planned_date_end IS NOT NULL
                AND T1.active = 't'
                AND T1.project_id IS NOT NULL
                AND T2.planned_date_begin IS NOT NULL
                AND T2.planned_date_end IS NOT NULL
                AND T2.project_id IS NOT NULL
                AND T2.active = 't'
        """
        operator_new = (operator == ">") and "inselect" or "not inselect"
        return [('id', operator_new, (query, ()))]

    def _compute_user_names(self):
        for task in self:
            task.user_names = ', '.join(task.user_ids.mapped('name'))

    @api.depends('planned_date_begin', 'planned_date_end', 'company_id.resource_calendar_id', 'user_ids')
    def _compute_allocated_hours(self):
        task_working_hours = self.filtered(lambda s: s.allocation_type == 'working_hours' and (s.user_ids or s.company_id))
        task_duration = self - task_working_hours
        for task in task_duration:
            # for each planning slot, compute the duration
            task.allocated_hours = task.duration * (len(task.user_ids) or 1)
        # This part of the code comes in major parts from planning, with adaptations.
        # Compute the conjunction of the task user's work intervals and the task.
        if not task_working_hours:
            return
        # if there are at least one task having start or end date, call the _get_valid_work_intervals
        start_utc = utc.localize(min(task_working_hours.mapped('planned_date_begin')))
        end_utc = utc.localize(max(task_working_hours.mapped('planned_date_end')))
        # work intervals per user/per calendar are retrieved with a batch
        user_work_intervals, calendar_work_intervals = task_working_hours.user_ids._get_valid_work_intervals(
            start_utc, end_utc, calendars=task_working_hours.company_id.resource_calendar_id
        )
        for task in task_working_hours:
            start = max(start_utc, utc.localize(task.planned_date_begin))
            end = min(end_utc, utc.localize(task.planned_date_end))
            interval = Intervals([(
                start, end, self.env['resource.calendar.attendance']
            )])
            sum_allocated_hours = 0.0
            if task.user_ids:
                # we sum up the allocated hours for each user
                for user in task.user_ids:
                    sum_allocated_hours += sum_intervals(user_work_intervals[user.id] & interval)
            else:
                sum_allocated_hours += sum_intervals(calendar_work_intervals[task.company_id.resource_calendar_id.id] & interval)
            task.allocated_hours = sum_allocated_hours

    @api.depends('planned_date_begin', 'planned_date_end')
    def _compute_allocation_type(self):
        for task in self:
            if task.duration < 24:
                task.allocation_type = 'duration'
            else:
                task.allocation_type = 'working_hours'

    @api.depends('planned_date_begin', 'planned_date_end')
    def _compute_duration(self):
        for task in self:
            if not (task.planned_date_begin and task.planned_date_end):
                task.duration = 0.0
            else:
                task.duration = (task.planned_date_end - task.planned_date_begin).total_seconds() / 3600.0

    @api.model
    def _calculate_planned_dates(self, date_start, date_stop, user_id=None, calendar=None):
        if not (date_start and date_stop):
            raise UserError('One parameter is missing to use this method. You should give a start and end dates.')
        start, stop = date_start, date_stop
        if isinstance(start, str):
            start = fields.Datetime.from_string(start)
        if isinstance(stop, str):
            stop = fields.Datetime.from_string(stop)

        if not calendar:
            user = self.env['res.users'].sudo().browse(user_id) if user_id and user_id != self.env.user.id else self.env.user
            calendar = user.resource_calendar_id or self.env.company.resource_calendar_id
            if not calendar:  # Then we stop and return the dates given in parameter.
                return date_start, date_stop

        if not start.tzinfo:
            start = start.replace(tzinfo=utc)
        if not stop.tzinfo:
            stop = stop.replace(tzinfo=utc)

        intervals = calendar._work_intervals_batch(start, stop)[False]
        if not intervals:  # Then we stop and return the dates given in parameter
            return date_start, date_stop
        list_intervals = [(start, stop) for start, stop, records in intervals]  # Convert intervals in interval list
        start = list_intervals[0][0].astimezone(utc).replace(tzinfo=None)  # We take the first date in the interval list
        stop = list_intervals[-1][1].astimezone(utc).replace(tzinfo=None)  # We take the last date in the interval list
        return start, stop

    def _get_tasks_by_resource_calendar_dict(self):
        """
            Returns a dict of:
                key = 'resource.calendar'
                value = recordset of 'project.task'
        """
        default_calendar = self.env.company.resource_calendar_id

        calendar_by_user_dict = {  # key: user_id, value: resource.calendar instance
            user.id:
                user.resource_calendar_id or default_calendar
            for user in self.mapped('user_ids')
        }

        tasks_by_resource_calendar_dict = defaultdict(
            lambda: self.env[self._name])  # key = resource_calendar instance, value = tasks
        for task in self:
            if len(task.user_ids) == 1:
                tasks_by_resource_calendar_dict[calendar_by_user_dict[task.user_ids.id]] |= task
            else:
                tasks_by_resource_calendar_dict[default_calendar] |= task

        return tasks_by_resource_calendar_dict

    def write(self, vals):
        compute_default_planned_dates = None
        if not self.env.context.get('fsm_mode', False) and 'planned_date_begin' in vals and 'planned_date_end' in vals:  # if fsm_mode=True then the processing in industry_fsm module is done for these dates.
            compute_default_planned_dates = self.filtered(lambda task: not task.planned_date_begin and not task.planned_date_end)

        res = super().write(vals)

        if compute_default_planned_dates:
            # Take the default planned dates
            planned_date_begin = vals.get('planned_date_begin', False)
            planned_date_end = vals.get('planned_date_end', False)

            # Then sort the tasks by resource_calendar and finally compute the planned dates
            tasks_by_resource_calendar_dict = compute_default_planned_dates._get_tasks_by_resource_calendar_dict()
            for (calendar, tasks) in tasks_by_resource_calendar_dict.items():
                date_start, date_stop = self._calculate_planned_dates(planned_date_begin, planned_date_end, calendar=calendar)
                tasks.write({
                    'planned_date_begin': date_start,
                    'planned_date_end': date_stop,
                })

        return res

    # -------------------------------------
    # Business Methods : Auto-shift
    # -------------------------------------

    @api.model
    def _web_gantt_reschedule_get_empty_cache(self):
        """ Get an empty object that would be used in order to prevent successive database calls during the
            rescheduling process.

            :return: An object that contains reusable information in the context of gantt record rescheduling.
                     The elements added to the cache are:
                     * A dict which caches the work intervals per company or resource. The reason why the key is type
                       mixed is due to the fact that a company has no resource associated.
                       The work intervals are resource dependant, and we will "query" this work interval rather than
                       calling _work_intervals_batch to save some db queries.
                     * A dict with resource's intervals of validity/invalidity per company or resource. The intervals
                       where the resource is "valid", i.e. under contract for an employee, and "invalid", i.e.
                       intervals where the employee was not already there or has been fired. When an interval is in the
                       invalid interval of a resource, then there is a fallback on its company intervals
                       (see _update_work_intervals).
            :rtype: dict
        """
        empty_cache = super()._web_gantt_reschedule_get_empty_cache()
        empty_cache.update({
            self._WEB_GANTT_RESCHEDULE_WORK_INTERVALS_CACHE_KEY: defaultdict(Intervals),
            self._WEB_GANTT_RESCHEDULE_RESOURCE_VALIDITY_CACHE_KEY: defaultdict(
                lambda: {'valid': Intervals(), 'invalid': Intervals()}
            ),
        })
        return empty_cache

    def _web_gantt_reschedule_get_resource(self):
        """ Get the resource linked to the task. """
        self.ensure_one()
        return self.user_ids._get_project_task_resource() if len(self.user_ids) == 1 else self.env['resource.resource']

    def _web_gantt_reschedule_get_resource_entity(self):
        """ Get the resource entity linked to the task.
            The resource entity is either a company, either a resource to cope with resource invalidity
            (i.e. not under contract, not yet created...)
            This is used as key to keep information in the rescheduling business methods.
        """
        self.ensure_one()
        return self._web_gantt_reschedule_get_resource() or self.company_id or self.project_id.company_id

    def _web_gantt_reschedule_get_resource_calendars_validity(
            self, date_start, date_end, intervals_to_search=None, resource=None
    ):
        """ Get the calendars and resources (for instance to later get the work intervals for the provided date_start
            and date_end).

            :param date_start: A start date for the search
            :param date_end: A end date fot the search
            :param intervals_to_search: If given, the periods for which the calendars validity must be retrieved.
            :param resource: If given, it overrides the resource in self._get_resource
            :return: a dict `resource_calendar_validity` with calendars as keys and their validity as values,
                     a dict `resource_validity` with 'valid' and 'invalid' keys, with the intervals where the resource
                     has a valid calendar (resp. no calendar)
            :rtype: tuple(defaultdict(), dict())
        """
        self.ensure_one()
        interval = Intervals([(date_start, date_end, self.env['resource.calendar.attendance'])])
        if intervals_to_search:
            interval &= intervals_to_search
        invalid_interval = interval
        resource = self._web_gantt_reschedule_get_resource() if resource is None else resource
        resource_calendar_validity = resource._get_calendars_validity_within_period(
            date_start, date_end, default_company=self.company_id or self.project_id.company_id
        )[resource.id]
        for calendar in resource_calendar_validity:
            resource_calendar_validity[calendar] &= interval
            invalid_interval -= resource_calendar_validity[calendar]
        resource_validity = {
            'valid': interval - invalid_interval,
            'invalid': invalid_interval,
        }
        return resource_calendar_validity, resource_validity

    def _web_gantt_reschedule_update_work_intervals(
            self, interval_to_search, cache, resource=None, resource_entity=None
    ):
        """ Update intervals cache if the interval to search for hasn't already been requested for work intervals.

            If the resource_entity has some parts of the interval_to_search which is unknown yet, then the calendar
            of the resource_entity must be retrieved and queried to have the work intervals. If the resource_entity
            is invalid (i.e. was not yet created, not under contract or fired)

            :param interval_to_search: Intervals for which we need to update the work_intervals if the interval
                   is not already searched
            :param cache: An object that contains reusable information in the context of gantt record rescheduling.
        """
        resource = self._web_gantt_reschedule_get_resource() if resource is None else resource
        resource_entity = self._web_gantt_reschedule_get_resource_entity() if resource_entity is None else resource_entity
        work_intervals, resource_validity = self._web_gantt_reschedule_extract_cache_info(cache)
        intervals_not_searched = interval_to_search - resource_validity[resource_entity]['valid'] \
            - resource_validity[resource_entity]['invalid']

        if not intervals_not_searched:
            return

        # For at least a part of the task, we don't have the work information of the resource
        # The interval between the very first date of the interval_to_search to the very last must be explored
        resource_calendar_validity_delta, resource_validity_tmp = self._web_gantt_reschedule_get_resource_calendars_validity(
            intervals_not_searched._items[0][0],
            intervals_not_searched._items[-1][1],
            intervals_to_search=intervals_not_searched, resource=resource
        )
        for calendar in resource_calendar_validity_delta:
            if not resource_calendar_validity_delta[calendar]:
                continue
            work_intervals[resource_entity] |= calendar._work_intervals_batch(
                resource_calendar_validity_delta[calendar]._items[0][0],
                resource_calendar_validity_delta[calendar]._items[-1][1],
                resources=resource
            )[resource.id] & resource_calendar_validity_delta[calendar]
        resource_validity[resource_entity]['valid'] |= resource_validity_tmp['valid']
        if resource_validity_tmp['invalid']:
            # If the resource is not valid for a given period (not yet created, not under contract...)
            # There is a fallback on its company calendar.
            resource_validity[resource_entity]['invalid'] |= resource_validity_tmp['invalid']
            company = self.company_id or self.project_id.company_id
            self._web_gantt_reschedule_update_work_intervals(
                interval_to_search, cache,
                resource=self.env['resource.resource'], resource_entity=company
            )
            # Fill the intervals cache of the resource entity with the intervals of the company.
            work_intervals[resource_entity] |= resource_validity_tmp['invalid'] & work_intervals[company]

    @api.model
    def _web_gantt_reschedule_get_interval_auto_shift(self, current, delta):
        """ Get the Intervals from current and current + delta, and in the right order.

            :param current: Baseline of the interval, its start if search_forward is true, its stop otherwise
            :param delta: Timedelta duration of the interval, expected to be positive if search_forward is True,
                          False otherwise
            :param search_forward: Interval direction, forward if True, backward otherwise.
        """
        start, stop = sorted([current, current + delta])
        return Intervals([(start, stop, self.env['resource.calendar.attendance'])])

    @api.model
    def _web_gantt_reschedule_extract_cache_info(self, cache):
        """ Extract the work_intervals and resource_validity

            :param cache: An object that contains reusable information in the context of gantt record rescheduling.
            :return: a tuple (work_intervals, resource_validity) where:
                     * work_intervals is a dict which caches the work intervals per company or resource. The reason why
                       the key is type mixed is due to the fact that a company has no resource associated.
                       The work intervals are resource dependant, and we will "query" this work interval rather than
                       calling _work_intervals_batch to save some db queries.
                     * resource_validity is a dict with resource's intervals of validity/invalidity per company or
                       resource. The intervals where the resource is "valid", i.e. under contract for an employee,
                       and "invalid", i.e. intervals where the employee was not already there or has been fired.
                       When an interval is in the invalid interval of a resource, then there is a fallback on its
                       company intervals (see _update_work_intervals).

        """
        return cache[self._WEB_GANTT_RESCHEDULE_WORK_INTERVALS_CACHE_KEY], \
            cache[self._WEB_GANTT_RESCHEDULE_RESOURCE_VALIDITY_CACHE_KEY]

    def _web_gantt_reschedule_get_first_working_datetime(self, date_candidate, cache, search_forward=True):
        """ Find and return the first work datetime for the provided work_intervals that matches the date_candidate
            and search_forward criteria. If there is no match in the work_intervals, the cache is updated and filled
            with work intervals for a larger date range.

            :param date_candidate: The date the work interval is searched for. If no exact match can be done,
                                   the closest is returned.
            :param cache: An object that contains reusable information in the context of gantt record rescheduling.
            :param search_forward: The search direction.
                                   Having search_forward truthy causes the search to be made chronologically,
                                   looking for an interval that matches interval_start <= date_time < interval_end.
                                   Having search_forward falsy causes the search to be made reverse chronologically,
                                   looking for an interval that matches interval_start < date_time <= interval_end.
            :return: datetime. The closest datetime that matches the search criteria and the
                     work_intervals updated with the data fetched from the database if any.
        """
        self.ensure_one()
        assert date_candidate.tzinfo
        delta = (1 if search_forward else -1) * relativedelta(months=1)
        date_to_search = date_candidate
        resource_entity = self._web_gantt_reschedule_get_resource_entity()

        interval_to_search = self._web_gantt_reschedule_get_interval_auto_shift(date_to_search, delta)

        work_intervals, dummy = self._web_gantt_reschedule_extract_cache_info(cache)
        interval = work_intervals[resource_entity] & interval_to_search
        while not interval:
            self._web_gantt_reschedule_update_work_intervals(interval_to_search, cache)
            interval = work_intervals[resource_entity] & interval_to_search
            date_to_search += delta
            interval_to_search = self._web_gantt_reschedule_get_interval_auto_shift(date_to_search, delta)

        return interval._items[0][0] if search_forward else interval._items[-1][1]

    @api.model
    def _web_gantt_reschedule_plan_hours_auto_shift(self, intervals, hours_to_plan, searched_date, search_forward=True):
        """ Get datetime after having planned hours from a searched date, in the future (search_forward) or in the
            past (not search_forward) given the intervals.

            :param intervals: The intervals to browse.
            :param : The remaining hours to plan.
            :param searched_date: The current value of the search_date.
            :param search_forward: The search direction. Having search_forward truthy causes the search to be made
                                   chronologically.
                                   Having search_forward falsy causes the search to be made reverse chronologically.
            :return: tuple ``(planned_hours, searched_date)``.
        """
        if not intervals:
            return hours_to_plan, searched_date
        if search_forward:
            interval = (searched_date, intervals._items[-1][1], self.env['resource.calendar.attendance'])
            intervals_to_browse = Intervals([interval]) & intervals
        else:
            interval = (intervals._items[0][0], searched_date, self.env['resource.calendar.attendance'])
            intervals_to_browse = reversed(Intervals([interval]) & intervals)
        new_planned_date = searched_date
        for interval in intervals_to_browse:
            delta = min(hours_to_plan, interval[1] - interval[0])
            new_planned_date = interval[0] + delta if search_forward else interval[1] - delta
            hours_to_plan -= delta
            if hours_to_plan <= timedelta(hours=0.0):
                break
        return hours_to_plan, new_planned_date

    def _web_gantt_reschedule_compute_dates(
            self, date_candidate, search_forward, start_date_field_name, stop_date_field_name, cache
    ):
        """ Compute start_date and end_date according to the provided arguments.
            This method is meant to be overridden when we need to add constraints that have to be taken into account
            in the computing of the start_date and end_date.

            :param date_candidate: The optimal date, which does not take any constraint into account.
            :param start_date_field_name: The start date field used in the gantt view.
            :param stop_date_field_name: The stop date field used in the gantt view.
            :param cache: An object that contains reusable information in the context of gantt record rescheduling.
            :return: a tuple of (start_date, end_date)
            :rtype: tuple(datetime, datetime)
        """

        first_datetime = self._web_gantt_reschedule_get_first_working_datetime(
            date_candidate, cache, search_forward=search_forward
        )

        search_factor = 1 if search_forward else -1
        if not self.planned_hours:
            # If there are no planned hours, keep the current duration
            duration = search_factor * (self[stop_date_field_name] - self[start_date_field_name])
            return sorted([first_datetime, first_datetime + duration])

        searched_date = current = first_datetime
        planned_hours = timedelta(hours=self.planned_hours)

        # Keeps track of the hours that have already been covered.
        hours_to_plan = planned_hours
        MIN_NUMB_OF_WEEKS = 1
        MAX_ELAPSED_TIME = timedelta(weeks=53)
        resource_entity = self._web_gantt_reschedule_get_resource_entity()
        work_intervals, dummy = self._web_gantt_reschedule_extract_cache_info(cache)
        while hours_to_plan > timedelta(hours=0.0) and search_factor * (current - first_datetime) < MAX_ELAPSED_TIME:
            # Look for the missing intervals with min search of 1 week
            delta = search_factor * max(hours_to_plan * 3, timedelta(weeks=MIN_NUMB_OF_WEEKS))
            task_interval = self._web_gantt_reschedule_get_interval_auto_shift(current, delta)
            self._web_gantt_reschedule_update_work_intervals(task_interval, cache)
            work_intervals_entry = work_intervals[resource_entity] & task_interval
            hours_to_plan, searched_date = self._web_gantt_reschedule_plan_hours_auto_shift(
                work_intervals_entry, hours_to_plan, searched_date, search_forward
            )
            current += delta

        if hours_to_plan > timedelta(hours=0.0):
            # Reached max iterations
            return False, False

        return sorted([first_datetime, searched_date])

    @api.model
    def _web_gantt_reschedule_is_record_candidate(self, start_date_field_name, stop_date_field_name):
        """ Get whether the record is a candidate for the rescheduling. This method is meant to be overridden when
            we need to add a constraint in order to prevent some records to be rescheduled. This method focuses on the
            record itself (if you need to have information on the relation (master and slave) rather override
            _web_gantt_reschedule_is_relation_candidate).

            :param start_date_field_name: The start date field used in the gantt view.
            :param stop_date_field_name: The stop date field used in the gantt view.
            :return: True if record can be rescheduled, False if not.
            :rtype: bool
        """
        is_record_candidate = super()._web_gantt_reschedule_is_record_candidate(start_date_field_name, stop_date_field_name)
        return is_record_candidate and self.project_id.allow_task_dependencies and not self.is_closed

    @api.model
    def _web_gantt_reschedule_is_relation_candidate(self, master, slave, start_date_field_name, stop_date_field_name):
        """ Get whether the relation between master and slave is a candidate for the rescheduling. This method is meant
            to be overridden when we need to add a constraint in order to prevent some records to be rescheduled.
            This method focuses on the relation between records (if your logic is rather on one record, rather override
            _web_gantt_reschedule_is_record_candidate).

            :param master: The master record we need to evaluate whether it is a candidate for rescheduling or not.
            :param slave: The slave record.
            :param start_date_field_name: The start date field used in the gantt view.
            :param stop_date_field_name: The stop date field used in the gantt view.
            :return: True if record can be rescheduled, False if not.
            :rtype: bool
        """
        is_relative_candidate = super()._web_gantt_reschedule_is_relation_candidate(
            master, slave,
            start_date_field_name, stop_date_field_name
        )
        return is_relative_candidate and master.project_id == slave.project_id

    # ----------------------------------------------------
    # Overlapping tasks
    # ----------------------------------------------------

    def action_fsm_view_overlapping_tasks(self):
        self.ensure_one()
        action = self.env['ir.actions.act_window']._for_xml_id('project.action_view_all_task')
        if 'views' in action:
            gantt_view = self.env.ref("project_enterprise.project_task_dependency_view_gantt")
            map_view = self.env.ref('project_enterprise.project_task_map_view_no_title')
            action['views'] = [(gantt_view.id, 'gantt'), (map_view.id, 'map')] + [(state, view) for state, view in action['views'] if view not in ['gantt', 'map']]
        action.update({
            'name': _('Overlapping Tasks'),
            'context': {
                'fsm_mode': False,
                'task_nameget_with_hours': False,
                'initialDate': self.planned_date_begin,
                'search_default_conflict_task': True,
                'search_default_planned_date_begin': self.planned_date_begin,
                'search_default_planned_date_end': self.planned_date_end,
                'search_default_user_ids': self.user_ids.ids,
            }
        })
        return action

    # ----------------------------------------------------
    # Gantt view
    # ----------------------------------------------------

    @api.model
    def gantt_unavailability(self, start_date, end_date, scale, group_bys=None, rows=None):
        start_datetime = fields.Datetime.from_string(start_date)
        end_datetime = fields.Datetime.from_string(end_date)
        user_ids = set()

        # function to "mark" top level rows concerning users
        # the propagation of that user_id to subrows is taken care of in the traverse function below
        def tag_user_rows(rows):
            for row in rows:
                group_bys = row.get('groupedBy')
                res_id = row.get('resId')
                if group_bys:
                    # if user_ids is the first grouping attribute
                    if group_bys[0] == 'user_ids' and res_id:
                        user_id = res_id
                        user_ids.add(user_id)
                        row['user_id'] = user_id
                    # else we recursively traverse the rows
                    elif 'user_ids' in group_bys:
                        tag_user_rows(row.get('rows'))

        tag_user_rows(rows)
        resources = self.env['res.users'].browse(user_ids).mapped('resource_ids').filtered(lambda r: r.company_id.id == self.env.company.id)
        # we reverse sort the resources by date to keep the first one created in the dictionary
        # to anticipate the case of a resource added later for the same employee and company
        user_resource_mapping = {resource.user_id.id: resource.id for resource in resources.sorted('create_date', True)}
        leaves_mapping = resources._get_unavailable_intervals(start_datetime, end_datetime)
        company_leaves = self.env.company.resource_calendar_id._unavailable_intervals(start_datetime.replace(tzinfo=utc), end_datetime.replace(tzinfo=utc))

        # function to recursively replace subrows with the ones returned by func
        def traverse(func, row):
            new_row = dict(row)
            if new_row.get('user_id'):
                for sub_row in new_row.get('rows'):
                    sub_row['user_id'] = new_row['user_id']
            new_row['rows'] = [traverse(func, row) for row in new_row.get('rows')]
            return func(new_row)

        cell_dt = timedelta(hours=1) if scale in ['day', 'week'] else timedelta(hours=12)

        # for a single row, inject unavailability data
        def inject_unavailability(row):
            new_row = dict(row)
            user_id = row.get('user_id')
            calendar = company_leaves
            if user_id:
                resource_id = user_resource_mapping.get(user_id)
                if resource_id:
                    calendar = leaves_mapping[resource_id]

            # remove intervals smaller than a cell, as they will cause half a cell to turn grey
            # ie: when looking at a week, a employee start everyday at 8, so there is a unavailability
            # like: 2019-05-22 20:00 -> 2019-05-23 08:00 which will make the first half of the 23's cell grey
            notable_intervals = filter(lambda interval: interval[1] - interval[0] >= cell_dt, calendar)
            new_row['unavailabilities'] = [{'start': interval[0], 'stop': interval[1]} for interval in notable_intervals]
            return new_row

        return [traverse(inject_unavailability, row) for row in rows]

    def _get_recurrence_start_date(self):
        self.ensure_one()
        return self.planned_date_begin or fields.Date.today()

    @api.depends('planned_date_begin')
    def _compute_recurrence_message(self):
        return super(Task, self)._compute_recurrence_message()

    def action_dependent_tasks(self):
        action = super().action_dependent_tasks()
        action['view_mode'] = 'tree,form,kanban,calendar,pivot,graph,gantt,activity,map'
        return action

    def action_recurring_tasks(self):
        action = super().action_recurring_tasks()
        action['view_mode'] = 'tree,form,kanban,calendar,pivot,graph,gantt,activity,map'
        return action

    def _web_gantt_progress_bar_user_ids(self, res_ids, start, stop):
        start_naive, stop_naive = start.replace(tzinfo=None), stop.replace(tzinfo=None)
        users = self.env['res.users'].search([('id', 'in', res_ids)])
        self.env['project.task'].check_access_rights('read')

        project_tasks = self.env['project.task'].sudo().search([
            ('user_ids', 'in', res_ids),
            ('planned_date_begin', '<=', stop_naive),
            ('planned_date_end', '>=', start_naive),
        ])

        planned_hours_mapped = defaultdict(float)
        user_work_intervals, _dummy = users.sudo()._get_valid_work_intervals(start, stop)
        for task in project_tasks:
            # if the task goes over the gantt period, compute the duration only within
            # the gantt period
            max_start = max(start, utc.localize(task.planned_date_begin))
            min_end = min(stop, utc.localize(task.planned_date_end))
            # for forecast tasks, use the conjunction between work intervals and task.
            interval = Intervals([(
                max_start, min_end, self.env['resource.calendar.attendance']
            )])
            nb_hours_per_user = (sum_intervals(interval) / (len(task.user_ids) or 1)) if task.allocation_type == 'duration' else 0.0
            for user in task.user_ids:
                if task.allocation_type == 'duration':
                    planned_hours_mapped[user.id] += nb_hours_per_user
                else:
                    work_intervals = interval & user_work_intervals[user.id]
                    planned_hours_mapped[user.id] += sum_intervals(work_intervals)
        # Compute employee work hours based on its work intervals.
        work_hours = {
            user_id: sum_intervals(work_intervals)
            for user_id, work_intervals in user_work_intervals.items()
        }
        return {
            user.id: {
                'value': planned_hours_mapped[user.id],
                'max_value': work_hours.get(user.id, 0.0),
            }
            for user in users
        }

    def _web_gantt_progress_bar(self, field, res_ids, start, stop):
        if field == 'user_ids':
            return dict(
                self._web_gantt_progress_bar_user_ids(res_ids, start, stop),
                warning=_("This user isn't expected to have task during this period. Planned hours :"),
            )
        raise NotImplementedError("This Progress Bar is not implemented.")

    @api.model
    def gantt_progress_bar(self, fields, res_ids, date_start_str, date_stop_str):
        if not self.user_has_groups("project.group_project_user"):
            return {field: {} for field in fields}
        start_utc, stop_utc = string_to_datetime(date_start_str), string_to_datetime(date_stop_str)

        progress_bars = {}
        for field in fields:
            progress_bars[field] = self._web_gantt_progress_bar(field, res_ids[field], start_utc, stop_utc)

        return progress_bars
