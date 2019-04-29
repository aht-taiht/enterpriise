# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import api, fields, models, _


class HelpdeskTicket(models.Model):
    _inherit = 'helpdesk.ticket'

    invoices_count = fields.Integer('Credit Notes Count', compute='_compute_credit_notes_count')
    invoice_ids = fields.Many2many('account.invoice', string='Credit Notes')

    @api.depends('invoice_ids')
    def _compute_credit_notes_count(self):
        for ticket in self:
            ticket.invoices_count = len(ticket.invoice_ids)

    def action_view_invoices(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': _('Credit Notes'),
            'res_model': 'account.invoice',
            'view_mode': 'tree,form',
            'domain': [('id', 'in', self.invoice_ids.ids)],
        }
