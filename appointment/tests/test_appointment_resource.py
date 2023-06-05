# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

from datetime import datetime, timedelta
from freezegun import freeze_time

from odoo.addons.appointment.tests.common import AppointmentCommon
from odoo.tests import tagged, users


@tagged('appointment_resources')
class AppointmentResource(AppointmentCommon):

    @users('apt_manager')
    def test_appointment_resource_link(self):
        """ Test link between resources when they are combinable. """
        resource_1, resource_2 = self.env['appointment.resource'].create([
            {
                'capacity': 4,
                'name': 'Table of 4',
            },
            {
                'capacity': 2,
                'name': 'Table of 2',
            }
        ])
        self.assertFalse(resource_1.linked_resource_ids)
        self.assertFalse(resource_2.linked_resource_ids)

        # Test: link resource 2 to resource 1, and add a new resource as an
        # embedded 2many creation
        resource_1.write({
            'linked_resource_ids': [
                (4, resource_2.id),  # new link
                (0, 0, {  # embedded creation
                    'capacity': 1,
                    'name': 'OnTheFly Table of 1'
                }),
            ],
        })
        new_resource_1 = self.env['appointment.resource'].search([('name', '=', 'OnTheFly Table of 1')])
        self.assertEqual(len(new_resource_1), 1, 'Should have created a new resource')
        self.assertEqual(new_resource_1.linked_resource_ids, resource_1,
                         'Link works both ways')
        self.assertFalse(new_resource_1.source_resource_ids)
        self.assertEqual(new_resource_1.destination_resource_ids, resource_1,
                         'Resource 2 is destination of link between 1 and 2')
        self.assertEqual(
            resource_1.linked_resource_ids,
            resource_2 + new_resource_1,
            'Resource 1 should be linked to linked resource 2 and newly created new'
        )
        self.assertEqual(resource_1.source_resource_ids, resource_2 + new_resource_1)
        self.assertFalse(resource_1.destination_resource_ids)
        self.assertEqual(resource_2.linked_resource_ids, resource_1,
                         'Link works both ways')
        self.assertFalse(resource_2.source_resource_ids)
        self.assertEqual(resource_2.destination_resource_ids, resource_1,
                         'Resource 2 is destination of link between 1 and 2')

        # Test: break link to resource 2, add an existing one (check duplication)
        # and create yet another one
        resource_1.write({
            'linked_resource_ids': [
                (3, resource_2.id),  # break link
                (4, new_resource_1.id),  # already existing
                (0, 0, {
                    'capacity': 1,
                    'name': 'OnTheFly Table of 1 (bis)'
                }),
            ],
        })
        new_resource_2 = self.env['appointment.resource'].search([('name', '=', 'OnTheFly Table of 1 (bis)')])
        self.assertEqual(len(new_resource_2), 1, 'Should have created a new resource')
        self.assertEqual(new_resource_1.linked_resource_ids, resource_1,
                         'Link works both ways')
        self.assertFalse(new_resource_1.source_resource_ids)
        self.assertEqual(new_resource_1.destination_resource_ids, resource_1)
        self.assertEqual(new_resource_2.linked_resource_ids, resource_1,
                         'Link works both ways')
        self.assertFalse(new_resource_2.source_resource_ids)
        self.assertEqual(new_resource_2.destination_resource_ids, resource_1)
        self.assertEqual(
            resource_1.linked_resource_ids,
            new_resource_1 + new_resource_2,
            'Resource 1 should be linked to linked resource 2 and newly created new'
        )
        self.assertEqual(resource_1.source_resource_ids, new_resource_1 + new_resource_2)
        self.assertFalse(resource_1.destination_resource_ids)
        self.assertFalse(resource_2.linked_resource_ids)
        self.assertFalse(resource_2.source_resource_ids)
        self.assertFalse(resource_2.destination_resource_ids)

        # Test: update link based on destination, not source as previous tests
        resource_2.write({
            'linked_resource_ids': [
                (4, new_resource_1.id),  # add a new entry in destination
            ]
        })
        new_resource_2.write({
            'linked_resource_ids': [
                (3, resource_1.id),  # break link
                (4, resource_2.id),  # new link, will have both sources and dest
                (4, new_resource_1.id),  # new link
            ]
        })
        self.assertEqual(len(new_resource_2), 1, 'Should have created a new resource')
        self.assertEqual(new_resource_1.linked_resource_ids, resource_1 + resource_2 + new_resource_2)
        self.assertFalse(new_resource_1.source_resource_ids)
        self.assertEqual(new_resource_1.destination_resource_ids, resource_1 + resource_2 + new_resource_2)
        self.assertEqual(new_resource_2.linked_resource_ids, resource_2 + new_resource_1)
        self.assertEqual(new_resource_2.source_resource_ids, resource_2 + new_resource_1)
        self.assertFalse(new_resource_2.destination_resource_ids)
        self.assertEqual(resource_1.linked_resource_ids, new_resource_1)
        self.assertEqual(resource_1.source_resource_ids, new_resource_1)
        self.assertFalse(resource_1.destination_resource_ids)
        self.assertEqual(resource_2.linked_resource_ids, new_resource_1 + new_resource_2)
        self.assertEqual(resource_2.source_resource_ids, new_resource_1)
        self.assertEqual(resource_2.destination_resource_ids, new_resource_2)

    @users('apt_manager')
    def test_appointment_resources_remaining_capacity(self):
        """ Test that the remaining capacity of resources are correctly computed """
        appointment = self.env['appointment.type'].create({
            'appointment_tz': 'UTC',
            'min_schedule_hours': 1.0,
            'max_schedule_days': 8,
            'name': 'Test',
            'resource_manage_capacity': True,
            'schedule_based_on': 'resources',
            'slot_ids': [(0, 0, {
                'weekday': str(self.reference_monday.isoweekday()),
                'start_hour': 6,
                'end_hour': 18,
            })],
        })

        resource_1, resource_2 = self.env['appointment.resource'].create([{
            'appointment_type_ids': appointment.ids,
            'capacity': 3,
            'name': 'Resource 1',
        }, {
            'appointment_type_ids': appointment.ids,
            'capacity': 2,
            'name': 'Resource 2',
            'shareable': True,
        }])

        start = datetime(2022, 2, 15, 14, 0, 0)
        end = start + timedelta(hours=1)

        self.assertTrue(appointment._get_resources_remaining_capacity(resource_1, start, end)['total_remaining_capacity'] == 3)
        self.assertTrue(appointment._get_resources_remaining_capacity(resource_2, start, end)['total_remaining_capacity'] == 2)

        # Create bookings for resource
        booking_1, booking_2 = self.env['calendar.event'].with_context(self._test_context).create([{
            'appointment_type_id': appointment.id,
            'booking_line_ids': [(0, 0, {'appointment_resource_id': resource_1.id, 'capacity_reserved': 1, 'capacity_used': resource_1.capacity})],
            'name': 'Booking 1',
            'start': start,
            'stop': end,
        }, {
            'appointment_type_id': appointment.id,
            'booking_line_ids': [(0, 0, {'appointment_resource_id': resource_2.id, 'capacity_reserved': 1})],
            'name': 'Booking 2',
            'start': start,
            'stop': end,
        }])
        bookings = booking_1 + booking_2

        self.assertTrue(
            appointment._get_resources_remaining_capacity(resource_1, start, end)['total_remaining_capacity'] == 0,
            'The resource should have no availabilities left')
        self.assertTrue(
            appointment._get_resources_remaining_capacity(resource_2, start, end)['total_remaining_capacity'] == 1,
            'The resource should have 1 availability left because it is shareable')

        bookings.unlink()
        resource_1.linked_resource_ids = resource_2
        self.assertTrue(
            appointment._get_resources_remaining_capacity(resource_1, start, end)['total_remaining_capacity'] == 5,
            "The resource should have 5 availabilities (3 from the resource and 2 from the other linked to it)")
        self.assertTrue(appointment._get_resources_remaining_capacity(resource_2, start, end)['total_remaining_capacity'] == 5)
        self.assertTrue(appointment._get_resources_remaining_capacity(resource_1, start, end)[resource_1] == 3)
        self.assertTrue(appointment._get_resources_remaining_capacity(resource_2, start, end)[resource_2] == 2)

        booking = self.env['calendar.event'].with_context(self._test_context).create([{
            'appointment_type_id': appointment.id,
            'booking_line_ids': [
                (0, 0, {'appointment_resource_id': resource_1.id, 'capacity_reserved': 3, 'capacity_used': 3}),
                (0, 0, {'appointment_resource_id': resource_2.id, 'capacity_reserved': 1}),
            ],
            'name': 'Booking',
            'start': start,
            'stop': end,
        }])

        self.assertTrue(len(booking.appointment_resource_ids) == 2)
        self.assertTrue(
            appointment._get_resources_remaining_capacity(resource_1, start, end)['total_remaining_capacity'] == 1,
            'The resource should have 1 availability left (the one from resource_2)')
        self.assertTrue(
            appointment._get_resources_remaining_capacity(resource_1, start, end)[resource_1] == 0,
            'The resource should have no availability left if alone')
        self.assertTrue(
            appointment._get_resources_remaining_capacity(resource_2, start, end)['total_remaining_capacity'] == 1,
            'The resource should have 1 availability left')


