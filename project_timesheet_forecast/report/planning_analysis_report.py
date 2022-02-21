# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import fields, models, api

class PlanningAnalysisReport(models.Model):
    _inherit = "planning.analysis.report"

    percentage_hours = fields.Float("Progress (%)", readonly=True, group_operator="avg")
    effective_hours = fields.Float("Effective Hours", readonly=True, help="Number of hours on the employee's Timesheets for this task (and its sub-tasks) during the timeframe of the shift.")
    remaining_hours = fields.Float("Remaining Hours", readonly=True, help="Allocated hours minus the effective hours.")
    allocated_hours_cost = fields.Float("Allocated Hours Cost", readonly=True)
    effective_hours_cost = fields.Float("Effective Hours Cost", readonly=True)

    @api.model
    def _select(self):
        return super()._select() + """,
            S.effective_hours AS effective_hours,
            S.percentage_hours AS percentage_hours,
            (S.allocated_hours - S.effective_hours) AS remaining_hours,
            S.allocated_hours * E.timesheet_cost AS allocated_hours_cost,
            S.effective_hours * E.timesheet_cost AS effective_hours_cost
        """

    @api.model
    def _group_by(self):
        return super()._group_by() + """,
            S.effective_hours, S.allocated_hours, E.timesheet_cost
        """
