/** @odoo-module */

import { useOpenChat } from "@mail/core/web/open_chat_hook";

import { Component } from "@odoo/owl";

import { registry } from "@web/core/registry";
import { Many2OneGridRow, many2OneGridRow } from "@web_grid/components/many2one_grid_row/many2one_grid_row";
import { EmployeeOvertimeIndication } from "../employee_overtime_indication/employee_overtime_indication";
import { useTimesheetOvertimeProps } from "../../hooks/useTimesheetOvertimeProps";
import { TimesheetGridMany2OneGridRow } from "../timesheet_grid_many2one/timesheet_grid_many2one_field";

export class TimesheetMany2OneAvatarEmployeeGridRow extends Component {
    static template = "timesheet_grid.TimesheetMany2OneAvatarEmployeeGridRow";

    static components = {
        Many2OneGridRow,
        EmployeeOvertimeIndication,
    };

    static props = {
        ...TimesheetGridMany2OneGridRow.props,
    };

    setup() {
        super.setup(...arguments);
        this.openChat = useOpenChat(this.relation);
        this.employeeOvertimeProps = useTimesheetOvertimeProps();
    }

    get relation() {
        return this.props.relation || this.props.model.fieldsInfo[this.props.name].relation;
    }

    get many2OneProps() {
        return Object.fromEntries(
            Object.entries(this.props).filter(
                ([key,]) => key !== "classNames" && key in this.constructor.components.Many2OneGridRow.props
            )
        );
    }

    get resId() {
        return this.value && this.value[0];
    }

    get displayName() {
        return this.value ? this.value[1] : "";
    }

    get value() {
        return 'value' in this.props ? this.props.value : this.props.row.initialRecordValues[this.props.name];
    }

    get timesheetOvertimeProps() {
        const { units_to_work, uom, worked_hours } = this.employeeOvertimeProps.props;
        return {
            planned_hours: units_to_work,
            uom,
            worked_hours,
        };
    }

    onClickAvatar() {
        if (this.resId) {
            this.openChat(this.resId);
        }
    }
}

export const timesheetMany2OneAvatarEmployeeGridRow = {
    ...many2OneGridRow,
    component: TimesheetMany2OneAvatarEmployeeGridRow,
};

registry
    .category("grid_components")
    .add("timesheet_many2one_avatar_employee", timesheetMany2OneAvatarEmployeeGridRow);
