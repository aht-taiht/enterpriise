# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

import psycopg2
import datetime
from dateutil.relativedelta import relativedelta
from math import copysign

from odoo import api, Command, fields, models, _
from odoo.exceptions import UserError, ValidationError
from odoo.tools import float_compare, float_is_zero, formatLang, end_of

DAYS_PER_MONTH = 30
DAYS_PER_YEAR = DAYS_PER_MONTH * 12

class AccountAsset(models.Model):
    _name = 'account.asset'
    _description = 'Asset/Revenue Recognition'
    _inherit = ['mail.thread', 'mail.activity.mixin', 'analytic.mixin']

    depreciation_entries_count = fields.Integer(compute='_compute_counts', string='# Posted Depreciation Entries')
    gross_increase_count = fields.Integer(compute='_compute_counts', string='# Gross Increases', help="Number of assets made to increase the value of the asset")
    total_depreciation_entries_count = fields.Integer(compute='_compute_counts', string='# Depreciation Entries', help="Number of depreciation entries (posted or not)")

    name = fields.Char(string='Asset Name', compute='_compute_name', store=True, required=True, readonly=False, tracking=True)
    company_id = fields.Many2one('res.company', string='Company', required=True, readonly=True, states={'draft': [('readonly', False)]}, default=lambda self: self.env.company)
    currency_id = fields.Many2one('res.currency', related='company_id.currency_id', store=True)
    state = fields.Selection(
        selection=[('model', 'Model'),
            ('draft', 'Draft'),
            ('open', 'Running'),
            ('paused', 'On Hold'),
            ('close', 'Closed'),
            ('cancelled', 'Cancelled')],
        string='Status',
        copy=False,
        default='draft',
        readonly=True,
        help="When an asset is created, the status is 'Draft'.\n"
            "If the asset is confirmed, the status goes in 'Running' and the depreciation lines can be posted in the accounting.\n"
            "The 'On Hold' status can be set manually when you want to pause the depreciation of an asset for some time.\n"
            "You can manually close an asset when the depreciation is over.\n"
            "By cancelling an asset, all depreciation entries will be reversed")
    active = fields.Boolean(default=True)
    asset_type = fields.Selection([('sale', 'Sale: Revenue Recognition'), ('purchase', 'Purchase: Asset'), ('expense', 'Deferred Expense')], compute='_compute_asset_type', store=True, index=True, copy=True)

    # Depreciation params
    method = fields.Selection(
        selection=[
            ('linear', 'Straight Line'),
            ('degressive', 'Declining'),
            ('degressive_then_linear', 'Declining then Straight Line')
        ],
        string='Method',
        readonly=True, states={'draft': [('readonly', False)], 'model': [('readonly', False)]},
        default='linear',
        help="Choose the method to use to compute the amount of depreciation lines.\n"
             "  * Straight Line: Calculated on basis of: Gross Value / Duration\n"
             "  * Declining: Calculated on basis of: Residual Value * Declining Factor\n"
             "  * Declining then Straight Line: Like Declining but with a minimum depreciation value equal to the straight line value."
    )
    method_number = fields.Integer(string='Duration', readonly=True, states={'draft': [('readonly', False)], 'model': [('readonly', False)]}, default=5, help="The number of depreciations needed to depreciate your asset")
    method_period = fields.Selection([('1', 'Months'), ('12', 'Years')], string='Number of Months in a Period', readonly=True, default='12', states={'draft': [('readonly', False)], 'model': [('readonly', False)]},
        help="The amount of time between two depreciations")
    method_progress_factor = fields.Float(string='Declining Factor', readonly=True, default=0.3, states={'draft': [('readonly', False)], 'model': [('readonly', False)]})
    prorata_computation_type = fields.Selection(
        selection=[
            ('none', 'No Prorata'),
            ('constant_periods', 'Constant Periods'),
            ('daily_computation', 'Based on days per period'),
        ],
        string="Computation",
        readonly=True, states={'draft': [('readonly', False)], 'model': [('readonly', False)]},
        required=True, default='constant_periods',
    )
    prorata_date = fields.Date(  # the starting date of the depreciations
        string='Prorata Date',
        compute='_compute_prorata_date', store=True, readonly=False,
        required=True, precompute=True
    )
    paused_prorata_date = fields.Date(compute='_compute_paused_prorata_date')  # number of days to shift the computation of future deprecations
    account_asset_id = fields.Many2one('account.account', string='Fixed Asset Account', compute='_compute_account_asset_id', help="Account used to record the purchase of the asset at its original price.", store=True, states={'draft': [('readonly', False)], 'model': [('readonly', False)]}, domain="[('company_id', '=', company_id), ('account_type', '!=', 'off_balance')]")
    account_depreciation_id = fields.Many2one(
        comodel_name='account.account',
        string='Depreciation Account',
        readonly=True, states={'draft': [('readonly', False)], 'model': [('readonly', False)]},
        domain="[('account_type', 'not in', ('asset_receivable', 'liability_payable', 'asset_cash', 'liability_credit_card', 'off_balance')), ('deprecated', '=', False), ('company_id', '=', company_id)]",
        help="Account used in the depreciation entries, to decrease the asset value."
    )
    account_depreciation_expense_id = fields.Many2one(
        comodel_name='account.account',
        string='Expense Account',
        readonly=True, states={'draft': [('readonly', False)], 'model': [('readonly', False)]},
        domain="[('account_type', 'not in', ('asset_receivable', 'liability_payable', 'asset_cash', 'liability_credit_card', 'off_balance')), ('deprecated', '=', False), ('company_id', '=', company_id)]",
        help="Account used in the periodical entries, to record a part of the asset as expense.",
    )

    journal_id = fields.Many2one(
        'account.journal',
        string='Journal',
        domain="[('type', '=', 'general'), ('company_id', '=', company_id)]",
        compute='_compute_journal_id', store=True, readonly=True,
        states={'draft': [('readonly', False)], 'model': [('readonly', False)]},
    )

    # Values
    original_value = fields.Monetary(string="Original Value", compute='_compute_value', store=True, states={'draft': [('readonly', False)]})
    book_value = fields.Monetary(string='Book Value', readonly=True, compute='_compute_book_value', recursive=True, store=True, help="Sum of the depreciable value, the salvage value and the book value of all value increase items")
    value_residual = fields.Monetary(string='Depreciable Value', compute='_compute_value_residual')
    salvage_value = fields.Monetary(string='Not Depreciable Value', readonly=True, states={'draft': [('readonly', False)]},
                                    help="It is the amount you plan to have that you cannot depreciate.")
    total_depreciable_value = fields.Monetary(compute='_compute_total_depreciable_value')
    gross_increase_value = fields.Monetary(string="Gross Increase Value", compute="_compute_book_value", compute_sudo=True)
    non_deductible_tax_value = fields.Monetary(string="Non Deductible Tax Value", compute="_compute_non_deductible_tax_value", store=True, readonly=True)
    related_purchase_value = fields.Monetary(compute='_compute_related_purchase_value')

    # Links with entries
    depreciation_move_ids = fields.One2many('account.move', 'asset_id', string='Depreciation Lines', readonly=True, states={'draft': [('readonly', False)], 'open': [('readonly', False)], 'paused': [('readonly', False)]})
    original_move_line_ids = fields.Many2many('account.move.line', 'asset_move_line_rel', 'asset_id', 'line_id', string='Journal Items', readonly=True, states={'draft': [('readonly', False)]}, copy=False)

    # Dates
    acquisition_date = fields.Date(
        compute='_compute_acquisition_date', store=True, precompute=True,
        states={'draft': [('readonly', False)]},
    )
    disposal_date = fields.Date(readonly=True, states={'draft': [('readonly', False)]}, compute="_compute_disposal_date", store=True)

    # model-related fields
    model_id = fields.Many2one('account.asset', string='Model', change_default=True, readonly=True, states={'draft': [('readonly', False)]}, domain="[('company_id', '=', company_id)]")
    account_type = fields.Selection(string="Type of the account", related='account_asset_id.account_type')
    display_account_asset_id = fields.Boolean(compute="_compute_display_account_asset_id")

    # Capital gain
    parent_id = fields.Many2one('account.asset', help="An asset has a parent when it is the result of gaining value")
    children_ids = fields.One2many('account.asset', 'parent_id', help="The children are the gains in value of this asset")

    # Adapt for import fields
    already_depreciated_amount_import = fields.Monetary(
        readonly=True, states={'draft': [('readonly', False)]},
        help="In case of an import from another software, you might need to use this field to have the right "
             "depreciation table report. This is the value that was already depreciated with entries not computed from this model",
    )

    asset_lifetime_days = fields.Integer(compute="_compute_lifetime_days")  # total number of days to consider for the computation of an asset depreciation board
    asset_paused_days = fields.Float(copy=False)

    # -------------------------------------------------------------------------
    # COMPUTE METHODS
    # -------------------------------------------------------------------------
    @api.depends('company_id')
    def _compute_journal_id(self):
        for asset in self:
            if asset.journal_id and asset.journal_id.company_id == asset.company_id:
                asset.journal_id = asset.journal_id
            else:
                asset.journal_id = self.env['account.journal'].search([('type', '=', 'general'), ('company_id', '=', asset.company_id.id)], limit=1)

    @api.depends('salvage_value', 'original_value')
    def _compute_total_depreciable_value(self):
        for asset in self:
            asset.total_depreciable_value = asset.original_value - asset.salvage_value

    @api.depends('depreciation_move_ids.date', 'state')
    def _compute_disposal_date(self):
        for asset in self:
            if asset.state == 'close':
                dates = asset.depreciation_move_ids.filtered(lambda m: m.date).mapped('date')
                asset.disposal_date = dates and max(dates)
            else:
                asset.disposal_date = False

    @api.depends('original_move_line_ids', 'original_move_line_ids.account_id', 'asset_type', 'non_deductible_tax_value')
    def _compute_value(self):
        for record in self:
            if not record.original_move_line_ids:
                record.original_value = record.original_value or False
                continue
            if any(line.move_id.state == 'draft' for line in record.original_move_line_ids):
                raise UserError(_("All the lines should be posted"))
            record.original_value = record.related_purchase_value
            if record.non_deductible_tax_value:
                record.original_value += record.non_deductible_tax_value

    @api.depends('original_move_line_ids')
    @api.depends_context('form_view_ref')
    def _compute_display_account_asset_id(self):
        for record in self:
            # Hide the field when creating an asset model from the CoA. (form_view_ref is set from there)
            model_from_coa = self.env.context.get('form_view_ref') and record.state == 'model'
            record.display_account_asset_id = not record.original_move_line_ids and not model_from_coa

    @api.depends('account_depreciation_id', 'account_depreciation_expense_id', 'original_move_line_ids')
    def _compute_account_asset_id(self):
        for record in self:
            if record.original_move_line_ids:
                if len(record.original_move_line_ids.account_id) > 1:
                    raise UserError(_("All the lines should be from the same account"))
                record.account_asset_id = record.original_move_line_ids.account_id
            if not record.account_asset_id:
                # Only set a default value, do not erase user inputs
                record._onchange_account_depreciation_id()
                record._onchange_account_depreciation_expense_id()

    @api.depends('original_move_line_ids')
    def _compute_analytic_distribution(self):
        for asset in self:
            distribution_asset = {}
            amount_total = sum(asset.original_move_line_ids.mapped("balance"))
            if not float_is_zero(amount_total, precision_rounding=asset.currency_id.rounding):
                for line in asset.original_move_line_ids._origin:
                    if line.analytic_distribution:
                        for account, distribution in line.analytic_distribution.items():
                            distribution_asset[account] = distribution_asset.get(account, 0) + distribution * line.balance
                for account, distribution_amount in distribution_asset.items():
                    distribution_asset[account] = distribution_amount / amount_total
            asset.analytic_distribution = distribution_asset if distribution_asset else asset.analytic_distribution

    @api.depends('method_number', 'method_period', 'prorata_computation_type')
    def _compute_lifetime_days(self):
        for asset in self:
            if asset.prorata_computation_type == 'daily_computation':
                asset.asset_lifetime_days = (asset.prorata_date + relativedelta(months=int(asset.method_period) * asset.method_number) - asset.prorata_date).days
            else:
                asset.asset_lifetime_days = int(asset.method_period) * asset.method_number * DAYS_PER_MONTH

    @api.depends('acquisition_date', 'company_id', 'prorata_computation_type')
    def _compute_prorata_date(self):
        for asset in self:
            if asset.prorata_computation_type == 'none' and asset.acquisition_date:
                fiscalyear_date = asset.company_id.compute_fiscalyear_dates(asset.acquisition_date).get('date_from')
                asset.prorata_date = fiscalyear_date
            else:
                asset.prorata_date = asset.acquisition_date

    @api.depends('prorata_date', 'prorata_computation_type', 'asset_paused_days')
    def _compute_paused_prorata_date(self):
        for asset in self:
            if asset.prorata_computation_type == 'daily_computation':
                asset.paused_prorata_date = asset.prorata_date + relativedelta(days=asset.asset_paused_days)
            else:
                asset.paused_prorata_date = asset.prorata_date + relativedelta(
                    months=int(asset.asset_paused_days / DAYS_PER_MONTH),
                    days=asset.asset_paused_days % DAYS_PER_MONTH
                )

    @api.depends('original_move_line_ids')
    def _compute_related_purchase_value(self):
        for asset in self:
            related_purchase_value = sum(asset.original_move_line_ids.mapped('balance'))
            if asset.account_asset_id.multiple_assets_per_line and len(asset.original_move_line_ids) == 1:
                related_purchase_value /= max(1, int(asset.original_move_line_ids.quantity))
            asset.related_purchase_value = related_purchase_value

    @api.depends('original_move_line_ids')
    def _compute_acquisition_date(self):
        for asset in self:
            asset.acquisition_date = asset.acquisition_date or min(asset.original_move_line_ids.mapped('date') + [fields.Date.today()])

    @api.depends('original_move_line_ids')
    def _compute_name(self):
        for record in self:
            record.name = record.name or (record.original_move_line_ids and record.original_move_line_ids[0].name or '')

    @api.depends('original_move_line_ids')
    @api.depends_context('asset_type')
    def _compute_asset_type(self):
        for record in self:
            if not record.asset_type and 'asset_type' in self.env.context:
                record.asset_type = self.env.context['asset_type']
            if not record.asset_type and record.original_move_line_ids:
                account = record.original_move_line_ids.account_id
                record.asset_type = account.asset_type

    @api.depends(
        'original_value', 'salvage_value', 'already_depreciated_amount_import',
        'depreciation_move_ids.state',
        'depreciation_move_ids.depreciation_value',
        'depreciation_move_ids.reversal_move_id'
    )
    def _compute_value_residual(self):
        for record in self:
            posted_depreciation_moves = record.depreciation_move_ids.filtered(lambda mv: mv.state == 'posted')
            record.value_residual = (
                record.original_value
                - record.salvage_value
                - record.already_depreciated_amount_import
                - sum(posted_depreciation_moves.mapped('depreciation_value'))
            )

    @api.depends('value_residual', 'salvage_value', 'children_ids.book_value')
    def _compute_book_value(self):
        for record in self:
            record.book_value = record.value_residual + record.salvage_value + sum(record.children_ids.mapped('book_value'))
            record.gross_increase_value = sum(record.children_ids.mapped('original_value'))

    @api.depends('original_move_line_ids')
    def _compute_non_deductible_tax_value(self):
        for record in self:
            record.non_deductible_tax_value = 0.0
            for line in record.original_move_line_ids:
                if line.non_deductible_tax_value:
                    account = line.account_id
                    auto_create_multi = account.create_asset != 'no' and account.multiple_assets_per_line
                    quantity = line.quantity if auto_create_multi else 1
                    record.non_deductible_tax_value += record.currency_id.round(line.non_deductible_tax_value / quantity)

    @api.depends('depreciation_move_ids.state', 'parent_id')
    def _compute_counts(self):
        depreciation_per_asset = {
            group['asset_id'][0]: group['move_ids']
            for group in self.env['account.move'].read_group(
                domain=[
                    ('asset_id', 'in', self.ids),
                    ('state', '=', 'posted'),
                ],
                fields=['move_ids:count(id)'],
                groupby=['asset_id'],
            )
        }
        for asset in self:
            asset.depreciation_entries_count = depreciation_per_asset.get(asset.id, 0)
            asset.total_depreciation_entries_count = len(asset.depreciation_move_ids)
            asset.gross_increase_count = len(asset.children_ids)

    # -------------------------------------------------------------------------
    # ONCHANGE METHODS
    # -------------------------------------------------------------------------
    def onchange(self, values, field_name, field_onchange):
        # Force the re-rendering of computed fields on the o2m
        if field_name == 'depreciation_move_ids':
            return super().onchange(values, False, {
                fname: spec
                for fname, spec in field_onchange.items()
                if fname.startswith('depreciation_move_ids') or fname.startswith('original_move_line_ids')
            })
        return super().onchange(values, field_name, field_onchange)

    @api.onchange('account_depreciation_id')
    def _onchange_account_depreciation_id(self):
        if not self.original_move_line_ids:
            if self.asset_type == 'expense':
                # Always change the account since it is not visible in the form
                self.account_asset_id = self.account_depreciation_id
            if self.asset_type == 'purchase' and not self.account_asset_id and self.state != 'model':
                # Only set a default value since it is visible in the form
                self.account_asset_id = self.account_depreciation_id

    @api.onchange('account_depreciation_expense_id')
    def _onchange_account_depreciation_expense_id(self):
        if not self.original_move_line_ids and self.asset_type not in ('purchase', 'expense'):
            self.account_asset_id = self.account_depreciation_expense_id

    @api.onchange('original_value', 'original_move_line_ids')
    def _display_original_value_warning(self):
        if self.original_move_line_ids:
            computed_original_value = self.related_purchase_value + self.non_deductible_tax_value
            if self.original_value != computed_original_value:
                warning = {
                    'title': _("Warning for the Original Value of %s", self.name),
                    'message': _("The amount you have entered (%s) does not match the Related Purchase's value (%s). "
                                 "Please make sure this is what you want.",
                                 formatLang(self.env, self.original_value, currency_obj=self.currency_id),
                                 formatLang(self.env, computed_original_value, currency_obj=self.currency_id))
                }
                return {'warning': warning}

    @api.onchange('original_move_line_ids')
    def _onchange_original_move_line_ids(self):
        # Force the recompute
        self.acquisition_date = False
        self._compute_acquisition_date()

    @api.onchange('account_asset_id')
    def _onchange_account_asset_id(self):
        if self.asset_type in ('purchase', 'expense'):
            self.account_depreciation_id = self.account_depreciation_id or self.account_asset_id
        else:
            self.account_depreciation_expense_id = self.account_depreciation_expense_id or self.account_asset_id

    @api.onchange('model_id')
    def _onchange_model_id(self):
        model = self.model_id
        if model:
            self.method = model.method
            self.method_number = model.method_number
            self.method_period = model.method_period
            self.method_progress_factor = model.method_progress_factor
            self.prorata_computation_type = model.prorata_computation_type
            self.analytic_distribution = model.analytic_distribution or self.analytic_distribution
            self.account_depreciation_id = model.account_depreciation_id
            self.account_depreciation_expense_id = model.account_depreciation_expense_id
            self.journal_id = model.journal_id

    @api.onchange('asset_type')
    def _onchange_type(self):
        if self.state != 'model':
            if self.asset_type == 'sale':
                self.method_period = '1'
            else:
                self.method_period = '12'

    @api.onchange('original_value', 'salvage_value', 'acquisition_date', 'method', 'method_progress_factor', 'method_period',
                 'method_number', 'prorata_computation_type', 'already_depreciated_amount_import', 'prorata_date',)
    def onchange_consistent_board(self):
        """ When changing the fields that should change the values of the entries, we unlink the entries, so the
         depreciation board is not inconsistent with the values of the asset"""
        self.write(
            {'depreciation_move_ids': [Command.set([])]}
        )

    # -------------------------------------------------------------------------
    # CONSTRAINT METHODS
    # -------------------------------------------------------------------------
    @api.constrains('active', 'state')
    def _check_active(self):
        for record in self:
            if not record.active and record.state != 'close':
                raise UserError(_('You cannot archive a record that is not closed'))

    @api.constrains('depreciation_move_ids')
    def _check_depreciations(self):
        for asset in self:
            if (
                asset.state == 'open'
                and asset.depreciation_move_ids
                and not asset.currency_id.is_zero(
                    asset.depreciation_move_ids.sorted(lambda x: (x.date, x.id))[-1].asset_remaining_value
                )
            ):
                raise UserError(_("The remaining value on the last depreciation line must be 0"))

    @api.constrains('original_move_line_ids')
    def _check_related_purchase(self):
        for asset in self:
            if asset.original_move_line_ids and asset.related_purchase_value == 0:
                raise UserError(_("You cannot create an asset from lines containing credit and debit on the account or with a null amount"))

    # -------------------------------------------------------------------------
    # LOW-LEVEL METHODS
    # -------------------------------------------------------------------------
    @api.ondelete(at_uninstall=True)
    def _unlink_if_model_or_draft(self):
        for asset in self:
            if asset.state in ['open', 'paused', 'close']:
                raise UserError(_(
                    'You cannot delete a document that is in %s state.',
                    dict(self._fields['state']._description_selection(self.env)).get(asset.state)
                ))

            posted_amount = len(asset.depreciation_move_ids.filtered(lambda x: x.state == 'posted'))
            if posted_amount > 0:
                raise UserError(_('You cannot delete an asset linked to posted entries.'
                                  '\nYou should either confirm the asset, then, sell or dispose of it,'
                                  ' or cancel the linked journal entries.'))

    def unlink(self):
        for asset in self:
            for line in asset.original_move_line_ids:
                if line.name:
                    body = _(
                        'A document linked to %s has been deleted: %s',
                        line.name,
                        asset._get_html_link(),
                    )
                else:
                    body = _(
                        'A document linked to this move has been deleted: %s',
                        asset._get_html_link(),
                    )
                line.move_id.message_post(body=body)
        return super(AccountAsset, self).unlink()

    def copy_data(self, default=None):
        if default is None:
            default = {}
        if self.state == 'model':
            default.update(state='model')
        default['name'] = self.name + _(' (copy)')
        default['account_asset_id'] = self.account_asset_id.id
        return super().copy_data(default)

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if 'state' in vals and vals['state'] != 'draft' and not (set(vals) - set({'account_depreciation_id', 'account_depreciation_expense_id', 'journal_id'})):
                raise UserError(_("Some required values are missing"))
            if self._context.get('default_state') != 'model' and vals.get('state') != 'model':
                vals['state'] = 'draft'
        new_recs = super(AccountAsset, self.with_context(mail_create_nolog=True)).create(vals_list)
        # if original_value is passed in vals, make sure the right value is set (as a different original_value may have been computed by _compute_value())
        for i, vals in enumerate(vals_list):
            if 'original_value' in vals:
                new_recs[i].original_value = vals['original_value']
        if self.env.context.get('original_asset'):
            # When original_asset is set, only one asset is created since its from the form view
            original_asset = self.env['account.asset'].browse(self.env.context.get('original_asset'))
            original_asset.model_id = new_recs
        return new_recs

    def write(self, vals):
        result = super().write(vals)
        if 'account_depreciation_id' in vals:
            self.depreciation_move_ids.line_ids[::2].account_id = vals['account_depreciation_id']
        if 'account_depreciation_expense_id' in vals:
            self.depreciation_move_ids.line_ids[1::2].account_id = vals['account_depreciation_expense_id']
        if 'journal_id' in vals:
            self.depreciation_move_ids.journal_id = vals['journal_id']
        return result

    def get_formview_id(self, access_uid=None):
        """ Overriding this method to redirect user to correct form view based on asset type """
        for vid, view_type in self._get_views(self.asset_type):
            if view_type == 'form':
                return vid

    # -------------------------------------------------------------------------
    # BOARD COMPUTATION
    # -------------------------------------------------------------------------
    def _compute_board_amount(self, residual_amount, period_start_date, period_end_date, days_already_depreciated, days_left_to_depreciated, residual_declining):
        number_days = self._get_delta_days(period_start_date, period_end_date)
        total_days = number_days + days_already_depreciated

        if self.method in ('degressive', 'degressive_then_linear'):
            # Declining by year but divided per month
            # We compute the amount of the period based on ratio how many days there are in the period
            # e.g: monthly period = 30 days --> (30/360) * 12000 * 0.4
            # => For each month in the year we will decline the same amount.
            amount = (number_days / DAYS_PER_YEAR) * residual_declining * self.method_progress_factor
        else:
            computed_linear_amount = (self.total_depreciable_value * total_days / self.asset_lifetime_days) + residual_amount - self.total_depreciable_value
            if float_compare(residual_amount, 0, precision_rounding=self.currency_id.rounding) >= 0:
                linear_amount = min(computed_linear_amount, residual_amount)
                amount = max(linear_amount, 0)
            else:
                linear_amount = max(computed_linear_amount, residual_amount)
                amount = min(linear_amount, 0)

        if self.method == 'degressive_then_linear' and days_left_to_depreciated != 0:
            linear_amount = number_days * self.total_depreciable_value / self.asset_lifetime_days
            amount = max(linear_amount, amount, key=abs)

        # if self.method == 'degressif_chelou' and days_left_to_depreciated != 0:
        #     linear_amount = number_days * residual_declining / days_left_to_depreciated
        #     if float_compare(residual_amount, 0, precision_rounding=self.currency_id.rounding) >= 0:
        #         amount = max(linear_amount, amount)
        #     else:
        #         amount = min(linear_amount, amount)


        if abs(residual_amount) < abs(amount) or total_days >= self.asset_lifetime_days:
            # If the residual amount is less than the computed amount, we keep the residual amount
            # If total_days is greater or equals to asset lifetime days, it should mean that
            # the asset will finish in this period and the value for this period is equals to the residual amount.
            amount = residual_amount
        return number_days, self.currency_id.round(amount)

    def compute_depreciation_board(self):
        self.ensure_one()
        new_depreciation_moves_data = self._recompute_board()

        # Need to unlink draft move before adding new one because if we create new move before, it will cause an error
        # in the compute for the depreciable/cumulative value
        self.depreciation_move_ids.filtered(lambda mv: mv.state == 'draft').unlink()
        new_depreciation_moves = self.env['account.move'].create(new_depreciation_moves_data)
        if self.state == 'open':
            # In case of the asset is in running mode, we post in the past and set to auto post move in the future
            new_depreciation_moves._post()

        return True

    def _recompute_board(self):
        self.ensure_one()
        # All depreciation moves that are posted
        posted_depreciation_move_ids = self.depreciation_move_ids.filtered(
            lambda mv: mv.state == 'posted' and not mv.asset_value_change
        ).sorted(key=lambda mv: (mv.date, mv.id))

        imported_amount = self.already_depreciated_amount_import
        residual_amount = self.value_residual
        if not posted_depreciation_move_ids:
            residual_amount += imported_amount
        residual_declining = residual_amount

        # Days already depreciated
        days_already_depreciated = sum(posted_depreciation_move_ids.mapped('asset_number_days'))
        days_left_to_depreciated = self.asset_lifetime_days - days_already_depreciated
        days_already_added = sum([(mv.date - mv.asset_depreciation_beginning_date).days + 1 for mv in posted_depreciation_move_ids])

        start_depreciation_date = self.paused_prorata_date + relativedelta(days=days_already_added)
        final_depreciation_date = self.paused_prorata_date + relativedelta(months=int(self.method_period) * self.method_number, days=-1)
        final_depreciation_date = self._get_end_period_date(final_depreciation_date)

        depreciation_move_values = []
        if not float_is_zero(self.value_residual, precision_rounding=self.currency_id.rounding):
            while days_already_depreciated < self.asset_lifetime_days:
                period_end_depreciation_date = self._get_end_period_date(start_depreciation_date)
                period_end_fiscalyear_date = self.company_id.compute_fiscalyear_dates(period_end_depreciation_date).get('date_to')

                days, amount = self._compute_board_amount(residual_amount, start_depreciation_date, period_end_depreciation_date, days_already_depreciated, days_left_to_depreciated, residual_declining)
                residual_amount -= amount

                if not posted_depreciation_move_ids:
                    # self.already_depreciated_amount_import management.
                    # Subtracts the imported amount from the first depreciation moves until we reach it
                    # (might skip several depreciation entries)
                    if abs(imported_amount) <= abs(amount):
                        amount -= imported_amount
                        imported_amount = 0
                    else:
                        imported_amount -= amount
                        amount = 0

                if self.method == 'degressive_then_linear' and final_depreciation_date < period_end_depreciation_date:
                    period_end_depreciation_date = final_depreciation_date

                if not float_is_zero(amount, precision_rounding=self.currency_id.rounding):
                    depreciation_move_values.append(self.env['account.move']._prepare_move_for_asset_depreciation({
                        'amount': amount,
                        'asset_id': self,
                        'depreciation_beginning_date': start_depreciation_date,
                        'date': period_end_depreciation_date,
                        'asset_number_days': days,
                    }))
                days_already_depreciated += days

                if period_end_depreciation_date == period_end_fiscalyear_date:
                    days_left_to_depreciated = self.asset_lifetime_days - days_already_depreciated
                    residual_declining = residual_amount

                start_depreciation_date = period_end_depreciation_date + relativedelta(days=1)

        return depreciation_move_values

    def _get_end_period_date(self, start_depreciation_date):
        """Get the end of the period in which the depreciation is posted.

        Can be the end of the month if the asset is depreciated monthly, or the end of the fiscal year is it is depreciated yearly.
        """
        self.ensure_one()
        fiscalyear_date = self.company_id.compute_fiscalyear_dates(start_depreciation_date).get('date_to')
        period_end_depreciation_date = fiscalyear_date if start_depreciation_date < fiscalyear_date else fiscalyear_date + relativedelta(years=1)

        if self.method_period == '1':  # If method period is set to monthly computation
            max_day_in_month = end_of(datetime.date(start_depreciation_date.year, start_depreciation_date.month, 1), 'month').day
            period_end_depreciation_date = min(start_depreciation_date.replace(day=max_day_in_month), period_end_depreciation_date)
        return period_end_depreciation_date

    def _get_delta_days(self, start_date, end_date):
        """Compute how many days there are between 2 dates.

        The computation is different if the asset is in daily_computation or not.
        """
        self.ensure_one()
        if self.prorata_computation_type == 'daily_computation':
            # Compute how many days there are between 2 dates using a daily_computation method
            return (end_date - start_date).days + 1
        else:
            # Compute how many days there are between 2 dates counting 30 days per month
            # Get how many days there are in the start date month
            start_date_days_month = end_of(start_date, 'month').day
            # Get how many days there are in the start date month (e.g: June 20th: (30 * (30 - 20 + 1)) / 30 = 11)
            start_prorata = (start_date_days_month - start_date.day + 1) / start_date_days_month
            # Get how many days there are in the end date month (e.g: You're the August 14th: (14 * 30) / 31 = 13.548387096774194)
            end_prorata = end_date.day / end_of(end_date, 'month').day
            # Compute how many days there are between these 2 dates
            # e.g: 13.548387096774194 + 11 + 360 * (2020 - 2020) + 30 * (8 - 6 - 1) = 24.548387096774194 + 360 * 0 + 30 * 1 = 54.548387096774194 day
            return sum((
                start_prorata * DAYS_PER_MONTH,
                end_prorata * DAYS_PER_MONTH,
                (end_date.year - start_date.year) * DAYS_PER_YEAR,
                (end_date.month - start_date.month - 1) * DAYS_PER_MONTH
            ))

    # -------------------------------------------------------------------------
    # PUBLIC ACTIONS
    # -------------------------------------------------------------------------
    def action_asset_modify(self):
        """ Returns an action opening the asset modification wizard.
        """
        self.ensure_one()
        new_wizard = self.env['asset.modify'].create({
            'asset_id': self.id,
            'modify_action': 'resume' if self.env.context.get('resume_after_pause') else 'dispose',
        })
        return {
            'name': _('Modify Asset'),
            'view_mode': 'form',
            'res_model': 'asset.modify',
            'type': 'ir.actions.act_window',
            'target': 'new',
            'res_id': new_wizard.id,
            'context': self.env.context,
        }

    def action_save_model(self):
        form_ref = {
            'purchase': 'account_asset.view_account_asset_form',
            'sale': 'account_asset.view_account_asset_revenue_form',
            'expense': 'account_asset.view_account_asset_expense_form',
        }.get(self.asset_type)

        return {
            'name': _('Save model'),
            'views': [[self.env.ref(form_ref).id, "form"]],
            'res_model': 'account.asset',
            'type': 'ir.actions.act_window',
            'context': {
                'default_asset_type': self.asset_type,
                'default_state': 'model',
                'default_account_asset_id': self.account_asset_id.id,
                'default_account_depreciation_id': self.account_depreciation_id.id,
                'default_account_depreciation_expense_id': self.account_depreciation_expense_id.id,
                'default_journal_id': self.journal_id.id,
                'default_method': self.method,
                'default_method_number': self.method_number,
                'default_method_period': self.method_period,
                'default_method_progress_factor': self.method_progress_factor,
                'default_prorata_date': self.prorata_date,
                'default_prorata_computation_type': self.prorata_computation_type,
                'default_analytic_distribution': self.analytic_distribution,
                'original_asset': self.id,
            }
        }

    def open_entries(self):
        return {
            'name': _('Journal Entries'),
            'view_mode': 'tree,form',
            'res_model': 'account.move',
            'search_view_id': [self.env.ref('account.view_account_move_filter').id, 'search'],
            'views': [(self.env.ref('account.view_move_tree').id, 'tree'), (False, 'form')],
            'type': 'ir.actions.act_window',
            'domain': [('id', 'in', self.depreciation_move_ids.ids)],
            'context': dict(self._context, create=False),
        }

    def open_related_entries(self):
        return {
            'name': _('Journal Items'),
            'view_mode': 'tree,form',
            'res_model': 'account.move.line',
            'view_id': False,
            'type': 'ir.actions.act_window',
            'domain': [('id', 'in', self.original_move_line_ids.ids)],
        }

    def open_increase(self):
        return {
            'name': _('Gross Increase'),
            'view_mode': 'tree,form',
            'res_model': 'account.asset',
            'view_id': False,
            'type': 'ir.actions.act_window',
            'domain': [('id', 'in', self.children_ids.ids)],
            'views': self.env['account.asset']._get_views(self.asset_type),
        }

    def validate(self):
        fields = [
            'method',
            'method_number',
            'method_period',
            'method_progress_factor',
            'salvage_value',
            'original_move_line_ids',
        ]
        ref_tracked_fields = self.env['account.asset'].fields_get(fields)
        self.write({'state': 'open'})
        for asset in self:
            tracked_fields = ref_tracked_fields.copy()
            if asset.method == 'linear':
                del tracked_fields['method_progress_factor']
            dummy, tracking_value_ids = asset._mail_track(tracked_fields, dict.fromkeys(fields))
            asset_name = {
                'purchase': (_('Asset created'), _('An asset has been created for this move:')),
                'sale': (_('Deferred revenue created'), _('A deferred revenue has been created for this move:')),
                'expense': (_('Deferred expense created'), _('A deferred expense has been created for this move:')),
            }[asset.asset_type]
            msg = asset_name[1] + f' {asset._get_html_link()}'
            asset.message_post(body=asset_name[0], tracking_value_ids=tracking_value_ids)
            for move_id in asset.original_move_line_ids.mapped('move_id'):
                move_id.message_post(body=msg)
            try:
                if not asset.depreciation_move_ids:
                    asset.compute_depreciation_board()
                asset._check_depreciations()
                asset.depreciation_move_ids.filtered(lambda move: move.state != 'posted')._post()
            except psycopg2.errors.CheckViolation:
                raise ValidationError(_("Atleast one asset (%s) couldn't be set as running because it lacks any required information", asset.name))

            if asset.account_asset_id.create_asset == 'no':
                asset._post_non_deductible_tax_value()

    def set_to_close(self, invoice_line_ids, date=None, message=None):
        self.ensure_one()
        disposal_date = date or fields.Date.today()
        if invoice_line_ids and self.children_ids.filtered(lambda a: a.state in ('draft', 'open') or a.value_residual > 0):
            raise UserError(_("You cannot automate the journal entry for an asset that has a running gross increase. Please use 'Dispose' on the increase(s)."))
        full_asset = self + self.children_ids
        move_ids = full_asset._get_disposal_moves([invoice_line_ids] * len(full_asset), disposal_date)
        for asset in full_asset:
            asset.message_post(body=
                _('Asset sold. %s', message if message else "")
                if invoice_line_ids else
                _('Asset disposed. %s', message if message else "")
            )
        full_asset.write({'state': 'close'})
        if move_ids:
            name = _('Disposal Move')
            view_mode = 'form'
            if len(move_ids) > 1:
                name = _('Disposal Moves')
                view_mode = 'tree,form'
            return {
                'name': name,
                'view_mode': view_mode,
                'res_model': 'account.move',
                'type': 'ir.actions.act_window',
                'target': 'current',
                'res_id': move_ids[0],
                'domain': [('id', 'in', move_ids)]
            }

    def set_to_cancelled(self):
        for asset in self:
            posted_moves = asset.depreciation_move_ids.filtered(lambda m: (
                not m.reversal_move_id
                and not m.reversed_entry_id
                and m.state == 'posted'
            ))
            if posted_moves:
                depreciation_change = sum(posted_moves.line_ids.mapped(
                    lambda l: l.debit if l.account_id == asset.account_depreciation_expense_id else 0.0
                ))
                acc_depreciation_change = sum(posted_moves.line_ids.mapped(
                    lambda l: l.credit if l.account_id == asset.account_depreciation_id else 0.0
                ))
                entries = '<br>'.join(posted_moves.sorted('date').mapped(lambda m:
                    f'{m.ref} - {m.date} - '
                    f'{formatLang(self.env, m.depreciation_value, currency_obj=m.currency_id)} - '
                    f'{m.name}'
                ))
                asset._cancel_future_moves(datetime.date.min)
                msg = _(
                        'Asset Cancelled <br>'
                        'The account %(exp_acc)s has been credited by %(exp_delta)s, '
                        'while the account %(dep_acc)s has been debited by %(dep_delta)s. '
                        'This corresponds to %(move_count)s cancelled %(word)s:<br>%(entries)s',
                        exp_acc=asset.account_depreciation_expense_id.display_name,
                        exp_delta=formatLang(self.env, depreciation_change, currency_obj=asset.currency_id),
                        dep_acc=asset.account_depreciation_id.display_name,
                        dep_delta=formatLang(self.env, acc_depreciation_change, currency_obj=asset.currency_id),
                        move_count=len(posted_moves),
                        word=_('entries') if len(posted_moves) > 1 else _('entry'),
                        entries=entries,
                    )
                asset._message_log(body=msg)
            else:
                asset._message_log(body=_('Asset Cancelled'))
            asset.depreciation_move_ids.filtered(lambda m: m.state == 'draft').with_context(force_delete=True).unlink()
            asset.asset_paused_days = 0
            asset.write({'state': 'cancelled'})

    def set_to_draft(self):
        self.write({'state': 'draft'})

    def set_to_running(self):
        if self.depreciation_move_ids and not max(self.depreciation_move_ids, key=lambda m: (m.date, m.id)).asset_remaining_value == 0:
            self.env['asset.modify'].create({'asset_id': self.id, 'name': _('Reset to running')}).modify()
        self.write({'state': 'open'})

    def resume_after_pause(self):
        """ Sets an asset in 'paused' state back to 'open'.
        A Depreciation line is created automatically to remove  from the
        depreciation amount the proportion of time spent
        in pause in the current period.
        """
        self.ensure_one()
        return self.with_context(resume_after_pause=True).action_asset_modify()

    def pause(self, pause_date, message=None):
        """ Sets an 'open' asset in 'paused' state, generating first a depreciation
        line corresponding to the ratio of time spent within the current depreciation
        period before putting the asset in pause. This line and all the previous
        unposted ones are then posted.
        """
        self.ensure_one()
        self._create_move_before_date(pause_date)
        self.write({'state': 'paused'})
        self.message_post(body=_("Asset paused. %s", message if message else ""))

    def open_asset(self, view_mode):
        if len(self) == 1:
            view_mode = ['form']
            asset_type = self.asset_type
        else:
            asset_type = self[0].asset_type
        views = [v for v in self._get_views(asset_type) if v[1] in view_mode]
        ctx = dict(self._context,
                asset_type=asset_type,
                default_asset_type=asset_type)
        ctx.pop('default_move_type', None)
        action = {
            'name': _('Asset'),
            'view_mode': ','.join(view_mode),
            'type': 'ir.actions.act_window',
            'res_id': self.id if 'tree' not in view_mode else False,
            'res_model': 'account.asset',
            'views': views,
            'domain': [('id', 'in', self.ids)],
            'context': ctx
        }
        if asset_type == 'sale':
            action['name'] = _('Deferred Revenue')
        elif asset_type == 'expense':
            action['name'] = _('Deferred Expense')

        return action

    # -------------------------------------------------------------------------
    # HELPER METHODS
    # -------------------------------------------------------------------------
    @api.model
    def _get_views(self, asset_type):
        form_view = self.env.ref('account_asset.view_account_asset_form')
        tree_view = self.env.ref('account_asset.view_account_asset_purchase_tree')
        if asset_type == 'sale':
            form_view = self.env.ref('account_asset.view_account_asset_revenue_form')
            tree_view = self.env.ref('account_asset.view_account_asset_sale_tree')
        elif asset_type == 'expense':
            form_view = self.env.ref('account_asset.view_account_asset_expense_form')
            tree_view = self.env.ref('account_asset.view_account_asset_expense_tree')
        return [[tree_view.id, "tree"], [form_view.id, "form"]]

    def _insert_depreciation_line(self, amount, beginning_depreciation_date, depreciation_date, days_depreciated):
        """ Inserts a new line in the depreciation board, shifting the sequence of
        all the following lines from one unit.
        :param amount:          The depreciation amount of the new line.
        :param label:           The name to give to the new line.
        :param date:            The date to give to the new line.
        """
        self.ensure_one()
        AccountMove = self.env['account.move']

        return AccountMove.create(AccountMove._prepare_move_for_asset_depreciation({
            'amount': amount,
            'asset_id': self,
            'depreciation_beginning_date': beginning_depreciation_date,
            'date': depreciation_date,
            'asset_number_days': days_depreciated,
        }))

    def _post_non_deductible_tax_value(self):
        # If the asset has a non-deductible tax, the value is posted in the chatter to explain why
        # the original value does not match the related purchase(s).
        if self.non_deductible_tax_value:
            currency = self.env.company.currency_id
            msg = _('A non deductible tax value of %s was added to %s\'s initial value of %s',
                    formatLang(self.env, self.non_deductible_tax_value, currency_obj=currency),
                    self.name,
                    formatLang(self.env, self.related_purchase_value, currency_obj=currency))
            self.message_post(body=msg)

    def _create_move_before_date(self, date):
        """Cancel all the moves after the given date and replace them by a new one.

        The new depreciation/move is depreciating the residual value.
        """
        self._cancel_future_moves(date)
        all_lines_before_date = self.depreciation_move_ids.filtered(lambda x: x.date <= date)

        days_already_depreciated = sum(all_lines_before_date.mapped('asset_number_days'))
        days_left = self.asset_lifetime_days - days_already_depreciated
        days_to_add = sum([
            (mv.date - mv.asset_depreciation_beginning_date).days + 1 for mv in
            all_lines_before_date.filtered(lambda x: not x.reversed_entry_id and not x.reversal_move_id)
        ])

        imported_amount = self.already_depreciated_amount_import if not all_lines_before_date else 0
        value_residual = self.value_residual + self.already_depreciated_amount_import if not all_lines_before_date else self.value_residual

        beginning_depreciation_date = self.paused_prorata_date + relativedelta(days=days_to_add)

        days_depreciated, amount = self._compute_board_amount(value_residual, beginning_depreciation_date, date, days_already_depreciated, days_left, value_residual)

        if abs(imported_amount) <= abs(amount):
            amount -= imported_amount
        if not float_is_zero(amount, precision_rounding=self.currency_id.rounding):
            new_line = self._insert_depreciation_line(amount, beginning_depreciation_date, date, days_depreciated)
            new_line._post()

    def _cancel_future_moves(self, date):
        """Cancel all the depreciation entries after the date given as parameter.

        When possible, it will reset those to draft before unlinking them, reverse them otherwise.

        :param date: date after which the moves are deleted/reversed
        """
        to_reverse = self.env['account.move']
        to_cancel = self.env['account.move']
        for asset in self:
            posted_moves = asset.depreciation_move_ids.filtered(lambda m: (
                not m.reversal_move_id
                and not m.reversed_entry_id
                and m.state == 'posted'
                and m.date > date
            ))
            lock_date = asset.company_id._get_user_fiscal_lock_date()
            for move in posted_moves:
                if move.inalterable_hash or move.date <= lock_date:
                    to_reverse += move
                else:
                    to_cancel += move
        to_reverse._reverse_moves(cancel=True)
        to_cancel.button_draft()
        self.depreciation_move_ids.filtered(lambda m: m.state == 'draft').unlink()

    def _get_disposal_moves(self, invoice_lines_list, disposal_date):
        """Create the move for the disposal of an asset.

        :param invoice_lines_list: list of recordset of `account.move.line`
            Each element of the list corresponds to one record of `self`
            These lines are used to generate the disposal move
        :param disposal_date: the date of the disposal
        """
        def get_line(asset, amount, account):
            return (0, 0, {
                'name': asset.name,
                'account_id': account.id,
                'balance': -amount,
                'analytic_distribution': analytic_distribution,
                'currency_id': asset.currency_id.id,
                'amount_currency': -asset.company_id.currency_id._convert(
                    from_amount=amount,
                    to_currency=asset.currency_id,
                    company=asset.company_id,
                    date=disposal_date,
                )
            })

        move_ids = []
        assert len(self) == len(invoice_lines_list)
        for asset, invoice_line_ids in zip(self, invoice_lines_list):
            asset._create_move_before_date(disposal_date)

            analytic_distribution = asset.analytic_distribution

            dict_invoice = {}
            invoice_amount = 0

            initial_amount = asset.original_value
            initial_account = asset.original_move_line_ids.account_id if len(asset.original_move_line_ids.account_id) == 1 else asset.account_asset_id

            all_lines_before_disposal = asset.depreciation_move_ids.filtered(lambda x: x.date <= disposal_date)
            depreciated_amount = asset.currency_id.round(copysign(
                sum(all_lines_before_disposal.mapped('depreciation_value')) + asset.already_depreciated_amount_import,
                -initial_amount,
            ))
            depreciation_account = asset.account_depreciation_id
            for invoice_line in invoice_line_ids:
                dict_invoice[invoice_line.account_id] = copysign(invoice_line.balance, -initial_amount) + dict_invoice.get(invoice_line.account_id, 0)
                invoice_amount += copysign(invoice_line.balance, -initial_amount)
            list_accounts = [(amount, account) for account, amount in dict_invoice.items()]
            difference = -initial_amount - depreciated_amount - invoice_amount
            difference_account = asset.company_id.gain_account_id if difference > 0 else asset.company_id.loss_account_id
            line_datas = [(initial_amount, initial_account), (depreciated_amount, depreciation_account)] + list_accounts + [(difference, difference_account)]
            vals = {
                'asset_id': asset.id,
                'ref': asset.name + ': ' + (_('Disposal') if not invoice_line_ids else _('Sale')),
                'asset_depreciation_beginning_date': disposal_date,
                'date': disposal_date,
                'journal_id': asset.journal_id.id,
                'move_type': 'entry',
                'line_ids': [get_line(asset, amount, account) for amount, account in line_datas if account],
            }
            asset.write({'depreciation_move_ids': [(0, 0, vals)]})
            move_ids += self.env['account.move'].search([('asset_id', '=', asset.id), ('state', '=', 'draft')]).ids

        return move_ids
