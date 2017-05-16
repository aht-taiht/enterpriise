from odoo import http
from odoo.http import request
from odoo.addons.website_sale.controllers.main import WebsiteSale


class UpsBillMyAccount(WebsiteSale):

    @http.route("/shop/ups_check_service_type", type='json', auth="public", website=True)
    def ups_check_service_type_is_available(self, **post):
        return request.env['sale.order'].sudo().check_ups_service_type(post)

    @http.route("/shop/ups_carrier_account/set", type='http', auth="public", website=True)
    def set_ups_carrier_account(self, **post):
        order = request.website.sale_get_order()
        # set ups bill my account data in sale order
        if order.carrier_id.ups_bill_my_account and post.get('ups_carrier_account'):
            # Update Quotation with ups_service_type and ups_carrier_account
            order.write({
                'ups_service_type': post['ups_service_type'],
                'ups_carrier_account': post['ups_carrier_account']
            })
        return request.redirect("/shop/payment")

    @http.route("/shop/ups_carrier_account/unset", type='http', auth="public", website=True)
    def reset_ups_carrier_account(self, **post):
        order = request.website.sale_get_order()
        # remove ups bill my account data in sale order
        if order.ups_carrier_account:
            order.write({
                'ups_service_type': False,
                'ups_carrier_account': False
            })
        return request.redirect("/shop/payment")
