
# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licens

from odoo import http, fields, _
from odoo.http import request
from odoo.osv import expression

import pytz
from werkzeug.utils import redirect
import babel
from werkzeug.exceptions import Forbidden
from odoo.tools.misc import get_lang

from odoo import tools


class ShiftController(http.Controller):

    @http.route(['/planning/<string:planning_token>/<string:employee_token>'], type='http', auth="public", website=True)
    def planning(self, planning_token, employee_token, message=False, **kwargs):
        """ Displays an employee's calendar and the current list of open shifts """
        employee_sudo = request.env['hr.employee'].sudo().search([('employee_token', '=', employee_token)], limit=1)
        if not employee_sudo:
            return request.not_found()

        planning_sudo = request.env['planning.planning'].sudo().search([('access_token', '=', planning_token)], limit=1)
        if not planning_sudo:
            return request.not_found()

        employee_tz = pytz.timezone(employee_sudo.tz or 'UTC')
        employee_fullcalendar_data = []
        open_slots = []

        if planning_sudo.include_unassigned:
            planning_slots = planning_sudo.slot_ids.filtered(lambda s: s.employee_id == employee_sudo or not s.employee_id)
        else:
            planning_slots = planning_sudo.slot_ids.filtered(lambda s: s.employee_id == employee_sudo)
        # filter and format slots
        for slot in planning_slots:
            if slot.employee_id:
                employee_fullcalendar_data.append({
                    'title': '%s%s' % (slot.role_id.name or '', u' \U0001F4AC' if slot.name else ''),
                    'start': str(pytz.utc.localize(slot.start_datetime).astimezone(employee_tz).replace(tzinfo=None)),
                    'end': str(pytz.utc.localize(slot.end_datetime).astimezone(employee_tz).replace(tzinfo=None)),
                    'color': self._format_planning_shifts(slot.role_id.color),
                    'alloc_hours': '%d:%02d' % (int(slot.allocated_hours), round(slot.allocated_hours % 1 * 60)),
                    'alloc_perc': slot.allocated_percentage,
                    'slot_id': slot.id,
                    'note': slot.name,
                    'allow_self_unassign': slot.allow_self_unassign
                })
            elif not slot.is_past and (not employee_sudo.planning_role_ids or not slot.role_id or slot.role_id in employee_sudo.planning_role_ids):
                open_slots.append(slot)

        return request.render('planning.period_report_template', {
            'employee_slots_fullcalendar_data': employee_fullcalendar_data,
            'open_slots_ids': open_slots,
            'planning_slots_ids': planning_slots,
            'planning_planning_id': planning_sudo,
            'locale': get_lang(request.env).iso_code,
            'employee': employee_sudo,
            'format_datetime': lambda dt, dt_format: tools.format_datetime(request.env, dt, dt_format=dt_format),
            'notification_text': message in ['assign', 'unassign', 'already_assign'],
            'message_slug': message,
        })

    @http.route('/planning/<string:token_planning>/<string:token_employee>/assign/<int:slot_id>', type="http", auth="public", website=True)
    def planning_self_assign(self, token_planning, token_employee, slot_id, message=False, **kwargs):
        slot_sudo = request.env['planning.slot'].sudo().browse(slot_id)
        if not slot_sudo.exists():
            return request.not_found()

        employee_sudo = request.env['hr.employee'].sudo().search([('employee_token', '=', token_employee)], limit=1)
        if not employee_sudo:
            return request.not_found()

        planning_sudo = request.env['planning.planning'].sudo().search([('access_token', '=', token_planning)], limit=1)
        if not planning_sudo or slot_sudo.id not in planning_sudo.slot_ids._ids:
            return request.not_found()

        if slot_sudo.employee_id:
            return redirect('/planning/%s/%s?message=%s' % (token_planning, token_employee, 'already_assign'))

        slot_sudo.write({'employee_id': employee_sudo.id})
        if message:
            return redirect('/planning/%s/%s?message=%s' % (token_planning, token_employee, 'assign'))
        else:
            return redirect('/planning/%s/%s' % (token_planning, token_employee))

    @http.route('/planning/<string:token_planning>/<string:token_employee>/unassign/<int:shift_id>', type="http", auth="public", website=True)
    def planning_self_unassign(self, token_planning, token_employee, shift_id, message=False, **kwargs):
        slot_sudo = request.env['planning.slot'].sudo().search([('id', '=', shift_id)], limit=1)
        if not slot_sudo or not slot_sudo.allow_self_unassign:
            return request.not_found()

        employee_sudo = request.env['hr.employee'].sudo().search([('employee_token', '=', token_employee)], limit=1)
        if not employee_sudo or employee_sudo.id != slot_sudo.employee_id.id:
            return request.not_found()

        planning_sudo = request.env['planning.planning'].sudo().search([('access_token', '=', token_planning)], limit=1)
        if not planning_sudo or slot_sudo.id not in planning_sudo.slot_ids._ids:
            return request.not_found()

        slot_sudo.write({'employee_id': False})
        if message:
            return redirect('/planning/%s/%s?message=%s' % (token_planning, token_employee, 'unassign'))
        else:
            return redirect('/planning/%s/%s' % (token_planning, token_employee))

    @http.route('/planning/assign/<string:token_employee>/<int:shift_id>', type="http", auth="user", website=True)
    def planning_self_assign_with_user(self, token_employee, shift_id, **kwargs):
        slot_sudo = request.env['planning.slot'].sudo().search([('id', '=', shift_id)], limit=1)
        if not slot_sudo:
            return request.not_found()

        employee = request.env.user.employee_id
        if not employee:
            return request.not_found()

        if not slot_sudo.employee_id:
            slot_sudo.write({'employee_id': employee})

        return redirect('/web?#action=planning.planning_action_open_shift')

    @http.route('/planning/unassign/<string:token_employee>/<int:shift_id>', type="http", auth="user", website=True)
    def planning_self_unassign_with_user(self, token_employee, shift_id, **kwargs):
        slot_sudo = request.env['planning.slot'].sudo().search([('id', '=', shift_id)], limit=1)
        if not slot_sudo or not slot_sudo.allow_self_unassign:
            return request.not_found()

        employee = request.env['hr.employee'].sudo().search([('employee_token', '=', token_employee)], limit=1)
        if not employee:
            employee = request.env.user.employee_id
        if not employee or employee != slot_sudo.employee_id:
            return request.not_found()

        slot_sudo.write({'employee_id': False})

        if request.env.user:
            return redirect('/web?#action=planning.planning_action_open_shift')
        return request.env['ir.ui.view']._render_template('planning.slot_unassign')

    @staticmethod
    def _format_planning_shifts(color_code):
        """Take a color code from Odoo's Kanban view and returns an hex code compatible with the fullcalendar library"""

        switch_color = {
            0: '#008784',   # No color (doesn't work actually...)
            1: '#EE4B39',   # Red
            2: '#F29648',   # Orange
            3: '#F4C609',   # Yellow
            4: '#55B7EA',   # Light blue
            5: '#71405B',   # Dark purple
            6: '#E86869',   # Salmon pink
            7: '#008784',   # Medium blue
            8: '#267283',   # Dark blue
            9: '#BF1255',   # Fushia
            10: '#2BAF73',  # Green
            11: '#8754B0'   # Purple
        }

        return switch_color[color_code]
