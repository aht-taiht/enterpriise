# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import api, fields, models


class HelpdeskTicket(models.Model):
    _inherit = 'helpdesk.ticket'

    commercial_partner_id = fields.Many2one(related='partner_id.commercial_partner_id')
    sale_order_id = fields.Many2one('sale.order', string='Sales Order', domain="[('partner_id', 'child_of', commercial_partner_id)]")

    @api.onchange('partner_id')
    def _onchange_partner_id_so_domain(self):
        return {
            'domain': {
                'sale_order_id': [('partner_id', 'child_of', self.commercial_partner_id.id)] if self.partner_id else []
            }
        }
