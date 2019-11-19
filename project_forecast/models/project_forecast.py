# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.
from datetime import datetime, timedelta

from dateutil.relativedelta import relativedelta
import logging

from odoo import api, fields, models, _
from odoo.exceptions import ValidationError


_logger = logging.getLogger(__name__)


class PlanningShift(models.Model):
    _inherit = 'planning.slot'

    project_id = fields.Many2one('project.project', string="Project", domain="[('company_id', '=', company_id), ('allow_forecast', '=', True)]", check_company=True, group_expand='_read_group_project_id')
    task_id = fields.Many2one('project.task', string="Task", domain="[('company_id', '=', company_id), ('project_id', '=?', project_id)]", check_company=True)

    _sql_constraints = [
        ('project_required_if_task', "CHECK( (task_id IS NOT NULL AND project_id IS NOT NULL) OR (task_id IS NULL) )", "If the planning is linked to a task, the project must be set too."),
    ]

    @api.onchange('task_id')
    def _onchange_task_id(self):
        self.project_id = self.task_id.project_id

    @api.onchange('project_id')
    def _onchange_project_id(self):
        if self.project_id != self.task_id.project_id:
            # reset task when changing project
            self.task_id = False

    @api.constrains('task_id', 'project_id')
    def _check_task_in_project(self):
        for forecast in self:
            if forecast.task_id and (forecast.task_id not in forecast.project_id.tasks):
                raise ValidationError(_("Your task is not in the selected project."))

    def _read_group_project_id(self, projects, domain, order):
        if self._context.get('planning_expand_project'):
            start_date = datetime.strptime([dom[2] for dom in domain if dom[0] == 'start_datetime'][0], '%Y-%m-%d %H:%M:%S') or datetime.now()
            min_date = start_date - timedelta(days=30)
            max_date = start_date + timedelta(days=30)
            return self.env['planning.slot'].search([('start_datetime', '>=', min_date), ('start_datetime', '<=', max_date)]).mapped('project_id')
        return projects

    def _get_fields_breaking_publication(self):
        """ Fields list triggering the `publication_warning` to True when updating shifts """
        result = super(PlanningShift, self)._get_fields_breaking_publication()
        result.extend(['project_id', 'task_id'])
        return result

    def _name_get_fields(self):
        fields = super(PlanningShift, self)._name_get_fields()
        return ['project_id', 'task_id'] + fields
