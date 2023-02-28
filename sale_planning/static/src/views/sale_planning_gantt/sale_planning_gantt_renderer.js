/** @odoo-module **/

import { _t } from "@web/core/l10n/translation";
import { Domain } from "@web/core/domain";
import { patch } from "@web/core/utils/patch";
import { PlanningGanttRenderer } from "@planning/views/planning_gantt/planning_gantt_renderer";
import { useService } from "@web/core/utils/hooks";

patch(PlanningGanttRenderer.prototype, "sale_planning_gantt_renderer", {
    setup() {
        this._super(...arguments);
        this.notification = useService("notification");
    },
    getPlanDialogDomain() {
        const domain = this._super(...arguments);
        return Domain.and([domain, [["sale_line_id", "!=", false]]]).toList({});
    },
    getSelectCreateDialogProps() {
        const props = this._super(...arguments);
        Object.assign(props.context, {
            search_default_group_by_resource: false,
            search_default_group_by_role: false,
            search_default_role_id: props.context.role_id || false,
            search_default_project_id: props.context.project_id || false,
            planning_slots_to_schedule: true,
            search_default_sale_order_id:
            props.context.planning_gantt_active_sale_order_id || null,
        });
        this.model.addSpecialKeys(props.context);
        return props;
    },
    openPlanDialogCallback(result) {
        if (!result) {
            this.notification.add(
                _t("This resource is not available for this shift during the selected period."),
                { type: "danger" }
            );
        }
    },
});
