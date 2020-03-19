# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.
from math import ceil

from odoo import api, fields, models, _
from odoo.exceptions import ValidationError


class HelpdeskTeam(models.Model):
    _inherit = 'helpdesk.team'

    project_id = fields.Many2one("project.project", string="Project", ondelete="restrict", domain="[('allow_timesheets', '=', True), ('company_id', '=', company_id)]",
        help="Project to which the tickets (and the timesheets) will be linked by default.")
    timesheet_timer = fields.Boolean('Timesheet Timer', default=True)

    @api.depends('use_helpdesk_timesheet')
    def _compute_timesheet_timer(self):
        for team in self:
            team.timesheet_timer = team.use_helpdesk_timesheet

    def _create_project(self, name, allow_billable, other):
        return self.env['project.project'].create({
            'name': name,
            'type_ids': [
                (0, 0, {'name': _('In Progress')}),
                (0, 0, {'name': _('Closed'), 'is_closed': True})
            ],
            'allow_timesheets': True,
            'allow_timesheet_timer': True,
            'allow_billable': allow_billable,
            **other,
        })

    @api.model
    def create(self, vals):
        if vals.get('use_helpdesk_timesheet') and not vals.get('project_id'):
            allow_billable = vals.get('use_helpdesk_sale_timesheet')
            vals['project_id'] = self._create_project(vals['name'], allow_billable, {}).id
        return super(HelpdeskTeam, self).create(vals)

    def write(self, vals):
        if 'use_helpdesk_timesheet' in vals and not vals['use_helpdesk_timesheet']:
            vals['project_id'] = False
        result = super(HelpdeskTeam, self).write(vals)
        for team in self.filtered(lambda team: team.use_helpdesk_timesheet and not team.project_id):
            team.project_id = team._create_project(team.name, team.use_helpdesk_sale_timesheet, {'allow_timesheets': True, 'allow_timesheet_timer': True})
            self.env['helpdesk.ticket'].search([('team_id', '=', team.id), ('project_id', '=', False)]).write({'project_id': team.project_id.id})
        return result

    @api.model
    def _init_data_create_project(self):
        for team in self.search([('use_helpdesk_timesheet', '=', True), ('project_id', '=', False)]):
            team.project_id = team._create_project(team.name, team.use_helpdesk_sale_timesheet, {'allow_timesheets': True, 'allow_timesheet_timer': True})
            self.env['helpdesk.ticket'].search([('team_id', '=', team.id), ('project_id', '=', False)]).write({'project_id': team.project_id.id})


