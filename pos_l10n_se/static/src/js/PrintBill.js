/** @odoo-module */
import { PrintBillButton } from "@pos_restaurant/js/Screens/ProductScreen/ControlButtons/PrintBillButton";
import { patch } from "@web/core/utils/patch";

patch(PrintBillButton.prototype, "pos_l10n_se.PrintBillButton", {
    async onClick() {
        const _super = this._super;
        const order = this.env.pos.get_order();
        if (this.env.pos.useBlackBoxSweden()) {
            order.isProfo = true;
            order.receipt_type = "profo";
            const sequence = await this.env.pos.get_profo_order_sequence_number();
            order.sequence_number = sequence;

            await this.env.pos.push_single_order(order);
            order.receipt_type = false;
        }
        await _super(...arguments);
        order.isProfo = false;
    },
});
