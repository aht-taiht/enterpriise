# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

from dateutil.relativedelta import relativedelta
from freezegun import freeze_time
import logging
from unittest.mock import patch

from odoo import api, fields, models


_logger = logging.getLogger(__name__)


class SaleOrder(models.Model):
    _name = "sale.order"
    _inherit = "sale.order"

    @api.model
    def _test_demo_flush_tracking(self):
        """ Force the creation of tracking values. """
        self.env.flush_all()
        self.env.cr.flush()

    def _test_demo_create_invoices(self, automatic=True):
        self._create_recurring_invoice(automatic=automatic)
        self.invoice_ids.filtered(lambda inv: inv.state == 'draft')._post(False)

    @api.model
    def _test_demo_generate_subscriptions(self):
        # Mocking for '_process_invoices_to_send'
        # Otherwise the whole sending mail process will be triggered and we don't want it in the post_init hook
        def _mock_process_invoices_to_send(account_moves, auto_commit):
            account_moves.is_move_sent = True

        with patch('odoo.addons.sale_subscription.models.sale_order.SaleOrder._process_invoices_to_send',
                  wraps=_mock_process_invoices_to_send):
            self._test_demo_generate_subscriptions_unpatched()

    def _test_demo_generate_subscriptions_unpatched(self):
        self._test_demo_flush_tracking()
        time_start = fields.Date.today() - relativedelta(years=1)
        subs_to_invoice = self.env['sale.order']
        with freeze_time(time_start.replace(day=1)):
            _logger.info('Generating Subscription historical data')
            sub_0 = self.env.ref('test_sale_subscription.test_subscription_portal_0', raise_if_not_found=False)
            sub_1 = self.env.ref('test_sale_subscription.test_subscription_portal_1', raise_if_not_found=False)
            if not sub_0 or not sub_1:
                _logger.error("Could not find demo data to use")
                return
            # Allows multiple -i of the module
            if sub_1.state == 'done':
                return

            subs_to_invoice |= sub_0 | sub_1
            # reset the dates that were defined "today", this allows to prevent the invoices in the past
            subs_to_invoice.start_date = False
            subs_to_invoice.next_invoice_date = False
            # prevent tu auto close the contract when the invoice cron run later than 15 days after the next_invoice_date
            subs_to_invoice.sale_order_template_id.auto_close_limit = 60
            subs_to_invoice.action_confirm()
            subs_to_invoice._test_demo_create_invoices()
            self._test_demo_flush_tracking()

        time_start = fields.Date.today() - relativedelta(months=11)
        with freeze_time(time_start.replace(day=10)):
            sub_1.order_line[0].product_uom_qty += 1
            subs_to_invoice._test_demo_create_invoices()
            self._test_demo_flush_tracking()

        time_start = fields.Date.today() - relativedelta(months=10)
        with freeze_time(time_start.replace(day=10)):
            subs_to_invoice._test_demo_create_invoices()
            self._test_demo_flush_tracking()

        # Upsell SO in the middle of the period
        time_start = fields.Date.today() - relativedelta(months=9)
        with freeze_time(time_start.replace(day=20)):
            subs_to_invoice._test_demo_create_invoices()
            action = sub_0.prepare_upsell_order()
            upsell_so = self.env['sale.order'].browse(action['res_id'])
            upsell_so.order_line[0].product_uom_qty += 1
            upsell_so.action_confirm()
            upsell_so._test_demo_create_invoices()
            self._test_demo_flush_tracking()

        time_start = fields.Date.today() - relativedelta(months=8)
        with freeze_time(time_start.replace(day=10)):
            subs_to_invoice._test_demo_create_invoices()
            self._test_demo_flush_tracking()

        # Renew
        time_start = fields.Date.today() - relativedelta(months=7)
        with freeze_time(time_start.replace(day=10)):
            action = sub_1.prepare_renewal_order()
            renew_so_1 = self.env['sale.order'].browse(action['res_id'])
            renew_so_1.order_line[0].product_uom_qty = 1
            renew_so_1.order_line[1].product_uom_qty = 4
            renew_so_1.order_line[2].product_uom_qty = 2
            renew_so_1.action_confirm()
            renew_so_1._test_demo_create_invoices()
            subs_to_invoice |= renew_so_1
            self._test_demo_flush_tracking()

        time_start = fields.Date.today() - relativedelta(months=6)
        with freeze_time(time_start.replace(day=10)):
            sub_2 = self.env.ref('test_sale_subscription.test_subscription_portal_2')
            # reset the dates that were defined "today", this allows to prevent the invoices in the past
            sub_2.start_date = False
            sub_2.next_invoice_date = False
            self._test_demo_flush_tracking()
            sub_2.action_confirm()
            subs_to_invoice |= sub_2
            subs_to_invoice._test_demo_create_invoices()
            self._test_demo_flush_tracking()

        time_start = fields.Date.today() - relativedelta(months=5)
        with freeze_time(time_start.replace(day=10)):
            subs_to_invoice._test_demo_create_invoices()
            self._test_demo_flush_tracking()

        time_start = fields.Date.today() - relativedelta(months=4)
        with freeze_time(time_start.replace(day=10)):
            action = sub_2.prepare_renewal_order()
            renew_so_2 = self.env['sale.order'].browse(action['res_id'])
            renew_so_2.order_line[0].product_uom_qty = 6
            self._test_demo_flush_tracking()
            renew_so_2.action_confirm()
            subs_to_invoice |= renew_so_2
            subs_to_invoice._test_demo_create_invoices()
            self._test_demo_flush_tracking()

        time_start = fields.Date.today() - relativedelta(months=3)
        with freeze_time(time_start.replace(day=10)):
            subs_to_invoice._test_demo_create_invoices()
            self._test_demo_flush_tracking()

        time_start = fields.Date.today() - relativedelta(months=2)
        with freeze_time(time_start.replace(day=10)):
            sub_3 = self.env.ref('test_sale_subscription.test_subscription_portal_3')
            # reset the dates that were defined "today", this allows to prevent the invoices in the past
            sub_3.start_date = False
            sub_3.next_invoice_date = False
            sub_3.order_line.product_uom_qty = 3
            sub_3.action_confirm()
            subs_to_invoice |= sub_3
            subs_to_invoice._test_demo_create_invoices()
            self._test_demo_flush_tracking()
            self._test_demo_flush_tracking()

        time_start = fields.Date.today() - relativedelta(months=1) + relativedelta(days=10)
        with freeze_time(time_start.replace(day=10)):
            sub_4 = self.env.ref('test_sale_subscription.test_subscription_portal_4')
            # reset the dates that were defined "today", this allows to prevent the invoices in the past
            sub_4.start_date = False
            sub_4.next_invoice_date = False
            sub_4.order_line.product_uom_qty = 2
            sub_4.action_confirm()
            subs_to_invoice |= sub_4
            subs_to_invoice._test_demo_create_invoices()
            sub_3.order_line.product_uom_qty = 1
            self._test_demo_flush_tracking()

        time_start = fields.Date.today() - relativedelta(days=10)
        with freeze_time(time_start):
            subs_to_invoice._test_demo_create_invoices()
            renew_so_1.order_line[0].product_uom_qty += 1 # 2
            renew_so_2.order_line[0].product_uom_qty += 1 # 7
            sub_3.action_cancel()
            self._test_demo_flush_tracking()

        time_start = fields.Date.today() - relativedelta(days=2)
        with freeze_time(time_start):
            subs_to_invoice._test_demo_create_invoices()
            renew_so_1.order_line[0].product_uom_qty += 1 # 3
            renew_so_2.order_line[0].product_uom_qty += 1 # 8
            self._test_demo_flush_tracking()

        subs_to_invoice.filtered(lambda so: so.state == 'sale')._test_demo_create_invoices(automatic=False)
        subs_to_invoice.to_renew = False
