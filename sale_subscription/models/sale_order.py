# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

import logging
from dateutil.relativedelta import relativedelta
from markupsafe import escape
from psycopg2.extensions import TransactionRollbackError
from ast import literal_eval
from collections import defaultdict

from odoo import fields, models, _, api, Command, SUPERUSER_ID, modules
from odoo.exceptions import UserError, ValidationError
from odoo.tools.float_utils import float_is_zero
from odoo.osv import expression
from odoo.tools import config, format_amount, split_every
from odoo.tools.date_utils import get_timedelta
from odoo.tools.misc import format_date

_logger = logging.getLogger(__name__)

SUBSCRIPTION_DRAFT_STATE = ['1_draft', '2_renewal']
SUBSCRIPTION_PROGRESS_STATE = ['3_progress', '4_paused']
SUBSCRIPTION_CLOSED_STATE = ['6_churn', '5_renewed']

SUBSCRIPTION_STATES = [
    ('1_draft', 'Quotation'),  # Quotation for a new subscription
    ('2_renewal', 'Renewal Quotation'),  # Renewal Quotation for existing subscription
    ('3_progress', 'In Progress'),  # Active Subscription or confirmed renewal for active subscription
    ('4_paused', 'Paused'),  # Active subscription with paused invoicing
    ('5_renewed', 'Renewed'),  # Active or ended subscription that has been renewed
    ('6_churn', 'Churned'),  # Closed or ended subscription
    ('7_upsell', 'Upsell'),  # Quotation or SO upselling a subscription
]


