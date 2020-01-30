# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

from datetime import date

from odoo import _, api, fields, models
from odoo.exceptions import ValidationError


class ResConfigSettings(models.TransientModel):
    _inherit = 'res.config.settings'

    fiscalyear_last_day = fields.Integer(related='company_id.fiscalyear_last_day', required=True, readonly=False)
    fiscalyear_last_month = fields.Selection(related='company_id.fiscalyear_last_month', required=True, readonly=False)
    period_lock_date = fields.Date(string='Lock Date for Non-Advisers',
                                   related='company_id.period_lock_date', readonly=False)
    fiscalyear_lock_date = fields.Date(string='Lock Date for All Users',
                                       related='company_id.fiscalyear_lock_date', readonly=False)
    tax_lock_date = fields.Date("Tax Lock Date", related='company_id.tax_lock_date', readonly=False)
    use_anglo_saxon = fields.Boolean(string='Anglo-Saxon Accounting', related='company_id.anglo_saxon_accounting', readonly=False)
    module_account_predictive_bills = fields.Boolean(string="Account Predictive Bills")
    transfer_account_id = fields.Many2one('account.account', string="Transfer Account",
        related='company_id.transfer_account_id', readonly=False,
        domain=lambda self: [('reconcile', '=', True), ('user_type_id.id', '=', self.env.ref('account.data_account_type_current_assets').id)],
        help="Intermediary account used when moving money from a liquidity account to another")
    invoicing_switch_threshold = fields.Date(string="Invoicing Switch Threshold", related='company_id.invoicing_switch_threshold', readonly=False)

    @api.constrains('fiscalyear_last_day', 'fiscalyear_last_month')
    def _check_fiscalyear(self):
        # We try if the date exists in 2020, which is a leap year.
        # We do not define the constrain on res.company, since the recomputation of the related
        # fields is done one field at a time.
        for wiz in self:
            try:
                date(2020, int(wiz.fiscalyear_last_month), wiz.fiscalyear_last_day)
            except ValueError:
                raise ValidationError(
                    _('Incorrect fiscal year date: day is out of range for month. Month: %s; Day: %s') %
                    (wiz.fiscalyear_last_month, wiz.fiscalyear_last_day)
                )
