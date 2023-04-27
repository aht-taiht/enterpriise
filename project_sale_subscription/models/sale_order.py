# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

from dateutil.relativedelta import relativedelta

from odoo import models
from odoo.tools.date_utils import get_timedelta


class SaleOrder(models.Model):
    _inherit = "sale.order"

    def _compute_project_ids(self):
        generatable_orders = self.filtered(lambda so: so._can_generate_service())
        super(SaleOrder, generatable_orders)._compute_project_ids()
        (self - generatable_orders).update({
            'project_ids': False,
            'project_count': 0,
        })

    def _can_generate_service(self):
        self.ensure_one()
        return not self.origin_order_id and self.subscription_state not in ['6_churn', '5_renewed']

    def _set_subscription_end_date_from_template(self):
        self.ensure_one()
        end_date = self.end_date
        if not end_date and self.sale_order_template_id.recurring_rule_boundary == 'limited':
            end_date = self.start_date + get_timedelta(
                self.sale_order_template_id.recurring_rule_count,
                self.sale_order_template_id.recurring_rule_type
            ) - relativedelta(days=1)

            for line in self.order_line:
                recurrence = line.task_id.recurrence_id
                if recurrence:
                    recurrence.write({
                        'repeat_type': 'until',
                        'repeat_until': end_date,
                    })
        self.write({'end_date': end_date})

    def _set_closed_state(self):
        super()._set_closed_state()
        self.filtered('is_subscription').order_line.task_id.action_unlink_recurrence()