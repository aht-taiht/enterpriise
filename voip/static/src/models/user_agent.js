/** @odoo-module **/

import { registerModel } from "@mail/model/model_core";
import { attr, one } from "@mail/model/model_field";

registerModel({
    name: "UserAgent",
    fields: {
        legacyUserAgent: attr(),
        registerer: one("Registerer", {
            inverse: "userAgent",
            isCausal: true,
        }),
        voip: one("Voip", {
            identifying: true,
            inverse: "userAgent",
            readonly: true,
            required: true,
        }),
        __sipJsUserAgent: attr(),
    },
});