class SaleOrder(models.Model):
    _name = "sale.order"
    _inherit = ["rating.mixin", "sale.order"]

    def _get_default_starred_user_ids(self):
        return [(4, self.env.uid)]

    ###################
    # Recurring order #
    ###################
    is_subscription = fields.Boolean("Recurring", compute='_compute_is_subscription', store=True, index=True)
    recurrence_id = fields.Many2one('sale.temporal.recurrence', compute='_compute_recurrence_id',
                                     string='Recurrence', ondelete='restrict', readonly=False, store=True)
    subscription_state = fields.Selection(
        string='Stage',
        selection=SUBSCRIPTION_STATES,
        compute='_compute_subscription_state', store=True, tracking=True, group_expand='_group_expand_states',
    )

    subscription_id = fields.Many2one('sale.order', string='Parent Contract', ondelete='restrict', copy=False)
    origin_order_id = fields.Many2one('sale.order', string='First contract', ondelete='restrict', store=True, copy=False,
                                      compute='_compute_origin_order_id')
    subscription_child_ids = fields.One2many('sale.order', 'subscription_id')

    start_date = fields.Date(string='Start Date',
                             compute='_compute_start_date',
                             readonly=False,
                             store=True,
                             tracking=True,
                             help="The start date indicate when the subscription periods begin.")
    last_invoice_date = fields.Date(string='Last invoice date', compute='_compute_last_invoice_date')
    next_invoice_date = fields.Date(
        string='Date of Next Invoice',
        compute='_compute_next_invoice_date',
        store=True, copy=False,
        readonly=False,
        tracking=True,
        help="The next invoice will be created on this date then the period will be extended.")
    end_date = fields.Date(string='End Date', tracking=True,
                           help="If set in advance, the subscription will be set to renew 1 month before the date and will be closed on the date set in this field.")
    first_contract_date = fields.Date(
        compute='_compute_first_contract_date',
        store=True,
        help="The first contract date is the start date of the first contract of the sequence. It is common across a subscription and its renewals.")
    close_reason_id = fields.Many2one("sale.order.close.reason", string="Close Reason", copy=False, tracking=True)

    #############
    # Invoicing #
    #############
    payment_token_id = fields.Many2one('payment.token', 'Payment Token', check_company=True, help='If not set, the automatic payment will fail.',
                                       domain="[('partner_id', 'child_of', commercial_partner_id), ('company_id', '=', company_id)]")
    is_batch = fields.Boolean(default=False, copy=False) # technical, batch of invoice processed at the same time
    is_invoice_cron = fields.Boolean(string='Is a Subscription invoiced in cron', default=False, copy=False)
    payment_exception = fields.Boolean("Contract in exception",
                                       help="Automatic payment with token failed. The payment provider configuration and token should be checked",
                                       copy=False)
    payment_term_id = fields.Many2one(tracking=True)

    ###################
    # KPI / reporting #
    ###################
    kpi_1month_mrr_delta = fields.Float('KPI 1 Month MRR Delta')
    kpi_1month_mrr_percentage = fields.Float('KPI 1 Month MRR Percentage')
    kpi_3months_mrr_delta = fields.Float('KPI 3 months MRR Delta')
    kpi_3months_mrr_percentage = fields.Float('KPI 3 Months MRR Percentage')

    team_user_id = fields.Many2one('res.users', string="Team Leader", related="team_id.user_id", readonly=False)
    country_id = fields.Many2one('res.country', related='partner_id.country_id', store=True,
                                 compute_sudo=True)  # TODO master: move to sale module
    industry_id = fields.Many2one('res.partner.industry', related='partner_id.industry_id',
                                  store=True)  # TODO master: move to module
    commercial_partner_id = fields.Many2one('res.partner', related='partner_id.commercial_partner_id')

    recurring_total = fields.Monetary(compute='_compute_recurring_total', string="Total Recurring", store=True)
    recurring_monthly = fields.Monetary(compute='_compute_recurring_monthly', string="Monthly Recurring",
                                        store=True, tracking=True)
    non_recurring_total = fields.Monetary(compute='_compute_non_recurring_total', string="Total Non Recurring Revenue")
    order_log_ids = fields.One2many('sale.order.log', 'order_id', string='Subscription Logs', readonly=True, copy=False)
    percentage_satisfaction = fields.Integer(
        compute="_compute_percentage_satisfaction",
        string="% Happy", store=True, compute_sudo=True, default=-1,
        help="Calculate the ratio between the number of the best ('great') ratings and the total number of ratings")
    health = fields.Selection([('normal', 'Neutral'), ('done', 'Good'), ('bad', 'Bad')], string="Health", copy=False,
                              default='normal', help="Show the health status")

    ###########
    # UI / UX #
    ###########
    recurring_details = fields.Html(compute='_compute_recurring_details')
    is_renewing = fields.Boolean(compute='_compute_is_renewing')
    is_upselling = fields.Boolean(compute='_compute_is_upselling')
    archived_product_ids = fields.Many2many('product.product', string='Archived Products', compute='_compute_archived')
    archived_product_count = fields.Integer("Archived Product", compute='_compute_archived')
    history_count = fields.Integer(compute='_compute_history_count')
    upsell_count = fields.Integer(compute='_compute_upsell_count')
    renewal_count = fields.Integer(compute="_compute_renewal_count")
    has_recurring_line = fields.Boolean(compute='_compute_has_recurring_line')

    starred_user_ids = fields.Many2many('res.users', 'sale_order_starred_user_rel', 'order_id', 'user_id',
                                        default=lambda s: s._get_default_starred_user_ids(), string='Members')
    starred = fields.Boolean(compute='_compute_starred', inverse='_inverse_starred',
                             string='Show Subscription on dashboard',
                             help="Whether this subscription should be displayed on the dashboard or not")

    _sql_constraints = [
        ('sale_subscription_state_coherence',
         "CHECK(NOT (is_subscription=TRUE AND state IN ('sale', 'done') AND subscription_state='1_draft'))",
         "You cannot set to draft a confirmed subscription. Please create a new quotation"),
        ('check_start_date_lower_next_invoice_date', 'CHECK((next_invoice_date IS NULL OR start_date IS NULL) OR (next_invoice_date >= start_date))',
         'The next invoice date of a sale order should be after its start date.'),
    ]

    @api.constrains('subscription_state', 'subscription_id', 'pricelist_id')
    def _constraint_subscription_upsell_multi_currency(self):
        for so in self:
            if so.subscription_state == '7_upsell' and so.subscription_id.pricelist_id.currency_id != so.pricelist_id.currency_id:
                raise ValidationError(_('You cannot upsell a subscription using a different currency.'))

    @api.constrains('recurrence_id', 'state', 'is_subscription')
    def _constraint_subscription_recurrence(self):
        recurring_product_orders = self.order_line.filtered(lambda l: l.product_id.recurring_invoice).order_id
        for so in self:
            if so.state in ['draft', 'cancel'] or so.subscription_state == '7_upsell':
                continue
            if so in recurring_product_orders and not so.recurrence_id:
                raise UserError(_('You cannot save a sale order with recurring product and no recurrence.'))
            if so.recurrence_id and so.order_line and so not in recurring_product_orders:
                raise UserError(_('You cannot save a sale order with a recurrence and no recurring product.'))

    @api.constrains('subscription_state', 'state')
    def _constraint_canceled_subscription(self):
        incompatible_states = SUBSCRIPTION_PROGRESS_STATE + ['5_renewed']
        for so in self:
            if so.state == 'cancel' and so.subscription_state in incompatible_states:
                raise ValidationError((_('A canceled SO cannot be in progress.'
                                        'You should close %s before canceling it.' % so.name)))

    @api.depends('recurrence_id')
    def _compute_is_subscription(self):
        for order in self:
            # upsells have recurrence but are not considered subscription. The method don't depend on subscription_state
            # to avois recomputing the is_subscription value each time the sub_state is updated. it would trigger
            # other recompute we want to avoid
            if not order.recurrence_id or order.subscription_state == '7_upsell':
                order.is_subscription = False
                continue
            order.is_subscription = True

    @api.depends('is_subscription')
    def _compute_subscription_state(self):
        # The compute method is used to set a default state for quotations
        # Once the order is confirmed, the state is updated by the actions (renew etc)
        for order in self:
            if order.state not in ['draft', 'sent']:
                continue
            elif order.subscription_state in ['2_renewal', '7_upsell']:
                continue
            elif order.is_subscription:
                order.subscription_state = '1_draft'
            else:
                order.subscription_state = False

    def _compute_sale_order_template_id(self):
        if not self.env.context.get('default_is_subscription', False):
            return super(SaleOrder, self)._compute_sale_order_template_id()
        for order in self:
            if order._origin.id or not order.company_id.sale_order_template_id.is_subscription:
                continue
            order.sale_order_template_id = order.company_id.sale_order_template_id

    def _compute_type_name(self):
        other_orders = self.env['sale.order']
        for order in self:
            if not (order.is_subscription and order.state in ('sale', 'done')):
                other_orders |= order
                continue
            order.type_name = _('Subscription')

        super(SaleOrder, other_orders)._compute_type_name()

    @api.depends('rating_percentage_satisfaction')
    def _compute_percentage_satisfaction(self):
        for subscription in self:
            subscription.percentage_satisfaction = int(subscription.rating_percentage_satisfaction)

    @api.depends('starred_user_ids')
    @api.depends_context('uid')
    def _compute_starred(self):
        for subscription in self:
            subscription.starred = self.env.user in subscription.starred_user_ids

    def _inverse_starred(self):
        starred_subscriptions = not_star_subscriptions = self.env['sale.order'].sudo()
        for subscription in self:
            if self.env.user in subscription.starred_user_ids:
                starred_subscriptions |= subscription
            else:
                not_star_subscriptions |= subscription
        not_star_subscriptions.write({'starred_user_ids': [(4, self.env.uid)]})
        starred_subscriptions.write({'starred_user_ids': [(3, self.env.uid)]})

    @api.depends('subscription_state', 'state', 'is_subscription', 'amount_untaxed')
    def _compute_recurring_monthly(self):
        """ Compute the amount monthly recurring revenue. When a subscription has a parent still ongoing.
        Depending on invoice_ids force the recurring monthly to be recomputed regularly, even for the first invoice
        where confirmation is set the next_invoice_date and first invoice do not update it (in automatic mode).
        """
        for order in self:
            if order.is_subscription or order.subscription_state == '7_upsell':
                order.recurring_monthly = sum(order.order_line.mapped('recurring_monthly'))
                continue
            order.recurring_monthly = 0


    @api.depends('subscription_state', 'state', 'is_subscription', 'amount_untaxed')
    def _compute_recurring_total(self):
        """ Compute the amount monthly recurring revenue. When a subscription has a parent still ongoing.
        Depending on invoice_ids force the recurring monthly to be recomputed regularly, even for the first invoice
        where confirmation is set the next_invoice_date and first invoice do not update it (in automatic mode).
        """
        for order in self:
            if order.is_subscription or order.subscription_state == '7_upsell':
                order.recurring_total = sum(order.order_line.filtered(lambda l: l.temporal_type == 'subscription').mapped('price_subtotal'))
                continue
            order.recurring_total = 0


    @api.depends('amount_untaxed', 'recurring_total')
    def _compute_non_recurring_total(self):
        for order in self:
            order.non_recurring_total = order.amount_untaxed - order.recurring_total

    @api.depends('is_subscription', 'recurring_total')
    def _compute_recurring_details(self):
        subscription_orders = self.filtered(lambda sub: sub.is_subscription or sub.subscription_id)
        self.recurring_details = ""
        if subscription_orders.ids:
            for so in subscription_orders:
                lang_code = so.partner_id.lang
                recurring_amount = so.recurring_total
                non_recurring_amount = so.amount_untaxed - recurring_amount
                recurring_formatted_amount = so.currency_id and format_amount(self.env, recurring_amount, so.currency_id, lang_code) or recurring_amount
                non_recurring_formatted_amount = so.currency_id and format_amount(self.env, non_recurring_amount, so.currency_id, lang_code) or non_recurring_amount
                rendering_values = [{
                    'non_recurring': non_recurring_formatted_amount,
                    'recurring': recurring_formatted_amount,
                }]
                so.recurring_details = self.env['ir.qweb']._render('sale_subscription.recurring_details', {'rendering_values': rendering_values})

    def _compute_access_url(self):
        super()._compute_access_url()
        for order in self:
            # Quotations are handled in the quotation menu
            if order.is_subscription and order.subscription_state in SUBSCRIPTION_PROGRESS_STATE + SUBSCRIPTION_CLOSED_STATE:
                order.access_url = '/my/subscription/%s' % order.id

    @api.depends('order_line.product_id', 'order_line.product_id.active')
    def _compute_archived(self):
        # Search which products are archived when reading the subscriptions lines
        archived_product_ids = self.env['product.product'].search(
            [('id', 'in', self.order_line.product_id.ids), ('recurring_invoice', '=', True),
             ('active', '=', False)])
        for order in self:
            products = archived_product_ids.filtered(lambda p: p.id in order.order_line.product_id.ids)
            order.archived_product_ids = [(6, 0, products.ids)]
            order.archived_product_count = len(products)

    def _compute_start_date(self):
        for so in self:
            if not so.is_subscription:
                so.start_date = False
            elif not so.start_date:
                so.start_date = fields.Date.today()

    @api.depends('origin_order_id.start_date', 'origin_order_id')
    def _compute_first_contract_date(self):
        for so in self:
            if so.origin_order_id:
                so.first_contract_date = so.origin_order_id.start_date
            else:
                # First contract of the sequence
                so.first_contract_date = so.start_date

    @api.depends('subscription_child_ids', 'origin_order_id')
    def _get_invoiced(self):
        so_with_origin = self.filtered('origin_order_id')
        res = super(SaleOrder, self - so_with_origin)._get_invoiced()
        if not so_with_origin:
            return res
        # Ensure that we give value to everyone
        so_with_origin.update({
            'invoice_ids': [],
            'invoice_count': 0
        })
        so_by_origin = defaultdict(lambda: self.env['sale.order'])
        for so in so_with_origin:
            # We only search for existing origin
            if so.origin_order_id.id:
                so_by_origin[so.origin_order_id.id] += so

        if not so_by_origin:
            return res

        so_with_origin.flush_recordset(fnames=['origin_order_id'])

        query = """
            SELECT so.origin_order_id, array_agg(DISTINCT am.id)
            
            FROM sale_order so
            JOIN sale_order_line sol ON sol.order_id = so.id
            JOIN sale_order_line_invoice_rel solam ON sol.id = solam.order_line_id
            JOIN account_move_line aml ON aml.id = solam.invoice_line_id
            JOIN account_move am ON am.id = aml.move_id
            
            WHERE so.origin_order_id IN %s
            AND am.company_id IN %s
            AND am.move_type IN ('out_invoice', 'out_refund')
            GROUP BY so.origin_order_id
        """
        self.env.cr.execute(query, [tuple(origin for origin in so_by_origin), tuple(self.env.companies.ids)])
        for origin_id, invoices_ids in self.env.cr.fetchall():
            so_by_origin[origin_id].update({
                'invoice_ids': invoices_ids,
                'invoice_count': len(invoices_ids)
            })
        return res

    @api.depends('is_subscription', 'state', 'start_date', 'subscription_state')
    def _compute_next_invoice_date(self):
        for so in self:
            if not so.is_subscription and so.subscription_state != '7_upsell':
                so.next_invoice_date = False
            elif not so.next_invoice_date and so.state == 'sale':
                # Define a default next invoice date.
                # It is increased by _update_next_invoice_date or when posting a invoice when when necessary
                so.next_invoice_date = so.start_date or fields.Date.today()

    @api.depends('start_date', 'state', 'next_invoice_date')
    def _compute_last_invoice_date(self):
        for order in self:
            last_date = order.next_invoice_date and order.next_invoice_date - get_timedelta(order.recurrence_id.duration, order.recurrence_id.unit)
            if order.recurrence_id and order.state in ['sale', 'done'] and order.start_date and last_date >= order.start_date:
                # we use get_timedelta and not the effective invoice date because
                # we don't want gaps. Invoicing date could be shifted because of technical issues.
                order.last_invoice_date = last_date
            else:
                order.last_invoice_date = False

    @api.depends('subscription_child_ids')
    def _compute_renewal_count(self):
        self.renewal_count = 0
        if not any(self.mapped('subscription_state')):
            return
        result = self.env['sale.order']._read_group([
                ('subscription_state', '=', '2_renewal'),
                ('subscription_id', 'in', self.ids)
            ],
            ['subscription_id'],
            ['__count'],
        )
        counters = {subscription.id: count for subscription, count in result}
        for so in self:
            so.renewal_count = counters.get(so.id, 0)

    @api.depends('subscription_child_ids')
    def _compute_upsell_count(self):
        self.upsell_count = 0
        if not any(self.mapped('subscription_state')):
            return
        result = self.env['sale.order']._read_group([
                ('subscription_state', '=', '7_upsell'),
                ('subscription_id', 'in', self.ids)
            ],
            ['subscription_id'],
            ['__count'],
        )
        counters = {subscription.id: count for subscription, count in result}
        for so in self:
            so.upsell_count = counters.get(so.id, 0)

    @api.depends('origin_order_id')
    def _compute_history_count(self):
        if not any(self.mapped('subscription_state')):
            self.history_count = 0
            return
        origin_ids = self.origin_order_id.ids + self.ids
        result = self.env['sale.order']._read_group([
                ('state', 'not in', ['cancel', 'draft']),
                ('origin_order_id', 'in', origin_ids)
            ],
            ['origin_order_id'],
            ['__count'],
        )
        counters = {origin_order: count + 1 for origin_order, count in result}
        for so in self:
            so.history_count = counters.get(so.origin_order_id.id or so.id, 0)

    @api.depends('is_subscription', 'subscription_state')
    def _compute_origin_order_id(self):
        for order in self:
            if order.subscription_state in ['2_renewal', '7_upsell'] and not order.origin_order_id:
                order.origin_order_id = order.subscription_id

    def _track_subtype(self, init_values):
        self.ensure_one()
        if 'subscription_state' in init_values:
            return self.env.ref('sale_subscription.subtype_state_change')
        return super()._track_subtype(init_values)

    @api.depends('sale_order_template_id')
    def _compute_recurrence_id(self):
        for order in self:
            if order.sale_order_template_id and order.sale_order_template_id.recurrence_id:
                order.recurrence_id = order.sale_order_template_id.recurrence_id
            else:
                order.recurrence_id = False

    def _compute_is_renewing(self):
        self.is_renewing = False
        renew_order_ids = self.env['sale.order'].search([
            ('id', 'in', self.subscription_child_ids.ids),
            ('subscription_state', '=', '2_renewal')
        ]).subscription_id
        renew_order_ids.is_renewing = True

    def _compute_is_upselling(self):
        self.is_upselling = False
        upsell_order_ids = self.env['sale.order'].search([
            ('id', 'in', self.subscription_child_ids.ids),
            ('state', '=', 'draft'),
            ('subscription_state', '=', '7_upsell')
        ]).subscription_id
        upsell_order_ids.is_upselling = True

    @api.depends('order_line')
    def _compute_has_recurring_line(self):
        recurring_product_orders = self.order_line.filtered(lambda l: l.product_id.recurring_invoice).order_id
        recurring_product_orders.has_recurring_line = True
        (self - recurring_product_orders).has_recurring_line = False

    def _create_mrr_log(self, template_value, initial_values):
        self.ensure_one()
        if self.subscription_state not in SUBSCRIPTION_PROGRESS_STATE:
            return
        cur_round = self.company_id.currency_id.rounding
        old_mrr = initial_values.get('recurring_monthly', self.recurring_monthly)
        transfer_mrr = 0
        mrr_difference = self.recurring_monthly - old_mrr
        if self.origin_order_id: # Is a confirmed renewal ( origin_order_id and category in progress)
            existing_transfer_log = self.order_log_ids.filtered(lambda ev: ev.event_type == '3_transfer')
            if not existing_transfer_log:
                # We transfer from the current MRR to the latest known MRR.
                # The parent contrat is now done and its MRR is 0
                parent_progress_logs = self.subscription_id.order_log_ids.filtered(
                    lambda l: l.subscription_state in SUBSCRIPTION_PROGRESS_STATE)
                parent_mrr = parent_progress_logs and parent_progress_logs.sorted('event_date')[
                    -1].recurring_monthly or 0
                transfer_mrr = min([self.recurring_monthly, parent_mrr])
        if not float_is_zero(transfer_mrr, precision_rounding=cur_round):
            transfer_values = template_value.copy()
            transfer_values.update({
                'event_type': '3_transfer',
                'amount_signed': transfer_mrr,
                'recurring_monthly': transfer_mrr,
                'event_date': self.start_date,
            })
            self.env['sale.order.log'].sudo().create(transfer_values)
            mrr_difference = self.recurring_monthly - transfer_mrr

        if not float_is_zero(mrr_difference, precision_rounding=cur_round):
            mrr_value = template_value.copy()
            if self.order_log_ids:
                event_type = self._get_change_event_type(mrr_difference)
            elif self.subscription_state == '5_renewed':
                event_type = '3_transfer'
            else:
                event_type = '0_creation'
            mrr_value.update({'event_type': event_type, 'amount_signed': mrr_difference,
                              'recurring_monthly': self.recurring_monthly})
            self.env['sale.order.log'].sudo().create(mrr_value)

    def _create_stage_log(self, values, initial_values):
        old_state = initial_values['subscription_state']
        new_state = self.subscription_state
        log = None
        cur_round = self.company_id.currency_id.rounding
        mrr_change_value = {}
        confirmed_renewal = self.origin_order_id and self.subscription_state in SUBSCRIPTION_PROGRESS_STATE
        alive_renewed = self.subscription_child_ids.filtered(lambda s: s.subscription_state == '3_progress')
        reopened_order = old_state == '6_churn' and new_state in SUBSCRIPTION_PROGRESS_STATE
        event_date = values['event_date']
        if new_state in SUBSCRIPTION_PROGRESS_STATE + SUBSCRIPTION_CLOSED_STATE and old_state != new_state:
            # subscription started, churned or transferred to renew
            if new_state in SUBSCRIPTION_PROGRESS_STATE:
                if confirmed_renewal:
                    # Transfer for the renewed value and MRR change for the rest
                    new_currency = self.currency_id
                    parent_curency = self.subscription_id.currency_id
                    parent_mrr = parent_curency._convert(self.subscription_id.recurring_monthly, to_currency=new_currency,
                                                         company=self.env.company,
                                                         date=fields.Date.today(), round=False)
                    # Creation of renewal: transfer and MRR change
                    event_type = '3_transfer'
                    amount_signed = parent_mrr
                    recurring_monthly = parent_mrr
                    if not float_is_zero(self.recurring_monthly - parent_mrr, precision_rounding=cur_round):
                        mrr_change_value = values.copy()
                        mrr_change_value.update({
                            'event_type': self._get_change_event_type(self.recurring_monthly - parent_mrr),
                            'recurring_monthly': self.recurring_monthly,
                            'amount_signed': self.recurring_monthly - parent_mrr
                        })
                elif reopened_order:
                    # We reopened a churned contract. We delete the churn log to keep the formal MRR.
                    churn_logs = self.order_log_ids.filtered(lambda log: log.event_type == '2_churn')
                    churn_log = churn_logs and churn_logs[-1]
                    previous_mrr = 0
                    if churn_log:
                        previous_mrr = - churn_log.amount_signed
                        churn_log.unlink()
                    mrr_difference = self.recurring_monthly - previous_mrr
                    if not float_is_zero(mrr_difference, precision_rounding=cur_round):
                        reopen_values = values.copy()
                        reopen_values.update({
                            'event_type': self._get_change_event_type(mrr_difference),
                            'amount_signed': mrr_difference,
                            'recurring_monthly': self.recurring_monthly,
                        })
                        self.env['sale.order.log'].sudo().create(reopen_values)
                    # Return True will prevent to create another MRR LOG
                    return True
                elif new_state == '3_progress':
                    event_type = '0_creation'
                    amount_signed = self.recurring_monthly
                    recurring_monthly = self.recurring_monthly
                else:
                    return
            else:
                amount_signed = - initial_values['recurring_monthly']
                recurring_monthly = 0
                if alive_renewed:
                    event_type = '3_transfer'
                else:
                    event_type = '2_churn'
                    event_date = fields.Date.today()
                    self.order_log_ids.filtered(lambda l: l.event_date > event_date).event_date = event_date
            if event_type == '3_transfer' and \
                    float_is_zero(recurring_monthly, precision_rounding=cur_round) and \
                    float_is_zero(amount_signed, precision_rounding=cur_round):
                # Avoid creating transfer log for free subscription that remains free
                return
            values.update({
                'event_type': event_type,
                'amount_signed': amount_signed,
                'recurring_monthly': recurring_monthly,
                'event_date': event_date,
            })
            # prevent duplicate logs
            previous_log = self.order_log_ids.filtered(
                lambda ev: (ev.event_type, ev.event_date, ev.event_date, ev.amount_signed, ev.recurring_monthly) ==
                           (values['event_type'], values['event_date'], values['amount_signed'], values['recurring_monthly'])
            )
            if not previous_log:
                log = self.env['sale.order.log'].sudo().create(values)
            if mrr_change_value and not self.order_log_ids.filtered(
                lambda ev: ev.event_type == mrr_change_value['event_type'] and ev.event_date == mrr_change_value['event_date']):
                log = self.env['sale.order.log'].sudo().create(mrr_change_value)
        return log

    def _mail_track(self, tracked_fields, initial_values):
        """ For a given record, fields to check (tuple column name, column info)
                and initial values, return a structure that is a tuple containing :
                 - a set of updated column names
                 - a list of ORM (0, 0, values) commands to create 'mail.tracking.value' """
        res = super()._mail_track(tracked_fields, initial_values)
        if not self.is_subscription:
            return res
        updated_fields, dummy = res
        order_start_date = self.start_date or fields.Date.context_today(self)
        values = {'event_date': max(fields.Date.context_today(self), order_start_date),
                  'order_id': self.id,
                  'currency_id': self.currency_id.id,
                  'subscription_state': self.subscription_state,
                  'user_id': self.user_id.id,
                  'team_id': self.team_id.id}
        stage_res = None

        if 'subscription_state' in initial_values:
            stage_res = self._create_stage_log(values, initial_values)
        if ('recurring_monthly' in updated_fields) and not stage_res:
            self._create_mrr_log(values, initial_values)
        return res

    def _get_change_event_type(self, mrr_difference):
        self.ensure_one()
        if self.currency_id.compare_amounts(mrr_difference, 0) <= 0:
            return '15_contraction'
        return '1_expansion'

    def _prepare_invoice(self):
        vals = super()._prepare_invoice()
        if self.sale_order_template_id.journal_id:
            vals['journal_id'] = self.sale_order_template_id.journal_id.id
        return vals

    def _notify_thread(self, message, msg_vals=False, **kwargs):
        if not kwargs.get('model_description') and self.is_subscription:
            kwargs['model_description'] = _("Subscription")
        super()._notify_thread(message, msg_vals=msg_vals, **kwargs)

    ###########
    # CRUD    #
    ###########

    @api.model_create_multi
    def create(self, vals_list):
        orders = super().create(vals_list)
        for order, vals in zip(orders, vals_list):
            if order.is_subscription:
                order.subscription_state = vals.get('subscription_state', '1_draft')
        return orders

    def write(self, vals):
        subscriptions = self.filtered('is_subscription')
        old_partners = {s.id: s.partner_id.id for s in subscriptions}
        res = super().write(vals)
        if vals.get('company_id'):
            # simple SO don't see their lines recomputed, especially when they are in a sent/confirmed state.
            # Subscription should be updated
            subscriptions.order_line._compute_tax_id()
        for subscription in subscriptions:
            if not subscription.subscription_state:
                subscription.subscription_state = vals.get('subscription_state') or '1_draft'
            if subscription.partner_id.id != old_partners[subscription.id]:
                subscription.message_unsubscribe([old_partners[subscription.id]])
                subscription.message_subscribe(subscription.partner_id.ids)
        return res

    @api.ondelete(at_uninstall=False)
    def _unlink_except_draft_or_cancel(self):
        for order in self:
            if order.state not in ['draft', 'sent'] and order.subscription_state and order.subscription_state not in SUBSCRIPTION_DRAFT_STATE + SUBSCRIPTION_CLOSED_STATE:
                raise UserError(_('You can not delete a confirmed subscription. You must first close and cancel it before you can delete it.'))
        return super(SaleOrder, self)._unlink_except_draft_or_cancel()

    def copy_data(self, default=None):
        if default is None:
            default = {}
        if self.subscription_state == '7_upsell':
            default.update({
                "client_order_ref": self.client_order_ref,
                "subscription_id": self.subscription_id.id,
                "origin_order_id": self.origin_order_id.id,
                'subscription_state': '7_upsell'
            })
        elif self.subscription_state and 'subscription_state' not in default:
            default.update({
                'subscription_state': '1_draft'
            })
        return super().copy_data(default)

    ###########
    # Actions #
    ###########

    def action_archived_product(self):
        archived_product_ids = self.with_context(active_test=False).archived_product_ids
        action = self.env["ir.actions.actions"]._for_xml_id("product.product_normal_action_sell")
        action['domain'] = [('id', 'in', archived_product_ids.ids), ('active', '=', False)]
        action['context'] = dict(literal_eval(action.get('context')), search_default_inactive=True)
        return action

    def action_draft(self):
        if any(order.state == 'cancel' and order.is_subscription and order.invoice_ids for order in self):
            raise UserError(
                _('You cannot set to draft a canceled quotation linked to invoiced subscriptions. Please create a new quotation.'))
        return super(SaleOrder, self).action_draft()

    def _action_cancel(self):
        for order in self:
            if order.subscription_state == '7_upsell':
                cancel_message_body = escape(_("The upsell %s has been canceled.")) % order._get_html_link()
                order.subscription_id.message_post(body=cancel_message_body)
            elif order.subscription_state == '2_renewal':
                cancel_message_body = escape(_("The renewal %s has been canceled.")) % order._get_html_link()
                order.subscription_id.message_post(body=cancel_message_body)
            elif order.subscription_state in SUBSCRIPTION_PROGRESS_STATE:
                # should not happen with the constraint but this is a safety for some custos.
                order.subscription_state = '6_churn'
        return super()._action_cancel()

    def _prepare_confirmation_values(self):
        """
        Override of the sale method. sale.order in self should have the same subscription_state in order to process
        them in batch.
        :return: dict of values
        """
        values = super()._prepare_confirmation_values()
        if all(self.mapped('is_subscription')):
            values['subscription_state'] = '3_progress'
        return values

    def action_confirm(self):
        """Update and/or create subscriptions on order confirmation."""
        recurring_order = self.env['sale.order']
        upsell = self.env['sale.order']
        renewal = self.env['sale.order']
        for order in self:
            if order.subscription_id:
                if order.subscription_state == '7_upsell' and order.state in ['draft', 'sent']:
                    upsell |= order
                elif order.subscription_state == '2_renewal':
                    renewal |= order
            if order.is_subscription:
                recurring_order |= order
                if not order.subscription_state:
                    order.subscription_state = '1_draft'

        new_subscriptions = recurring_order - renewal
        # _prepare_confirmation_values will update subscription_state for all confirmed subscription.
        # We call super for two batches to avoid trigger the stage_coherence constraint.
        res_sub = super(SaleOrder, recurring_order).action_confirm()
        res_other = super(SaleOrder, self - recurring_order).action_confirm()
        (new_subscriptions | renewal)._confirm_subscription()
        renewal._confirm_renewal()
        upsell._confirm_upsell()

        return res_sub and res_other

    def _confirm_subscription(self):
        today = fields.Date.today()
        for sub in self:
            sub._portal_ensure_token()
            # We set the start date and invoice date at the date of confirmation
            if not sub.start_date:
                sub.start_date = today
            sub._set_subscription_end_date_from_template()
            sub.order_line._reset_subscription_qty_to_invoice()
            sub._save_token_from_payment()

    def _set_subscription_end_date_from_template(self):
        self.ensure_one()
        end_date = self.end_date
        if self.sale_order_template_id.recurring_rule_boundary == 'limited' and not end_date:
            end_date = self.start_date + get_timedelta(
                self.sale_order_template_id.recurring_rule_count,
                self.sale_order_template_id.recurring_rule_type
            ) - relativedelta(days=1)
        self.write({'end_date': end_date})

    def _confirm_upsell(self):
        """
        When confirming an upsell order, the recurring product lines must be updated
        """
        for so in self:
            # We check the subscription direct invoice and not the one related to the whole SO
            if so.subscription_id.start_date == so.subscription_id.next_invoice_date:
                raise ValidationError(_("You can not upsell or upsell a subscription that has not been invoiced yet. "
                                        "Please, update directly the %s contract or invoice it first.", so.subscription_id.name))
        existing_line_ids = self.subscription_id.order_line
        dummy, update_values = self.update_existing_subscriptions()
        updated_line_ids = self.env['sale.order.line'].browse({val[1] for val in update_values})
        new_lines_ids = self.subscription_id.order_line - existing_line_ids
        # Example: with a new yearly line starting in june when the expected next invoice date is december,
        # discount is 50% and the default next_invoice_date will be in june too.
        # We need to get the default next_invoice_date that was saved on the upsell because the compute has no way
        # to differentiate new line created by an upsell and new line created by the user.
        for upsell in self:
            upsell.subscription_id.message_post(body=escape(_("The upsell %s has been confirmed.")) % upsell._get_html_link())
        for line in (updated_line_ids | new_lines_ids).with_context(skip_line_status_compute=True):
            # The upsell invoice will take care of the invoicing for this period
            line.qty_to_invoice = 0
            line.qty_invoiced = line.product_uom_qty
            # We force the invoice status because the current period will be invoiced by the upsell flow
            # when the upsell so is invoiced
            line.invoice_status = 'no'

    def _confirm_renewal(self):
        """
        When confirming an renew order, the recurring product lines must be updated
        """
        today = fields.Date.today()
        for renew in self:
            # When parent subscription reaches his end_date, it will be closed with a close_reason_renew so it won't be considered as a simple churn.
            parent = renew.subscription_id
            if renew.start_date < parent.next_invoice_date:
                raise ValidationError(_("You cannot validate a renewal quotation starting before the next invoice date "
                                        "of the parent contract. Please update the start date after the %s.", format_date(self.env, parent.next_invoice_date)))
            elif parent.start_date == parent.next_invoice_date:
                raise ValidationError(_("You can not upsell or renew a subscription that has not been invoiced yet. "
                                        "Please, update directly the %s contract or invoice it first.", parent.name))
            other_renew_so_ids = parent.subscription_child_ids.filtered(lambda so: so.subscription_state == '2_renewal') - renew
            if other_renew_so_ids:
                other_renew_so_ids._action_cancel()

            renew_msg_body = escape(_("This subscription is renewed in %s with a change of plan.")) % renew._get_html_link()
            parent.message_post(body=renew_msg_body)
            parent.end_date = parent.next_invoice_date
            parent.set_close()
            # TODO fix : This can create hole that are not taken into account by progress_sub upselling
            start_date = renew.start_date or parent.next_invoice_date
            renew.write({'date_order': today, 'start_date': start_date})
            renew._save_token_from_payment()

    def _save_token_from_payment(self):
        self.ensure_one()
        last_token = self.transaction_ids._get_last().token_id.id
        if last_token:
            self.payment_token_id = last_token

    def _group_expand_states(self, states, domain, order):
        return ['3_progress', '4_paused']

    @api.model
    def read_group(self, domain, fields, groupby, offset=0, limit=None, orderby=False, lazy=True):
        res = super().read_group(domain, fields, groupby, offset=offset, limit=limit, orderby=orderby, lazy=lazy)
        if groupby and groupby[0] == 'subscription_state':
            # Sort because group expand force progress and paused as first
            res = sorted(res, key=lambda r: r.get('subscription_state') or '')
        return res

    @api.model
    def _get_associated_so_action(self):
        return {
            "type": "ir.actions.act_window",
            "res_model": "sale.order",
            "views": [[self.env.ref('sale_subscription.sale_subscription_view_tree').id, "tree"],
                      [self.env.ref('sale_subscription.sale_subscription_primary_form_view').id, "form"],
                      [False, "kanban"], [False, "calendar"], [False, "pivot"], [False, "graph"]],
        }

    def open_subscription_history(self):
        self.ensure_one()
        action = {
            "type": "ir.actions.act_window",
            "res_model": "sale.order",
            "views": [[self.env.ref('sale_subscription.sale_subscription_quotation_tree_view').id, "tree"],
                      [self.env.ref('sale_subscription.sale_subscription_primary_form_view').id, "form"]]
        }
        origin_order_id = self.origin_order_id.id or self.id
        action['name'] = _("History")
        action['domain'] = [('state', 'not in', ['cancel', 'draft']), '|', ('id', '=', origin_order_id), ('origin_order_id', '=', origin_order_id)]
        action['context'] = {
            **action.get('context', {}),
            'create': False,
        }
        return action

    def open_subscription_renewal(self):
        self.ensure_one()
        action = self._get_associated_so_action()
        action['name'] = _("Renewal Quotations")
        renewal = self.subscription_child_ids.filtered(lambda so: so.subscription_state == '2_renewal')
        if len(renewal) == 1:
            action['res_id'] = renewal.id
            action['views'] = [(self.env.ref('sale_subscription.sale_subscription_primary_form_view').id, 'form')]
        else:
            action['domain'] = [('subscription_id', '=', self.id), ('subscription_state', '=', '2_renewal')]
            action['views'] = [(self.env.ref('sale.view_quotation_tree').id, 'tree'),
                               (self.env.ref('sale_subscription.sale_subscription_primary_form_view').id, 'form')]

        action['context'] = {
            **action.get('context', {}),
            'create': False,
        }
        return action

    def open_subscription_upsell(self):
        self.ensure_one()
        action = self._get_associated_so_action()
        action['name'] = _("Upsell Quotations")
        upsell = self.subscription_child_ids.filtered(lambda so: so.subscription_state == '7_upsell')
        if len(upsell) == 1:
            action['res_id'] = upsell.id
            action['views'] = [(self.env.ref('sale_subscription.sale_subscription_primary_form_view').id, 'form')]
        else:
            action['domain'] = [('subscription_id', '=', self.id), ('subscription_state', '=', '7_upsell'), ('state', 'in', ['draft', 'sent'])]
            action['views'] = [(self.env.ref('sale.view_quotation_tree').id, 'tree'),
                               (self.env.ref('sale_subscription.sale_subscription_primary_form_view').id, 'form')]
        action['context'] = {
            **action.get('context', {}),
            'create': False,
        }
        return action

    def action_open_subscriptions(self):
        """ Display the linked subscription and adapt the view to the number of records to display."""
        self.ensure_one()
        subscriptions = self.order_line.mapped('subscription_id')
        action = self.env["ir.actions.actions"]._for_xml_id("sale_subscription.sale_subscription_action")
        if len(subscriptions) > 1:
            action['domain'] = [('id', 'in', subscriptions.ids)]
        elif len(subscriptions) == 1:
            form_view = [(self.env.ref('sale_subscription.sale_subscription_view_form').id, 'form')]
            if 'views' in action:
                action['views'] = form_view + [(state, view) for state, view in action['views'] if view != 'form']
            else:
                action['views'] = form_view
            action['res_id'] = subscriptions.ids[0]
        else:
            action = {'type': 'ir.actions.act_window_close'}
        action['context'] = dict(self._context, create=False)
        return action

    def action_sale_order_log(self):
        action = self.env["ir.actions.actions"]._for_xml_id("sale_subscription.sale_order_log_analysis_action")
        origin_order_ids = self.origin_order_id.ids + self.ids
        genealogy_orders_ids = self.search(['|', ('id', 'in', origin_order_ids), ('origin_order_id', 'in', origin_order_ids)])
        action.update({
            'name': _('MRR changes'),
            'domain': [('order_id', 'in', genealogy_orders_ids.ids)],
            'context': {'search_default_group_by_event_date': 1},
        })
        return action

    def _prepare_renew_upsell_order(self, subscription_state, message_body):
        self.ensure_one()
        values = self._prepare_upsell_renew_order_values(subscription_state)
        order = self.env['sale.order'].create(values)
        self.subscription_child_ids = [Command.link(order.id)]
        order.message_post(body=message_body)
        if subscription_state == '7_upsell':
            parent_message_body = escape(_("An upsell quotation %s has been created"))
        else:
            parent_message_body = escape(_("A renewal quotation %s has been created"))
        self.message_post(body=parent_message_body % order._get_html_link())
        order.order_line._compute_tax_id()
        action = self._get_associated_so_action()
        action['name'] = _('Upsell') if subscription_state == '7_upsell' else _('Renew')
        action['views'] = [(self.env.ref('sale_subscription.sale_subscription_primary_form_view').id, 'form')]
        action['res_id'] = order.id
        return action

    def _get_order_digest(self, origin='', template='sale_subscription.sale_order_digest', lang=None):
        self.ensure_one()
        values = {'origin': origin,
                  'record_url': self._get_html_link(),
                  'start_date': self.start_date,
                  'next_invoice_date': self.next_invoice_date,
                  'recurring_monthly': self.recurring_monthly,
                  'untaxed_amount': self.amount_untaxed,
                  'quotation_template': self.sale_order_template_id.name}
        return self.env['ir.qweb'].with_context(lang=lang)._render(template, values)

    def subscription_open_related(self):
        self.ensure_one()
        action = self._get_associated_so_action()
        action['views'] = [(self.env.ref('sale_subscription.sale_subscription_primary_form_view').id, 'form')]
        if self.subscription_state == '5_renewed':
            action['res_id'] = self.subscription_child_ids.filtered(lambda c: c.subscription_state not in ['7_upsell', '2_renewal'])[0].id
        elif self.subscription_state in ['2_renewal', '7_upsell']:
            action['res_id'] = self.subscription_id.id
        else:
            return
        return action

    def prepare_renewal_order(self):
        self.ensure_one()
        lang = self.partner_id.lang or self.env.user.lang
        renew_msg_body = self._get_order_digest(origin='renewal', lang=lang)
        action = self._prepare_renew_upsell_order('2_renewal', renew_msg_body)

        return action

    def prepare_upsell_order(self):
        self.ensure_one()
        lang = self.partner_id.lang or self.env.user.lang
        upsell_msg_body = self._get_order_digest(origin='upsell', lang=lang)
        action = self._prepare_renew_upsell_order('7_upsell', upsell_msg_body)
        return action

    def reopen_order(self):
        if set(self.mapped('subscription_state')) != {'6_churn'}:
            raise UserError(_("You cannot reopen a subscription that isn't closed."))
        self.close_reason_id = False
        self.subscription_state = '3_progress'

    def pause_subscription(self):
        self.filtered(lambda so: so.subscription_state == '3_progress').write({'subscription_state': '4_paused'})

    def resume_subscription(self):
        self.filtered(lambda so: so.subscription_state == '4_paused').write({'subscription_state': '3_progress'})

    def create_alternative(self):
        self.ensure_one()
        alternative_so = self.copy({
            'origin_order_id': self.origin_order_id.id,
            'subscription_id': self.subscription_id.id,
            'subscription_state': '2_renewal',
        })
        action = alternative_so._get_associated_so_action()
        action['views'] = [(self.env.ref('sale_subscription.sale_subscription_primary_form_view').id, 'form')]
        action['res_id'] = alternative_so.id
        return action

    ####################
    # Business Methods #
    ####################

    def update_existing_subscriptions(self):
        """
        Update subscriptions already linked to the order by updating or creating lines.
        This method is only called on upsell confirmation
        :rtype: list(integer)
        :return: ids of modified subscriptions
        """
        create_values, update_values = [], []
        for order in self:
            # We don't propagate the line description from the upsell order to the subscription
            create_values, update_values = order.order_line.filtered(lambda sol: not sol.display_type)._subscription_update_line_data(order.subscription_id)
            order.subscription_id.with_context(skip_next_invoice_update=True).write({'order_line': create_values + update_values})
        return create_values, update_values

    def _set_closed_state(self):
        renewed_orders = self.env['sale.order']
        closed_orders = self.env['sale.order']
        for order in self:
            if order.subscription_child_ids.filtered(lambda s: s.subscription_state in SUBSCRIPTION_PROGRESS_STATE):
                renewed_orders += order
            else:
                closed_orders += order
        closed_orders.write({'subscription_state': '6_churn'})
        renewed_orders.write({'subscription_state': '5_renewed', 'state': 'done'})

    def set_close(self, close_reason_id=None):
        self._set_closed_state()
        today = fields.Date.context_today(self)
        values = {'end_date': today}
        if close_reason_id:
            values['close_reason_id'] = close_reason_id
            self.update(values)
        else:
            renew_close_reason_id = self.env.ref('sale_subscription.close_reason_renew').id
            end_of_contract_reason_id = self.env.ref('sale_subscription.close_reason_end_of_contract').id
            close_reason_unknown_id = self.env.ref('sale_subscription.close_reason_unknown').id
            for sub in self:
                if sub.subscription_state == "5_renewed":
                    close_reason_id = renew_close_reason_id
                elif sub.end_date and sub.end_date <= today:
                    close_reason_id = end_of_contract_reason_id
                else:
                    close_reason_id = close_reason_unknown_id
                sub.write({'close_reason_id': close_reason_id})
        return True

    def set_open(self):
        self.filtered('is_subscription').write({'subscription_state': '3_progress'})

    @api.model
    def _cron_update_kpi(self):
        subscriptions = self.search([('subscription_state', '=', '3_progress'), ('is_subscription', '=', True)])
        subscriptions._compute_kpi()

    def _prepare_upsell_renew_order_values(self, subscription_state):
        """
        Create a new draft order with the same lines as the parent subscription. All recurring lines are linked to their parent lines
        :return: dict of new sale order values
        """
        self.ensure_one()
        subscription = self.with_company(self.company_id)
        order_lines = self.order_line._get_renew_upsell_values(subscription_state, period_end=self.next_invoice_date)
        is_subscription = subscription_state == '2_renewal'
        option_lines_data = [fields.Command.clear()]
        option_lines_data += [
            fields.Command.create(
                option._prepare_option_line_values()
            )
            for option in self.sale_order_template_id.sale_order_template_option_ids
        ]
        if subscription_state == '7_upsell':
            start_date = fields.Date.today()
            next_invoice_date = self.next_invoice_date
            internal_note = ""
        else:
            # renewal
            start_date = self.next_invoice_date
            next_invoice_date = self.next_invoice_date # the next invoice date is the start_date for new contract
            internal_note = subscription.internal_note
        return {
            'is_subscription': is_subscription,
            'subscription_id': subscription.id,
            'pricelist_id': subscription.pricelist_id.id,
            'partner_id': subscription.partner_id.id,
            'order_line': order_lines,
            'analytic_account_id': subscription.analytic_account_id.id,
            'subscription_state': subscription_state,
            'origin': subscription.client_order_ref,
            'client_order_ref': subscription.client_order_ref,
            'origin_order_id': subscription.origin_order_id.id,
            'note': subscription.note,
            'user_id': subscription.user_id.id,
            'payment_term_id': subscription.payment_term_id.id,
            'company_id': subscription.company_id.id,
            'sale_order_template_id': self.sale_order_template_id.id,
            'sale_order_option_ids': option_lines_data,
            'payment_token_id': False,
            'start_date': start_date,
            'next_invoice_date': next_invoice_date,
            'recurrence_id': subscription.recurrence_id.id,
            'internal_note': internal_note,
        }

    def _compute_kpi(self):
        for subscription in self:
            delta_1month = subscription._get_subscription_delta(fields.Date.today() - relativedelta(months=1))
            delta_3months = subscription._get_subscription_delta(fields.Date.today() - relativedelta(months=3))
            subscription.write({
                'kpi_1month_mrr_delta': delta_1month['delta'],
                'kpi_1month_mrr_percentage': delta_1month['percentage'],
                'kpi_3months_mrr_delta': delta_3months['delta'],
                'kpi_3months_mrr_percentage': delta_3months['percentage'],
            })

    def _get_portal_return_action(self):
        """ Return the action used to display orders when returning from customer portal. """
        if self.is_subscription:
            return self.env.ref('sale_subscription.sale_subscription_action')
        else:
            return super(SaleOrder, self)._get_portal_return_action()

    ####################
    # Invoicing Methods #
    ####################

    @api.model
    def _cron_recurring_create_invoice(self):
        return self._create_recurring_invoice()

    def _get_invoiceable_lines(self, final=False):
        date_from = fields.Date.today()
        res = super()._get_invoiceable_lines(final=final)
        res = res.filtered(lambda l: l.temporal_type != 'subscription')
        automatic_invoice = self.env.context.get('recurring_automatic')

        invoiceable_line_ids = []
        downpayment_line_ids = []
        pending_section = None

        for line in self.order_line:
            if line.display_type == 'line_section':
                # Only add section if one of its lines is invoiceable
                pending_section = line
                continue

            if automatic_invoice:
                # We don't invoice line before their SO's next_invoice_date
                line_condition = line.order_id.next_invoice_date and line.order_id.next_invoice_date <= date_from and line.order_id.start_date and line.order_id.start_date <= date_from
            else:
                # We don't invoice line past their SO's end_date
                line_condition = not line.order_id.end_date or line.order_id.next_invoice_date < line.order_id.end_date

            line_to_invoice = False
            if line in res:
                # Line was already marked as to be invoice
                line_to_invoice = True
            elif line.display_type or line.temporal_type != 'subscription':
                # Avoid invoicing section/notes or lines starting in the future or not starting at all
                line_to_invoice = False
            elif line_condition and line.product_id.invoice_policy == 'order' and line.order_id.state == 'sale':
                # Invoice due lines
                line_to_invoice = True
            elif line_condition and line.product_id.invoice_policy == 'delivery' and (not float_is_zero(line.qty_delivered, precision_rounding=line.product_id.uom_id.rounding)):
                line_to_invoice = True

            if line_to_invoice:
                if line.is_downpayment:
                    # downpayment line must be kept at the end in its dedicated section
                    downpayment_line_ids.append(line.id)
                    continue
                if pending_section:
                    invoiceable_line_ids.append(pending_section.id)
                    pending_section = False
                invoiceable_line_ids.append(line.id)

        return self.env["sale.order.line"].browse(invoiceable_line_ids + downpayment_line_ids)

    def _subscription_post_success_free_renewal(self):
        """ Action done after the successful payment has been performed """
        self.ensure_one()
        msg_body = _(
            'Automatic renewal succeeded. Free subscription. Next Invoice: %(inv)s. No email sent.',
            inv=self.next_invoice_date
        )
        self.message_post(body=msg_body)

    def _subscription_post_success_payment(self, invoice, transaction):
        """ Action done after the successful payment has been performed """
        self.ensure_one()
        invoice.write({'payment_reference': transaction.reference, 'ref': transaction.reference})
        msg_body = escape(_(
            'Automatic payment succeeded. Payment reference: %(ref)s. Amount: %(amount)s. Contract set to: In Progress, Next Invoice: %(inv)s. Email sent to customer.')) % {
            'ref': transaction._get_html_link(title=transaction.reference),
            'amount': transaction.amount,
            'inv': self.next_invoice_date,
        }
        self.message_post(body=msg_body)
        if invoice.state != 'posted':
            invoice.with_context(ocr_trigger_delta=15)._post()
        self.send_success_mail(transaction, invoice)

    def _get_subscription_mail_payment_context(self, mail_ctx=None):
        self.ensure_one()
        if not mail_ctx:
            mail_ctx = {}
        return {**self._context, **mail_ctx, **{'total_amount': self.amount_total, 'currency_name': self.currency_id.name, 'responsible_email': self.user_id.email}}

    def _update_next_invoice_date(self):
        """ Update the next_invoice_date according to the periodicity of the order.
            At quotation confirmation, last_invoice_date is false, next_invoice is start date and start_date is today
            by default. The next_invoice_date should be bumped up each time an invoice is created except for the
            first period.

            The next invoice date should be updated according to these rules :
            -> If the trigger is manuel : We should always increment the next_invoice_date
            -> If the trigger is automatic & date_next_invoice < today :
                    -> If there is a payment_token : We should increment at the payment reconciliation
                    -> If there is no token : We always increment the next_invoice_date even if there is nothing to invoice
            """
        for order in self:
            if not order.is_subscription:
                continue
            last_invoice_date = order.next_invoice_date or order.start_date
            if last_invoice_date:
                order.next_invoice_date = last_invoice_date + get_timedelta(order.recurrence_id.duration, order.recurrence_id.unit)

    def _update_subscription_payment_failure_values(self,):
        # allow to override the subscription values in case of payment failure
        return {}

    def _handle_subscription_payment_failure(self, invoice, transaction, email_context):
        self.ensure_one()
        current_date = fields.Date.today()
        reminder_mail_template = self.env.ref('sale_subscription.email_payment_reminder', raise_if_not_found=False)
        close_mail_template = self.env.ref('sale_subscription.email_payment_close', raise_if_not_found=False)
        invoice.unlink()
        auto_close_days = self.sale_order_template_id.auto_close_limit or 15
        date_close = self.next_invoice_date + relativedelta(days=auto_close_days)
        close_contract = current_date >= date_close
        _logger.info('Failed to create recurring invoice for contract %s', self.client_order_ref or self.name)
        if close_contract:
            close_mail_template.with_context(email_context).send_mail(self.id)
            _logger.debug("Sending Contract Closure Mail to %s for contract %s and closing contract",
                          self.partner_id.email, self.id)
            msg_body = _("Automatic payment failed after multiple attempts. Contract closed automatically.")
            self.message_post(body=msg_body)
            subscription_values = {'payment_exception': False}
            # close the contract as needed
            self.set_close(close_reason_id=self.env.ref('sale_subscription.close_reason_auto_close_limit_reached').id)
        else:
            msg_body = _('Automatic payment failed. No email sent this time. Error: %s', transaction and transaction.state_message or _('No valid Payment Method'))

            if (fields.Date.today() - self.next_invoice_date).days in [2, 7, 14]:
                email_context.update({'date_close': date_close})
                reminder_mail_template.with_context(email_context).send_mail(self.id)
                _logger.debug("Sending Payment Failure Mail to %s for contract %s and setting contract to pending", self.partner_id.email, self.id)
                msg_body = _('Automatic payment failed. Email sent to customer. Error: %s', transaction and transaction.state_message or _('No Payment Method'))
            self.message_post(body=msg_body)
            subscription_values = {'payment_exception': False, 'is_batch': True}
        subscription_values.update(self._update_subscription_payment_failure_values())
        self.write(subscription_values)

    def _invoice_is_considered_free(self, invoiceable_lines):
        """
        In some case, we want to skip the invoice generation for subscription.
        By default, we only consider it free if the amount is 0, but we could use other criterion
        :return: bool: true if the contract is free
        :return: bool: true if the contract should be in exception
        """
        self.ensure_one()
        amount_total = sum(invoiceable_lines.mapped('price_total'))
        non_recurring_line = invoiceable_lines.filtered(lambda l: l.temporal_type != 'subscription')
        is_free, is_exception = False, False
        if self.currency_id.compare_amounts(self.recurring_monthly, 0) < 0 and non_recurring_line:
            # We have a mix of recurring lines whose sum is negative and non recurring lines to invoice
            # We don't know what to do
            is_free = True
            is_exception = True
        elif self.currency_id.compare_amounts(amount_total, 0) < 1:
            # We can't create an invoice, it will be impossible to validate
            is_free = True
        elif self.currency_id.compare_amounts(self.recurring_monthly, 0) < 1 and not non_recurring_line:
            # We have a recurring null/negative amount. It is not desired even if we have a non-recurring positive amount
            is_free = True
        return is_free, is_exception

    def _recurring_invoice_domain(self, extra_domain=None):
        if not extra_domain:
            extra_domain = []
        current_date = fields.Date.today()
        search_domain = [('is_batch', '=', False),
                         ('is_invoice_cron', '=', False),
                         ('is_subscription', '=', True),
                         ('subscription_state', '=', '3_progress'),
                         ('payment_exception', '=', False),
                         '|', ('next_invoice_date', '<=', current_date), ('end_date', '<=', current_date)]
        if extra_domain:
            search_domain = expression.AND([search_domain, extra_domain])
        return search_domain

    def _subscription_commit_cursor(self, auto_commit):
        if auto_commit:
            self.env.cr.commit()

    def _subscription_rollback_cursor(self, auto_commit):
        if auto_commit:
            self.env.cr.rollback()

    # The following function is used so that it can be overwritten in test files
    def _subscription_launch_cron_parallel(self, batch_size):
        self.env.ref('sale_subscription.account_analytic_cron_for_invoice')._trigger()

    def _create_recurring_invoice(self, batch_size=30):
        today = fields.Date.today()
        auto_commit = not bool(config['test_enable'] or config['test_file'])

        all_subscriptions = self or self.search(self._recurring_invoice_domain(), limit=batch_size + 1)
        need_cron_trigger = not self and len(all_subscriptions) > batch_size
        if need_cron_trigger:
            all_subscriptions = all_subscriptions[:batch_size]
        if not all_subscriptions:
            return self.env['account.move']

        # We mark current batch as having been seen by the cron
        all_subscriptions.write({'is_invoice_cron': True})

        # Don't spam sale with assigned emails.
        all_subscriptions = all_subscriptions.with_context(mail_auto_subscribe_no_notify=True)

        # Close ending subscriptions
        auto_close_subscription = all_subscriptions.filtered_domain([('end_date', '!=', False)])
        closed_contract = auto_close_subscription._subscription_auto_close()
        all_subscriptions -= closed_contract

        if not all_subscriptions:
            return self.env['account.move']

        lines_to_reset_qty = self.env['sale.order.line']
        account_moves = self.env['account.move']
        all_invoiceable_lines = all_subscriptions.with_context(recurring_automatic=True)._get_invoiceable_lines()
        # Set quantity to invoice before the invoice creation. If something goes wrong, the line will appear as "to invoice"
        # It prevent to use the _compute method and compare the today date and the next_invoice_date in the compute which would be bad for perfs
        all_invoiceable_lines._reset_subscription_qty_to_invoice()
        self._subscription_commit_cursor(auto_commit)
        for subscription in all_subscriptions:
            subscription = subscription[0]  # Trick to not prefetch other subscriptions, as the cache is currently invalidated at each iteration

            # We check that the subscription should not be processed or that it has not already been set to "in exception" by previous cron failure
            # We only invoice contract in sale state. Locked contracts are invoiced in advance. They are frozen.

            if subscription.subscription_state != '3_progress' or subscription.payment_exception:
                continue
            try:
                self._subscription_commit_cursor(auto_commit)  # To avoid a rollback in case something is wrong, we create the invoices one by one
                draft_invoices = subscription.invoice_ids.filtered(lambda am: am.state == 'draft')
                if subscription.payment_token_id and draft_invoices:
                    draft_invoices.button_cancel()
                elif draft_invoices:
                    # Skip subscription if no payment_token, and it has a draft invoice
                    continue
                invoiceable_lines = all_invoiceable_lines.filtered(lambda l: l.order_id.id == subscription.id)
                invoice_is_free, is_exception = subscription._invoice_is_considered_free(invoiceable_lines)
                if not invoiceable_lines or invoice_is_free:
                    if is_exception:
                        # Mix between recurring and non-recurring lines. We let the contract in exception, it should be
                        # handled manually
                        msg_body = _(
                            "Mix of negative recurring lines and non-recurring line. The contract should be fixed manually",
                            inv=self.next_invoice_date
                        )
                        subscription.message_post(body=msg_body)
                        subscription.payment_exception = True
                    # We still update the next_invoice_date if it is due
                    elif subscription.next_invoice_date and subscription.next_invoice_date <= today:
                        subscription._update_next_invoice_date()
                        if invoice_is_free:
                            for line in invoiceable_lines:
                                line.qty_invoiced = line.product_uom_qty
                            subscription._subscription_post_success_free_renewal()
                    continue

                try:
                    invoice = subscription.with_context(recurring_automatic=True)._create_invoices(final=True)
                    lines_to_reset_qty |= invoiceable_lines
                except Exception as e:
                    # We only raise the error in test, if the transaction is broken we should raise the exception
                    if not auto_commit and isinstance(e, TransactionRollbackError):
                        raise
                    # we suppose that the payment is run only once a day
                    self._subscription_rollback_cursor(auto_commit)
                    email_context = subscription._get_subscription_mail_payment_context()
                    error_message = _("Error during renewal of contract %s (Payment not recorded)", subscription.name)
                    _logger.exception(error_message)
                    mail = self.env['mail.mail'].sudo().create({'body_html': error_message, 'subject': error_message, 'email_to': email_context['responsible_email'], 'auto_delete': True})
                    mail.send()
                    continue
                self._subscription_commit_cursor(auto_commit)
                # Handle automatic payment or invoice posting
                existing_invoices = subscription._handle_automatic_invoices(invoice, auto_commit)
                account_moves |= existing_invoices
                subscription.with_context(mail_notrack=True).write({'payment_exception': False})
            except Exception:
                _logger.exception("Error during renewal of contract %s", subscription.client_order_ref or subscription.name)
                self._subscription_rollback_cursor(auto_commit)
        self._subscription_commit_cursor(auto_commit)
        lines_to_reset_qty._reset_subscription_quantity_post_invoice()
        all_subscriptions._process_invoices_to_send(account_moves)
        # There is still some subscriptions to process. Then, make sure the CRON will be triggered again asap.
        if need_cron_trigger:
            self._subscription_launch_cron_parallel(batch_size)

        if not need_cron_trigger:
            cron_subs = self.search([('is_invoice_cron', '=', True)])
            cron_subs.write({'is_invoice_cron': False})
            failing_subscriptions = self.search([('is_batch', '=', True)])
            failing_subscriptions.write({'is_batch': False})

        return account_moves

    def _create_invoices(self, grouped=False, final=False, date=None):
        """ Override to increment periods when needed """
        order_already_invoiced = self.env['sale.order']
        for order in self:
            if not order.is_subscription:
                continue
            if order.order_line.invoice_lines.move_id.filtered(lambda r: r.move_type in ('out_invoice', 'out_refund') and r.state == 'draft'):
                order_already_invoiced |= order
        if order_already_invoiced:
            order_error = ", ".join(order_already_invoiced.mapped('name'))
            raise ValidationError(_("The following recurring orders have draft invoices. Please Confirm them or cancel them "
                                    "before creating new invoices. %s.", order_error))
        invoices = super()._create_invoices(grouped=grouped, final=final, date=date)
        return invoices

    def _subscription_auto_close(self):
        """ Handle contracts that need to be automatically closed/set to renews.
        This method is only called during a cron
        """
        current_date = fields.Date.context_today(self)
        close_contract_ids = self.filtered(lambda contract: contract.end_date and contract.end_date <= current_date)
        close_contract_ids.set_close()
        return close_contract_ids

    def _handle_automatic_invoices(self, invoices, auto_commit):
        """ This method handle the subscription with or without payment token """
        Mail = self.env['mail.mail']
        existing_invoices = invoices
        for order in self:
            invoice = invoices.filtered(lambda inv: inv.invoice_origin == order.name)
            email_context = self._get_subscription_mail_payment_context()
            # Set the contract in exception. If something go wrong, the exception remains.
            order.with_context(mail_notrack=True).write({'payment_exception': True})
            if not order.payment_token_id:
                invoice.action_post()
            else:
                payment_callback_done = False
                try:
                    payment_token = order.payment_token_id
                    transaction = None
                    # execute payment
                    if payment_token:
                        if not payment_token.partner_id.country_id:
                            msg_body = _('Automatic payment failed. No country specified on payment_token\'s partner')
                            order.message_post(body=msg_body)
                            invoice.unlink()
                            existing_invoices -= invoice
                            self._subscription_commit_cursor(auto_commit)
                            continue
                        transaction = order._do_payment(payment_token, invoice)
                        payment_callback_done = transaction and transaction.sudo().callback_is_done
                        # commit change as soon as we try the payment, so we have a trace in the payment_transaction table
                        self._subscription_commit_cursor(auto_commit)
                    # if transaction is a success, post a message
                    if transaction and transaction.state == 'done':
                        order.with_context(mail_notrack=True).write({'payment_exception': False})
                        self._subscription_post_success_payment(invoice, transaction)
                        self._subscription_commit_cursor(auto_commit)
                    # if no transaction or failure, log error, rollback and remove invoice
                    if transaction and not transaction.renewal_allowed:
                        self._subscription_rollback_cursor(auto_commit)
                        order._handle_subscription_payment_failure(invoice, transaction, email_context)
                        existing_invoices -= invoice  # It will be unlinked in the call above
                except Exception:
                    self._subscription_rollback_cursor(auto_commit)
                    # we suppose that the payment is run only once a day
                    last_transaction = self.env['payment.transaction'].search(['|',
                        ('reference', 'like', order.client_order_ref),
                        ('reference', 'like', order.name)
                    ], limit=1)
                    error_message = "Error during renewal of contract [%s] %s (%s)" \
                                    % (order.id, order.client_order_ref or order.name, 'Payment recorded: %s' % last_transaction.reference
                                       if last_transaction and last_transaction.state == 'done' else 'Payment not recorded')
                    _logger.exception(error_message)
                    mail = Mail.sudo().create({'body_html': error_message, 'subject': error_message,
                                        'email_to': email_context.get('responsible_email'), 'auto_delete': True})
                    mail.send()
                    if invoice.state == 'draft':
                        existing_invoices -= invoice
                        if not payment_callback_done:
                            invoice.unlink()

        return existing_invoices

    def _get_expired_subscriptions(self):
        # We don't use CURRENT_DATE to allow using freeze_time in tests.
        today = fields.Datetime.today()
        self.env.cr.execute(
            """
                SELECT (so.next_invoice_date + INTERVAL '1 day' * COALESCE(sot.auto_close_limit,15)) AS "payment_limit",
                           so.next_invoice_date,
                           so.id AS so_id
                  FROM sale_order so
             LEFT JOIN sale_order_template sot ON sot.id=so.sale_order_template_id
                 WHERE so.is_subscription
                   AND so.state IN ('sale', 'done')
                   AND so.subscription_state = '3_progress'
                AND (so.next_invoice_date + INTERVAL '1 day' * COALESCE(sot.auto_close_limit,15))< %s
            """, [today.strftime('%Y-%m-%d')]
        )
        return self.env.cr.dictfetchall()

    def _get_unpaid_subscriptions(self):
        # We don't use CURRENT_DATE to allow using freeze_time in tests.
        today = fields.Datetime.today()
        self.env.cr.execute(
            """
                WITH payment_limit_query AS (
                      SELECT (aml2.dm + INTERVAL '1 day' * COALESCE(sot.auto_close_limit,15) ) AS "payment_limit",
                              aml2.dm AS date_maturity,
                              str.unit AS unit,
                              str.duration AS duration,
                              CASE
                                WHEN str.unit='week' THEN INTERVAL '1 day' * 7 * str.duration
                                WHEN str.unit='month' THEN INTERVAL '1 day' * 30 * str.duration
                                WHEN str.unit='year' THEN INTERVAL '1 day' * 365 * str.duration
                              END AS conversion,
                              str.duration || ' ' || str.unit AS recurrence,
                              am.payment_state AS payment_state,
                              am.id AS am_id,
                              so.id AS so_id,
                              so.next_invoice_date AS next_invoice_date
                        FROM sale_order so
                        JOIN sale_order_line sol ON sol.order_id = so.id
                        JOIN account_move_line aml ON aml.subscription_id = so.id
                        JOIN account_move am ON am.id = aml.move_id
                        JOIN sale_temporal_recurrence str ON str.id=so.recurrence_id
                        JOIN sale_order_line_invoice_rel rel ON rel.invoice_line_id=aml.id
                   LEFT JOIN sale_order_template sot ON sot.id = so.sale_order_template_id
           LEFT JOIN LATERAL ( SELECT MAX(date_maturity) AS dm FROM account_move_line aml WHERE aml.move_id = am.id) AS aml2 ON TRUE
                      WHERE so.is_subscription
                        AND so.state IN ('sale', 'done')
                        AND so.subscription_state ='3_progress'
                        AND am.payment_state = 'not_paid'
                        AND am.move_type = 'out_invoice'
                        AND am.state = 'posted'
                        AND rel.order_line_id=sol.id
                   GROUP BY so_id,am_id,sot.auto_close_limit,payment_state,aml2.dm,str.unit,str.duration
               )
              SELECT payment_limit::DATE,
                     date_maturity,
                     recurrence,
                     next_invoice_date - plq.conversion AS last_invoice_date,
                     payment_state,
                     am_id,so_id,
                     next_invoice_date
                FROM
                    payment_limit_query plq
                    WHERE payment_limit < %s and payment_limit >= (next_invoice_date - plq.conversion)::DATE
            """, [today.strftime('%Y-%m-%d')]
        )
        return self.env.cr.dictfetchall()

    def _handle_unpaid_subscriptions(self):
        unpaid_result = self._get_unpaid_subscriptions()
        return {res['so_id']: res['am_id'] for res in unpaid_result}

    def _cron_subscription_expiration(self):
        # Flush models according to following SQL requests
        self.env['sale.order'].flush_model(
            fnames=['order_line', 'sale_order_template_id', 'state', 'subscription_state', 'next_invoice_date'])
        self.env['account.move'].flush_model(fnames=['payment_state', 'line_ids'])
        self.env['account.move.line'].flush_model(fnames=['move_id', 'sale_line_ids'])
        self.env['sale.order.template'].flush_model(fnames=['auto_close_limit'])
        today = fields.Date.today()
        # set to close if date is passed or if locked sale order is passed
        domain_close = [
            ('is_subscription', '=', True),
            ('end_date', '<', today),
            ('state', 'in', ['sale', 'done']),
            ('subscription_state', 'in', SUBSCRIPTION_PROGRESS_STATE)]
        subscriptions_close = self.search(domain_close)
        unpaid_results = self._handle_unpaid_subscriptions()
        unpaid_ids = unpaid_results.keys()
        expired_result = self._get_expired_subscriptions()
        expired_ids = [r['so_id'] for r in expired_result]
        subscriptions_close |= self.env['sale.order'].browse(unpaid_ids) | self.env['sale.order'].browse(expired_ids)
        auto_commit = not bool(config['test_enable'] or config['test_file'])
        expired_close_reason = self.env.ref('sale_subscription.close_reason_auto_close_limit_reached')
        unpaid_close_reason = self.env.ref('sale_subscription.close_reason_unpaid_subscription')
        for batched_to_close in split_every(30, subscriptions_close.ids, self.env['sale.order'].browse):
            unpaid_so = self.env['sale.order']
            expired_so = self.env['sale.order']
            for so in batched_to_close:
                if so.id in unpaid_ids:
                    unpaid_so |= so
                    account_move = self.env['account.move'].browse(unpaid_results[so.id])
                    so.message_post(
                        body=escape(_("The last invoice (%s) of this subscription is unpaid after the due date.")) % \
                               account_move._get_html_link(),
                        partner_ids=so.team_user_id.partner_id.ids,
                        message_type='email')
                elif so.id in expired_ids:
                    expired_so |= so

            unpaid_so.set_close(close_reason_id=unpaid_close_reason)
            expired_so.set_close(close_reason_id=expired_close_reason)
            (batched_to_close - unpaid_so - expired_so).set_close()
            if auto_commit:
                self.env.cr.commit()
        return dict(closed=subscriptions_close.ids)

    def _get_subscription_delta(self, date):
        self.ensure_one()
        delta, percentage = False, False
        subscription_log = self.env['sale.order.log'].search([
            ('order_id', '=', self.id),
            ('event_type', 'in', ['0_creation', '1_expansion', '15_contraction', '2_transfer']),
            ('event_date', '<=', date)],
            order='event_date desc',
            limit=1)
        if subscription_log:
            delta = self.recurring_monthly - subscription_log.recurring_monthly
            percentage = delta / subscription_log.recurring_monthly if subscription_log.recurring_monthly != 0 else 100
        return {'delta': delta, 'percentage': percentage}

    def _nothing_to_invoice_error_message(self):
        error_message = super()._nothing_to_invoice_error_message()
        if any(self.mapped('is_subscription')):
            error_message += _(
                "\n- You are trying to invoice recurring orders that are past their end date. Please change their end date or renew them "
                "before creating new invoices."
            )
        return error_message

    def _do_payment(self, payment_token, invoice):
        tx_obj = self.env['payment.transaction']
        values = []
        for subscription in self:
            values.append({
                'provider_id': payment_token.provider_id.id,
                'sale_order_ids': [Command.link(subscription.id)],
                'amount': invoice.amount_total,
                'currency_id': invoice.currency_id.id,
                'partner_id': subscription.partner_id.id,
                'token_id': payment_token.id,
                'operation': 'offline',
                'invoice_ids': [(6, 0, [invoice.id])],
                'callback_model_id': self.env['ir.model']._get_id(subscription._name),
                'callback_res_id': subscription.id,
                'callback_method': 'reconcile_pending_transaction'})
        transactions = tx_obj.create(values)
        for tx in transactions:
            tx._send_payment_request()
        return transactions

    def send_success_mail(self, tx, invoice):
        self.ensure_one()
        if invoice.is_move_sent or not invoice._is_ready_to_be_sent() or invoice.state != 'posted':
            return
        current_date = fields.Date.today()
        next_date = self.next_invoice_date or current_date
        # if no recurring next date, have next invoice be today + interval
        if not self.next_invoice_date:
            invoicing_periods = [next_date + pricing_id.recurrence_id.get_recurrence_timedelta() for pricing_id in self.order_line.pricing_id]
            next_date = invoicing_periods and min(invoicing_periods) or current_date
        email_context = {**self.env.context.copy(),
                         **{'payment_token': self.payment_token_id.payment_details,
                            '5_renewed': True,
                            'total_amount': tx.amount,
                            'next_date': next_date,
                            'previous_date': self.next_invoice_date,
                            'email_to': self.partner_id.email,
                            'code': self.client_order_ref,
                            'subscription_name': self.name,
                            'currency': self.currency_id.name,
                            'date_end': self.end_date}}
        _logger.debug("Sending Payment Confirmation Mail to %s for subscription %s", self.partner_id.email, self.id)
        template = self.env.ref('sale_subscription.email_payment_success')

        # This function can be called by the public user via the callback_method set in
        # /my/subscription/transaction/. The email template contains the invoice PDF in
        # attachment, so to render it successfully sudo() is not enough.
        if self.env.su:
            template = template.with_user(SUPERUSER_ID)
        return invoice.with_context(email_context)._generate_pdf_and_send_invoice(template)
    @api.model
    def _process_invoices_to_send(self, account_moves):
        for invoice in account_moves:
            if not invoice.is_move_sent and invoice._is_ready_to_be_sent() and invoice.state == 'posted':
                subscription = invoice.line_ids.subscription_id
                subscription.validate_and_send_invoice(invoice)
                invoice.message_subscribe(subscription.user_id.partner_id.ids)
            elif invoice.line_ids.subscription_id:
                invoice.message_subscribe(invoice.line_ids.subscription_id.user_id.partner_id.ids)

    def validate_and_send_invoice(self, invoice):
        self.ensure_one()
        email_context = {**self.env.context.copy(), **{
            'total_amount': invoice.amount_total,
            'email_to': self.partner_id.email,
            'code': self.client_order_ref or self.name,
            'currency': self.currency_id.name,
            'date_end': self.end_date,
            'no_new_invoice': True}}
        auto_commit = not bool(config['test_enable'] or config['test_file'])
        if auto_commit:
            self.env.cr.commit()
        invoice_mail_template_id = self.sale_order_template_id.invoice_mail_template_id \
            or self.env.ref('sale_subscription.mail_template_subscription_invoice', raise_if_not_found=False)
        if invoice_mail_template_id:
            _logger.debug("Sending Invoice Mail to %s for subscription %s", self.partner_id.email, self.id)
            invoice.with_context(email_context)._generate_pdf_and_send_invoice(invoice_mail_template_id)

    def _reconcile_and_assign_token(self, tx):
        """ Callback method to make the reconciliation and assign the payment token.
            This method is always used in non-automatic mode, all the recurring lines should be invoiced
        :param recordset tx: The transaction that created the token, and that must be reconciled,
                             as a `payment.transaction` record
        :return: Whether the conditions were met to execute the callback
        """
        self.ensure_one()
        if tx.renewal_allowed:
            self._assign_token(tx)
            self.with_context(recurring_automatic=False)._reconcile_and_send_mail(tx)
            return True
        return False

    def _assign_token(self, tx):
        """ Callback method to assign a token after the validation of a transaction.
        Note: self.ensure_one()
        :param recordset tx: The validated transaction, as a `payment.transaction` record
        :return: Whether the conditions were met to execute the callback
        """
        self.ensure_one()
        if tx.renewal_allowed:
            self.payment_token_id = tx.token_id.id
            return True
        return False

    def _reconcile_and_send_mail(self, tx):
        """ Callback method to make the reconciliation and send a confirmation email.
        :param recordset tx: The transaction to reconcile, as a `payment.transaction` record
        """
        self.ensure_one()
        if self.reconcile_pending_transaction(tx):
            invoice = tx.invoice_ids[0]
            self.send_success_mail(tx, invoice)
            msg_body = escape(_("Manual payment succeeded. Payment reference: %(ref)s; Amount: %(amount)s. Invoice %(invoice)s")) % {
                'ref': tx._get_html_link(),
                'amount': tx.amount,
                'invoice': invoice._get_html_link(),
            }
            self.message_post(body=msg_body)
            return True
        return False

    def reconcile_pending_transaction(self, tx):
        """ Callback method to make the reconciliation.
        :param recordset tx: The transaction to reconcile, as a `payment.transaction` record
        :return: Whether the transaction was successfully reconciled
        """
        self.ensure_one()
        if tx.renewal_allowed:  # The payment is confirmed, it can be reconciled
            # avoid to create an invoice when one is already linked
            if not tx.invoice_ids:
                tx._create_or_link_to_invoice()
            self.set_open()
            return True
        return False
