/** @odoo-module */

import { Component } from "@odoo/owl";

export class StockMove extends Component {
    static props = {
        clickable: Boolean,
        displayUOM: Boolean,
        label: { optional: true, type: String },
        parent: Object,
        record: Object,
        uom: { optional: true, type: Object },
    };
    static template = "mrp_workorder.StockMove";

    setup() {
        this.fieldState = "state";
        this.isLongPressable = false;
        this.longPressed = false;
        this.resModel = this.props.record.resModel;
    }

    get cssClass() {
        let cssClass = this.isLongPressable ? "o_longpressable" : "";
        if (this.isComplete) {
            cssClass += " text-muted";
        }
        return cssClass;
    }

    get isComplete() {
        if (this.toConsumeQuantity) {
            return this.props.record.data.quantity_done >= this.toConsumeQuantity;
        }
        return Boolean(this.props.record.data.quantity_done);
    }

    get toConsumeQuantity() {
        const move = this.props.record.data;
        const parent = this.props.parent.data;
        let toConsumeQuantity = move.should_consume_qty || move.product_uom_qty;
        if (parent.product_tracking == "serial" && !parent.show_serial_mass_produce) {
            toConsumeQuantity /= this.props.parent.data.product_qty;
        }
        return toConsumeQuantity;
    }

    get quantityDone() {
        return this.props.record.data.quantity_done;
    }

    longPress() {}

    onAnimationEnd(ev) {
        if (ev.animationName === "longpress") {
            this.longPressed = true;
            this.longPress();
        }
    }

    onClick() {
        if (!this.props.clickable) {
            return;
        }
        if (this.longPressed) {
            this.longPressed = false;
            return; // Do nothing since the longpress event was already called.
        }
        this.clicked();
    }

    async clicked() {
        const resIds = [this.props.resId];
        const action = await this.props.record.model.orm.call(
            this.resModel,
            "action_show_details",
            resIds
        );
        const options = {
            onClose: async () => {
                await this.reload();
                //await this.props.record.load();
                //this.render();
            },
        };
        this.props.record.model.action.doAction(action, options);
    }

    async openMoveDetails() {
        if (!this.props.clickable) {
            return;
        }
        if (!this.toConsumeQuantity) {
            return this.clicked();
        }
        const quantity = this.isComplete ? 0 : this.toConsumeQuantity;
        this.props.record.update({ quantity_done: quantity }, { save: true });
        await this.reload();
    }

    async reload() {
        await this.props.parent.load();
        await this.props.record.load();
    }

    get state() {
        return this.props.record.data[this.fieldState];
    }
}
