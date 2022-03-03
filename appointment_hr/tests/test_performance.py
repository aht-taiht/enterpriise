# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

import random
import time

from datetime import date, timedelta
from freezegun import freeze_time
from logging import getLogger

from odoo.addons.appointment_hr.tests.common import AppointmentHrCommon
from odoo.addons.website.tests.test_performance import UtilPerf
from odoo.tests import tagged, users
from odoo.tests.common import warmup

_logger = getLogger(__name__)


class AppointmenHrPerformanceCase(AppointmentHrCommon):

    @classmethod
    def setUpClass(cls):
        super(AppointmenHrPerformanceCase, cls).setUpClass()

        cls.test_calendar = cls.env['resource.calendar'].create({
            'company_id': cls.company_admin.id,
            'name': 'Test Calendar',
            'tz': 'Europe/Brussels',
        })

        cls.staff_users = cls.env['res.users'].with_context(cls._test_context).create([
            {'company_id': cls.company_admin.id,
             'company_ids': [(4, cls.company_admin.id)],
             'email': 'brussels.%s@test.example.com' % idx,
             'groups_id': [(4, cls.env.ref('base.group_user').id)],
             'name': 'Employee Brussels %s' % idx,
             'login': 'staff_users_bxl_%s' % idx,
             'notification_type': 'email',
             'tz': 'Europe/Brussels',
            } for idx in range(20)
        ])

        # User resources and employees
        cls.staff_users_resources = cls.env['resource.resource'].create([
            {'calendar_id': cls.test_calendar.id,
             'company_id': user.company_id.id,
             'name': user.name,
             'user_id': user.id,
             'tz': user.tz,
            } for user in cls.staff_users
        ])
        cls.staff_users_employees = cls.env['hr.employee'].create([
            {'company_id': user.company_id.id,
             'resource_calendar_id': cls.test_calendar.id,
             'resource_id': cls.staff_users_resources[user_idx].id,
            } for user_idx, user in enumerate(cls.staff_users)
        ])

        # Events and leaves
        cls.test_events = cls.env['calendar.event'].with_context(cls._test_context).create([
            {'attendee_ids': [(0, 0, {'partner_id': user.partner_id.id})],
             'name': 'Event for %s' % user.name,
             'partner_ids': [(4, user.partner_id.id)],
             'start': cls.reference_monday + timedelta(weeks=week_idx, days=day_idx, hours=(user_idx / 4)),
             'stop': cls.reference_monday + timedelta(weeks=week_idx, days=day_idx, hours=(user_idx / 4) + 1),
             'user_id': user.id,
            }
            for day_idx in range(5)
            for week_idx in range(5)
            for user_idx, user in enumerate(cls.staff_users)
        ])
        cls.test_leaves = cls.env['resource.calendar.leaves'].with_context(cls._test_context).create([
            {'calendar_id': user.resource_calendar_id.id,
             'company_id': user.company_id.id,
             'date_from': cls.reference_monday + timedelta(weeks=week_idx * 2, days=(user_idx / 4), hours=2),
             'date_to': cls.reference_monday + timedelta(weeks=week_idx * 2, days=(user_idx / 4), hours=8),
             'name': 'Leave for %s' % user.name,
             'resource_id': user.resource_ids[0].id,
             'time_type': 'leave',
            }
            for week_idx in range(5)  # one leave every 2 weeks
            for user_idx, user in enumerate(cls.staff_users)
        ])

        cls.test_apt_type = cls.env['calendar.appointment.type'].create({
            'appointment_tz': 'Europe/Brussels',
            'appointment_duration': 1,
            'assign_method': 'random',
            'category': 'website',
            'max_schedule_days': 60,
            'min_cancellation_hours': 1,
            'min_schedule_hours': 1,
            'name': 'Test Appointment Type',
            'slot_ids': [
                (0, 0, {'end_hour': hour + 1,
                        'start_hour': hour,
                        'weekday': weekday,
                        })
                for weekday in ['1', '2', '3', '4', '5']
                for hour in range(8, 16)
            ],
            'staff_user_ids': [(4, user.id) for user in cls.staff_users],
            'work_hours_activated': True,
        })

    def setUp(self):
        super(AppointmenHrPerformanceCase, self).setUp()
        # patch registry to simulate a ready environment
        self.patch(self.env.registry, 'ready', True)
        self._flush_tracking()


