# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo.addons.appointment.controllers.calendar import AppointmentController
from odoo.osv.expression import AND


class WebsiteAppointmentController(AppointmentController):
    def _get_staff_user_appointment_type_domain(self):
        domain = super()._get_staff_user_appointment_type_domain()
        return AND([domain, [('website_published', '=', True)]])
