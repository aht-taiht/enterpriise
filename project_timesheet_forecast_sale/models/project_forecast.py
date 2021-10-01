# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import fields, models


class Forecast(models.Model):

    _inherit = 'planning.slot'

    order_line_id = fields.Many2one('sale.order.line', string='Sales Order Line', related="task_id.sale_line_id", store=True, readonly=False)

    def _prepare_slot_analytic_line(self, day_date, work_hours_count):
        res = super()._prepare_slot_analytic_line(day_date, work_hours_count)
        res['so_line'] = self.sale_line_id.id
        return res
