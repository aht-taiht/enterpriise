from openerp import models, fields, api


class SaleSubscription(models.Model):
    _name = "sale.subscription"
    _inherit = "sale.subscription"

    asset_category_id = fields.Many2one('account.asset.category', 'Deferred Revenue Category',
                                        help="This asset category will be applied to the lines of the contract's invoices.",
                                        domain="[('type','=','sale')]")
    template_asset_category_id = fields.Many2one('account.asset.category', 'Deferred Revenue Category',
                                        help="This asset category will be applied to the subscriptions based on this template. This field is company-dependent.",
                                        domain="[('type','=','sale')]", company_dependent=True)

    @api.onchange('template_id')
    def onchange_template_asset(self):
        if self.template_id.template_asset_category_id:
            self.asset_category_id = self.template_id.template_asset_category_id.id

    def _prepare_invoice_lines(self, fiscal_position_id):
        self.ensure_one()
        inv_lines = super(SaleSubscription, self)._prepare_invoice_lines(fiscal_position_id)

        for line in inv_lines:
            if self.asset_category_id:
                line[2]['asset_category_id'] = self.asset_category_id.id
            elif line[2].get('product_id'):
                Product = self.env['product.product'].browse([line[2]['product_id']])
                line[2]['asset_category_id'] = Product.product_tmpl_id.deferred_revenue_category_id.id

        return inv_lines


class SaleOrderLine(models.Model):
    _inherit = "sale.order.line"

    @api.multi
    def _prepare_invoice_line(self, qty):
        """
            For recurring products, add the deferred revenue category on the invoice line
        """
        res = super(SaleOrderLine, self)._prepare_invoice_line(qty)
        if self.product_id.recurring_invoice and self.order_id.subscription_id.asset_category_id:
            res['asset_category_id'] = self.order_id.subscription_id.asset_category_id.id
        return res
