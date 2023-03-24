/** @odoo-module */

import { PaymentScreen } from "@point_of_sale/js/Screens/PaymentScreen/PaymentScreen";
import { patch } from "@web/core/utils/patch";
import { float_is_zero } from "web.utils";
import { ConfirmPopup } from "@point_of_sale/js/Popups/ConfirmPopup";

patch(PaymentScreen.prototype, "pos_settle_due.PaymentScreen", {
    get partnerInfos() {
        const order = this.currentOrder;
        return this.pos.getPartnerCredit(order.get_partner());
    },
    get highlightPartnerBtn() {
        const order = this.currentOrder;
        const partner = order.get_partner();
        return (!this.partnerInfos.useLimit && partner) || (!this.partnerInfos.overDue && partner);
    },
    //@override
    async validateOrder(isForceValidate) {
        const _super = this._super;
        const order = this.currentOrder;
        const change = order.get_change();
        const paylaterPaymentMethod = this.env.pos.payment_methods.filter(
            (method) =>
                this.env.pos.config.payment_method_ids.includes(method.id) &&
                method.type == "pay_later"
        )[0];
        const existingPayLaterPayment = order
            .get_paymentlines()
            .find((payment) => payment.payment_method.type == "pay_later");
        if (
            order.get_orderlines().length === 0 &&
            !float_is_zero(change, this.env.pos.currency.decimal_places) &&
            paylaterPaymentMethod &&
            !existingPayLaterPayment
        ) {
            const partner = order.get_partner();
            if (partner) {
                const { confirmed } = await this.popup.add(ConfirmPopup, {
                    title: this.env._t("The order is empty"),
                    body: _.str.sprintf(
                        this.env._t("Do you want to deposit %s to %s?"),
                        this.env.pos.format_currency(change),
                        order.get_partner().name
                    ),
                    confirmText: this.env._t("Yes"),
                });
                if (confirmed) {
                    const paylaterPayment = order.add_paymentline(paylaterPaymentMethod);
                    paylaterPayment.set_amount(-change);
                    return _super(...arguments);
                }
            } else {
                const { confirmed } = await this.popup.add(ConfirmPopup, {
                    title: this.env._t("The order is empty"),
                    body: _.str.sprintf(
                        this.env._t(
                            "Do you want to deposit %s to a specific customer? If so, first select him/her."
                        ),
                        this.env.pos.format_currency(change)
                    ),
                    confirmText: this.env._t("Yes"),
                });
                if (confirmed) {
                    const { confirmed: confirmedPartner, payload: newPartner } =
                        await this.pos.showTempScreen("PartnerListScreen");
                    if (confirmedPartner) {
                        order.set_partner(newPartner);
                    }
                    const paylaterPayment = order.add_paymentline(paylaterPaymentMethod);
                    paylaterPayment.set_amount(-change);
                    return _super(...arguments);
                }
            }
        } else {
            return _super(...arguments);
        }
    },
    async _finalizeValidation() {
        await this._super(...arguments);
        const hasCustomerAccountAsPaymentMethod = this.currentOrder
            .get_paymentlines()
            .find((paymentline) => paymentline.payment_method.type === "pay_later");
        if (hasCustomerAccountAsPaymentMethod) {
            this.env.pos.refreshTotalDueOfPartner(this.currentOrder.get_partner());
        }
    },
});