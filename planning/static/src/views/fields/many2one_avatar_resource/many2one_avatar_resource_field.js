/** @odoo-module **/

import { registry } from "@web/core/registry";
import {
    Many2OneAvatarField,
    many2OneAvatarField,
} from "@web/views/fields/many2one_avatar/many2one_avatar_field";

export class Many2OneAvatarResourceField extends Many2OneAvatarField {}
Many2OneAvatarResourceField.template = "planning.Many2OneAvatarResourceField";

export const many2OneAvatarResourceField = {
    ...many2OneAvatarField,
    component: Many2OneAvatarResourceField,
    fieldDependencies: {
        resource_type: { type: "selection" },
    },
    additionalClasses: ["o_field_many2one_avatar"],
};

registry.category("fields").add("many2one_avatar_resource", many2OneAvatarResourceField);
