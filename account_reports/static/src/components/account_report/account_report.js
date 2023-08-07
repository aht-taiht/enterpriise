/** @odoo-module */

import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";
import { Dropdown } from "@web/core/dropdown/dropdown";
import { DropdownItem } from "@web/core/dropdown/dropdown_item";
import { ControlPanel } from "@web/search/control_panel/control_panel";

import { Component, onWillStart, useState, useSubEnv } from "@odoo/owl";

import { AccountReportController } from "@account_reports/components/account_report/controller";
import { AccountReportEllipsis } from "@account_reports/components/account_report/ellipsis/ellipsis";
import { AccountReportFilters } from "@account_reports/components/account_report/filters/filters";
import { AccountReportHeader } from "@account_reports/components/account_report/header/header";
import { AccountReportLine } from "@account_reports/components/account_report/line/line";
import { AccountReportLineCell } from "@account_reports/components/account_report/line_cell/line_cell";
import { AccountReportLineName } from "@account_reports/components/account_report/line_name/line_name";
import { AccountReportSearchBar } from "@account_reports/components/account_report/search_bar/search_bar";

export class AccountReport extends Component {
    static template = "account_reports.AccountReport";
    static props = {
        action: Object,
        actionId: { type: Number, optional: true },
        className: { type: String, optional: true },
        globalState: { type: Object, optional: true },
    };
    static components = {
        ControlPanel,
        Dropdown,
        DropdownItem,
        AccountReportSearchBar,
    };

    static customizableComponents = [
        AccountReportEllipsis,
        AccountReportFilters,
        AccountReportHeader,
        AccountReportLine,
        AccountReportLineCell,
        AccountReportLineName,
    ];
    static defaultComponentsMap = [];

    setup() {
        // Can not use 'control-panel-bottom-right' slot without this, as viewSwitcherEntries doesn't exist here.
        this.env.config.viewSwitcherEntries = [];

        this.orm = useService("orm");
        this.actionService = useService("action");
        this.controller = useState(new AccountReportController(this.props.action));
        this.initialQuery = this.props.action.context?.default_filter_accounts;

        for (const customizableComponent of AccountReport.customizableComponents)
            AccountReport.defaultComponentsMap[customizableComponent.name] = customizableComponent;

        onWillStart(async () => {
            await this.controller.load(this.env);
        });

        useSubEnv({
            controller: this.controller,
            component: this.getComponent.bind(this),
            template: this.getTemplate.bind(this),
        });
    }

    // -----------------------------------------------------------------------------------------------------------------
    // Custom overrides
    // -----------------------------------------------------------------------------------------------------------------
    static registerCustomComponent(customComponent) {
        registry.category("account_reports_custom_components").add(customComponent.template, customComponent);
    }

    get cssCustomClass() {
        return this.controller.data.custom_display.client_css_custom_class || "";
    }

    getComponent(name) {
        const customComponents = this.controller.data.custom_display.components;

        if (customComponents && customComponents[name])
            return registry.category("account_reports_custom_components").get(customComponents[name]);

        return AccountReport.defaultComponentsMap[name];
    }

    getTemplate(name) {
        const customTemplates = this.controller.data.custom_display.templates;

        if (customTemplates && customTemplates[name])
            return customTemplates[name];

        return `account_reports.${ name }Customizable`;
    }

    // -----------------------------------------------------------------------------------------------------------------
    // Table
    // -----------------------------------------------------------------------------------------------------------------
    get tableClasses() {
        let classes = "";

        if (this.controller.options.columns.length > 1)
            classes += " striped";

        return classes;
    }
}

registry.category("actions").add("account_report", AccountReport);
