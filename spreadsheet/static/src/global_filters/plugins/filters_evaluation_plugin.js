/** @odoo-module */

/**
 * @typedef {import("../../helpers/basic_data_source").Field} Field
 * @typedef {import("./filters_plugin").GlobalFilter} GlobalFilter
 */

import { _t } from "@web/core/l10n/translation";
import { sprintf } from "@web/core/utils/strings";
import { Domain } from "@web/core/domain";
import { constructDateRange, getPeriodOptions, QUARTER_OPTIONS } from "@web/search/utils/dates";

import spreadsheet from "@spreadsheet/o_spreadsheet/o_spreadsheet_extended";
import CommandResult from "@spreadsheet/o_spreadsheet/cancelled_reason";

import { checkFiltersTypeValueCombination } from "@spreadsheet/global_filters/helpers";
import { isEmpty } from "@spreadsheet/helpers/helpers";
import { FILTER_DATE_OPTION } from "@spreadsheet/assets_backend/constants";

const { DateTime } = luxon;

const MONTHS = {
    january: { value: 1, granularity: "month" },
    february: { value: 2, granularity: "month" },
    march: { value: 3, granularity: "month" },
    april: { value: 4, granularity: "month" },
    may: { value: 5, granularity: "month" },
    june: { value: 6, granularity: "month" },
    july: { value: 7, granularity: "month" },
    august: { value: 8, granularity: "month" },
    september: { value: 9, granularity: "month" },
    october: { value: 10, granularity: "month" },
    november: { value: 11, granularity: "month" },
    december: { value: 12, granularity: "month" },
};

export default class FiltersEvaluationPlugin extends spreadsheet.UIPlugin {
    constructor(getters, history, dispatch, config) {
        super(getters, history, dispatch, config);
        this.orm = config.evalContext.env ? config.evalContext.env.services.orm : undefined;
        /**
         * Cache record display names for relation filters.
         * For each filter, contains a promise resolving to
         * the list of display names.
         */
        this.recordsDisplayName = {};
        /** @type {Object.<string, string|Array<string>|Object>} */
        this.values = {};
    }

    /**
     * Check if the given command can be dispatched
     *
     * @param {Object} cmd Command
     */
    allowDispatch(cmd) {
        switch (cmd.type) {
            case "SET_GLOBAL_FILTER_VALUE": {
                const filter = this.getters.getGlobalFilter(cmd.id);
                if (!filter) {
                    return CommandResult.FilterNotFound;
                }
                return checkFiltersTypeValueCombination(filter.type, cmd.value);
            }
        }
        return CommandResult.Success;
    }

    /**
     * Handle a spreadsheet command
     *
     * @param {Object} cmd Command
     */
    handle(cmd) {
        switch (cmd.type) {
            case "ADD_GLOBAL_FILTER":
                this.recordsDisplayName[cmd.filter.id] = cmd.filter.defaultValueDisplayNames;
                break;
            case "EDIT_GLOBAL_FILTER":
                if (this.values[cmd.id] && this.values[cmd.id].rangeType !== cmd.filter.rangeType) {
                    delete this.values[cmd.id];
                }
                this.recordsDisplayName[cmd.filter.id] = cmd.filter.defaultValueDisplayNames;
                break;
            case "SET_GLOBAL_FILTER_VALUE":
                this.recordsDisplayName[cmd.id] = cmd.displayNames;
                this._setGlobalFilterValue(cmd.id, cmd.value);
                break;
            case "REMOVE_GLOBAL_FILTER":
                delete this.recordsDisplayName[cmd.id];
                delete this.values[cmd.id];
                break;
            case "CLEAR_GLOBAL_FILTER_VALUE":
                this.recordsDisplayName[cmd.id] = [];
                this._clearGlobalFilterValue(cmd.id);
                break;
        }
        switch (cmd.type) {
            case "START":
            case "ADD_GLOBAL_FILTER":
            case "EDIT_GLOBAL_FILTER":
            case "SET_GLOBAL_FILTER_VALUE":
            case "REMOVE_GLOBAL_FILTER":
            case "CLEAR_GLOBAL_FILTER_VALUE":
                this._updateAllDomains();
                break;
        }
    }

    // -------------------------------------------------------------------------
    // Getters
    // -------------------------------------------------------------------------

