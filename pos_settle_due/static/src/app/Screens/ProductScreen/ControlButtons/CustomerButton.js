/** @odoo-module */

import { CustomerButton } from "@point_of_sale/js/Screens/ProductScreen/ControlButtons/CustomerButton";
import { patch } from "@web/core/utils/patch";

patch(CustomerButton.prototype, "point_of_sale.CustomerButton", {
    get partnerInfos() {
        return this.pos.getPartnerCredit(this.partner);
    },
});