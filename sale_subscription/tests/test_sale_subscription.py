# -*- coding: utf-8 -*-
import datetime
from dateutil.relativedelta import relativedelta
from freezegun import freeze_time
from markupsafe import Markup

from odoo.addons.sale_subscription.tests.common_sale_subscription import TestSubscriptionCommon
from odoo.tests import Form, tagged
from odoo.tools import mute_logger
from odoo import fields, Command
from odoo.exceptions import ValidationError


@tagged('post_install', '-at_install')
class TestSubscription(TestSubscriptionCommon):

    def flush_tracking(self):
        """ Force the creation of tracking values. """
        self.env['base'].flush()
        self.cr.precommit.run()
        self.cr.flush()


    def setUp(self):
        super(TestSubscription, self).setUp()
        self.flush_tracking()

    def _get_quantities(self, order_line):
        order_line = order_line.sorted('pricing_id')
        values = {
                  'delivered_qty': order_line.mapped('qty_delivered'),
                  'qty_delivered_method': order_line.mapped('qty_delivered_method'),
                  'to_invoice': order_line.mapped('qty_to_invoice'),
                  'invoiced': order_line.mapped('qty_invoiced'),
                  }
        return values

    @mute_logger('odoo.addons.base.models.ir_model', 'odoo.models')
    def test_automatic(self):
        self.assertTrue(True)
        sub = self.subscription
        context_no_mail = {'no_reset_password': True, 'mail_create_nosubscribe': True, 'mail_create_nolog': True, }
        sub_product_tmpl = self.env['product.template'].with_context(context_no_mail).create({
            'name': 'Subscription Product',
            'type': 'service',
            'recurring_invoice': True,
            'uom_id': self.env.ref('uom.product_uom_unit').id,
        })
        product = sub_product_tmpl.product_variant_id
        template = self.env['sale.order.template'].create({
            'name': 'Subscription template without discount',
            'recurring_rule_type': 'year',
            'recurring_rule_boundary': 'limited',
            'recurring_rule_count': 2,
            'user_closable': True,
            'payment_mode': 'draft_invoice',
            'auto_close_limit': 3,
            'sale_order_template_line_ids': [Command.create({
                'name': "monthly",
                'product_id': product.id,
                'pricing_id': self.pricing_month.id,
                'product_uom_id': product.uom_id.id
            }),
                Command.create({
                    'name': "yearly",
                    'product_id': product.id,
                    'pricing_id': self.pricing_year.id,
                    'product_uom_id': product.uom_id.id,
                })
            ]

        })
        self.company = self.env.company

        self.acquirer = self.env['payment.acquirer'].create(
            {'name': 'The Wire',
             'provider': 'transfer',
             'company_id': self.company.id,
             'state': 'test',
             'redirect_form_view_id': self.env['ir.ui.view'].search([('type', '=', 'qweb')], limit=1).id})

        self.payment_method = self.env['payment.token'].create(
            {'name': 'Jimmy McNulty',
             'partner_id': sub.partner_id.id,
             'acquirer_id': self.acquirer.id,
             'acquirer_ref': 'Omar Little'})
        sub.payment_token_id = self.payment_method.id
        sub.sale_order_template_id = template.id
        sub._onchange_sale_order_template_id()
        with freeze_time("2021-01-03"):
            self.subscription.order_line.write({'start_date': False, 'next_invoice_date': False})
            sub.action_confirm()
            self.assertEqual(sub.invoice_count, 0)
            self.env['sale.order']._cron_recurring_create_invoice()
            lines = sub.order_line.sorted('next_invoice_date')
            self.assertEqual([datetime.datetime(2021, 1, 3), datetime.datetime(2021, 1, 3)], lines.mapped('start_date'), 'start date should be reset at confirmation')
            self.assertEqual([datetime.datetime(2021, 2, 3), datetime.datetime(2022, 1, 3)], lines.mapped('next_invoice_date'), 'next invoice date should be updated')
            inv = sub.invoice_ids.sorted('date')[-1]
            inv_line = inv.invoice_line_ids.sorted('id')[0]
            invoice_periods = inv_line.name.split('\n')[1]
            self.assertEqual(invoice_periods, "01/03/2021 to 02/03/2021")
            self.assertEqual(inv_line.date, datetime.date(2021, 1, 3))

        with freeze_time("2021-02-03"):
            self.assertEqual(sub.invoice_count, 1)
            self.env['sale.order']._cron_recurring_create_invoice()
            self.assertEqual(sub.invoice_count, 2)
            lines = sub.order_line.sorted('next_invoice_date')
            self.assertEqual([datetime.datetime(2021, 1, 3), datetime.datetime(2021, 1, 3)], lines.mapped('start_date'))
            self.assertEqual([datetime.datetime(2021, 3, 3), datetime.datetime(2022, 1, 3)], lines.mapped('next_invoice_date'))
            inv = sub.invoice_ids.sorted('date')[-1]
            invoice_periods = inv.invoice_line_ids.name.split('\n')[1]
            self.assertEqual(invoice_periods, "02/03/2021 to 03/03/2021")
            self.assertEqual(inv.invoice_line_ids.date, datetime.date(2021, 2, 3))

        with freeze_time("2021-03-03"):
            self.env['sale.order']._cron_recurring_create_invoice()
            self.assertEqual([datetime.datetime(2021, 1, 3), datetime.datetime(2021, 1, 3)], lines.mapped('start_date'))
            self.assertEqual([datetime.datetime(2021, 4, 3), datetime.datetime(2022, 1, 3)], lines.mapped('next_invoice_date'))
            inv = sub.invoice_ids.sorted('date')[-1]
            invoice_periods = inv.invoice_line_ids.name.split('\n')[1]
            self.assertEqual(invoice_periods, "03/03/2021 to 04/03/2021")
            self.assertEqual(inv.invoice_line_ids.date, datetime.date(2021, 3, 3))

    @mute_logger('odoo.addons.base.models.ir_model', 'odoo.models')
    def test_template(self):
        """ Test behaviour of on_change_template """
        Subscription = self.env['sale.order']
        self.assertEqual(self.subscription.note, Markup('<p>original subscription description</p>'), "Original subscription note")
        # on_change_template on cached record (NOT present in the db)
        temp = Subscription.new({'name': 'CachedSubscription',
                                 'partner_id': self.user_portal.partner_id.id})
        temp.update({'sale_order_template_id': self.subscription_tmpl.id})
        temp._onchange_sale_order_template_id()
        self.assertEqual(temp.note, Markup('<p>This is the template description</p>'), 'Override the subscription note')

    @mute_logger('odoo.addons.base.models.ir_model', 'odoo.models')
    def test_unlimited_sale_order(self):
        """ Test behaviour of on_change_template """
        with freeze_time("2021-01-03"):
            sub = self.subscription
            sub.order_line = [Command.clear()]
            context_no_mail = {'no_reset_password': True, 'mail_create_nosubscribe': True, 'mail_create_nolog': True, }
            sub_product_tmpl = self.env['product.template'].with_context(context_no_mail).create({
                'name': 'Subscription Product',
                'type': 'service',
                'recurring_invoice': True,
                'uom_id': self.env.ref('uom.product_uom_unit').id,
            })
            product = sub_product_tmpl.product_variant_id
            sub.order_line = [Command.create({'product_id': product.id,
                                              'name': "coucou",
                                              'price_unit': 42,
                                              'product_uom_qty': 2,
                                              'pricing_id': self.pricing_month.id,
                                              })]
            sub.action_confirm()
            self.assertFalse(sub.order_line.last_invoice_date)
            self.assertEqual("2021-01-03", sub.order_line.start_date.strftime("%Y-%m-%d"))
            self.assertEqual("2021-02-03", sub.order_line.next_invoice_date.strftime("%Y-%m-%d"))

            sub._create_recurring_invoice(automatic=True)
            # Next invoice date should not be bumped up because it is the first period
            self.assertEqual("2021-02-03", sub.order_line.next_invoice_date.strftime("%Y-%m-%d"))

            invoice_periods = sub.invoice_ids.invoice_line_ids.name.split('\n')[1]
            self.assertEqual(invoice_periods, "01/03/2021 to 02/03/2021")
            self.assertEqual(sub.invoice_ids.invoice_line_ids.date, datetime.date(2021, 1, 3))
        with freeze_time("2021-02-03"):
            # February
            sub._create_recurring_invoice(automatic=True)
            self.assertEqual("2021-02-03", sub.order_line.last_invoice_date.strftime("%Y-%m-%d"))
            self.assertEqual("2021-03-03", sub.order_line.next_invoice_date.strftime("%Y-%m-%d"))
            inv = sub.invoice_ids.sorted('date')[-1]
            invoice_periods = inv.invoice_line_ids.name.split('\n')[1]
            self.assertEqual(invoice_periods, "02/03/2021 to 03/03/2021")
            self.assertEqual(inv.invoice_line_ids.date, datetime.date(2021, 2, 3))
        with freeze_time("2021-03-03"):
            # March
            sub._create_recurring_invoice(automatic=True)
            self.assertEqual("2021-03-03", sub.order_line.last_invoice_date.strftime("%Y-%m-%d"))
            self.assertEqual("2021-04-03", sub.order_line.next_invoice_date.strftime("%Y-%m-%d"))
            inv = sub.invoice_ids.sorted('date')[-1]
            invoice_periods = inv.invoice_line_ids.name.split('\n')[1]
            self.assertEqual(invoice_periods, "03/03/2021 to 04/03/2021")
            self.assertEqual(inv.invoice_line_ids.date, datetime.date(2021, 3, 3))

    def test_auto_close(self):
        """Ensure a 15 days old 'online payment' subscription gets closed if no token is set."""
        self.subscription_tmpl.payment_mode = 'success_payment'
        self.subscription.action_confirm()
        # Put next invoice date in the past
        self.subscription.order_line.write({'next_invoice_date': fields.Date.today() - relativedelta(days=17)})
        self.env['sale.order']._cron_recurring_create_invoice()
        self.assertEqual(self.subscription.stage_category, 'closed', 'website_contract: subscription with online payment and no payment method set should get closed after 15 days')

    @mute_logger('odoo.models.unlink')
    def test_renewal(self):
        """ Test subscription renewal """
        with freeze_time("2021-11-18"):
            self.subscription.order_line.write({'start_date': False, 'next_invoice_date': False})
            # add an so line with a different uom
            uom_dozen = self.env.ref('uom.product_uom_dozen').id
            self.subscription_tmpl.recurring_rule_count = 3 # end after 3 years to adapt to the following line
            pricing_3_year = self.env['product.pricing'].create({'duration': 3, 'unit': 'year', 'price': 50, 'product_template_id': self.product.product_tmpl_id.id})
            self.env['sale.order.line'].create({'name': self.product.name,
                                                'order_id': self.subscription.id,
                                                'product_id': self.product.id,
                                                'product_uom_qty': 42,
                                                'pricing_id': pricing_3_year.id,
                                                'product_uom': uom_dozen,
                                                'price_unit': 42})

            self.subscription.action_confirm()
            self.assertEqual(self.subscription.end_date, datetime.date(2024, 11, 17), 'The end date of the subscription should be updated according to the template')
            self.assertFalse(self.subscription.to_renew)
            next_invoice_dates = self.subscription.mapped('order_line').sorted('id').mapped('next_invoice_date')
            self.assertEqual(next_invoice_dates, [datetime.datetime(2021, 12, 18), datetime.datetime(2022, 11, 18), datetime.datetime(2024, 11, 18)])

        with freeze_time("2024-11-1"):
            self.env['sale.order'].cron_subscription_expiration()
            self.assertTrue(self.subscription.to_renew)

            action = self.subscription.prepare_renewal_order()
            renewal_so = self.env['sale.order'].browse(action['res_id'])
            # check produt_uom_qty
            self.assertEqual(renewal_so.sale_order_template_id.id, self.subscription.sale_order_template_id.id,
                             'sale_subscription: renewal so should have the same template')
            renewal_so.action_confirm()
            self.assertFalse(self.subscription.to_renew, 'sale_subscription: confirm the renewal order should remove the to_renew flag of parent')
            self.assertEqual(self.subscription.recurring_monthly, 49, 'Only the last line is still ongoing on 2023-11-1')
            self.assertEqual(renewal_so.subscription_management, 'renew', 'so should be set to "renew" in the renewal process')
            self.assertEqual(renewal_so.date_order.date(), self.subscription.end_date, 'renewal start date should depends on the parent end date')

            line_values = [(line.product_uom_qty, line.pricing_id.id, line.start_date,
                            line.next_invoice_date, line.product_uom.id,) for line in renewal_so.mapped('order_line').sorted('id')]
            # First, all quantity are equal to 0. The salesman has to edit the SO before confirmation
            self.assertEqual(line_values[0], (0, self.pricing_month.id, datetime.datetime(2021, 12, 18), datetime.datetime(2022, 1, 18), self.product.uom_id.id), 'First line start after next invoice')
            self.assertEqual(line_values[1], (0, self.pricing_year.id, datetime.datetime(2022, 11, 18), datetime.datetime(2023, 11, 18), self.product.uom_id.id), 'Second line is kept')
            self.assertEqual(line_values[2], (0, pricing_3_year.id, datetime.datetime(2024, 11, 18), datetime.datetime(2027, 11, 18), uom_dozen), 'Third line is kept')

        with freeze_time("2024-11-19"):
            self.env['sale.order'].cron_subscription_expiration()
            renew_close_reason_id = self.env.ref('sale_subscription.close_reason_renew').id
            self.assertEqual(self.subscription.stage_category, 'closed')
            self.assertEqual(self.subscription.close_reason_id.id, renew_close_reason_id)

    def test_upsell_via_so(self):
        # Test the upsell flow using an intermediary upsell quote.
        princing_2_month = self.env['product.pricing'].create({'duration': 2, 'unit': 'month', 'price': 50, 'product_template_id': self.product.product_tmpl_id.id})
        princing_6_month2 = self.env['product.pricing'].create({'duration': 6, 'unit': 'month', 'price': 20, 'product_template_id': self.product2.product_tmpl_id.id})
        princing_6_month3 = self.env['product.pricing'].create({'duration': 6, 'unit': 'month', 'price': 15, 'product_template_id': self.product3.product_tmpl_id.id})
        with freeze_time("2021-01-01"):
            self.subscription.order_line = False
            self.subscription.write({
                'partner_id': self.partner.id,
                'order_line': [Command.create({'product_id': self.product.id,
                                               'name': "month",
                                               'price_unit': 42,
                                               'product_uom_qty': 2,
                                               'pricing_id': self.pricing_month.id,
                                               }),
                               Command.create({'product_id': self.product.id,
                                               'name': "2 month",
                                               'price_unit': 420,
                                               'product_uom_qty': 3,
                                               'pricing_id': princing_2_month.id
                                               }),
                               ]
            })
            self.subscription.action_confirm()
            self.env['sale.order']._cron_recurring_create_invoice()
            self.assertEqual(self.subscription.order_line.sorted('pricing_id').mapped('product_uom_qty'), [2, 3], "Quantities should be equal to 2 and 3")
        with freeze_time("2021-01-15"):
            action = self.subscription.prepare_upsell_order()
            upsell_so = self.env['sale.order'].browse(action['res_id'])
            self.assertEqual(upsell_so.order_line.mapped('product_uom_qty'), [0, 0], 'The upsell order has 0 quantity')
            upsell_names = upsell_so.order_line.sorted('id').mapped('name')
            line1_period = upsell_names[0].split('\n')[1]
            self.assertEqual(line1_period, '01/15/2021 to 01/31/2021', "Prorated duration correspond to the dates")
            line2_period = upsell_names[1].split('\n')[1]
            self.assertEqual(line2_period, '01/15/2021 to 02/28/2021', "Prorated duration correspond to the dates")

            upsell_so.order_line.product_uom_qty = 1
            # When the upsell order is created, all quantities are equal to 0
            # add line to quote manually, it must be taken into account in the subscription after validation
            so_line_vals = [{
                'name': self.product2.name,
                'order_id': upsell_so.id,
                'product_id': self.product2.id,
                'product_uom_qty': 2,
                'product_uom': self.product2.uom_id.id,
                'price_unit': self.product2.list_price,
                'pricing_id': princing_6_month2.id # start now, will be next invoiced in 6 months, on the 15 of July
            }, {
                'name': self.product3.name,
                'order_id': upsell_so.id,
                'product_id': self.product3.id,
                'product_uom_qty': 1,
                'product_uom': self.product3.uom_id.id,
                'price_unit': self.product3.list_price,
                'pricing_id': princing_6_month3.id,
                'start_date': datetime.datetime(2021, 6, 1), # start in june
            }]

            new_line = self.env['sale.order.line'].create(so_line_vals)
            upsell_so.action_confirm()
            discounts = [round(v, 2) for v in upsell_so.order_line.sorted('pricing_id').mapped('discount')]
            self.assertEqual(discounts, [45.16, 23.73, 0.0, 0.0], 'Prorated prices should be applied')
            prices = [round(v, 2) for v in upsell_so.order_line.sorted('pricing_id').mapped('price_subtotal')]
            self.assertEqual(prices, [27.42, 38.14, 40, 42], 'Prorated prices should be applied')

            upsell_so._create_invoices()
            last_invoice_line_name = upsell_so.invoice_ids.line_ids.sorted('id')[2].name.split('\n')[1]
            self.assertEqual(last_invoice_line_name, '01/15/2021 to 07/14/2021 - 6 month',
                             "The upsell invoice take into account the first period, the line is valid 6 months.")

            sorted_lines = self.subscription.order_line.sorted('pricing_id')
            self.assertEqual(sorted_lines.mapped('product_uom_qty'), [3, 4, 2, 1], "Quantities should be equal to 3, 4, 2")
            new_line_starting_now = sorted_lines[2]
            self.assertEqual([new_line_starting_now.start_date, new_line_starting_now.next_invoice_date], [datetime.datetime(2021, 1, 15), datetime.datetime(2021, 7, 15)], "The upsell invoice take into account the first period")

        with freeze_time("2021-02-01"):
            self.env['sale.order']._cron_recurring_create_invoice()
        with freeze_time("2021-03-01"):
            self.env['sale.order']._cron_recurring_create_invoice()
        with freeze_time("2021-04-01"):
            self.env['sale.order']._cron_recurring_create_invoice()
        with freeze_time("2021-05-01"):
            self.env['sale.order']._cron_recurring_create_invoice()

        with freeze_time("2021-06-01"):
            self.subscription._create_recurring_invoice(automatic=True)
            inv = self.subscription.invoice_ids.sorted('date')[-1]
            invoice_periods = inv.invoice_line_ids.sorted('id').mapped('name')
            first_period = invoice_periods[0].split('\n')[1]
            self.assertEqual(first_period, "06/01/2021 to 07/01/2021")
            second_period = invoice_periods[1].split('\n')[1]
            self.assertEqual(second_period, "06/01/2021 to 12/01/2021")

        self.assertEqual(self.subscription, new_line.order_id.subscription_id,
                         'sale_subscription: upsell line added to quote after creation but before validation must be automatically  linked to correct subscription')
        self.assertEqual(len(self.subscription.order_line), 4)

    def test_upsell_prorata(self):
        """ Test the prorated values obtained when creating an upsell. complementary to the previous one where new
         lines had no existing default values.
        """
        princing_2_month = self.env['product.pricing'].create({'duration': 2, 'unit': 'month'})
        with freeze_time("2021-01-01"):
            self.subscription.order_line = False
            self.subscription.write({
                'partner_id': self.partner.id,
                'order_line': [
                    Command.create({
                        'product_id': self.product.id,
                        'name': "month: original",
                        'price_unit': 50,
                        'product_uom_qty': 1,
                        'pricing_id': self.pricing_month.id,
                        'start_date': '2021-01-01'
                    }),
                    Command.create({
                        'product_id': self.product.id,
                        'name': "2 month: original",
                        'price_unit': 50,
                        'product_uom_qty': 1,
                        'pricing_id': princing_2_month.id,
                        'start_date': '2021-01-01'
                    }),
                    Command.create({
                        'product_id': self.product2.id,
                        'name': "1 month: original shifted",
                        'price_unit': 50,
                        'product_uom_qty': 1,
                        'pricing_id': self.pricing_month.id,
                        'start_date': '2021-01-10',
                    }),
                ]
            })
            self.subscription.action_confirm()

        with freeze_time("2021-01-20"):
            action = self.subscription.prepare_upsell_order()
            upsell_so = self.env['sale.order'].browse(action['res_id'])
            # Create new lines that should be aligned with existing ones
            so_line_vals = [{
                'name': 'Upsell added: 1 month',
                'order_id': upsell_so.id,
                'product_id': self.product2.id,
                'product_uom_qty': 1,
                'product_uom': self.product2.uom_id.id,
                'price_unit': self.product.list_price,
                'pricing_id': self.pricing_month.id
            }, {
                'name': 'Upsell added: 2 month',
                'order_id': upsell_so.id,
                'product_id': self.product3.id,
                'product_uom_qty': 1,
                'product_uom': self.product3.uom_id.id,
                'price_unit': self.product3.list_price,
                'pricing_id': princing_2_month.id,
            }]
            self.env['sale.order.line'].create(so_line_vals)
            upsell_so.order_line.product_uom_qty = 1
            discounts = [round(v) for v in upsell_so.order_line.sorted('pricing_id').mapped('discount')]
            # discounts for: 12d/31d; 40d/59d; 21d/31d (shifted); 31d/41d; 59d/78d;
            self.assertEqual(discounts, [61, 32, 32, 24, 24], 'Prorated prices should be applied')
            prices = [round(v, 2) for v in upsell_so.order_line.sorted('pricing_id').mapped('price_subtotal')]
            self.assertEqual(prices, [19.36, 33.9, 13.55, 15.12, 31.77], 'Prorated prices should be applied')

    def test_recurring_revenue(self):
        """Test computation of recurring revenue"""
        pricing_4_year = self.env['product.pricing'].create({'duration': 4, 'unit': 'year', 'price': 50, 'product_template_id': self.product.product_tmpl_id.id})
        pricing_2_month = self.env['product.pricing'].create({'duration': 2, 'unit': 'month', 'price': 50, 'product_template_id': self.product.product_tmpl_id.id})
        # Initial subscription is $100/y
        self.subscription_tmpl.write({'recurring_rule_count': 1, 'recurring_rule_type': 'year'})
        self.subscription.write({
            'partner_id': self.partner.id,
            'company_id': self.company.id,
            'payment_token_id': self.payment_method.id,
        })

        self.subscription.order_line.filtered(lambda l: l.pricing_id.unit == 'year').write({'price_unit': 1200})
        self.subscription.order_line.filtered(lambda l: l.pricing_id.unit == 'month').write({'price_unit': 200})
        self.subscription.action_confirm()
        self.assertAlmostEqual(self.subscription.amount_untaxed, 1400, msg="unexpected price after setup")
        self.assertAlmostEqual(self.subscription.recurring_monthly, 300, msg="unexpected MRR")
        # Change periodicity
        self.subscription.order_line.filtered(lambda l: l.pricing_id.unit == 'year').write({'pricing_id': pricing_4_year.id})
        self.subscription.order_line.filtered(lambda l: l.pricing_id.unit == 'month').write({'pricing_id': pricing_2_month.id})
        self.assertAlmostEqual(self.subscription.amount_untaxed, 100, msg='total should not change when interval changes')
        # 1200 over 4 year = 25/year + 100 per month
        self.assertAlmostEqual(self.subscription.recurring_monthly, 26.04, msg='unexpected MRR')

    def test_compute_kpi(self):
        self.subscription_tmpl.write({'good_health_domain': "[('recurring_monthly', '>=', 120.0)]",
                                      'bad_health_domain': "[('recurring_monthly', '<=', 80.0)]",
                                      })
        self.subscription.recurring_monthly = 80.0
        self.subscription.action_confirm()
        self.env['sale.order']._cron_update_kpi()
        self.assertEqual(self.subscription.health, 'bad')

        # 16 to 6 weeks: 80
        # 6 to 2 weeks: 100
        # 2weeks - today : 120
        date_log = datetime.date.today() - relativedelta(weeks=16)
        self.env['sale.order.log'].sudo().create({
            'event_type': '1_change',
            'event_date': date_log,
            'create_date': date_log,
            'order_id': self.subscription.id,
            'recurring_monthly': 80,
            'amount_signed': 80,
            'currency_id': self.subscription.currency_id.id,
            'category': self.subscription.stage_category,
            'user_id': self.subscription.user_id.id,
            'team_id': self.subscription.team_id.id,
        })

        date_log = datetime.date.today() - relativedelta(weeks=6)
        self.env['sale.order.log'].sudo().create({
            'event_type': '1_change',
            'event_date': date_log,
            'create_date': date_log,
            'order_id': self.subscription.id,
            'recurring_monthly': 100,
            'amount_signed': 20,
            'currency_id': self.subscription.currency_id.id,
            'category': self.subscription.stage_category,
            'user_id': self.subscription.user_id.id,
            'team_id': self.subscription.team_id.id,
         })

        self.subscription.recurring_monthly = 120.0
        date_log = datetime.date.today() - relativedelta(weeks=2)
        self.env['sale.order.log'].sudo().create({
            'event_type': '1_change',
            'event_date': date_log,
            'create_date': date_log,
            'order_id': self.subscription.id,
            'recurring_monthly': 120,
            'amount_signed': 20,
            'currency_id': self.subscription.currency_id.id,
            'category': self.subscription.stage_category,
            'user_id': self.subscription.user_id.id,
            'team_id': self.subscription.team_id.id,
        })
        self.subscription._cron_update_kpi()
        self.assertEqual(self.subscription.kpi_1month_mrr_delta, 20.0)
        self.assertEqual(self.subscription.kpi_1month_mrr_percentage, 0.2)
        self.assertEqual(self.subscription.kpi_3months_mrr_delta, 40.0)
        self.assertEqual(self.subscription.kpi_3months_mrr_percentage, 0.5)
        self.assertEqual(self.subscription.health, 'done')

    def test_onchange_date_start(self):
        recurring_bound_tmpl = self.env['sale.order.template'].create({
            'name': 'Recurring Bound Template',
            'recurring_rule_boundary': 'limited',
            'recurring_rule_type': 'month',
            'recurring_rule_count': 1,
            'sale_order_template_line_ids': [Command.create({
                'name': "monthly",
                'product_id': self.product.id,
                'pricing_id': self.pricing_month.id,
                'product_uom_qty': 1,
                'product_uom_id': self.product.uom_id.id
            })]
        })
        sub_form = Form(self.env['sale.order'])
        sub_form.partner_id = self.user_portal.partner_id
        sub_form.sale_order_template_id = recurring_bound_tmpl
        sub = sub_form.save()
        sub._onchange_sale_order_template_id()
        # The end date is set upon confirmation
        sub.action_confirm()
        self.assertEqual(sub.sale_order_template_id.recurring_rule_boundary, 'limited')
        self.assertIsInstance(sub.end_date, datetime.date)

    def test_changed_next_invoice_date(self):
        # Test wizard to change next_invoice_date manually
        with freeze_time("2022-01-01"):
            self.subscription.order_line.write({'start_date': False, 'next_invoice_date': False})
            self.env['sale.order.line'].create({
                'name': self.product2.name,
                'order_id': self.subscription.id,
                'product_id': self.product2.id,
                'product_uom_qty': 3,
                'pricing_id': self.pricing_month.id,
                'product_uom': self.product2.uom_id.id,
                'price_unit': 42})

            self.subscription.action_confirm()
            self.subscription._create_recurring_invoice(automatic=True)
            today = fields.Datetime.today()
            start_date = self.subscription.order_line.mapped('start_date')
            self.assertEqual(start_date, [today, today, today], "All start date should be set to today")

            next_invoice_dates = self.subscription.order_line.sorted('pricing_id').mapped('next_invoice_date')
            self.assertEqual(next_invoice_dates, [datetime.datetime(2022, 2, 1), datetime.datetime(2023, 1, 1), datetime.datetime(2022, 2, 1)])
            # We decide to invoice the monthly subscription on the 5 of february
            sols = self.subscription.order_line.filtered(lambda l: l.next_invoice_date == fields.Datetime.from_string('2022-02-01'))
            sols.next_invoice_date = fields.Datetime.from_string('2022-02-05')

        with freeze_time("2022-02-01"):
            next_invoice_dates = self.subscription.order_line.sorted('next_invoice_date').mapped('next_invoice_date')
            self.assertEqual(next_invoice_dates, [datetime.datetime(2022, 2, 5), datetime.datetime(2022, 2, 5), datetime.datetime(2023, 1, 1)])
            # Nothing should be invoiced
            self.subscription._cron_recurring_create_invoice()
            # next_invoice_date : 2022-02-5 but the previous invoice subscription_end_date was set on the 2022-02-01
            # We can't prevent it to be re-invoiced.
            inv = self.subscription.invoice_ids.sorted('date')
            # Nothing was invoiced
            self.assertEqual(inv.date, datetime.date(2022, 1, 1))

        with freeze_time("2022-02-05"):
            self.env['sale.order']._cron_recurring_create_invoice()
            inv = self.subscription.invoice_ids.sorted('date')
            self.assertEqual(inv[-1].date, datetime.date(2022, 2, 5))

    def test_product_change(self):
        """Check behaviour of the product onchange (taxes mostly)."""
        # check default tax
        self.subscription.order_line.unlink()
        sub_form = Form(self.subscription)
        with sub_form.order_line.new() as line:
            line.product_id = self.product
        sub = sub_form.save()
        self.assertEqual(sub.order_line.product_id.taxes_id, self.tax_10, 'Default tax for product should have been applied.')
        self.assertEqual(sub.amount_tax, 5.0,
                         'Default tax for product should have been applied.')
        self.assertEqual(sub.amount_total, 55.0,
                         'Default tax for product should have been applied.')
        # Change the product
        line_id = sub.order_line.ids
        sub.write({
            'order_line': [(1, line_id[0], {'product_id': self.product4.id})]
        })
        self.assertEqual(sub.order_line.product_id.taxes_id, self.tax_20,
                         'Default tax for product should have been applied.')
        self.assertEqual(sub.amount_tax, 3,
                         'Default tax for product should have been applied.')
        self.assertEqual(sub.amount_total, 18,
                         'Default tax for product should have been applied.')

    def test_log_change_pricing(self):
        """ Test subscription log generation when template_id is changed """
        # Create a subscription and add a line, should have logs with MMR 120
        pricing_month = self.env['product.pricing'].create({'duration': 1, 'unit': 'month', 'price': 120})
        pricing_year = self.env['product.pricing'].create({'duration': 1, 'unit': 'year', 'price': 120})
        self.sub_product_tmpl.product_pricing_ids = [Command.set(pricing_month.ids + pricing_year.ids)]
        subscription = self.env['sale.order'].create({
            'name': 'TestSubscription',
            'is_subscription': True,
            'partner_id': self.user_portal.partner_id.id,
            'pricelist_id': self.env.ref('product.list0').id,
            'sale_order_template_id': self.subscription_tmpl.id,
        })
        self.cr.precommit.clear()
        subscription.write({'order_line': [(0, 0, {
            'name': 'TestRecurringLine',
            'product_id': self.product.id,
            'product_uom_qty': 1,
            'pricing_id': pricing_month.id,
            'product_uom': self.product.uom_id.id})]})
        subscription.action_confirm()
        self.flush_tracking()
        init_nb_log = len(subscription.order_log_ids)
        self.assertEqual(subscription.order_line.recurring_monthly, 120)
        subscription.order_line.write({'pricing_id': pricing_year.id})
        self.assertEqual(subscription.order_line.recurring_monthly, 10)
        self.flush_tracking()
        # Should get one more log with MRR 10 (so change is -110)
        self.assertEqual(len(subscription.order_log_ids), init_nb_log + 1,
                         "Subscription log not generated after change of the subscription template")
        self.assertRecordValues(subscription.order_log_ids[-1],
                                [{'recurring_monthly': 10.0, 'amount_signed': -110}])

    def test_fiscal_position(self):
        # Test that the fiscal postion FP is applied on recurring invoice.
        # FP must mapped an included tax of 21% to an excluded one of 0%
        tax_include_id = self.env['account.tax'].create({'name': "Include tax",
                                                         'amount': 21.0,
                                                         'price_include': True,
                                                         'type_tax_use': 'sale'})
        tax_exclude_id = self.env['account.tax'].create({'name': "Exclude tax",
                                                         'amount': 0.0,
                                                         'type_tax_use': 'sale'})

        product_tmpl = self.env['product.template'].create(dict(name="Voiture",
                                                                list_price=121,
                                                                taxes_id=[(6, 0, [tax_include_id.id])]))

        fp = self.env['account.fiscal.position'].create({'name': "fiscal position",
                                                         'sequence': 1,
                                                         'auto_apply': True,
                                                         'tax_ids': [(0, 0, {'tax_src_id': tax_include_id.id,
                                                                             'tax_dest_id': tax_exclude_id.id})]})
        self.subscription.fiscal_position_id = fp.id
        self.subscription.partner_id.property_account_position_id = fp
        sale_order = self.env['sale.order'].create({
            'name': 'TestSubscription',
            'is_subscription': True,
            'fiscal_position_id': fp.id,
            'partner_id': self.user_portal.partner_id.id,
            'pricelist_id': self.company_data['default_pricelist'].id,
            'order_line': [Command.create({
                'product_id': product_tmpl.product_variant_id.id,
                'product_uom': self.env.ref('uom.product_uom_unit').id,
                'pricing_id': self.pricing_month.id,
                'product_uom_qty': 1
            })]
        })
        sale_order.action_confirm()
        inv = sale_order._create_invoices()
        self.assertEqual(100, inv.invoice_line_ids[0].price_unit, "The included tax must be subtracted to the price")

    def test_quantity_on_product_invoice_ordered_qty(self):
        # This test checks that the invoiced qty and to_invoice qty have the right behavior
        # Auto post invoices
        self.subscription.sale_order_template_id.payment_mode = 'validate_send'
        # Service product
        self.product.write({
            'detailed_type': 'service'
        })
        with freeze_time("2021-01-01"):
            self.subscription.order_line = False
            self.subscription.write({
                'partner_id': self.partner.id,
                'order_line': [Command.create({'product_id': self.product.id,
                                               'name': "month",
                                               'price_unit': 42,
                                               'product_uom_qty': 1,
                                               'pricing_id': self.pricing_month.id,
                                               }),
                               Command.create({'product_id': self.product2.id,
                                               'name': "year",
                                               'price_unit': 420,
                                               'product_uom_qty': 3,
                                               'pricing_id': self.pricing_year.id,
                                               }),
                               ]
            })
            self.subscription.action_confirm()
            val_confirm = self._get_quantities(self.subscription.order_line)
            self.assertEqual(val_confirm['to_invoice'], [1, 3], "To invoice should be equal to quantity")
            self.assertEqual(val_confirm['invoiced'], [0, 0], "To invoice should be equal to quantity")
            self.assertEqual(val_confirm['delivered_qty'], [0, 0], "Delivered qty not should be set")
            self.env['sale.order']._cron_recurring_create_invoice()
            self.subscription.order_line.filtered(lambda l: l.pricing_id.unit == 'month').write({'qty_delivered': 1})
            val_invoice = self._get_quantities(self.subscription.order_line)
            self.assertEqual(val_invoice['to_invoice'], [0, 0], "To invoice should be equal to quantity")
            self.assertEqual(val_invoice['invoiced'], [1, 3], "To invoice should be equal to quantity")
            self.assertEqual(val_invoice['delivered_qty'], [1, 0], "Delivered qty should be set")

        with freeze_time("2021-02-02"):
            self.env['sale.order']._cron_recurring_create_invoice()
            val_invoice = self._get_quantities(self.subscription.order_line)
            self.assertEqual(val_invoice['to_invoice'], [0, 0], "To invoice should be equal to quantity")
            self.assertEqual(val_invoice['invoiced'], [1, 3], "To invoice should be equal to quantity")
            self.assertEqual(val_invoice['delivered_qty'], [1, 0], "Delivered qty should be equal to quantity")

        with freeze_time("2021-02-15"):
            self.subscription.order_line.filtered(lambda l: l.pricing_id.id == self.pricing_month.id).write({'qty_delivered': 3, 'product_uom_qty': 3})
            val_invoice = self._get_quantities(
                self.subscription.order_line
            )
            self.assertEqual(val_invoice['to_invoice'], [2, 0], "To invoice should be equal to quantity")
            self.assertEqual(val_invoice['invoiced'], [1, 3], "invoiced should be correct")
            self.assertEqual(val_invoice['delivered_qty'], [3, 0], "Delivered qty should be equal to quantity")

        with freeze_time("2021-03-01"):
            self.env['sale.order']._cron_recurring_create_invoice()
            self.subscription.invalidate_cache()
            val_invoice = self._get_quantities(self.subscription.order_line)
            self.assertEqual(val_invoice['to_invoice'], [0, 0], "To invoice should be equal to quantity")
            self.assertEqual(val_invoice['delivered_qty'], [3, 0], "Delivered qty should be equal to quantity")
            self.assertEqual(val_invoice['invoiced'], [3, 3], "To invoice should be equal to quantity delivered")

    def test_update_prices_template(self):
        recurring_bound_tmpl = self.env['sale.order.template'].create({
            'name': 'Subscription template without discount',
            'recurring_rule_type': 'year',
            'recurring_rule_boundary': 'limited',
            'recurring_rule_count': 2,
            'note': "This is the template description",
            'auto_close_limit': 5,
            'sale_order_template_line_ids': [
                Command.create({
                    'name': "monthly",
                    'product_id': self.product.id,
                    'pricing_id': self.pricing_month.id,
                    'product_uom_id': self.product.uom_id.id
                }),
                Command.create({
                    'name': "yearly",
                    'product_id': self.product.id,
                    'pricing_id': self.pricing_year.id,
                    'product_uom_id': self.product.uom_id.id,
                }),
            ],
            'sale_order_template_option_ids': [
                Command.create({
                    'name': "option",
                    'product_id': self.product.id,
                    'quantity': 1,
                    'uom_id': self.product2.uom_id.id
                }),
            ],
        })

        sub_form = Form(self.env['sale.order'])
        sub_form.partner_id = self.user_portal.partner_id
        sub_form.sale_order_template_id = recurring_bound_tmpl
        sub = sub_form.save()
        self.assertEqual(len(sub.order_line.ids), 2)

    def test_product_invoice_delivery(self):
        sub = self.subscription
        sub.order_line = [Command.clear()]
        context_no_mail = {'no_reset_password': True, 'mail_create_nosubscribe': True, 'mail_create_nolog': True, }
        delivered_product_tmpl = self.env['product.template'].with_context(context_no_mail).create({
            'name': 'Delivery product',
            'type': 'service',
            'recurring_invoice': True,
            'uom_id': self.env.ref('uom.product_uom_unit').id,
            'invoice_policy': 'delivery',
        })
        product = delivered_product_tmpl.product_variant_id
        product.write({
            'list_price': 50.0,
            'taxes_id': [(6, 0, [self.tax_10.id])],
            'property_account_income_id': self.account_income.id,
        })

        with freeze_time("2021-01-03"):
            # January
            sub.order_line = [Command.create({'product_id': product.id,
                                              'name': "coucou",
                                              'price_unit': 42,
                                              'product_uom_qty': 1,
                                              'pricing_id': self.pricing_month.id,
                                              })]
            sub.action_confirm()
            self.assertFalse(sub.order_line.qty_delivered)
            # We only invoice what we deliver
            self.assertFalse(sub.order_line.qty_to_invoice)
            sub._create_recurring_invoice(automatic=True)
            # Next invoice date should not be bumped up because it is the first period
            invoice_line = sub.invoice_ids.invoice_line_ids
            self.assertFalse(invoice_line.quantity, "We can't invoice if we don't deliver the product")
            sub.invoice_ids.unlink()
            sub.order_line.qty_delivered = 1
            self.assertEqual(sub.order_line.qty_to_invoice, 1)
            sub._create_recurring_invoice(automatic=True)
            # The quantity to invoice and delivered are reset after the creation of the invoice
            self.assertFalse(sub.order_line.qty_delivered)
            inv = sub.invoice_ids.sorted('date')[-1]
            self.assertEqual(inv.invoice_line_ids.quantity, 1)

        with freeze_time("2021-02-03"):
            # February
            sub.order_line.qty_delivered = 1
            sub._create_recurring_invoice(automatic=True)
            self.assertEqual(sub.order_line.qty_delivered, 0)
            inv = sub.invoice_ids.sorted('date')[-1]
            self.assertEqual(inv.invoice_line_ids.quantity, 1)
        with freeze_time("2021-03-03"):
            # March
            sub.order_line.qty_delivered = 2
            sub._create_recurring_invoice(automatic=True)
            inv = sub.invoice_ids.sorted('date')[-1]
            self.assertEqual(inv.invoice_line_ids.quantity, 2)
            self.assertEqual(sub.order_line.product_uom_qty, 1)

    def test_recurring_invoices_from_interface(self):
        # From the interface, all the subscription lines are invoiced each time the button is pressed
        sub = self.subscription
        sub.end_date = datetime.date(2029, 4, 1)
        with freeze_time("2021-01-01"):
            self.subscription.order_line.write({'start_date': False, 'next_invoice_date': False})
            sub.action_confirm()
            # first invoice: automatic or not, it's the same behavior. All line are invoiced
            sub._create_recurring_invoice(automatic=False)
            lines = sub.order_line.sorted('pricing_id') # monthly before yearly
            self.assertEqual("2021-02-01", lines[0].next_invoice_date.strftime("%Y-%m-%d"))
            self.assertEqual("2022-01-01", lines[1].next_invoice_date.strftime("%Y-%m-%d"))
            inv = sub.invoice_ids.sorted('date')[-1]
            invoice_start_periods = inv.invoice_line_ids.mapped('subscription_start_date')
            invoice_end_periods = inv.invoice_line_ids.mapped('subscription_end_date')
            self.assertEqual(invoice_start_periods, [datetime.date(2021, 1, 1), datetime.date(2021, 1, 1)])
            self.assertEqual(invoice_end_periods, [datetime.date(2021, 1, 31), datetime.date(2021, 12, 31)])
        with freeze_time("2021-02-01"):
            sub._create_recurring_invoice(automatic=False)
            self.assertEqual("2021-03-01", lines[0].next_invoice_date.strftime("%Y-%m-%d"))
            self.assertEqual("2023-01-01", lines[1].next_invoice_date.strftime("%Y-%m-%d"))
            inv = sub.invoice_ids.sorted('date')[-1]
            invoice_start_periods = inv.invoice_line_ids.mapped('subscription_start_date')
            invoice_end_periods = inv.invoice_line_ids.mapped('subscription_end_date')
            self.assertEqual(invoice_start_periods, [datetime.date(2021, 2, 1), datetime.date(2022, 1, 1)], "monthly is updated everytime in manual action")
            self.assertEqual(invoice_end_periods, [datetime.date(2021, 2, 28), datetime.date(2022, 12, 31)], "yearly is updated everytime in manual action")

            sub._create_recurring_invoice(automatic=False)
            self.assertEqual("2021-04-01", lines[0].next_invoice_date.strftime("%Y-%m-%d"))
            self.assertEqual("2024-01-01", lines[1].next_invoice_date.strftime("%Y-%m-%d"))
            inv = sub.invoice_ids.sorted('date')[-1]
            invoice_start_periods = inv.invoice_line_ids.mapped('subscription_start_date')
            invoice_end_periods = inv.invoice_line_ids.mapped('subscription_end_date')
            self.assertEqual(invoice_start_periods, [datetime.date(2021, 3, 1), datetime.date(2023, 1, 1)], "monthly is updated everytime in manual action")
            self.assertEqual(invoice_end_periods, [datetime.date(2021, 3, 31), datetime.date(2023, 12, 31)], "yearly is updated everytime in manual action")

        with freeze_time("2021-04-01"):
            # Automatic invoicing, only one line generated
            sub._create_recurring_invoice(automatic=True)
            inv = sub.invoice_ids.sorted('date')[-1]
            invoice_start_periods = inv.invoice_line_ids.mapped('subscription_start_date')
            invoice_end_periods = inv.invoice_line_ids.mapped('subscription_end_date')
            self.assertEqual(invoice_start_periods, [datetime.date(2021, 4, 1)], "Monthly is because it is due, but yearly is not.")
            self.assertEqual(invoice_end_periods, [datetime.date(2021, 4, 30)], "Monthly is because it is due, but yearly is not.")
            self.assertEqual(inv.date, datetime.date(2021, 4, 1))

        with freeze_time("2021-05-01"):
            # Automatic invoicing, only one line generated
            sub._create_recurring_invoice(automatic=True)
            inv = sub.invoice_ids.sorted('date')[-1]
            invoice_start_periods = inv.invoice_line_ids.mapped('subscription_start_date')
            invoice_end_periods = inv.invoice_line_ids.mapped('subscription_end_date')
            self.assertEqual(invoice_start_periods, [datetime.date(2021, 5, 1)], "Monthly is because it is due, but yearly is not.")
            self.assertEqual(invoice_end_periods, [datetime.date(2021, 5, 31)], "Monthly is because it is due, but yearly is not.")
            self.assertEqual(inv.date, datetime.date(2021, 5, 1))

    def test_renew_kpi_mrr(self):
        # Test that renew with MRR transfer give correct result
        with freeze_time("2021-01-01"):
            # so creation with mail tracking
            context_mail = {'tracking_disable': False}
            sub = self.env['sale.order'].with_context(context_mail).create(
                {'name': 'TestSubscription', 'is_subscription': True,
                 'note': "original subscription description",
                 'partner_id': self.user_portal.partner_id.id,
                 'pricelist_id': self.company_data['default_pricelist'].id,
                 'sale_order_template_id': self.subscription_tmpl.id,
                 })
            self.flush_tracking()
            sub._onchange_sale_order_template_id()
            sub.name = "Parent Sub"
            sub.order_line.start_date = fields.Datetime.today()
            pricing_1 = self.env['product.pricing'].create({'duration': 1, 'unit': 'month', 'price': 30})
            pricing_2 = self.env['product.pricing'].create({'duration': 1, 'unit': 'year', 'price': 120})
            # Same product for both lines
            sub.order_line[0].product_id.product_pricing_ids = [Command.set(pricing_1.ids + pricing_2.ids)]
            sub.order_line.product_uom_qty = 1
            sub.order_line[0].pricing_id = pricing_1.id
            sub.order_line[1].pricing_id = pricing_2.id
            sub.end_date = datetime.date(2022, 1, 1)
            sub.action_confirm()
            self.flush_tracking()
            self.assertEqual(sub.recurring_monthly, 40)
            self.env['sale.order'].with_context(tracking_disable=False)._cron_recurring_create_invoice()
        with freeze_time("2021-02-01"):
            self.env['sale.order'].with_context(tracking_disable=False)._cron_recurring_create_invoice()
        with freeze_time("2021-03-01"):
            self.env['sale.order']._cron_recurring_create_invoice()
        with freeze_time("2021-04-01"):
            # We create a renewal order in april for the new year
            self.env['sale.order']._cron_recurring_create_invoice()
            action = sub.with_context(tracking_disable=False).prepare_renewal_order()
            renewal_so = self.env['sale.order'].browse(action['res_id'])
            renewal_so = renewal_so.with_context(tracking_disable=False)
            renewal_so.order_line.product_uom_qty = 2
            renewal_so.name = "Renewal"
            renewal_so.action_confirm()
            self.flush_tracking()
            self.assertEqual(sub.recurring_monthly, 40, "The first SO is still valid")
            self.assertEqual(renewal_so.recurring_monthly, 0, "MRR of renewal should not be computed before start_date of the lines")
            self.flush_tracking()
            # renew is still not ongoing;  Total MRR is 40 coming from the original sub
            self.env['sale.order'].cron_subscription_expiration()
            self.assertEqual(sub.recurring_monthly, 40)
            self.assertEqual(renewal_so.recurring_monthly, 0)
            self.env['sale.order']._cron_recurring_create_invoice()
            self.flush_tracking()
            self.subscription._cron_update_kpi()
            self.assertEqual(self.subscription.kpi_1month_mrr_delta, 0)
            self.assertEqual(self.subscription.kpi_1month_mrr_percentage, 0)
            self.assertEqual(self.subscription.kpi_3months_mrr_delta, 0)
            self.assertEqual(self.subscription.kpi_3months_mrr_percentage, 0)

        with freeze_time("2021-05-01"):
            # Renewal first period is from 2021-05 to 2021-06
            self.env['sale.order']._cron_recurring_create_invoice()
            self.assertEqual(sub.recurring_monthly, 40)
            self.assertEqual(renewal_so.recurring_monthly, 60)
            self.flush_tracking()

        with freeze_time("2021-05-15"):
            self.env['sale.order']._cron_recurring_create_invoice()
            self.flush_tracking()

        with freeze_time("2021-06-01"):
            self.subscription._cron_update_kpi()
            self.env['sale.order']._cron_recurring_create_invoice()
            self.assertEqual(sub.recurring_monthly, 10)
            self.assertEqual(renewal_so.recurring_monthly, 60)
            self.flush_tracking()

        with freeze_time("2021-07-01"):
            # Total MRR is 70 coming from original sub and renew
            self.subscription._cron_update_kpi()
            self.env['sale.order']._cron_recurring_create_invoice()
            self.env['sale.order'].cron_subscription_expiration()
            # we trigger the compute because it depends on today value.
            self.assertEqual(sub.recurring_monthly, 10)
            self.assertEqual(renewal_so.recurring_monthly, 60)
            self.flush_tracking()

        with freeze_time("2021-08-01"):
            self.env['sale.order']._cron_recurring_create_invoice()
            self.flush_tracking()
        with freeze_time("2021-09-01"):
            self.env['sale.order']._cron_recurring_create_invoice()
            self.flush_tracking()
        with freeze_time("2021-10-01"):
            self.env['sale.order']._cron_recurring_create_invoice()
            self.flush_tracking()
        with freeze_time("2021-11-01"):
            self.env['sale.order']._cron_recurring_create_invoice()
            self.flush_tracking()
        with freeze_time("2021-12-01"):
            self.env['sale.order']._cron_recurring_create_invoice()
            self.env['sale.order'].cron_subscription_expiration()
            self.flush_tracking()

        # We switch the cron the X of january to make sure the day of the cron does not affect the numbers
        with freeze_time("2022-01-07"):
            # Total MRR is 80 coming from renewed sub
            self.env['sale.order']._cron_recurring_create_invoice()
            # (sub|renewal_so)._compute_recurring_monthly()
            self.env['sale.order'].cron_subscription_expiration()
            self.assertEqual(sub.recurring_monthly, 0)
            self.assertEqual(renewal_so.recurring_monthly, 80)
            self.assertEqual(sub.stage_category, "closed")
            self.flush_tracking()
        with freeze_time("2022-02-02"):
            renewal_so.order_line.product_uom_qty = 3
            # We update the MRR of the renewed
            self.env['sale.order']._cron_recurring_create_invoice()
            # renewal_so._compute_recurring_monthly()
            self.env['sale.order'].cron_subscription_expiration()
            self.assertEqual(renewal_so.recurring_monthly, 120)
            self.flush_tracking()
            self.subscription._cron_update_kpi()
            self.assertEqual(self.subscription.kpi_1month_mrr_delta, 0)
            self.assertEqual(self.subscription.kpi_1month_mrr_percentage, 0)
            self.assertEqual(self.subscription.kpi_3months_mrr_delta, 0)
            self.assertEqual(self.subscription.kpi_3months_mrr_percentage, 0)
        # self.assertEqual(self.subscription.health, 'bad')

        order_log_ids = sub.order_log_ids.sorted('event_date')
        sub_data = [(log.event_type, log.event_date, log.category, log.amount_signed, log.recurring_monthly) for log in order_log_ids]
        self.assertEqual(sub_data, [('0_creation', datetime.date(2021, 1, 1), 'progress', 40.0, 40.0), ('3_transfer', datetime.date(2021, 5, 15), 'progress', -30.0, 10.0), ('3_transfer', datetime.date(2022, 1, 7), 'closed', 0.0, -10.0)])
        renew_logs = renewal_so.order_log_ids.sorted('event_date')
        renew_data = [(log.event_type, log.event_date, log.category, log.amount_signed, log.recurring_monthly) for log in renew_logs]
        self.assertEqual(renew_data, [('1_change', datetime.date(2021, 5, 1), 'progress', 30.0, 60.0),
                                      ('3_transfer', datetime.date(2021, 5, 1), 'progress', 30.0, 30.0),
                                      ('3_transfer', datetime.date(2022, 1, 7), 'progress', 10.0, 70.0),
                                      ('1_change', datetime.date(2022, 1, 7), 'progress', 10.0, 80.0),
                                      ('1_change', datetime.date(2022, 2, 2), 'progress', 40.0, 120.0)])

    def test_option_template(self):
        pricing_year_1 = self.env['product.pricing'].create({'duration': 3, 'unit': 'year', 'price': 10,
                                                             'pricelist_id': self.company_data['default_pricelist'].id,
                                                             'product_template_id': self.product.product_tmpl_id.id})
        other_pricelist = self.env['product.pricelist'].create({
            'name': 'New pricelist',
            'currency_id': self.company.currency_id.id,
        })
        self.env['product.pricing'].create(
            {'duration': 3, 'unit': 'year', 'pricelist_id': other_pricelist.id, 'price': 15, 'product_template_id': self.product.product_tmpl_id.id})
        template = self.subscription_tmpl = self.env['sale.order.template'].create({
            'name': 'Subscription template without discount',
            'recurring_rule_boundary': 'unlimited',
            'note': "This is the template description",
            'auto_close_limit': 5,
            'sale_order_template_line_ids': [Command.create({
                'name': "monthly",
                'product_id': self.product.id,
                'pricing_id': pricing_year_1.id,
                'product_uom_qty': 1,
                'product_uom_id': self.product.uom_id.id
            }), ],
            'sale_order_template_option_ids': [Command.create({
                'name': "line 1",
                'product_id': self.product.id,
                'option_pricing_id': pricing_year_1.id,
                'quantity': 1,
                'uom_id': self.product.uom_id.id,
            })],
        })
        subscription = self.env['sale.order'].create({
            'name': 'TestSubscription',
            'is_subscription': True,
            'partner_id': self.user_portal.partner_id.id,
            'pricelist_id': self.company_data['default_pricelist'].id,
            'sale_order_template_id': template.id,
        })
        subscription._onchange_sale_order_template_id()
        self.assertEqual(subscription.order_line.price_unit, 10, "The second pricing should be applied")
        self.assertEqual(subscription.sale_order_option_ids.price_unit, 10, "The second pricing should be applied")
        subscription.pricelist_id = other_pricelist.id
        subscription.sale_order_template_id = template.id
        subscription._onchange_sale_order_template_id()
        self.assertEqual(subscription.pricelist_id.id, other_pricelist.id, "The second pricelist should be applied")
        self.assertEqual(subscription.order_line.price_unit, 15, "The second pricing should be applied")
        self.assertEqual(subscription.sale_order_option_ids.price_unit, 15, "The second pricing should be applied")
        # Note: the pricing_id on the line is not saved on the line, but it is used to calculate the price.

    def test_update_subscription_company(self):
        """ Update the taxes of confirmed lines when the subscription company is updated """
        tax_group_1 = self.env['account.tax.group'].create({
            'name': 'Test tax group',
            'property_tax_receivable_account_id': self.company_data['default_account_receivable'].copy().id,
            'property_tax_payable_account_id': self.company_data['default_account_payable'].copy().id,
        })
        sale_tax_percentage_incl_1 = self.env['account.tax'].create({
            'name': 'sale_tax_percentage_incl_1',
            'amount': 20.0,
            'amount_type': 'percent',
            'type_tax_use': 'sale',
            'price_include': True,
            'tax_group_id': tax_group_1.id,
        })
        other_company_data = self.setup_company_data("Company 3", chart_template=self.env.company.chart_template_id)
        tax_group_2 = self.env['account.tax.group'].create({
            'name': 'Test tax group',
            'property_tax_receivable_account_id': other_company_data['default_account_receivable'].copy().id,
            'property_tax_payable_account_id': other_company_data['default_account_payable'].copy().id,
        })
        sale_tax_percentage_incl_2 = self.env['account.tax'].create({
            'name': 'sale_tax_percentage_incl_2',
            'amount': 40.0,
            'amount_type': 'percent',
            'type_tax_use': 'sale',
            'price_include': True,
            'tax_group_id': tax_group_2.id,
            'company_id': other_company_data['company'].id,
        })
        self.product.write({
            'taxes_id': [(6, 0, [sale_tax_percentage_incl_1.id, sale_tax_percentage_incl_2.id])],
        })
        simple_so = self.env['sale.order'].create({
            'partner_id': self.partner_a.id,
            'company_id': self.company_data['company'].id,
            'order_line': [
                (0, 0, {
                    'name': self.product.name,
                    'product_id': self.product.id,
                    'product_uom_qty': 2.0,
                    'product_uom': self.product.uom_id.id,
                    'price_unit': 12,
                })],
        })
        self.assertEqual(simple_so.order_line.tax_id.id, sale_tax_percentage_incl_1.id, 'The so has the first tax')
        subscription = self.env['sale.order'].create({
            'partner_id': self.partner_a.id,
            'company_id': self.company_data['company'].id,
            'order_line': [
                (0, 0, {
                    'name': self.product.name,
                    'product_id': self.product.id,
                    'product_uom_qty': 2.0,
                    'product_uom': self.product.uom_id.id,
                    'price_unit': 12,
                    'pricing_id': self.pricing_month.id,
                })],
        })
        self.assertEqual(subscription.order_line.tax_id.id, sale_tax_percentage_incl_1.id)
        (simple_so | subscription).write({'company_id': other_company_data['company'].id})
        self.assertEqual(simple_so.order_line.tax_id.id, sale_tax_percentage_incl_1.id, "Simple SO can't see their company changed")
        self.assertEqual(subscription.order_line.tax_id.id, sale_tax_percentage_incl_2.id, "Subscription company can be updated")

    def test_onchange_product_quantity_with_different_currencies(self):
        # onchange_product_quantity compute price unit into the currency of the sale_order pricelist
        # when currency of the product (Gold Coin) is different than subscription pricelist (USD)
        self.subscription.order_line = False
        self.subscription.write({'order_line': [(0, 0, {
            'name': 'TestRecurringLine',
            'pricing_id': self.pricing_month.id,
            'product_id': self.product.id,
            'product_uom_qty': 1,
            'price_unit': 50,
            'product_uom': self.product.uom_id.id,
        })]})
        line = self.subscription.order_line
        self.assertEqual(line.price_unit, 50, 'Price unit should not have changed')
        line.currency_id = self.currency_data['currency']
        conversion_rate = self.env['res.currency']._get_conversion_rate(
            self.product.currency_id,
            self.subscription.pricelist_id.currency_id,
            self.product.company_id or self.env.company,
            fields.Date.today())
        self.assertEqual(line.price_unit, self.subscription.pricelist_id.currency_id.round(50 * conversion_rate),
                         'Price unit must be converted into the currency of the pricelist (USD)')

    def test_archive_partner_invoice_shipping(self):
        # archived a partner must not remain set on invoicing/shipping address in subscription
        # here, they are set manually on subscription
        self.subscription.action_confirm()
        self.subscription.write({
            'partner_invoice_id': self.partner_a_invoice.id,
            'partner_shipping_id': self.partner_a_shipping.id,
        })
        self.assertEqual(self.partner_a_invoice, self.subscription.partner_invoice_id,
                         "Invoice address should have been set manually on the subscription.")
        self.assertEqual(self.partner_a_shipping, self.subscription.partner_shipping_id,
                         "Delivery address should have been set manually on the subscription.")
        invoice = self.subscription._create_recurring_invoice()
        self.assertEqual(self.partner_a_invoice, invoice.partner_id,
                         "On the invoice, invoice address should be the same as on the subscription.")
        self.assertEqual(self.partner_a_shipping, invoice.partner_shipping_id,
                         "On the invoice, delivery address should be the same as on the subscription.")
        with self.assertRaises(ValidationError):
            self.partner_a.child_ids.write({'active': False})

    def test_subscription_invoice_shipping_address(self):
        """Test to check that subscription invoice first try to use partner_shipping_id and partner_id from
        subscription"""
        partner = self.env['res.partner'].create(
            {'name': 'Stevie Nicks',
             'email': 'sti@fleetwood.mac',
             'company_id': self.env.company.id})

        partner2 = self.env['res.partner'].create(
            {'name': 'Partner 2',
             'email': 'sti@fleetwood.mac',
             'company_id': self.env.company.id})

        subscription = self.env['sale.order'].create({
            'partner_id': partner.id,
            'company_id': self.company_data['company'].id,
            'order_line': [
                (0, 0, {
                    'name': self.product.name,
                    'product_id': self.product.id,
                    'product_uom_qty': 2.0,
                    'product_uom': self.product.uom_id.id,
                    'price_unit': 12,
                    'pricing_id': self.pricing_month.id,
                })],
        })
        subscription.action_confirm()

        invoice_id = subscription._create_recurring_invoice()
        addr = subscription.partner_id.address_get(['delivery', 'invoice'])
        self.assertEqual(invoice_id.partner_shipping_id.id, addr['invoice'])
        self.assertEqual(invoice_id.partner_id.id, addr['delivery'])

        subscription.write({
            'partner_id': partner.id,
            'partner_shipping_id': partner2.id,
        })

        invoice_id = subscription._create_recurring_invoice()
        self.assertEqual(invoice_id.partner_shipping_id.id, partner2.id)
        self.assertEqual(invoice_id.partner_id.id, partner.id)

    def test_portal_pay_subscription(self):
        # When portal pays a subscription, a success mail is sent.
        # This calls AccountMove.amount_by_group, which triggers _compute_invoice_taxes_by_group().
        # As this method writes on this field and also reads tax_ids, which portal has no rights to,
        # it might cause some access rights issues. This test checks that no error is raised.
        portal_partner = self.user_portal.partner_id
        portal_partner.country_id = self.env['res.country'].search([('code', '=', 'US')])
        invoice = self.env['account.move'].create({
            'move_type': 'out_invoice',
        })
        acquirer = self.env['payment.acquirer'].create({
            'name': 'Test',
        })
        tx = self.env['payment.transaction'].create({
            'amount': 100,
            'acquirer_id': acquirer.id,
            'currency_id': self.env.company.currency_id.id,
            'partner_id': portal_partner.id,
        })
        self.subscription.with_user(self.user_portal).sudo().send_success_mail(tx, invoice)
