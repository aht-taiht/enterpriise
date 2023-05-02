/** @odoo-module */

import { Component, useState } from "@odoo/owl";

import { useService } from "@web/core/utils/hooks";
import { WarningDialog } from "@web/core/errors/error_dialogs";

import { DateTimeInput } from '@web/core/datetime/datetime_input';
import { Dropdown } from "@web/core/dropdown/dropdown";
import { DropdownItem } from "@web/core/dropdown/dropdown_item";
import { Many2ManyTagsField } from "@web/views/fields/many2many_tags/many2many_tags_field";
import { Record } from "@web/views/record";

const { DateTime } = luxon;

export class AccountReportFilters extends Component {
    static template = "account_reports.AccountReportFilters";
    static props = {};
    static components = {
        DateTimeInput,
        Dropdown,
        DropdownItem,
        Many2ManyTagsField,
        Record,
    };

    setup() {
        this.dialog = useService("dialog");
        this.controller = useState(this.env.controller);
    }

    //------------------------------------------------------------------------------------------------------------------
    // Getters
    //------------------------------------------------------------------------------------------------------------------
    get selectedFiscalPositionName() {
        switch (this.controller.options.fiscal_position) {
            case "domestic":
                return "Domestic";
            case "all":
                return "All";
            default:
                for (const fiscalPosition of this.controller.options.available_vat_fiscal_positions)
                    if (fiscalPosition.id === this.controller.options.fiscal_position)
                        return fiscalPosition.name;
        }
    }

    get selectedHorizontalGroupName() {
        for (const horizontalGroup of this.controller.options.available_horizontal_groups)
            if (horizontalGroup.id === this.controller.options.selected_horizontal_group_id)
                return horizontalGroup.name;

        return "None";
    }

    get selectedTaxUnitName() {
        if (this.controller.options.tax_unit === "company_only")
            return "Company Only";
        else
            for (const taxUnit of this.controller.options.available_tax_units)
                if (taxUnit.id === this.controller.options.tax_unit)
                    return taxUnit.name;
    }

    get selectedVariantName() {
        for (const variant of this.controller.options.available_variants)
            if (variant.id === this.controller.options.report_id)
                return variant.name;
    }

    //------------------------------------------------------------------------------------------------------------------
    // Helpers
    //------------------------------------------------------------------------------------------------------------------
    get hasAnalyticGroupbyFilter() {
        return Boolean(this.controller.groups.analytic_accounting) && (Boolean(this.controller.filters.show_analytic_groupby) || Boolean(this.controller.filters.show_analytic_plan_groupby));
    }

    get hasExtraOptionsFilter() {
        return "report_cash_basis" in this.controller.options || this.controller.filters.show_draft || this.controller.filters.show_all || this.controller.filters.show_unreconciled;
    }

    get hasFiscalPositionFilter() {
        return this.controller.options.available_vat_fiscal_positions.length > (this.controller.options.allow_domestic ? 0 : 1) && this.controller.options.multi_company;
    }

    //------------------------------------------------------------------------------------------------------------------
    // Dates
    //------------------------------------------------------------------------------------------------------------------
    // Getters
    dateFrom(optionKey) {
        return DateTime.fromISO(this.controller.options[optionKey].date_from);
    }

    dateTo(optionKey) {
        return DateTime.fromISO(this.controller.options[optionKey].date_to);
    }

    localeDateFrom(optionKey) {
        return this.dateFrom(optionKey).toLocaleString(DateTime.DATE_MED);
    }

    localeDateTo(optionKey) {
        return this.dateTo(optionKey).toLocaleString(DateTime.DATE_MED);
    }

    // Setters
    setDate(optionKey, type, date) {
        if (date)
            this.controller.options[optionKey][`date_${type}`] = date;
        else
            this.dialog.add(WarningDialog, {
                title: this.env._t("Odoo Warning"),
                message: this.env._t("Date cannot be empty"),
            });
    }

    setDateFrom(optionKey, dateFrom) {
        this.setDate(optionKey, 'from', dateFrom);
    }

    setDateTo(optionKey, dateTo) {
        this.setDate(optionKey, 'to', dateTo);
    }

    //------------------------------------------------------------------------------------------------------------------
    // Number of periods
    //------------------------------------------------------------------------------------------------------------------
    setNumberPeriods(ev) {
        const numberPeriods = ev.target.value;

        if (numberPeriods >= 1)
            this.controller.options.comparison.number_period = parseInt(numberPeriods);
        else
            this.dialog.add(WarningDialog, {
                title: this.env._t("Odoo Warning"),
                message: this.env._t("Number of periods cannot be smaller than 1"),
            });
    }

    //------------------------------------------------------------------------------------------------------------------
    // Records
    //------------------------------------------------------------------------------------------------------------------
    recordProps(string, relation, optionKey) {
        const fields = {
            record_data: {
                string: this.env._t(string),
                relation: relation,
                type: "many2many",
                relatedFields: {
                    display_name: {
                        type: "char"
                    },
                },
            },
        };

        return {
            fields: fields,
            values: {
                record_data: this.controller.options[optionKey],
            },
            activeFields: fields,
            onRecordChanged: async (record) => {
                await this.updateFilter(optionKey, record.data.record_data.currentIds);
            },
        };
    }

    //------------------------------------------------------------------------------------------------------------------
    // Generic filters
    //------------------------------------------------------------------------------------------------------------------
    async updateFilter(optionKey, optionValue) {
        this.controller.updateOption(optionKey, optionValue);
        await this.controller.load(this.controller.options);
    }

    async toggleFilter(optionKey) {
        this.controller.toggleOption(optionKey);
        await this.controller.load(this.controller.options);
    }

    //------------------------------------------------------------------------------------------------------------------
    // Custom filters
    //------------------------------------------------------------------------------------------------------------------
    async filterJournal(journal) {
        journal.selected = !journal.selected;

        if (journal.model === 'account.journal.group')
            this.controller.options.__journal_group_action = {
                'action': journal.selected ? "remove" : "add",
                'id': parseInt(journal.id),
            };

        await this.controller.load(this.controller.options);
    }
}