    /**
     * Get the current value of a global filter
     *
     * @param {string} filterId Id of the filter
     *
     * @returns {string|Array<string>|Object} value Current value to set
     */
    getGlobalFilterValue(filterId) {
        const filter = this.getters.getGlobalFilter(filterId);

        const value = filterId in this.values ? this.values[filterId].value : filter.defaultValue;

        if (filter.type === "date" && isEmpty(value) && filter.defaultsToCurrentPeriod) {
            return this._getValueOfCurrentPeriod(filterId);
        }

        return value;
    }

    /**
     * @param {string} id Id of the filter
     *
     * @returns { boolean } true if the given filter is active
     */
    isFilterActive(id) {
        const { type } = this.getters.getGlobalFilter(id);
        const value = this.getGlobalFilterValue(id);
        switch (type) {
            case "text":
                return value;
            case "date":
                return value && (value.yearOffset !== undefined || value.period);
            case "relation":
                return value && value.length;
        }
    }

    /**
     * Get the number of active global filters
     *
     * @returns {number}
     */
    getActiveFilterCount() {
        return this.getters.getGlobalFilters().filter((filter) => this.isFilterActive(filter.id))
            .length;
    }

    getFilterDisplayValue(filterName) {
        const filter = this.getters.getGlobalFilterLabel(filterName);
        if (!filter) {
            throw new Error(sprintf(_t(`Filter "%s" not found`), filterName));
        }
        const value = this.getGlobalFilterValue(filter.id);
        switch (filter.type) {
            case "text":
                return value || "";
            case "date": {
                if (!value || value.yearOffset === undefined) {
                    return "";
                }
                const periodOptions = getPeriodOptions(DateTime.local());
                const year = String(DateTime.local().year + value.yearOffset);
                const period = periodOptions.find(({ id }) => value.period === id);
                let periodStr = period && period.description;
                // Named months aren't in getPeriodOptions
                if (!period) {
                    periodStr =
                        MONTHS[value.period] && String(MONTHS[value.period].value).padStart(2, "0");
                }
                return periodStr ? periodStr + "/" + year : year;
            }
            case "relation":
                if (!value || !this.orm) return "";
                if (!this.recordsDisplayName[filter.id]) {
                    this.orm.call(filter.modelName, "name_get", [value]).then((result) => {
                        const names = result.map(([, name]) => name);
                        this.recordsDisplayName[filter.id] = names;
                        this.dispatch("EVALUATE_CELLS", {
                            sheetId: this.getters.getActiveSheetId(),
                        });
                    });
                    return "";
                }
                return this.recordsDisplayName[filter.id].join(", ");
        }
    }

    // -------------------------------------------------------------------------
    // Handlers
    // -------------------------------------------------------------------------

    /**
     * Set the current value of a global filter
     *
     * @param {string} id Id of the filter
     * @param {string|Array<string>|Object} value Current value to set
     */
    _setGlobalFilterValue(id, value) {
        this.values[id] = { value: value, rangeType: this.getters.getGlobalFilter(id).rangeType };
    }

    /**
     * Get the filter value corresponding to the current period, depending of the type of range of the filter.
     * For example if rangeType === "month", the value will be the current month of the current year.
     *
     * @param {string} filterId a global filter
     * @return {Object} filter value
     */
    _getValueOfCurrentPeriod(filterId) {
        const filter = this.getters.getGlobalFilter(filterId);
        const rangeType = filter.rangeType;
        switch (rangeType) {
            case "year":
                return { yearOffset: 0 };
            case "month": {
                const month = new Date().getMonth() + 1;
                const period = Object.entries(MONTHS).find((item) => item[1].value === month)[0];
                return { yearOffset: 0, period };
            }
            case "quarter": {
                const quarter = Math.floor(new Date().getMonth() / 3);
                const period = FILTER_DATE_OPTION.quarter[quarter];
                return { yearOffset: 0, period };
            }
        }
        return {};
    }

    /**
     * Set the current value to empty values which functionally deactivate the filter
     *
     * @param {string} id Id of the filter
     */
    _clearGlobalFilterValue(id) {
        const { type, rangeType } = this.getters.getGlobalFilter(id);
        let value;
        switch (type) {
            case "text":
                value = "";
                break;
            case "date":
                value = { yearOffset: undefined };
                break;
            case "relation":
                value = [];
                break;
        }
        this.values[id] = { value, rangeType };
    }