class HelpdeskTicket(models.Model):
    _name = 'helpdesk.ticket'
    _inherit = ['helpdesk.ticket', 'timer.mixin']

    @api.model
    def default_get(self, fields_list):
        result = super(HelpdeskTicket, self).default_get(fields_list)
        if result.get('team_id') and not result.get('project_id'):
            result['project_id'] = self.env['helpdesk.team'].browse(result['team_id']).project_id.id
        return result

    project_id = fields.Many2one("project.project", string="Project", domain="[('allow_timesheets', '=', True), ('company_id', '=', company_id)]")
    task_id = fields.Many2one("project.task", string="Task", domain="[('id', 'in', _related_task_ids)]", tracking=True, help="The task must have the same customer as this ticket.")
    _related_task_ids = fields.Many2many('project.task', compute='_compute_related_task_ids')
    timesheet_ids = fields.One2many('account.analytic.line', 'helpdesk_ticket_id', 'Timesheets')
    is_closed = fields.Boolean(related="task_id.stage_id.is_closed", string="Is Closed", readonly=True)
    is_task_active = fields.Boolean(related="task_id.active", string='Is Task Active', readonly=True)
    use_helpdesk_timesheet = fields.Boolean('Timesheet activated on Team', related='team_id.use_helpdesk_timesheet', readonly=True)
    timesheet_timer = fields.Boolean(related='team_id.timesheet_timer')
    display_timesheet_timer = fields.Boolean("Display Timesheet Time", compute='_compute_display_timesheet_timer')
    total_hours_spent = fields.Float(compute='_compute_total_hours_spent', default=0)

    display_timer_start_secondary = fields.Boolean(compute='_compute_display_timer_buttons')

    @api.depends('display_timesheet_timer', 'timer_start', 'timer_pause', 'total_hours_spent')
    def _compute_display_timer_buttons(self):
        for ticket in self:
            displays = super()._compute_display_timer_buttons()
            start_p, start_s, stop, pause, resume = displays['start_p'], displays['start_p'], displays['stop'], displays['pause'], displays['resume']
            if not ticket.display_timesheet_timer:
                start_p, start_s, stop, pause, resume = False, False, False, False, False
            else:
                if not ticket.timer_start:
                    stop, pause, resume = False, False, False
                    if not ticket.total_hours_spent:
                        start_s = False
                    else:
                        start_p = False
            ticket.write({
                'display_timer_start_primary': start_p,
                'display_timer_start_secondary': start_s,
                'display_timer_stop': stop,
                'display_timer_pause': pause,
                'display_timer_resume': resume,
            })

    @api.depends('use_helpdesk_timesheet', 'timesheet_timer', 'timesheet_ids')
    def _compute_display_timesheet_timer(self):
        for ticket in self:
            ticket.display_timesheet_timer = ticket.use_helpdesk_timesheet and ticket.timesheet_timer

    @api.depends('project_id', 'company_id')
    def _compute_related_task_ids(self):
        for t in self:
            domain = [('project_id.allow_timesheets', '=', True), ('company_id', '=', t.company_id.id)]
            if t.project_id:
                domain = [('project_id', '=', t.project_id.id)]
            t._related_task_ids = self.env['project.task'].search(domain)._origin

    @api.depends('timesheet_ids')
    def _compute_total_hours_spent(self):
        for ticket in self:
            ticket.total_hours_spent = round(sum(ticket.timesheet_ids.mapped('unit_amount')), 2)

    @api.onchange('project_id')
    def _onchange_project_id(self):
        if self.project_id != self.task_id.project_id:
            # reset task when changing project
            self.task_id = False
    @api.onchange('task_id')
    def _onchange_task_id(self):
        if self.timesheet_ids:
            if self.task_id:
                msg = _("All timesheet hours will be assigned to the selected task on save. Discard to avoid the change.")
            else:
                msg = _("Timesheet hours will not be assigned to a customer task. Set a task to charge a customer.")
            return {'warning':
                {
                    'title': _("Warning"),
                    'message': msg
                }
            }

    @api.constrains('project_id', 'team_id')
    def _check_project_id(self):
        for ticket in self:
            if ticket.use_helpdesk_timesheet and not ticket.project_id:
                raise ValidationError(_("The project is required to track time on ticket."))

    @api.constrains('project_id', 'task_id')
    def _check_task_in_project(self):
        for ticket in self:
            if ticket.task_id:
                if ticket.task_id.project_id != ticket.project_id:
                    raise ValidationError(_("The task must be in ticket's project."))

    @api.model_create_multi
    def create(self, value_list):
        team_ids = set([value['team_id'] for value in value_list if value.get('team_id')])
        teams = self.env['helpdesk.team'].browse(team_ids)

        team_project_map = {}  # map with the team that require a project
        for team in teams:
            if team.use_helpdesk_timesheet:
                team_project_map[team.id] = team.project_id.id

        for value in value_list:
            if value.get('team_id') and not value.get('project_id') and team_project_map.get(value['team_id']):
                value['project_id'] = team_project_map[value['team_id']]

        return super(HelpdeskTicket, self).create(value_list)

    def write(self, values):
        result = super(HelpdeskTicket, self).write(values)
        # force timesheet values: changing ticket's task or project will reset timesheet ones
        timesheet_vals = {}
        for fname in self._timesheet_forced_fields():
            if fname in values:
                timesheet_vals[fname] = values[fname]
        if timesheet_vals:
            self.sudo().mapped('timesheet_ids').write(timesheet_vals)  # sudo since helpdesk user can change task
        return result

    @api.model
    def _fields_view_get(self, view_id=None, view_type='form', toolbar=False, submenu=False):
        """ Set the correct label for `unit_amount`, depending on company UoM """
        result = super(HelpdeskTicket, self)._fields_view_get(view_id=view_id, view_type=view_type, toolbar=toolbar, submenu=submenu)
        result['arch'] = self.env['account.analytic.line']._apply_timesheet_label(result['arch'])
        return result

    def action_view_ticket_task(self):
        self.ensure_one()
        return {
            'view_mode': 'form',
            'res_model': 'project.task',
            'type': 'ir.actions.act_window',
            'res_id': self.task_id.id,
        }

    def _timesheet_forced_fields(self):
        """ return the list of field that should also be written on related timesheets """
        return ['task_id', 'project_id']

    def action_timer_start(self):
        if not self.user_timer_id.timer_start and self.display_timesheet_timer:
            super().action_timer_start()

    def action_timer_stop(self):
        # timer was either running or paused
        if self.user_timer_id.timer_start and self.display_timesheet_timer:
            minutes_spent = super().action_timer_stop()
            minimum_duration = int(self.env['ir.config_parameter'].sudo().get_param('hr_timesheet.timesheet_min_duration', 0))
            rounding = int(self.env['ir.config_parameter'].sudo().get_param('hr_timesheet.timesheet_rounding', 0))
            minutes_spent = self._timer_rounding(minutes_spent, minimum_duration, rounding)
            return self._action_create_timesheet(minutes_spent * 60 / 3600)
        return False

    def _action_create_timesheet(self, time_spent):
        return {
            "name": _("Validate Spent Time"),
            "type": 'ir.actions.act_window',
            "res_model": 'helpdesk.ticket.create.timesheet',
            "views": [[False, "form"]],
            "target": 'new',
            "context": {
                **self.env.context,
                'active_id': self.id,
                'active_model': self._name,
                'default_time_spent': time_spent,
            },
        }