@tagged('appointment_performance', 'post_install', '-at_install')
class AppointmentTest(AppointmenHrPerformanceCase):

    def test_appointment_initial_values(self):
        """ Check initial values to ease understanding and reproducing tests. """
        self.assertEqual(len(self.test_apt_type.slot_ids), 40)
        self.assertTrue(all(employee.resource_id for employee in self.staff_users_employees))
        self.assertTrue(all(employee.resource_id.calendar_id for employee in self.staff_users_employees))
        self.assertTrue(all(employee.user_id for employee in self.staff_users_employees))

    @users('staff_user_bxls')
    def test_get_appointment_slots_custom(self):
        """ Custom type: mono user, unique slots, work hours check. """
        apt_type_custom_bxls = self.env['calendar.appointment.type'].sudo().create({
            'appointment_tz': 'Europe/Brussels',
            'appointment_duration': 1,
            'assign_method': 'random',
            'category': 'custom',
            'location': 'Bxls Office',
            'name': 'Bxls Appt Type',
            'min_cancellation_hours': 1,
            'min_schedule_hours': 1,
            'max_schedule_days': 30,
            'slot_ids': [
                (0, 0, {'end_datetime': self.reference_monday + timedelta(days=day, hours=hour + 1),
                        'start_datetime': self.reference_monday + timedelta(days=day, hours=hour),
                        'slot_type': 'unique',
                        'weekday': '1',  # not used actually
                       }
                )
                for day in range(30)
                for hour in range(8, 16)
            ],
            'staff_user_ids': [(4, self.staff_users[0].id)],
            'work_hours_activated': False,
        })
        apt_type_custom_bxls.flush()
        apt_type_custom_bxls = apt_type_custom_bxls.with_user(self.env.user)

        # with self.profile(collectors=['sql']) as profile:
        with self.mockAppointmentCalls(), \
             self.assertQueryCount(staff_user_bxls=504):  # apt only: 500
            t0 = time.time()
            res = apt_type_custom_bxls._get_appointment_slots('Europe/Brussels', reference_date=self.reference_now)
            t1 = time.time()

        _logger.info('Called _get_appointment_slots, time %.3f', t1 - t0)
        _logger.info('Called methods\nSearch calendar event called %s\n'
                     'Search count calendar event called %s\n'
                     'Partner calendar check called %s\n'
                     'Resource Calendar work intervals batch called %s',
                     self._mock_calevent_search.call_count,
                     self._mock_calevent_search_count.call_count,
                     self._mock_partner_calendar_check.call_count,
                     self._mock_cal_work_intervals.call_count)
        # Time before optimization: ~0.45
        # Method count before optimization: 480 - 480 - 480 - 1

        global_slots_startdate = self.reference_now_monthweekstart
        global_slots_enddate = date(2022, 4, 2)  # last day of last week of May
        self.assertSlots(
            res,
            [{'name_formated': 'February 2022',
              'weeks_count': 5,  # 30/01 -> 27/02 (05/03)
             },
             {'name_formated': 'March 2022',
              'weeks_count': 5,  # 27/02 -> 27/03 (02/04)
             }
            ],
            {'enddate': global_slots_enddate,
             'startdate': global_slots_startdate,
            }
        )

    @users('staff_user_bxls')
    def test_get_appointment_slots_custom_whours(self):
        """ Custom type: mono user, unique slots, work hours check. """
        apt_type_custom_bxls = self.env['calendar.appointment.type'].sudo().create({
            'appointment_tz': 'Europe/Brussels',
            'appointment_duration': 1,
            'assign_method': 'random',
            'category': 'custom',
            'location': 'Bxls Office',
            'name': 'Bxls Appt Type',
            'min_cancellation_hours': 1,
            'min_schedule_hours': 1,
            'max_schedule_days': 30,
            'slot_ids': [
                (0, 0, {'end_datetime': self.reference_monday + timedelta(days=day, hours=hour + 1),
                        'start_datetime': self.reference_monday + timedelta(days=day, hours=hour),
                        'slot_type': 'unique',
                        'weekday': '1',  # not used actually
                       }
                )
                for day in range(30)
                for hour in range(8, 16)
            ],
            'staff_user_ids': [(4, self.staff_users[0].id)],
            'work_hours_activated': True,
        })
        apt_type_custom_bxls.flush()
        apt_type_custom_bxls = apt_type_custom_bxls.with_user(self.env.user)

        # with self.profile(collectors=['sql']) as profile:
        with self.mockAppointmentCalls(), \
             self.assertQueryCount(staff_user_bxls=504):  # apt only: 500
            t0 = time.time()
            res = apt_type_custom_bxls._get_appointment_slots('Europe/Brussels', reference_date=self.reference_now)
            t1 = time.time()

        _logger.info('Called _get_appointment_slots, time %.3f', t1 - t0)
        _logger.info('Called methods\nSearch calendar event called %s\n'
                     'Search count calendar event called %s\n'
                     'Partner calendar check called %s\n'
                     'Resource Calendar work intervals batch called %s',
                     self._mock_calevent_search.call_count,
                     self._mock_calevent_search_count.call_count,
                     self._mock_partner_calendar_check.call_count,
                     self._mock_cal_work_intervals.call_count)
        # Time before optimization: ~0.48
        # Method count before optimization: 480 - 480 - 480 - 1

        global_slots_startdate = self.reference_now_monthweekstart
        global_slots_enddate = date(2022, 4, 2)  # last day of last week of May
        self.assertSlots(
            res,
            [{'name_formated': 'February 2022',
              'weeks_count': 5,  # 30/01 -> 27/02 (05/03)
             },
             {'name_formated': 'March 2022',
              'weeks_count': 5,  # 27/02 -> 27/03 (02/04)
             }
            ],
            {'enddate': global_slots_enddate,
             'startdate': global_slots_startdate,
            }
        )

    @users('staff_user_bxls')
    def test_get_appointment_slots_website(self):
        """ Website type: multi users (choose first available), without working
        hours. """
        random.seed(1871)  # fix shuffle in _slots_available
        self.test_apt_type.write({'work_hours_activated': False})
        apt_type = self.test_apt_type.with_user(self.env.user)

        # with self.profile(collectors=['sql']) as profile:
        with self.mockAppointmentCalls(), \
             self.assertQueryCount(staff_user_bxls=514):  # apt only: 507
            t0 = time.time()
            res = apt_type._get_appointment_slots('Europe/Brussels', reference_date=self.reference_now)
            t1 = time.time()

        _logger.info('Called _get_appointment_slots, time %.3f', t1 - t0)
        _logger.info('Called methods\nSearch calendar event called %s\n'
                     'Search count calendar event called %s\n'
                     'Partner calendar check called %s\n'
                     'Resource Calendar work intervals batch called %s',
                     self._mock_calevent_search.call_count,
                     self._mock_calevent_search_count.call_count,
                     self._mock_partner_calendar_check.call_count,
                     self._mock_cal_work_intervals.call_count)
        # Time before optimization: ~1.0
        # Method count before optimization: 402 - 402 - 402 - 20

        global_slots_startdate = self.reference_now_monthweekstart
        global_slots_enddate = date(2022, 4, 30)  # last day of last week of April
        self.assertSlots(
            res,
            [{'name_formated': 'February 2022',
              'weeks_count': 5,  # 30/01 -> 27/02 (05/03)
             },
             {'name_formated': 'March 2022',
              'weeks_count': 5,  # 27/02 -> 27/03 (02/04)
             },
             {'name_formated': 'April 2022',
              'weeks_count': 5,  # 27/03 -> 24/04 (30/04)
             }
            ],
            {'enddate': global_slots_enddate,
             'slots_duration': 1,
             'slots_hours': range(8, 16, 1),
             'slots_startdt': self.reference_monday,
             'startdate': global_slots_startdate,
            }
        )

    @users('staff_user_bxls')
    def test_get_appointment_slots_website_whours(self):
        """ Website type: multi users (choose first available), with working hours
        involved. """
        random.seed(1871)  # fix shuffle in _slots_available
        apt_type = self.test_apt_type.with_user(self.env.user)

        # with self.profile(collectors=['sql']) as profile:
        with self.mockAppointmentCalls(), \
             self.assertQueryCount(staff_user_bxls=1373):  # apt only: 1366
            t0 = time.time()
            res = apt_type._get_appointment_slots('Europe/Brussels', reference_date=self.reference_now)
            t1 = time.time()

        _logger.info('Called _get_appointment_slots, time %.3f', t1 - t0)
        _logger.info('Called methods\nSearch calendar event called %s\n'
                     'Search count calendar event called %s\n'
                     'Partner calendar check called %s\n'
                     'Resource Calendar work intervals batch called %s',
                     self._mock_calevent_search.call_count,
                     self._mock_calevent_search_count.call_count,
                     self._mock_partner_calendar_check.call_count,
                     self._mock_cal_work_intervals.call_count)
        # Time before optimization: ~1.8
        # Method count before optimization: 1261 - 1261 - 1261 - 20

        global_slots_startdate = self.reference_now_monthweekstart
        global_slots_enddate = date(2022, 4, 30)  # last day of last week of April
        self.assertSlots(
            res,
            [{'name_formated': 'February 2022',
              'weeks_count': 5,  # 30/01 -> 27/02 (05/03)
             },
             {'name_formated': 'March 2022',
              'weeks_count': 5,  # 27/02 -> 27/03 (02/04)
             },
             {'name_formated': 'April 2022',
              'weeks_count': 5,  # 27/03 -> 24/04 (30/04)
             }
            ],
            {'enddate': global_slots_enddate,
             'slots_duration': 1,
             'slots_hours': range(8, 16, 1),
             'slots_startdt': self.reference_monday,
             'startdate': global_slots_startdate,
            }
        )

    @users('staff_user_bxls')
    def test_get_appointment_slots_website_whours_short(self):
        """ Website type: multi users (choose first available), with working hours
        involved. """
        random.seed(1871)  # fix shuffle in _slots_available
        self.test_apt_type.write({'max_schedule_days': 10})
        self.test_apt_type.flush()
        apt_type = self.test_apt_type.with_user(self.env.user)

        # with self.profile(collectors=['sql']) as profile:
        with self.mockAppointmentCalls(), \
             self.assertQueryCount(staff_user_bxls=349):  # apt only: 342
            t0 = time.time()
            res = apt_type._get_appointment_slots('Europe/Brussels', reference_date=self.reference_now)
            t1 = time.time()

        _logger.info('Called _get_appointment_slots, time %.3f', t1 - t0)
        _logger.info('Called methods\nSearch calendar event called %s\n'
                     'Search count calendar event called %s\n'
                     'Partner calendar check called %s\n'
                     'Resource Calendar work intervals batch called %s',
                     self._mock_calevent_search.call_count,
                     self._mock_calevent_search_count.call_count,
                     self._mock_partner_calendar_check.call_count,
                     self._mock_cal_work_intervals.call_count)
        # Time before optimization: ~0.35
        # Method count before optimization: 237 - 237 - 237 - 20

        global_slots_startdate = self.reference_now_monthweekstart
        global_slots_enddate = date(2022, 3, 5)  # last day of last week of Feb
        self.assertSlots(
            res,
            [{'name_formated': 'February 2022',
              'weeks_count': 5,  # 30/01 -> 27/02 (05/03)
             }
            ],
            {'enddate': global_slots_enddate,
             'startdate': global_slots_startdate,
            }
        )

    @warmup
    @users('staff_user_bxls')
    def test_get_appointment_slots_website_whours_short_warmup(self):
        """ Website type: multi users (choose first available), with working hours
        involved. """
        random.seed(1871)  # fix shuffle in _slots_available
        self.test_apt_type.write({'max_schedule_days': 10})
        self.test_apt_type.flush()
        apt_type = self.test_apt_type.with_user(self.env.user)

        # with self.profile(collectors=['sql']) as profile:
        with self.mockAppointmentCalls(), \
             self.assertQueryCount(staff_user_bxls=324):  # apt only: 317
            t0 = time.time()
            res = apt_type._get_appointment_slots('Europe/Brussels', reference_date=self.reference_now)
            t1 = time.time()

        _logger.info('Called _get_appointment_slots, time %.3f', t1 - t0)
        _logger.info('Called methods\nSearch calendar event called %s\n'
                     'Search count calendar event called %s\n'
                     'Partner calendar check called %s\n'
                     'Resource Calendar work intervals batch called %s',
                     self._mock_calevent_search.call_count,
                     self._mock_calevent_search_count.call_count,
                     self._mock_partner_calendar_check.call_count,
                     self._mock_cal_work_intervals.call_count)
        # Time before optimization: ~0.35
        # Method count before optimization: 237 - 237 - 237 - 20

        global_slots_startdate = self.reference_now_monthweekstart
        global_slots_enddate = date(2022, 3, 5)  # last day of last week of Feb
        self.assertSlots(
            res,
            [{'name_formated': 'February 2022',
              'weeks_count': 5,  # 30/01 -> 27/02 (05/03)
             }
            ],
            {'enddate': global_slots_enddate,
             'startdate': global_slots_startdate,
            }
        )

    @users('staff_user_bxls')
    def test_get_appointment_slots_work_hours(self):
        """ Work hours type: mono user, involved work hours check. """
        self.apt_type_bxls_2days.write({
            'category': 'work_hours',
            'max_schedule_days': 90,
            'slot_ids': [(5, 0)] + [  # while loop in _slots_generate generates the actual slots
                (0, 0, {'end_hour': 23.99,
                        'start_hour': hour * 0.5,
                        'weekday': str(day + 1),
                       }
                )
                for hour in range(2)
                for day in range(7)
            ],
            'staff_user_ids': [(5, 0), (4, self.staff_users[0].id)],
            'work_hours_activated': True,
            })
        self.apt_type_bxls_2days.flush()
        apt_type = self.apt_type_bxls_2days.with_user(self.env.user)

        # with self.profile(collectors=['sql']) as profile:
        with self.mockAppointmentCalls(), \
             self.assertQueryCount(staff_user_bxls=4215):  # apt only: 4210
            t0 = time.time()
            res = apt_type._get_appointment_slots('Europe/Brussels', reference_date=self.reference_now)
            t1 = time.time()

        _logger.info('Called _get_appointment_slots, time %.3f', t1 - t0)
        _logger.info('Called methods\nSearch calendar event called %s\n'
                     'Search count calendar event called %s\n'
                     'Partner calendar check called %s\n'
                     'Resource Calendar work intervals batch called %s',
                     self._mock_calevent_search.call_count,
                     self._mock_calevent_search_count.call_count,
                     self._mock_partner_calendar_check.call_count,
                     self._mock_cal_work_intervals.call_count)
        # Time before optimization: ~3.40
        # Method count before optimization: 4186 - 4186 - 4186 - 1

        global_slots_startdate = date(2022, 1, 30)  # starts on a Sunday, first week containing Feb day
        global_slots_enddate = date(2022, 6, 4)  # last day of last week of May
        self.assertSlots(
            res,
            [{'name_formated': 'February 2022',
              'weeks_count': 5,  # 30/01 -> 27/02 (05/03)
             },
             {'name_formated': 'March 2022',
              'weeks_count': 5,  # 27/02 -> 27/03 (02/04)
             },
             {'name_formated': 'April 2022',
              'weeks_count': 5,
             },
             {'name_formated': 'May 2022',
              'weeks_count': 5,
             },
            ],
            {'enddate': global_slots_enddate,
             'startdate': global_slots_startdate,
            }
        )

    @users('staff_user_bxls')
    def test_get_appointment_slots_work_hours_short(self):
        """ Work hours type: mono user, involved work hours check. """
        self.apt_type_bxls_2days.write({
            'category': 'work_hours',
            'max_schedule_days': 10,
            'slot_ids': [(5, 0)] + [  # while loop in _slots_generate generates the actual slots
                (0, 0, {'end_hour': 23.99,
                        'start_hour': hour * 0.5,
                        'weekday': str(day + 1),
                       }
                )
                for hour in range(2)
                for day in range(7)
            ],
            'staff_user_ids': [(5, 0), (4, self.staff_users[0].id)],
            'work_hours_activated': True,
        })
        self.apt_type_bxls_2days.flush()
        apt_type = self.apt_type_bxls_2days.with_user(self.env.user)

        # with self.profile(collectors=['sql']) as profile:
        with self.mockAppointmentCalls(), \
             self.assertQueryCount(staff_user_bxls=535):  # apt only: 530
            t0 = time.time()
            res = apt_type._get_appointment_slots('Europe/Brussels', reference_date=self.reference_now)
            t1 = time.time()

        _logger.info('Called _get_appointment_slots, time %.3f', t1 - t0)
        _logger.info('Called methods\nSearch calendar event called %s\n'
                     'Search count calendar event called %s\n'
                     'Partner calendar check called %s\n'
                     'Resource Calendar work intervals batch called %s',
                     self._mock_calevent_search.call_count,
                     self._mock_calevent_search_count.call_count,
                     self._mock_partner_calendar_check.call_count,
                     self._mock_cal_work_intervals.call_count)
        # Time before optimization: ~0.50
        # Method count before optimization: 506 - 506 - 506 - 1

        global_slots_startdate = self.reference_now_monthweekstart
        global_slots_enddate = date(2022, 3, 5)  # last day of last week of Feb
        self.assertSlots(
            res,
            [{'name_formated': 'February 2022',
              'weeks_count': 5,  # 30/01 -> 27/02 (05/03)
             },
            ],
            {'enddate': global_slots_enddate,
             'startdate': global_slots_startdate,
            }
        )