    /**
     * Update the domain of all pivots and all lists
     *
     * @private
     */
    _updateAllDomains() {
        for (const pivotId of this.getters.getPivotIds()) {
            const domain = this._getComputedDomain((filterId) =>
                this.getters.getGlobalFilterFieldPivot(filterId, pivotId)
            );
            this.dispatch("ADD_PIVOT_DOMAIN", { id: pivotId, domain });
        }
        for (const listId of this.getters.getListIds()) {
            const domain = this._getComputedDomain((filterId) =>
                this.getters.getGlobalFilterFieldList(filterId, listId)
            );
            this.dispatch("ADD_LIST_DOMAIN", { id: listId, domain });
        }
    }

    // -------------------------------------------------------------------------
    // Private
    // -------------------------------------------------------------------------

    /**
     * Get the domain relative to a date field
     *
     * @private
     *
     * @param {GlobalFilter} filter
     * @param {Field} fieldDesc
     *
     * @returns {Domain|undefined}
     */
    _getDateDomain(filter, fieldDesc) {
        if (!this.isFilterActive(filter.id)) {
            return undefined;
        }
        let granularity;
        const value = this.getGlobalFilterValue(filter.id);
        const field = fieldDesc.field;
        const type = fieldDesc.type;
        const luxonDate = DateTime.local();
        const setParam = { year: luxonDate.year };
        const plusParam = { years: value.yearOffset || 0 };
        if (!value.period || value.period === "empty") {
            granularity = "year";
        } else {
            switch (filter.rangeType) {
                case "month":
                    granularity = "month";
                    setParam.month = MONTHS[value.period].value;
                    break;
                case "quarter":
                    granularity = "quarter";
                    setParam.quarter = QUARTER_OPTIONS[value.period].setParam.quarter;
                    break;
            }
        }
        return constructDateRange({
            referenceMoment: luxonDate,
            fieldName: field,
            fieldType: type,
            granularity,
            setParam,
            plusParam,
        }).domain;
    }

    /**
     * Get the domain relative to a text field
     *
     * @private
     *
     * @param {GlobalFilter} filter
     * @param {Field} fieldDesc
     *
     * @returns {Domain|undefined}
     */
    _getTextDomain(filter, fieldDesc) {
        const value = this.getGlobalFilterValue(filter.id);
        if (!value) {
            return undefined;
        }
        const field = fieldDesc.field;
        return new Domain([[field, "ilike", value]]);
    }

    /**
     * Get the domain relative to a relation field
     *
     * @private
     *
     * @param {GlobalFilter} filter
     * @param {Field} fieldDesc
     *
     * @returns {Domain|undefined}
     */
    _getRelationDomain(filter, fieldDesc) {
        const values = this.getGlobalFilterValue(filter.id);
        if (!values || values.length === 0) {
            return undefined;
        }
        const field = fieldDesc.field;
        return new Domain([[field, "in", values]]);
    }

    /**
     * Get the computed domain of a global filters applied to the field given
     * by the callback
     *
     * @private
     *
     * @param {Function<Field>} getFieldDesc Callback to get the field description
     * on which the global filters is applied
     *
     * @returns {string}
     */
    _getComputedDomain(getFieldDesc) {
        let domain = new Domain([]);
        for (let filter of this.getters.getGlobalFilters()) {
            const fieldDesc = getFieldDesc(filter.id);
            if (!fieldDesc) {
                continue;
            }
            let domainToAdd = undefined;
            switch (filter.type) {
                case "date":
                    domainToAdd = this._getDateDomain(filter, fieldDesc);
                    break;
                case "text":
                    domainToAdd = this._getTextDomain(filter, fieldDesc);
                    break;
                case "relation":
                    domainToAdd = this._getRelationDomain(filter, fieldDesc);
                    break;
            }
            if (domainToAdd) {
                domain = Domain.and([domain, domainToAdd]);
            }
        }
        return domain.toString();
    }
}

FiltersEvaluationPlugin.getters = [
    "getFilterDisplayValue",
    "getGlobalFilterValue",
    "getActiveFilterCount",
    "isFilterActive",
];