@tagged('appointment_resources', 'post_install', '-at_install')
class AppointmentResourceBookingTest(AppointmentCommon):

    @users('apt_manager')
    def test_appointment_resources(self):
        """ Slots generation and availability of appointment type with resources """
        appointment = self.env['appointment.type'].create({
            'appointment_tz': 'UTC',
            'assign_method': 'time_auto_assign',
            'min_schedule_hours': 1.0,
            'max_schedule_days': 8,
            'name': 'Test',
            'resource_manage_capacity': True,
            'schedule_based_on': 'resources',
            'slot_ids': [(0, 0, {
                'weekday': str(self.reference_monday.isoweekday()),
                'start_hour': 6,
                'end_hour': 18,
            })],
        })

        self.env['appointment.resource'].create([
            {
                'appointment_type_ids': appointment.ids,
                'capacity': 3,
                'name': 'Resource %s' % i,
            } for i in range(20)
        ])

        with freeze_time(self.reference_now):
            with self.assertQueryCount(default=10):
                appointment._get_appointment_slots('UTC')

    @users('apt_manager')
    def test_appointment_resources_combinable(self):
        """ Check that combinable resources are correctly process. """
        table_c2, table_c4, table_c6 = self.env['appointment.resource'].create([{
            'appointment_type_ids': self.apt_type_resource.ids,
            'capacity': i,
            'name': 'Table for %s' % i,
            'sequence': i,
        } for i in range(2, 7, 2)])

        table_c2.linked_resource_ids = (table_c4 + table_c6)
        table_c4.linked_resource_ids = (table_c2 + table_c6)
        table_c6.linked_resource_ids = (table_c2 + table_c4)

        with freeze_time(self.reference_now):
            slots = self.apt_type_resource._get_appointment_slots('UTC')
            resource_slots_c1 = self._filter_appointment_slots(slots)
            slots = self.apt_type_resource._get_appointment_slots('UTC', asked_capacity=3)
            resource_slots_c3 = self._filter_appointment_slots(slots)
            slots = self.apt_type_resource._get_appointment_slots('UTC', asked_capacity=4)
            resource_slots_c4 = self._filter_appointment_slots(slots)
            slots = self.apt_type_resource._get_appointment_slots('UTC', asked_capacity=6)
            resource_slots_c6 = self._filter_appointment_slots(slots)
            slots = self.apt_type_resource._get_appointment_slots('UTC', asked_capacity=9)
            resource_slots_c9 = self._filter_appointment_slots(slots)
        available_resources_c1 = [resource['id'] for resource in resource_slots_c1[0]['available_resources']]
        available_resources_c3 = [resource['id'] for resource in resource_slots_c3[0]['available_resources']]
        available_resources_c4 = [resource['id'] for resource in resource_slots_c4[0]['available_resources']]
        available_resources_c6 = [resource['id'] for resource in resource_slots_c6[0]['available_resources']]
        available_resources_c9 = [resource['id'] for resource in resource_slots_c9[0]['available_resources']]
        self.assertListEqual(available_resources_c1, table_c2.ids)
        self.assertListEqual(available_resources_c3, table_c4.ids,
            "The table for 4 should be selected here as it's linked to the table for 2 and we don't want to lose capacity with a combination")
        self.assertListEqual(available_resources_c4, table_c4.ids)
        self.assertListEqual(available_resources_c6, table_c6.ids)
        self.assertListEqual(available_resources_c9, (table_c4 + table_c6).ids)

        table_c4.sequence = 1
        with freeze_time(self.reference_now):
            slots = self.apt_type_resource._get_appointment_slots('UTC')
            resource_slots_c1 = self._filter_appointment_slots(slots)
            slots = self.apt_type_resource._get_appointment_slots('UTC', asked_capacity=3)
            resource_slots_c3 = self._filter_appointment_slots(slots)
            slots = self.apt_type_resource._get_appointment_slots('UTC', asked_capacity=4)
            resource_slots_c4 = self._filter_appointment_slots(slots)
            slots = self.apt_type_resource._get_appointment_slots('UTC', asked_capacity=6)
            resource_slots_c6 = self._filter_appointment_slots(slots)
            slots = self.apt_type_resource._get_appointment_slots('UTC', asked_capacity=9)
            resource_slots_c9 = self._filter_appointment_slots(slots)
        available_resources_c1 = [resource['id'] for resource in resource_slots_c1[0]['available_resources']]
        available_resources_c3 = [resource['id'] for resource in resource_slots_c3[0]['available_resources']]
        available_resources_c4 = [resource['id'] for resource in resource_slots_c4[0]['available_resources']]
        available_resources_c6 = [resource['id'] for resource in resource_slots_c6[0]['available_resources']]
        available_resources_c9 = [resource['id'] for resource in resource_slots_c9[0]['available_resources']]
        self.assertListEqual(available_resources_c1, table_c4.ids)
        self.assertListEqual(available_resources_c3, table_c4.ids)
        self.assertListEqual(available_resources_c4, table_c4.ids)
        self.assertListEqual(available_resources_c6, table_c6.ids)
        self.assertListEqual(available_resources_c9, (table_c4 + table_c6).ids)

    @users('apt_manager')
    def test_appointment_resources_combinable_avoid_losing_extra_capacity(self):
        """ Check that we don't lose capacity with the resource selected.
            If a capacity needed is greater than the capacity of the resource initially selected
            we should check if the linked resources of the one selected are not a better fit to avoid losing capacity.
        """

        nordic, scandinavian, snow = self.env["appointment.resource"].create([{
            'appointment_type_ids': self.apt_type_resource.ids,
            'capacity': 4,
            'name': 'Nordic',
            'sequence': 2,
        }, {
            'appointment_type_ids': self.apt_type_resource.ids,
            'capacity': 8,
            'name': 'Scandinavian',
            'sequence': 3,
        }, {
            'appointment_type_ids': self.apt_type_resource.ids,
            'capacity': 6,
            'name': 'Snow',
            'sequence': 4,
        }])

        nordic.linked_resource_ids = scandinavian

        with freeze_time(self.reference_now):
            slots = self.apt_type_resource._get_appointment_slots('UTC', asked_capacity=5)
        resource_slots_c5 = self._filter_appointment_slots(slots)
        available_resources_c5 = [resource['id'] for resource in resource_slots_c5[0]['available_resources']]
        self.assertListEqual(available_resources_c5, scandinavian.ids)

        snow.sequence = 1
        with freeze_time(self.reference_now):
            slots = self.apt_type_resource._get_appointment_slots('UTC', asked_capacity=5)
        resource_slots_c5 = self._filter_appointment_slots(slots)
        available_resources_c5 = [resource['id'] for resource in resource_slots_c5[0]['available_resources']]
        self.assertListEqual(available_resources_c5, snow.ids)

        snow.sequence = 4
        scandinavian.write({
            'linked_resource_ids': [(4, nordic.id)],
            'sequence': 1,
        })

        with freeze_time(self.reference_now):
            slots = self.apt_type_resource._get_appointment_slots('UTC', asked_capacity=5)
            resource_slots_c5 = self._filter_appointment_slots(slots)
            slots = self.apt_type_resource._get_appointment_slots('UTC', asked_capacity=2)
            resource_slots_c2 = self._filter_appointment_slots(slots)
        available_resources_c5 = [resource['id'] for resource in resource_slots_c5[0]['available_resources']]
        available_resources_c2 = [resource['id'] for resource in resource_slots_c2[0]['available_resources']]
        self.assertListEqual(available_resources_c5, scandinavian.ids)
        self.assertListEqual(available_resources_c2, scandinavian.ids)

    @users('apt_manager')
    def test_appointment_resources_combinable_complex(self):
        """ Check resources assignation when the linked resources are not mirrored for all resources """

        table1_c2, table2_c2, table3_c2 = self.env['appointment.resource'].create([{
            'appointment_type_ids': self.apt_type_resource.ids,
            'capacity': 2,
            'name': 'Table 2A',
            'sequence': 1,
        }, {
            'appointment_type_ids': self.apt_type_resource.ids,
            'capacity': 2,
            'name': 'Table 2B',
            'sequence': 3,
        }, {
            'appointment_type_ids': self.apt_type_resource.ids,
            'capacity': 2,
            'name': 'Table 2C',
            'sequence': 2,
        }])
        table1_c2.linked_resource_ids = table2_c2 + table3_c2
        table2_c2.linked_resource_ids = table1_c2 + table3_c2
        table3_c2.linked_resource_ids = table1_c2 + table2_c2

        table_c3 = self.env['appointment.resource'].create({
            'appointment_type_ids': self.apt_type_resource.ids,
            'capacity': 3,
            'name': 'Table 3A',
            'sequence': 4,
        })

        table1_c6, table2_c6 = self.env['appointment.resource'].create([{
            'appointment_type_ids': self.apt_type_resource.ids,
            'capacity': 6,
            'name': 'Table 6A',
            'sequence': 5,
        }, {
            'appointment_type_ids': self.apt_type_resource.ids,
            'capacity': 6,
            'name': 'Table 6B',
            'sequence': 6,
        }])

        table1_c6.linked_resource_ids = table_c3
        table2_c6.linked_resource_ids = table1_c2 + table2_c2 + table3_c2

        table1_c8, table2_c8, bar = self.env['appointment.resource'].create([{
            'appointment_type_ids': self.apt_type_resource.ids,
            'capacity': 8,
            'name': 'Table 8A',
            'sequence': 8,
        }, {
            'appointment_type_ids': self.apt_type_resource.ids,
            'capacity': 8,
            'name': 'Table 8B',
            'sequence': 9,
        }, {
            'appointment_type_ids': self.apt_type_resource.ids,
            'capacity': 10,
            'name': 'Bar',
            'sequence': 15,
            'shareable': True,
        }])
        table1_c8.sequence = 10
        with freeze_time(self.reference_now):
            slots = self.apt_type_resource._get_appointment_slots('UTC', asked_capacity=4)
            resource_slots_c4 = self._filter_appointment_slots(slots)
            slots = self.apt_type_resource._get_appointment_slots('UTC', asked_capacity=8)
            resource_slots_c8 = self._filter_appointment_slots(slots)
            slots = self.apt_type_resource._get_appointment_slots('UTC', asked_capacity=10)
            resource_slots_c10 = self._filter_appointment_slots(slots)
            slots = self.apt_type_resource._get_appointment_slots('UTC', asked_capacity=12)
            resource_slots_c12 = self._filter_appointment_slots(slots)
        available_resources_c4 = [resource['id'] for resource in resource_slots_c4[0]['available_resources']]
        available_resources_c8 = [resource['id'] for resource in resource_slots_c8[0]['available_resources']]
        available_resources_c10 = [resource['id'] for resource in resource_slots_c10[0]['available_resources']]
        available_resources_c12 = [resource['id'] for resource in resource_slots_c12[0]['available_resources']]
        self.assertListEqual(available_resources_c4, (table1_c2 + table3_c2).ids)
        self.assertListEqual(available_resources_c8, table2_c8.ids)
        self.assertListEqual(available_resources_c10, bar.ids)
        self.assertListEqual(available_resources_c12, (table2_c6 + table2_c6.linked_resource_ids).sorted('sequence').ids)

    @users('apt_manager')
    def test_appointment_resources_combinable_performance(self):
        """ Simple use case of appointment type with combinable resources """
        appointment = self.env['appointment.type'].create({
            'appointment_tz': 'UTC',
            'assign_method': 'time_auto_assign',
            'min_schedule_hours': 1.0,
            'max_schedule_days': 8,
            'name': 'Test',
            'resource_manage_capacity': True,
            'schedule_based_on': 'resources',
            'slot_ids': [(0, 0, {
                'weekday': str(self.reference_monday.isoweekday()),
                'start_hour': 6,
                'end_hour': 18,
            })],
        })

        table1_c2, table2_c2, table3_c2 = self.env['appointment.resource'].create([
            {
                'appointment_type_ids': appointment.ids,
                'capacity': 2,
                'name': 'Table %s - 2' % (i + 1),
            } for i in range(3)
        ])

        table1_c4, table2_c4, table3_c4 = self.env['appointment.resource'].create([
            {
                'appointment_type_ids': appointment.ids,
                'capacity': 4,
                'name': 'Table %s - 4' % (i + 1),
            } for i in range(3)
        ])

        table1_c6 = self.env['appointment.resource'].create({
            'appointment_type_ids': appointment.ids,
            'capacity': 6,
            'name': 'Table - 6',
        })

        (table1_c4 + table2_c4 + table3_c4).linked_resource_ids = table1_c2 + table2_c2 + table3_c2 + table1_c6
        (table1_c2 + table2_c2 + table3_c2).linked_resource_ids = table1_c4 + table2_c4 + table3_c4
        table1_c6.linked_resource_ids = table1_c4 + table2_c4 + table3_c4

        with freeze_time(self.reference_now):
            with self.assertQueryCount(default=10):
                slots = appointment._get_appointment_slots('UTC')
            resource_slots = self._filter_appointment_slots(
                slots,
                filter_weekdays=[0],
            )
            table1_c2_slots = self._filter_appointment_slots(
                slots,
                filter_weekdays=[0],
                filter_resources=table1_c2,
            )
            self.assertTrue(len(resource_slots) > 0)
            self.assertEqual(len(resource_slots), len(table1_c2_slots))
            with self.assertQueryCount(default=1):
                slots = appointment._get_appointment_slots('UTC', asked_capacity=5)
            resource_slots = self._filter_appointment_slots(
                slots,
                filter_weekdays=[0],
            )
            table1_c2_slots = self._filter_appointment_slots(
                slots,
                filter_weekdays=[0],
                filter_resources=table1_c2,
            )
            table1_c2_c4_slots = self._filter_appointment_slots(
                slots,
                filter_weekdays=[0],
                filter_resources=(table1_c2 + table1_c4),
            )
            self.assertTrue(len(resource_slots) > 0)
            self.assertEqual(len(table1_c2_slots), 0)
            self.assertEqual(len(resource_slots), len(table1_c2_c4_slots))

    @users('apt_manager')
    def test_appointment_resources_sequence(self):
        """ Check that the sequence is correctly taken into account when selecting resources for slots """

        resource_1, resource_2 = self.env['appointment.resource'].create([{
            'appointment_type_ids': self.apt_type_resource.ids,
            'capacity': 4,
            'name': 'Resource 1',
            'sequence': 5,
        }, {
            'appointment_type_ids': self.apt_type_resource.ids,
            'capacity': 10,
            'name': 'Resource 2',
            'sequence': 10,
        }])

        with freeze_time(self.reference_now):
            slots = self.apt_type_resource._get_appointment_slots('UTC')
            resource_slots_c1 = self._filter_appointment_slots(slots)
            slots = self.apt_type_resource._get_appointment_slots('UTC', asked_capacity=4)
            resource_slots_c4 = self._filter_appointment_slots(slots)
            slots = self.apt_type_resource._get_appointment_slots('UTC', asked_capacity=6)
            resource_slots_c6 = self._filter_appointment_slots(slots)
        available_resources_c1 = [resource['id'] for resource in resource_slots_c1[0]['available_resources']]
        available_resources_c4 = [resource['id'] for resource in resource_slots_c4[0]['available_resources']]
        available_resources_c6 = [resource['id'] for resource in resource_slots_c6[0]['available_resources']]
        self.assertTrue(len(resource_slots_c1) > 0)
        self.assertListEqual(available_resources_c1, resource_1.ids)
        self.assertTrue(len(resource_slots_c4) > 0)
        self.assertListEqual(available_resources_c4, resource_1.ids)
        self.assertTrue(len(resource_slots_c6) > 0)
        self.assertListEqual(available_resources_c6, resource_2.ids)

        resource_2.sequence = 1
        with freeze_time(self.reference_now):
            slots = self.apt_type_resource._get_appointment_slots('UTC')
            resource_slots_c1 = self._filter_appointment_slots(slots)
            slots = self.apt_type_resource._get_appointment_slots('UTC', asked_capacity=4)
            resource_slots_c4 = self._filter_appointment_slots(slots)
            slots = self.apt_type_resource._get_appointment_slots('UTC', asked_capacity=6)
            resource_slots_c6 = self._filter_appointment_slots(slots)
        available_resources_c1 = [resource['id'] for resource in resource_slots_c1[0]['available_resources']]
        available_resources_c4 = [resource['id'] for resource in resource_slots_c4[0]['available_resources']]
        available_resources_c6 = [resource['id'] for resource in resource_slots_c6[0]['available_resources']]
        self.assertTrue(len(resource_slots_c1) > 0)
        self.assertListEqual(available_resources_c1, resource_2.ids)
        self.assertTrue(len(resource_slots_c4) > 0)
        self.assertListEqual(available_resources_c4, resource_1.ids)
        self.assertTrue(len(resource_slots_c6) > 0)
        self.assertListEqual(available_resources_c6, resource_2.ids)

    @users('apt_manager')
    def test_appointment_resources_shareable(self):
        """ Check shareable resources are correctly used """

        resource, resource_shareable = self.env['appointment.resource'].create([{
            'appointment_type_ids': self.apt_type_resource.ids,
            'capacity': 5,
            'name': 'Resource',
            'sequence': 5,
        }, {
            'appointment_type_ids': self.apt_type_resource.ids,
            'capacity': 10,
            'name': 'Resource Shareable',
            'sequence': 10,
            'shareable': True,
        }])

        with freeze_time(self.reference_now):
            slots = self.apt_type_resource._get_appointment_slots('UTC', asked_capacity=4)
            resource_slots_c4 = self._filter_appointment_slots(slots)
            slots = self.apt_type_resource._get_appointment_slots('UTC', asked_capacity=6)
            resource_slots_c6 = self._filter_appointment_slots(slots)
        available_resources_c4 = [resource['id'] for resource in resource_slots_c4[0]['available_resources']]
        available_resources_c6 = [resource['id'] for resource in resource_slots_c6[0]['available_resources']]
        self.assertListEqual(available_resources_c4, resource.ids)
        self.assertListEqual(available_resources_c6, resource_shareable.ids)

        start = datetime(2022, 2, 14, 15, 0, 0)
        end = start + timedelta(hours=1)
        self.env['calendar.event'].with_context(self._test_context).create([{
            'appointment_type_id': self.apt_type_resource.id,
            'booking_line_ids': [(0, 0, {'appointment_resource_id': resource_shareable.id, 'capacity_reserved': 4, 'capacity_used': 4})],
            'name': 'Booking 1',
            'start': start,
            'stop': end,
        }, {
            'appointment_type_id': self.apt_type_resource.id,
            'booking_line_ids': [(0, 0, {'appointment_resource_id': resource_shareable.id, 'capacity_reserved': 2, 'capacity_used': 2})],
            'name': 'Booking 2',
            'start': start,
            'stop': end,
        }])

        with freeze_time(self.reference_now):
            slots = self.apt_type_resource._get_appointment_slots('UTC', asked_capacity=4)
            resource_slots_c4 = self._filter_appointment_slots(slots)
            slots = self.apt_type_resource._get_appointment_slots('UTC', asked_capacity=5)
            resource_slots_c5 = self._filter_appointment_slots(slots)
            slots = self.apt_type_resource._get_appointment_slots('UTC', asked_capacity=6)
            resource_slots_c6 = self._filter_appointment_slots(slots)
        available_resources_c4 = [resource['id'] for resource in resource_slots_c4[0]['available_resources']]
        available_resources_c5 = [resource['id'] for resource in resource_slots_c5[0]['available_resources']]
        available_resources_c6 = resource_slots_c6 and [resource['id'] for resource in resource_slots_c6[0]['available_resources']]
        self.assertListEqual(available_resources_c4, resource.ids)
        self.assertListEqual(available_resources_c5, resource.ids)
        self.assertListEqual(available_resources_c6, [])

        resource_shareable.sequence = 1
        with freeze_time(self.reference_now):
            slots = self.apt_type_resource._get_appointment_slots('UTC', asked_capacity=4)
            resource_slots_c4 = self._filter_appointment_slots(slots)
            slots = self.apt_type_resource._get_appointment_slots('UTC', asked_capacity=5)
            resource_slots_c5 = self._filter_appointment_slots(slots)
        available_resources_c4 = [resource['id'] for resource in resource_slots_c4[0]['available_resources']]
        available_resources_c5 = [resource['id'] for resource in resource_slots_c5[0]['available_resources']]
        self.assertListEqual(available_resources_c4, resource_shareable.ids)
        self.assertListEqual(available_resources_c5, resource.ids)

    @users('apt_manager')
    def test_appointment_resources_shareable_linked_with_capacity(self):
        """ Check that resources shareable linked together with the capacity management
         correctly compute the remaining capacity """

        resource_1, resource_2 = self.env['appointment.resource'].create([{
            'appointment_type_ids': self.apt_type_resource.ids,
            'capacity': 5,
            'name': 'Resource 1',
            'sequence': 5,
            'shareable': True,
        }, {
            'appointment_type_ids': self.apt_type_resource.ids,
            'capacity': 6,
            'name': 'Resource 2',
            'sequence': 10,
            'shareable': True,
        }])

        resource_1.linked_resource_ids = resource_2

        with freeze_time(self.reference_now):
            slots = self.apt_type_resource._get_appointment_slots('UTC', asked_capacity=5)
            resource_slots_c5 = self._filter_appointment_slots(slots)
            slots = self.apt_type_resource._get_appointment_slots('UTC', asked_capacity=7)
            resource_slots_c7 = self._filter_appointment_slots(slots)
        available_resources_c5 = [resource['id'] for resource in resource_slots_c5[0]['available_resources']]
        available_resources_c7 = [resource['id'] for resource in resource_slots_c7[0]['available_resources']]
        self.assertListEqual(available_resources_c5, resource_1.ids,
                             "Should pick the first resource as it's a best match")
        self.assertListEqual(available_resources_c7, (resource_1 + resource_2).ids,
                             "Should pick both resources as asked capacity exceeds each resource capacity")

        # Create a booking for the first resource for all its capacity
        start = datetime(2022, 2, 14, 15, 0, 0)
        end = start + timedelta(hours=1)
        self.env['calendar.event'].with_context(self._test_context).create({
            'appointment_type_id': self.apt_type_resource.id,
            'booking_line_ids': [(0, 0, {'appointment_resource_id': resource_1.id, 'capacity_reserved': 5, 'capacity_used': 5})],
            'name': 'Booking 1',
            'start': start,
            'stop': end,
        })

        with freeze_time(self.reference_now):
            slots = self.apt_type_resource._get_appointment_slots('UTC', asked_capacity=5)
            resource_slots_c5 = self._filter_appointment_slots(slots)
            slots = self.apt_type_resource._get_appointment_slots('UTC', asked_capacity=7)
            resource_slots_c7 = self._filter_appointment_slots(slots)
        available_resources_c5 = [resource['id'] for resource in resource_slots_c5[0]['available_resources']]
        self.assertListEqual(available_resources_c5, resource_2.ids,
                             "Should pick the second resource as the first one is already taken")
        self.assertEqual(len(resource_slots_c7), 0,
                         "There should not be enough capacity remaining for the asked capacity")

    @users('apt_manager')
    def test_appointment_resources_shareable_performance(self):
        """" Simple use case with shareable resources """
        appointment = self.env['appointment.type'].create({
            'appointment_tz': 'UTC',
            'assign_method': 'time_auto_assign',
            'min_schedule_hours': 1.0,
            'max_schedule_days': 8,
            'name': 'Test',
            'resource_manage_capacity': True,
            'schedule_based_on': 'resources',
            'slot_ids': [(0, 0, {
                'weekday': str(self.reference_monday.isoweekday()),
                'start_hour': 6,
                'end_hour': 18,
            })],
        })

        self.env['appointment.resource'].create([
            {
                'appointment_type_ids': appointment.ids,
                'capacity': 5,
                'name': 'Resource %s' % i,
                'shareable': True,
            } for i in range(20)
        ])

        with freeze_time(self.reference_now):
            with self.assertQueryCount(default=10):
                appointment._get_appointment_slots('UTC')

    @users('apt_manager')
    def test_appointment_resources_restrict_resources(self):
        """" Check that resources restricted on slots are taken into account """
        appointment = self.env['appointment.type'].create({
            'appointment_tz': 'UTC',
            'assign_method': 'time_resource',  # easier to check all resources available for each slot
            'min_schedule_hours': 1.0,
            'max_schedule_days': 5,
            'name': 'Test',
            'resource_manage_capacity': True,
            'schedule_based_on': 'resources',
            'slot_ids': [(0, 0, {
                'weekday': str(self.reference_monday.isoweekday()),
                'start_hour': 15,
                'end_hour': 16,
            }), (0, 0, {
                'weekday': str(self.reference_monday.isoweekday() + 1),
                'start_hour': 15,
                'end_hour': 16,
            }), (0, 0, {
                'weekday': str(self.reference_monday.isoweekday() + 2),
                'start_hour': 15,
                'end_hour': 16,
            })],
        })

        resource1, resource2, resource3 = self.env['appointment.resource'].create([
            {
                'appointment_type_ids': appointment.ids,
                'name': 'Resource %s' % i,
            } for i in range(3)
        ])

        appointment.slot_ids[0].restrict_to_resource_ids = resource1.ids
        appointment.slot_ids[1].restrict_to_resource_ids = (resource2 + resource3).ids

        with freeze_time(self.reference_now):
            slots = appointment._get_appointment_slots('UTC')
        monday_slots = self._filter_appointment_slots(slots, filter_weekdays=[0])
        tuesday_slots = self._filter_appointment_slots(slots, filter_weekdays=[1])
        wednesday_slots = self._filter_appointment_slots(slots, filter_weekdays=[2])
        available_resources_monday = [resource['id'] for resource in monday_slots[0]['available_resources']]
        available_resources_tuesday = [resource['id'] for resource in tuesday_slots[0]['available_resources']]
        available_resources_wednesday = [resource['id'] for resource in wednesday_slots[0]['available_resources']]
        self.assertListEqual(available_resources_monday, resource1.ids)
        self.assertListEqual(available_resources_tuesday, (resource2 + resource3).ids)
        self.assertListEqual(available_resources_wednesday, (resource1 + resource2 + resource3).ids)

    @users('apt_manager')
    def test_appointment_resources_assign_time_resource(self):
        """ Check that all resources are available with time_resource assign method. """
        self.apt_type_resource.assign_method = 'time_resource'

        nordic, scandinavian, snow = self.env["appointment.resource"].create([{
            'appointment_type_ids': self.apt_type_resource.ids,
            'capacity': 4,
            'name': 'Nordic',
            'sequence': 2,
        }, {
            'appointment_type_ids': self.apt_type_resource.ids,
            'capacity': 8,
            'name': 'Scandinavian',
            'sequence': 3,
        }, {
            'appointment_type_ids': self.apt_type_resource.ids,
            'capacity': 6,
            'name': 'Snow',
            'sequence': 4,
        }])

        with freeze_time(self.reference_now):
            slots = self.apt_type_resource._get_appointment_slots('UTC')
            available_resources_c1 = self._filter_appointment_slots(slots)
            slots = self.apt_type_resource._get_appointment_slots('UTC', asked_capacity=4)
            available_resources_c4 = self._filter_appointment_slots(slots)
            slots = self.apt_type_resource._get_appointment_slots('UTC', asked_capacity=5)
            available_resources_c5 = self._filter_appointment_slots(slots)
        available_resources_c1 = [resource['id'] for resource in available_resources_c1[0]['available_resources']]
        available_resources_c4 = [resource['id'] for resource in available_resources_c4[0]['available_resources']]
        available_resources_c5 = [resource['id'] for resource in available_resources_c5[0]['available_resources']]
        self.assertListEqual(available_resources_c1, (nordic + scandinavian + snow).ids,
            "All resources should be available with asked_capacity=1")
        self.assertListEqual(available_resources_c4, (nordic + scandinavian + snow).ids,
            "All resources should be available, the perfect matches are ignored with time_resource assign method")
        self.assertListEqual(available_resources_c5, (scandinavian + snow).ids)

    @users('apt_manager')
    def test_appointment_resources_without_capacity_management(self):
        """ Check use case where capacity management is not activated """

        self.apt_type_resource.resource_manage_capacity = False

        resource_1, resource_2, resource_3 = self.env['appointment.resource'].create([{
            'appointment_type_ids': self.apt_type_resource.ids,
            'capacity': 6,
            'name': 'Resource 1',
            'sequence': 1,
            'shareable': True,
        }, {
            'appointment_type_ids': self.apt_type_resource.ids,
            'capacity': 4,
            'name': 'Resource 2',
            'sequence': 2,
        }, {
            'appointment_type_ids': self.apt_type_resource.ids,
            'capacity': 1,
            'name': 'Resource 3',
            'sequence': 3
        }])

        resource_2.linked_resource_ids = resource_3

        with freeze_time(self.reference_now):
            slots = self.apt_type_resource._get_appointment_slots('UTC')
        resource_slots = self._filter_appointment_slots(slots)
        available_resources = [resource['id'] for resource in resource_slots[0]['available_resources']]
        self.assertListEqual(available_resources, resource_1.ids)

        start = datetime(2022, 2, 14, 15, 0, 0)
        end = start + timedelta(hours=1)
        booking = self.env['calendar.event'].with_context(self._test_context).create({
            'appointment_type_id': self.apt_type_resource.id,
            'booking_line_ids': [(0, 0, {'appointment_resource_id': resource_1.id, 'capacity_reserved': 1, 'capacity_used': resource_1.capacity})],
            'name': 'Booking 1',
            'start': start,
            'stop': end,
        })

        self.assertEqual(booking.booking_line_ids.capacity_reserved, 1)
        self.assertEqual(booking.booking_line_ids.capacity_used, 6,
            "When we don't manage capacity, the shareable option should be ignored")

        with freeze_time(self.reference_now):
            slots = self.apt_type_resource._get_appointment_slots('UTC')
        resource_slots = self._filter_appointment_slots(slots)
        available_resources = [resource['id'] for resource in resource_slots[0]['available_resources']]
        self.assertListEqual(available_resources, resource_2.ids,
            "The first resource should now be unavailable and the second one is chosen")