@tagged('appointment_performance', 'post_install', '-at_install')
class AppointmentUIPerformanceCase(AppointmenHrPerformanceCase, UtilPerf):

    @classmethod
    def setUpClass(cls):
        super(AppointmentUIPerformanceCase, cls).setUpClass()
        # if website_livechat is installed, disable it
        if 'website' in cls.env and 'channel_id' in cls.env['website']:
            cls.env['website'].search([]).channel_id = False

    def _test_url_open(self, url):
        url += ('?' not in url and '?' or '') + '&nocache'
        return self.url_open(url)


@tagged('appointment_performance', 'post_install', '-at_install')
class OnlineAppointmentPerformance(AppointmentUIPerformanceCase):

    @warmup
    def test_appointment_type_page_website_whours_user(self):
        """ Website type: multi users (choose first available), with working hours
        involved. """
        random.seed(1871)  # fix shuffle in _slots_available

        t0 = time.time()
        with freeze_time(self.reference_now):
            self.authenticate('staff_user_bxls', 'staff_user_bxls')
            with self.assertQueryCount(default=1365):  # apt only: 1356 (1357 w website)
                self._test_url_open('/calendar/%i' % self.test_apt_type.id)
        t1 = time.time()

        _logger.info('Browsed /calendar/%i, time %.3f', self.test_apt_type.id, t1 - t0)
        # Time before optimization: ~1.90 (but with boilerplate)

    @warmup
    def test_appointment_type_page_work_hours(self):
        """ Work hours type: mono user, involved work hours check. """
        random.seed(1871)  # fix shuffle in _slots_available

        self.test_apt_type.write({
            'category': 'work_hours',
            'max_schedule_days': 90,
            'slot_ids': [(5, 0)] + [  # while loop in _slots_generate generates the actual slots
                (0, 0, {'end_hour': 23.99,
                        'start_hour': hour * 0.5,
                        'weekday': str(day + 1),
                       }
                )
                for hour in range(2)
                for day in range(7)
            ],
            'staff_user_ids': [(5, 0), (4, self.staff_users[0].id)],
            })
        self.test_apt_type.flush()

        t0 = time.time()
        with freeze_time(self.reference_now):
            self.authenticate('staff_user_bxls', 'staff_user_bxls')
            with self.assertQueryCount(default=4236):  # apt only: 4227 (4228 w website)
                self._test_url_open('/calendar/%i' % self.test_apt_type.id)
        t1 = time.time()

        _logger.info('Browsed /calendar/%i, time %.3f', self.test_apt_type.id, t1 - t0)
        # Time before optimization: ~4.60 (but with boilerplate)
