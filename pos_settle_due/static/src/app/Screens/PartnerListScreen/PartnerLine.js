/** @odoo-module */

import { PartnerLine } from "@point_of_sale/js/Screens/PartnerListScreen/PartnerLine";
import { patch } from "@web/core/utils/patch";
import { SelectionPopup } from "@point_of_sale/js/Popups/SelectionPopup";
import { usePos } from "@point_of_sale/app/pos_hook";
import { useService } from "@web/core/utils/hooks";

patch(PartnerLine.prototype, "pos_settle_due.PartnerLine", {
    setup() {
        this._super(...arguments);
        this.pos = usePos();
        this.popup = useService("popup");
    },
    getPartnerLink() {
        return `/web#model=res.partner&id=${this.props.partner.id}`;
    },
    get partnerInfos() {
        return this.pos.getPartnerCredit(this.props.partner);
    },
    async settlePartnerDue(event) {
        const { globalState } = this.pos;
        if (this.props.selectedPartner == this.props.partner) {
            event.stopPropagation();
        }
        const totalDue = this.props.partner.total_due;
        const paymentMethods = globalState.payment_methods.filter(
            (method) =>
                globalState.config.payment_method_ids.includes(method.id) &&
                method.type != "pay_later"
        );
        const selectionList = paymentMethods.map((paymentMethod) => ({
            id: paymentMethod.id,
            label: paymentMethod.name,
            item: paymentMethod,
        }));
        const { confirmed, payload: selectedPaymentMethod } = await this.popup.add(SelectionPopup, {
            title: this.env._t("Select the payment method to settle the due"),
            list: selectionList,
        });
        if (!confirmed) {
            return;
        }
        this.trigger("discard"); // make sure the PartnerListScreen resolves and properly closed.
        const newOrder = globalState.add_new_order();
        const payment = newOrder.add_paymentline(selectedPaymentMethod);
        payment.set_amount(totalDue);
        newOrder.set_partner(this.props.partner);
        this.pos.showScreen("PaymentScreen");
    },
});
