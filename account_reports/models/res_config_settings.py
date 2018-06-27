# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import fields, models


class ResConfigSettings(models.TransientModel):
    _inherit = 'res.config.settings'

    days_between_two_followups = fields.Integer(related='company_id.days_between_two_followups', string='Days between two follow-ups')
    totals_below_sections = fields.Boolean(related='company_id.totals_below_sections', string='Add totals below sections',
                                           help='When ticked, totals and subtotals appear below the sections of the report.')