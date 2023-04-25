/** @odoo-module */

import { PosDB } from "@point_of_sale/js/db";
import { patch } from "@web/core/utils/patch";

patch(PosDB.prototype, "pos_settle_due.PosDB", {
    update_partners(partnersWithUpdatedFields) {
        for (const updatedFields of partnersWithUpdatedFields) {
            Object.assign(this.partner_by_id[updatedFields.id], updatedFields);
        }
    },
});
