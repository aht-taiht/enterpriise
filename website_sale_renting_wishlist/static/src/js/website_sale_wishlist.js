/** @odoo-module **/

import publicWidget from '@web/legacy/js/public/public_widget';
import '@website_sale_wishlist/js/website_sale_wishlist';
import { RentingMixin } from '@website_sale_renting/js/renting_mixin';

publicWidget.registry.ProductWishlist.include(RentingMixin);
publicWidget.registry.ProductWishlist.include({

    /**
     * Get the cart update params with renting.
     *
     * @param {string} productId
     * @param {string} qty
     * @override
     */
    _getCartUpdateJsonParams(productId, qty) {
        const params = this._super.apply(this, arguments);
        const tr = this.el.querySelector(`tr[data-product-id="${productId}"]`);
        const isRental = tr && tr.querySelector('input[name=is_rental]');
        if (isRental && isRental.value) {
            Object.assign(params, this._getSerializedRentingDates($(tr)));
        }
        return params;
    },

});
