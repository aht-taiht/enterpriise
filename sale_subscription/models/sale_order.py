# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

import logging
from dateutil.relativedelta import relativedelta
from psycopg2.extensions import TransactionRollbackError
from ast import literal_eval
from collections import defaultdict

from odoo import fields, models, _, api, Command, SUPERUSER_ID, modules
from odoo.exceptions import UserError, ValidationError
from odoo.tools.float_utils import float_is_zero
from odoo.osv import expression
from odoo.tools import config, format_amount
from odoo.tools.date_utils import get_timedelta

_logger = logging.getLogger(__name__)


class SaleOrder(models.Model):
    _name = "sale.order"
    _inherit = ["rating.mixin", "sale.order"]

    def _get_default_stage_id(self):
        return self.env['sale.order.stage'].search([], order='sequence', limit=1).id

    def _get_default_starred_user_ids(self):
        return [(4, self.env.uid)]

    ###################
    # Recurring order #
    ###################
    is_subscription = fields.Boolean("Recurring", compute='_compute_is_subscription', store=True, index=True)
    recurrence_id = fields.Many2one('sale.temporal.recurrence', compute='_compute_recurrence_id',
                                     string='Recurrence', ondelete='restrict', readonly=False, store=True)
    subscription_management = fields.Selection(
        string='Subscription Management',
        selection=[
            ('create', 'Creation'), # ARJ TODO MASTER: remove this option if we don't do anything with it
            ('renew', 'Renewal'),
            ('renewal_so', 'Renewal Quote'), # sale.order with subscription_management confirmed when sale.subscription was a thing
            ('upsell', 'Upsell')],
        default=False,
        help="Creation: The Sales Order created the subscription\n"
             "Upsell: The Sales Order added lines to the subscription\n"
             "Renewal: The Sales Order replaced the subscription's content with its own")

    subscription_id = fields.Many2one('sale.order', string='Parent Contract', ondelete='restrict', copy=False)
    origin_order_id = fields.Many2one('sale.order', string='First contract', ondelete='restrict', store=True, copy=False,
                                      compute='_compute_origin_order_id')
    subscription_child_ids = fields.One2many('sale.order', 'subscription_id')

    stage_id = fields.Many2one('sale.order.stage', string='Stage', index=True, default=lambda s: s._get_default_stage_id(),
                               copy=False, group_expand='_read_group_stage_ids', tracking=True)
    stage_category = fields.Selection(related='stage_id.category', store=True)
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
                                       help="Automatic payment with token failed. The payment provider configuration and token should be checked")
    to_renew = fields.Boolean(string='To Renew', default=False, copy=False)

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

    recurring_live = fields.Boolean(string='Alive', compute='_compute_recurring_live', store=True, tracking=True)
    recurring_monthly = fields.Monetary(compute='_compute_recurring_monthly', string="Monthly Recurring Revenue",
                                        store=True, tracking=True)
    order_log_ids = fields.One2many('sale.order.log', 'order_id', string='Subscription Logs', readonly=True)
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
    is_upselling = fields.Boolean(compute='_compute_is_upselling')
    renew_state = fields.Selection(
        [('renewing', 'Renewing'), ('renewed', 'Renewed')], compute='_compute_renew_state')

    archived_product_ids = fields.Many2many('product.product', string='Archived Products', compute='_compute_archived')
    archived_product_count = fields.Integer("Archived Product", compute='_compute_archived')
    history_count = fields.Integer(compute='_compute_history_count')
    # TODO REMOVE MASTER
    show_rec_invoice_button = fields.Boolean(compute='_compute_show_rec_invoice_button')
    has_recurring_line = fields.Boolean(compute='_compute_has_recurring_line')

    starred_user_ids = fields.Many2many('res.users', 'sale_order_starred_user_rel', 'order_id', 'user_id',
                                        default=lambda s: s._get_default_starred_user_ids(), string='Members')
    starred = fields.Boolean(compute='_compute_starred', inverse='_inverse_starred',
                             string='Show Subscription on dashboard',
                             help="Whether this subscription should be displayed on the dashboard or not")

    _sql_constraints = [
        ('sale_subscription_stage_coherence',
         "CHECK(NOT (is_subscription=TRUE AND state IN ('sale', 'done') AND stage_category='draft'))",
         "You cannot set to draft a confirmed subscription. Please create a new quotation"),
        ('check_start_date_lower_next_invoice_date', 'CHECK((next_invoice_date IS NULL OR start_date IS NULL) OR (next_invoice_date >= start_date))',
         'The next invoice date of a sale order should be after its start date.'),
    ]

    @api.constrains('subscription_management', 'subscription_id', 'pricelist_id')
    def _constraint_subscription_upsell_multi_currency(self):
        for so in self:
            if so.subscription_management == 'upsell' and so.subscription_id.pricelist_id.currency_id != so.pricelist_id.currency_id:
                raise ValidationError(_('You cannot upsell a subscription using a different currency.'))

    @api.constrains('recurrence_id', 'state', 'is_subscription')
    def _constraint_subscription_recurrence(self):
        recurring_product_orders = self.order_line.filtered(lambda l: l.product_id.recurring_invoice).order_id
        for so in self:
            if so.state in ['draft', 'cancel'] or so.subscription_management == 'upsell':
                continue
            if so in recurring_product_orders and not so.recurrence_id:
                raise UserError(_('You cannot save a sale order with recurring product and no recurrence.'))
            if so.recurrence_id and so.order_line and so not in recurring_product_orders:
                raise UserError(_('You cannot save a sale order with a recurrence and no recurring product.'))

    @api.depends('recurrence_id', 'subscription_management')
    def _compute_is_subscription(self):
        for order in self:
            if not order.recurrence_id or order.subscription_management == 'upsell':
                order.is_subscription = False
                continue
            order.is_subscription = True

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

    @api.depends('stage_category', 'state', 'is_subscription', 'amount_untaxed')
    def _compute_recurring_monthly(self):
        """ Compute the amount monthly recurring revenue. When a subscription has a parent still ongoing.
        Depending on invoice_ids force the recurring monthly to be recomputed regularly, even for the first invoice
        where confirmation is set the next_invoice_date and first invoice do not update it (in automatic mode).
        """
        for order in self:
            if not order.is_subscription or order.stage_category not in ['progress', 'paused'] or \
                    order.state not in ['sale', 'done']:
                order.recurring_monthly = 0.0
                continue
            order.recurring_monthly = sum(order.order_line.mapped('recurring_monthly'))

    @api.depends('is_subscription', 'order_line.price_total')
    def _compute_recurring_details(self):
        subscription_orders = self.filtered(lambda sub: sub.is_subscription or sub.subscription_id)
        self.recurring_details = ""
        if subscription_orders.ids:
            query = """
                SELECT order_id, 
                       pt.recurring_invoice recurring_invoice,
                       SUM(price_subtotal) AS subtotal,
                       SUM(price_total) as total 
                  FROM sale_order_line sol 
                  JOIN sale_order so ON sol.order_id=so.id
                  JOIN product_product pp ON pp.id=sol.product_id 
                  JOIN product_template pt ON pt.id=pp.product_tmpl_id 
                 WHERE order_id IN %s
                   AND so.recurrence_id IS NOT NULL
                   AND pt.recurring_invoice IS NOT NULL
              GROUP BY order_id,recurring_invoice
            """
            self.env.cr.execute(query, (tuple(subscription_orders.ids),))
            recurring_details = self.env.cr.dictfetchall()
            for so in subscription_orders:
                lang_code = so.partner_id.lang
                values = [details for details in recurring_details if details['order_id'] == so.id and details['subtotal'] and details['total']]
                recurring_amount = sum([v['subtotal'] for v in values if v.get('recurring_invoice')])
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
            if order.is_subscription and order.stage_category in ['progress', 'closed']:
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

    @api.depends('origin_order_id.start_date', 'subscription_management', 'is_subscription', 'start_date')
    def _compute_first_contract_date(self):
        for so in self:
            if not so.is_subscription:
                continue
            elif so.subscription_management in ['renew', 'upsell']:
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

    @api.depends('state', 'stage_category', 'start_date', 'next_invoice_date', 'subscription_id.state', 'subscription_id.stage_category')
    def _compute_recurring_live(self):
        """ The live state allows to select the latest running subscription of a family
            It is helpful to see on which record next activities should be saved, count the real number of live contracts etc
            It depends on the parent state and stage because when a parent contrat is ended, the child renewal should
            become alive.
        """
        today = fields.Date.today()
        for order in self:
            if not order.is_subscription or order.state not in ['sale', 'done'] or order.stage_category not in ['progress', 'paused']:
                order.recurring_live = False
            elif order.start_date and order.start_date <= today:
                order.recurring_live = True
            else:
                order.recurring_live = False

    @api.depends('is_subscription', 'state', 'start_date', 'subscription_management')
    def _compute_next_invoice_date(self):
        for so in self:
            if not so.is_subscription and not so.subscription_management == 'upsell':
                so.next_invoice_date = False
                continue
            elif not so.next_invoice_date and so.state == 'sale':
                # Define a default next invoice date.
                # It is increased manually by _update_next_invoice_date when necessary
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

    @api.depends('origin_order_id')
    def _compute_history_count(self):
        subscription_history_needed = self.mapped('is_subscription') + self.mapped('subscription_management')
        if not any(subscription_history_needed):
            self.history_count = 0
            return
        origin_ids = self.origin_order_id.ids + self.ids
        result = self.env['sale.order'].read_group([
                ('state', '!=', 'cancel'),
                ('origin_order_id', 'in', origin_ids)
            ],
            ['origin_order_id'],
            ['origin_order_id']
        )
        counters = {data['origin_order_id'][0]: data['origin_order_id_count'] + 1 for data in result}
        for so in self:
            so.history_count = counters.get(so.origin_order_id.id or so.id, 0)

    @api.depends('is_subscription', 'subscription_management')
    def _compute_origin_order_id(self):
        for order in self:
            if order.subscription_management in ['renew', 'upsell'] and not order.origin_order_id:
                order.origin_order_id = order.subscription_id

    @api.model
    def _read_group_stage_ids(self, stages, domain, order):
        return stages.sudo().search([], order=order)

    def _track_subtype(self, init_values):
        self.ensure_one()
        if 'stage_id' in init_values:
            return self.env.ref('sale_subscription.subtype_stage_change')
        return super()._track_subtype(init_values)

    def _compute_show_rec_invoice_button(self):
        self.show_rec_invoice_button = False
        for order in self:
            if not order.is_subscription or order.stage_category != 'progress' or order.state not in ['sale', 'done']:
                continue
            order.show_rec_invoice_button = True

    @api.depends('sale_order_template_id')
    def _compute_recurrence_id(self):
        for order in self:
            if order.sale_order_template_id and order.sale_order_template_id.recurrence_id:
                order.recurrence_id = order.sale_order_template_id.recurrence_id
            else:
                order.recurrence_id = False

    def _compute_is_upselling(self):
        self.is_upselling = False
        upsell_order_ids = self.env['sale.order'].search([
            ('id', 'in', self.subscription_child_ids.ids),
            ('state', '=', 'draft'),
            ('subscription_management', '=', 'upsell')
        ]).subscription_id
        upsell_order_ids.is_upselling = True

    @api.depends('order_line')
    def _compute_has_recurring_line(self):
        recurring_product_orders = self.order_line.filtered(lambda l: l.product_id.recurring_invoice).order_id
        recurring_product_orders.has_recurring_line = True
        (self - recurring_product_orders).has_recurring_line = False

    def _compute_renew_state(self):
        self.renew_state = False
        renew_order_values = self.env['sale.order'].search_read(
            [
                ('id', 'in', self.subscription_child_ids.ids),
                ('subscription_management', '=', 'renew')
            ], ['state', 'subscription_id']
        )
        if not renew_order_values:
            return
        renewed_with_quotation = []
        renewed_with_confirmation = []
        for vals in renew_order_values:
            if vals.get('state') == 'draft':
                renewed_with_quotation.append(vals['subscription_id'][0])
            elif vals.get('state') == 'sale':
                renewed_with_confirmation.append(vals['subscription_id'][0])
        for order in self:
            if order.id in renewed_with_confirmation and order.state == 'done':
                order.renew_state = "renewed"
            elif order.id in renewed_with_quotation:
                order.renew_state = "renewing"

    def _create_mrr_log(self, template_value, initial_values):
        if self.stage_category not in ['progress', 'paused']:
            return
        confirmed_renewal = self.subscription_id and self.subscription_management == 'renew'
        alive_child_categories = self.subscription_child_ids.mapped('stage_category')
        is_transfered_parent = any([stage in ['progress', 'paused'] for stage in alive_child_categories])
        cur_round = self.company_id.currency_id.rounding
        old_mrr = initial_values.get('recurring_monthly', self.recurring_monthly)
        transfer_mrr = 0
        mrr_difference = self.recurring_monthly - old_mrr
        if confirmed_renewal:
            existing_transfer_log = self.order_log_ids.filtered(lambda ev: ev.event_type == '3_transfer')
            if not existing_transfer_log:
                # We transfer from the current MRR to the latest known MRR.
                # The parent contrat is now done and its MRR is 0
                parent_mrr = self.subscription_id.order_log_ids and self.subscription_id.order_log_ids[-1].recurring_monthly or 0
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
            event_type = '1_change' if self.order_log_ids else '0_creation'
            if is_transfered_parent:
                event_type = '3_transfer'
            mrr_value.update({'event_type': event_type, 'amount_signed': mrr_difference, 'recurring_monthly': self.recurring_monthly})
            self.env['sale.order.log'].sudo().create(mrr_value)

    def _create_stage_log(self, values, initial_values):
        old_stage_id = initial_values['stage_id']
        new_stage_id = self.stage_id
        log = None
        cur_round = self.company_id.currency_id.rounding
        mrr_change_value = {}
        confirmed_renewal = self.subscription_id and self.subscription_management == 'renew' and self.stage_category in ['progress', 'paused']
        alive_renewed = self.subscription_child_ids.filtered(
            lambda s: s.subscription_management == 'renew' and s.recurring_live)
        if new_stage_id.category in ['progress', 'paused', 'closed'] and old_stage_id.category != new_stage_id.category:
            # subscription started, churned or transferred to renew
            if new_stage_id.category in ['progress', 'paused']:
                if confirmed_renewal:
                    # Transfer for the renewed value and MRR change for the rest
                    parent_mrr = self.subscription_id.recurring_monthly
                    # Creation of renewal: transfer and MRR change
                    event_type = '3_transfer'
                    amount_signed = parent_mrr
                    recurring_monthly = parent_mrr
                    if not float_is_zero(self.recurring_monthly - parent_mrr, precision_rounding=cur_round):
                        mrr_change_value = values.copy()
                        mrr_change_value.update({
                            'event_type': '1_change',
                            'recurring_monthly': self.recurring_monthly,
                            'amount_signed': self.recurring_monthly - parent_mrr
                        })
                else:
                    event_type = '0_creation'
                    amount_signed = self.recurring_monthly
                    recurring_monthly = self.recurring_monthly
            else:
                event_type = '3_transfer' if alive_renewed else '2_churn'
                amount_signed = - initial_values['recurring_monthly']
                recurring_monthly = 0
                if event_type == '3_transfer' and \
                        float_is_zero(recurring_monthly, precision_rounding=cur_round) and \
                        float_is_zero(amount_signed, precision_rounding=cur_round):
                    # Avoid creating transfer log for free subscription that remains free
                    return

            if confirmed_renewal and self.start_date > fields.Date.today():
                # We don't create logs for confirmed renewal that start in the future
                return
            values.update({
                'event_type': event_type,
                'amount_signed': recurring_monthly,
                'recurring_monthly': amount_signed
            })
            # prevent duplicate logs
            if not self.order_log_ids.filtered(
                lambda ev: ev.event_type == values['event_type'] and ev.event_date == values['event_date']):
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
                  'category': self.stage_id.category,
                  'user_id': self.user_id.id,
                  'team_id': self.team_id.id}
        stage_log = None

        if 'stage_id' in initial_values:
            stage_log = self._create_stage_log(values, initial_values)
        if ('recurring_monthly' in updated_fields or 'recurring_live' in updated_fields) and not stage_log:
            self._create_mrr_log(values, initial_values)
        return res

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
            if not order.is_subscription:
                continue
            order.subscription_management = vals.get('subscription_management', 'create')
            if vals.get('stage_id'):
                order._send_subscription_rating_mail(force_send=True)
        return orders

    def write(self, vals):
        subscriptions = self.filtered('is_subscription')
        old_partners = {s.id: s.partner_id.id for s in subscriptions}
        old_in_progress = {s.id: s.stage_category == "progress" for s in subscriptions}
        res = super().write(vals)
        if vals.get('company_id'):
            # simple SO don't see their lines recomputed, especially when they are in a sent/confirmed state.
            # Subscription should be updated
            subscriptions.order_line._compute_tax_id()
        subscriptions_to_confirm = self.env['sale.order']
        subscriptions_to_cancel = self.env['sale.order']
        for subscription in subscriptions:
            if not subscription.subscription_management:
                # vals.get('subscription_management', 'create') of {'subscription_management': False} returns False
                subscription.subscription_management = vals.get('subscription_management') or 'create'
            diff_partner = subscription.partner_id.id != old_partners[subscription.id]
            diff_in_progress = (subscription.stage_category == "progress") != old_in_progress[subscription.id]
            if diff_partner or diff_in_progress:
                if subscription.stage_category == "progress" and diff_partner:
                    subscription.message_subscribe(subscription.partner_id.ids)
                    subscriptions_to_confirm += subscription
                if subscription.stage_category == "closed" and not subscription.state == 'done':
                    subscriptions_to_cancel += subscription
                if diff_partner or subscription.stage_category != "progress":
                    subscription.message_unsubscribe([old_partners[subscription.id]])
        if vals.get('stage_id'):
            subscriptions_to_rate = subscriptions - subscriptions_to_confirm - subscriptions_to_cancel
            subscriptions_to_rate._send_subscription_rating_mail(force_send=True)
        if subscriptions_to_confirm:
            subscriptions_to_confirm.action_confirm()
        return res

    @api.ondelete(at_uninstall=False)
    def _unlink_except_draft_or_cancel(self):
        for order in self:
            # To have a subscription with the state 'cancel',
            # it has to have a stage_category which is 'closed'.
            if order.is_subscription and (order.state not in ['draft', 'sent'] and order.stage_category != 'closed'):
                raise UserError(_('You can not delete a confirmed subscription. You must first close and cancel it before you can delete it.'))
        return super(SaleOrder, self)._unlink_except_draft_or_cancel()

    def copy_data(self, default=None):
        if default is None:
            default = {}
        if self.subscription_management == "upsell":
            default.update({
                "client_order_ref": self.client_order_ref,
                "subscription_id": self.subscription_id.id,
                "origin_order_id": self.origin_order_id.id
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
            if order.subscription_management and order.subscription_id:
                if order.subscription_management == 'upsell':
                    cancel_message_body = _("The upsell %s has been canceled.", order._get_html_link())
                elif order.subscription_management == 'renew':
                    cancel_message_body = _("The renewal %s has been canceled.", order._get_html_link())
                else:
                    # Normal SO
                    continue
                order.subscription_id.message_post(body=cancel_message_body)
        return super()._action_cancel()

    def _prepare_confirmation_values(self):
        """
        Override of the sale method. sale.order in self should have the same stage_id in order to process
        them in batch.
        :return: dict of values
        """
        values = super()._prepare_confirmation_values()
        is_subscription = all(self.mapped('is_subscription'))
        if is_subscription:
            stages_in_progress = self.env['sale.order.stage'].search([('category', '=', 'progress')])
            if not stages_in_progress:
                raise ValidationError(_("Unable to put the subscription in a progress stage"))
            next_stage_in_progress = stages_in_progress.filtered(lambda s: s.sequence > self.stage_id.sequence)[:1]
            if not next_stage_in_progress:
                next_stage_in_progress = stages_in_progress.filtered(lambda s: s.id == max(stages_in_progress.ids))
            values.update({'stage_id': next_stage_in_progress.id, 'stage_category': next_stage_in_progress.category})
        return values

    def action_confirm(self):
        """Update and/or create subscriptions on order confirmation."""
        confirmed_subscription = self.filtered('is_subscription')
        child_subscriptions = self.filtered('subscription_id')
        # We can't confirm twice the child order. To avoid two messages in the chatter, quantity mismatch etc
        renew = child_subscriptions.filtered(lambda s: s.subscription_management == 'renew' and s.state in ['draft', 'sent'])
        upsell = child_subscriptions.filtered(lambda s: s.subscription_management == 'upsell' and s.state in ['draft', 'sent'])
        # We need to call super with batches of subscription in the same stage
        res = super(SaleOrder, self - confirmed_subscription).action_confirm()
        for stage in confirmed_subscription.mapped('stage_id'):
            subs_current_stage = confirmed_subscription.filtered(lambda so: so.stage_id.id == stage.id)
            res = res and super(SaleOrder, subs_current_stage).action_confirm()
        confirmed_subscription._confirm_subscription()
        upsell._confirm_upsell()
        renew._confirm_renew()
        return res

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
                raise ValidationError(_("You can not upsell a subscription that has not been invoiced yet. "
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
            upsell.subscription_id.message_post(body=_("The upsell  %s has been confirmed.", upsell._get_html_link()))
        for line in (updated_line_ids | new_lines_ids).with_context(skip_line_status_compute=True):
            # The upsell invoice will take care of the invoicing for this period
            line.qty_to_invoice = 0
            line.qty_invoiced = line.product_uom_qty
            # We force the invoice status because the current period will be invoiced by the upsell flow
            # when the upsell so is invoiced
            line.invoice_status = 'no'

    def _confirm_renew(self):
        """
        When confirming an renew order, the recurring product lines must be updated
        """
        today = fields.Date.today()
        self.subscription_id.write({'to_renew': False})
        for renew in self:
            # When parent subscription reaches his end_date, it will be closed with a close_reason_renew so it won't be considered as a simple churn.
            parent = renew.subscription_id
            other_renew_so_ids = parent.subscription_child_ids.filtered(
                lambda so: so.subscription_management == 'renew' and so.state in ['draft', 'sent'] and so.stage_category == 'draft') - renew
            if other_renew_so_ids:
                other_renew_so_ids._action_cancel()

            renew_msg_body = _(
                "This subscription is renewed in %s with a change of plan.", renew._get_html_link()
            )
            parent.message_post(body=renew_msg_body)
            parent.state = 'done'
            parent.end_date = parent.next_invoice_date
            start_date = renew.start_date or parent.next_invoice_date
            renew.write({'date_order': today, 'start_date': start_date})
            renew._save_token_from_payment()

    def _save_token_from_payment(self):
        self.ensure_one()
        last_token = self.transaction_ids._get_last().token_id.id
        if last_token:
            self.payment_token_id = last_token

    @api.model
    def _get_associated_so_action(self):
        return {
            "type": "ir.actions.act_window",
            "res_model": "sale.order",
            "views": [[self.env.ref('sale_subscription.sale_order_view_tree_subscription').id, "tree"],
                      [self.env.ref('sale_subscription.sale_subscription_primary_form_view').id, "form"],
                      [False, "kanban"], [False, "calendar"], [False, "pivot"], [False, "graph"]],
        }

    def open_subscription_history(self):
        self.ensure_one()
        action = self._get_associated_so_action()
        origin_order_id = self.origin_order_id.id or self.id
        action['name'] = _("History")
        action['domain'] = ['|', ('id', '=', origin_order_id), ('origin_order_id', '=', origin_order_id)]
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
        action = self.env["ir.actions.actions"]._for_xml_id("sale_subscription.action_sale_order_log")
        origin_order_ids = self.origin_order_id.ids + self.ids
        genealogy_orders_ids = self.search(['|', ('id', 'in', origin_order_ids), ('origin_order_id', 'in', origin_order_ids)])
        action.update({
            'name': _('MRR changes'),
            'domain': [('order_id', 'in', genealogy_orders_ids.ids), ('event_type', '!=', '3_transfer')],
        })
        return action

    def _prepare_renew_upsell_order(self, subscription_management, message_body):
        self.ensure_one()
        values = self._prepare_upsell_renew_order_values(subscription_management)
        order = self.env['sale.order'].create(values)
        self.subscription_child_ids = [Command.link(order.id)]
        order.message_post(body=message_body)
        if subscription_management == 'upsell':
            parent_message_body = _("An upsell quotation %s has been created", order._get_html_link())
        else:
            parent_message_body = _("A renewal quotation %s has been created", order._get_html_link())
        self.message_post(body=parent_message_body)
        order.order_line._compute_tax_id()
        action = self._get_associated_so_action()
        action['name'] = _('Upsell') if subscription_management == 'upsell' else _('Renew')
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

    def prepare_renewal_order(self):
        self.ensure_one()
        lang = self.partner_id.lang or self.env.user.lang
        renew_msg_body = self._get_order_digest(origin='renew', lang=lang)
        action = self._prepare_renew_upsell_order('renew', renew_msg_body)

        return action

    def prepare_upsell_order(self):
        self.ensure_one()
        lang = self.partner_id.lang or self.env.user.lang
        upsell_msg_body = self._get_order_digest(origin='upsell', lang=lang)
        action = self._prepare_renew_upsell_order('upsell', upsell_msg_body)
        return action

    def create_alternative(self):
        self.ensure_one()
        alternative_so = self.copy({
            'origin_order_id': self.origin_order_id.id,
            'subscription_id': self.subscription_id.id
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
        stages_closed = self.env['sale.order.stage'].search([('category', '=', 'closed')])
        closed_orders = self.filtered('is_subscription')
        if not stages_closed and closed_orders:
            ValidationError(_("Error: unable to put the subscription in a closed stage"))
        for order in closed_orders:
            next_closed_stage = stages_closed.filtered(lambda s: s.sequence > order.stage_id.sequence)[:1]
            if not next_closed_stage:
                next_closed_stage = stages_closed.filtered(lambda s: s.id == max(stages_closed.ids))
            order.write({'stage_id': next_closed_stage.id, 'to_renew': False})

    def set_close(self):
        today = fields.Date.context_today(self)
        renew_close_reason = self.env.ref('sale_subscription.close_reason_renew', raise_if_not_found=False)
        self._set_closed_state()
        for sub in self:
            values = {}
            if sub.sale_order_template_id and sub.sale_order_template_id.recurring_rule_boundary == 'unlimited' or not sub.end_date or today < sub.end_date:
                values['end_date'] = today
            renew = sub.subscription_child_ids.filtered(
                lambda so: so.subscription_management == 'renew' and so.state in ['sale', 'done'] and so.date_order and so.date_order.date() >= sub.end_date)
            if renew and renew_close_reason:
                # The subscription has been renewed. We set a close_reason to avoid consider it as a simple churn.
                values['close_reason_id'] = renew_close_reason.id
            sub.write(values)
        return True

    def set_to_renew(self):
        return self.write({'to_renew': True})

    def set_open(self):
        search = self.env['sale.order.stage'].search
        for sub in self:
            stage = search([('category', '=', 'progress'), ('sequence', '>=', sub.stage_id.sequence)], limit=1)
            if not stage:
                stage = search([('category', '=', 'progress')], limit=1)
            date = sub.end_date if sub.end_date and sub.sale_order_template_id.recurring_rule_boundary == 'limited' else False
            sub.write({'stage_id': stage.id, 'to_renew': False, 'end_date': date})

    @api.model
    def _cron_update_kpi(self):
        subscriptions = self.search([('stage_category', '=', 'progress'), ('is_subscription', '=', True)])
        subscriptions._compute_kpi()

    def _prepare_upsell_renew_order_values(self, subscription_management):
        """
        Create a new draft order with the same lines as the parent subscription. All recurring lines are linked to their parent lines
        :return: dict of new sale order values
        """
        self.ensure_one()
        subscription = self.with_company(self.company_id)
        order_lines = self.order_line._get_renew_upsell_values(subscription_management, period_end=self.next_invoice_date)
        is_subscription = subscription_management == 'renew'
        option_lines_data = [fields.Command.clear()]
        option_lines_data += [
            fields.Command.create(
                option._prepare_option_line_values()
            )
            for option in self.sale_order_template_id.sale_order_template_option_ids
        ]
        if subscription_management == 'upsell':
            start_date = fields.Date.today()
            next_invoice_date = self.next_invoice_date
            internal_note = ""
            stage_id = False
        else:
            # renew
            start_date = self.next_invoice_date
            next_invoice_date = self.next_invoice_date # the next invoice date is the start_date for new contract
            internal_note = subscription.internal_note
            stage_id = self._get_default_stage_id()
        return {
            'is_subscription': is_subscription,
            'subscription_id': subscription.id,
            'pricelist_id': subscription.pricelist_id.id,
            'partner_id': subscription.partner_id.id,
            'order_line': order_lines,
            'analytic_account_id': subscription.analytic_account_id.id,
            'subscription_management': subscription_management,
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
            'stage_id': stage_id,
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

    def _find_mail_template(self):
        template = super()._find_mail_template()
        if self.is_subscription:
            if self.to_renew:
                subscription_template = self.env.ref(
                    'sale_subscription.mail_template_subscription_alert', raise_if_not_found=False)
                if subscription_template:
                    template = subscription_template
        return template

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

            time_condition = line.order_id.next_invoice_date and line.order_id.next_invoice_date <= date_from and line.order_id.start_date and line.order_id.start_date <= date_from
            line_condition = time_condition or not automatic_invoice # automatic mode force the invoice when line are not null
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
        msg_body = _(
            'Automatic payment succeeded. Payment reference: %(ref)s. Amount: %(amount)s. Contract set to: In Progress, Next Invoice: %(inv)s. Email sent to customer.',
            ref=transaction._get_html_link(title=transaction.reference), amount=transaction.amount, inv=self.next_invoice_date)
        self.message_post(body=msg_body)
        if invoice.state != 'posted':
            invoice._post()
        invoice.is_move_sent = True
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
            subscription_values = {'end_date': current_date, 'payment_exception': False}
            # close the contract as needed
            self.set_close()
        else:
            msg_body = _('Automatic payment failed. Contract set to "To Renew". No email sent this time. Error: %s', transaction and transaction.state_message or _('No valid Payment Method'))

            if (fields.Date.today() - self.next_invoice_date).days in [2, 7, 14]:
                email_context.update({'date_close': date_close})
                reminder_mail_template.with_context(email_context).send_mail(self.id)
                _logger.debug("Sending Payment Failure Mail to %s for contract %s and setting contract to pending", self.partner_id.email, self.id)
                msg_body = _('Automatic payment failed. Contract set to "To Renew". Email sent to customer. Error: %s', transaction and transaction.state_message or _('No Payment Method'))
            self.message_post(body=msg_body)
            subscription_values = {'to_renew': True, 'payment_exception': False, 'is_batch': True}
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

    @api.model
    def _get_automatic_subscription_values(self):
        return {'to_renew': True}

    def _recurring_invoice_domain(self, extra_domain=None):
        if not extra_domain:
            extra_domain = []
        current_date = fields.Date.today()
        search_domain = [('is_batch', '=', False),
                         ('is_invoice_cron', '=', False),
                         ('is_subscription', '=', True),
                         ('subscription_management', '!=', 'upsell'),
                         ('state', 'in', ['sale', 'done']), # allow to close done subscription at the beginning of the invoicing cron
                         ('payment_exception', '=', False),
                         '&', '|', ('next_invoice_date', '<=', current_date), ('end_date', '<=', current_date), ('stage_category', '=', 'progress')]
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

            if (not subscription.state == 'sale' and subscription.stage_category == "progress") or subscription.payment_exception:
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
                    elif subscription.next_invoice_date <= today:
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
        automatic_values = self._get_automatic_subscription_values()
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
                            msg_body = _('Automatic payment failed. Contract set to "To Renew". No country specified on payment_token\'s partner')
                            order.message_post(body=msg_body)
                            order.with_context(mail_notrack=True).write(automatic_values)
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

    def cron_subscription_expiration(self):
        today = fields.Date.today()
        next_month = today + relativedelta(months=1)
        # set to pending if date is in less than a month
        domain_pending = [('is_subscription', '=', True), ('end_date', '<', next_month), ('stage_category', '=', 'progress')]
        subscriptions_pending = self.search(domain_pending)
        subscriptions_pending.set_to_renew()
        # set to close if date is passed or if locked sale order is passed
        domain_close = [
            ('is_subscription', '=', True),
            ('end_date', '<', today),
            ('state', 'in', ['sale', 'done']),
            '|',
            ('stage_category', '=', 'progress'),
            ('to_renew', '=', True)]
        subscriptions_close = self.search(domain_close)
        subscriptions_close.set_close()
        return dict(closed=subscriptions_close.ids)

    def _get_subscription_delta(self, date):
        self.ensure_one()
        delta, percentage = False, False
        subscription_log = self.env['sale.order.log'].search([
            ('order_id', '=', self.id),
            ('event_type', 'in', ['0_creation', '1_change', '2_transfer']),
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
                "\n- You should wait for the current subscription period to pass. New quantities to invoice will be ready "
                "at the end of the current period. \n  Negative recurring lines are considered free."
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
                            'renewed': True,
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
        return template.with_context(email_context).send_mail(invoice.id)

    @api.model
    def _process_invoices_to_send(self, account_moves):
        for invoice in account_moves:
            if not invoice.is_move_sent and invoice._is_ready_to_be_sent() and invoice.state == 'posted':
                subscription = invoice.line_ids.subscription_id
                subscription.validate_and_send_invoice(invoice)

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
        _logger.debug("Sending Invoice Mail to %s for subscription %s", self.partner_id.email, self.id)
        # ARJ TODO master: take the invoice template in the settings
        if self.sale_order_template_id.invoice_mail_template_id:
            invoice.with_context(email_context).message_post_with_source(
                self.sale_order_template_id.invoice_mail_template_id,
                force_send=False,
                subtype_xmlid='mail.mt_comment',
            )
        invoice.is_move_sent = True

    def _send_subscription_rating_mail(self, force_send=False):
        for subscription in self:
            if not subscription.stage_id.rating_template_id or not subscription.is_subscription:
                continue
            subscription.rating_send_request(
                subscription.stage_id.rating_template_id,
                lang=subscription.partner_id.lang,
                force_send=force_send)

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
            msg_body = _(
                "Manual payment succeeded. Payment reference: %s; Amount: %(amount)s. Invoice %(invoice)s",
                tx_model=tx._get_html_link(), amount=tx.amount,
                invoice=invoice._get_html_link(),
            )
            self.message_post(body=msg_body)
            return True
        return False

    def reconcile_pending_transaction(self, tx):
        """ Callback method to make the reconciliation.
        :param recordset tx: The transaction to reconcile, as a `payment.transaction` record
        :return: Whether the transaction was successfully reconciled
        """
        self.ensure_one()
        recurring_automatic = self.env.context.get('recurring_automatic') or True
        if tx.renewal_allowed:  # The payment is confirmed, it can be reconciled
            # avoid to create an invoice when one is already linked
            if not tx.invoice_ids:
                # Create the invoice that was either deleted in a controller or failed to be created by the _create_recurring_invoice method
                invoice = self.with_context(recurring_automatic=recurring_automatic)._create_invoices()
                invoice.write({'ref': tx.reference, 'payment_reference': tx.reference})
                # Only update the invoice date if there is already one invoice for the lines and when the so is not done
                # locked contract are finished or renewed
                invoice.message_post_with_source(
                    'mail.message_origin_link',
                    render_values={'self': invoice, 'origin': self},
                    subtype_xmlid='mail.mt_note',
                )
                tx.invoice_ids = invoice.id
            self.set_open()
            return True
        return False
