/** @odoo-module */

import { _t, _lt } from "@web/core/l10n/translation";
import spreadsheet from "@spreadsheet/o_spreadsheet/o_spreadsheet_extended";
import CommandResult from "@spreadsheet/o_spreadsheet/cancelled_reason";
import { RecordsSelector } from "@spreadsheet/global_filters/components/records_selector/records_selector";
import { useService } from "@web/core/utils/hooks";
import { LegacyComponent } from "@web/legacy/legacy_component";
import { ModelSelector } from "@web/core/model_selector/model_selector";
import { sprintf } from "@web/core/utils/strings";
import { FilterFieldOffset } from "./components/filter_field_offset";
import { RELATIVE_DATE_RANGE_TYPES } from "@spreadsheet/helpers/constants";
import { DateFilterValue } from "@spreadsheet/global_filters/components/filter_date_value/filter_date_value";
import { globalFiltersFieldMatchers } from "@spreadsheet/global_filters/plugins/global_filters_core_plugin";
import { ModelFieldSelector } from "@web/core/model_field_selector/model_field_selector";

const { onMounted, onWillStart, useState } = owl;
const uuidGenerator = new spreadsheet.helpers.UuidGenerator();

const RANGE_TYPES = [
    { type: "year", description: _lt("Year") },
    { type: "quarter", description: _lt("Quarter") },
    { type: "month", description: _lt("Month") },
    { type: "relative", description: _lt("Relative Period") },
];

const ALLOWED_FIELD_TYPES = {
    text: ["many2one", "text", "char"],
    date: ["datetime", "date"],
    relation: ["many2one", "many2many", "one2many"],
};

/**
 * @typedef {import("@spreadsheet/data_sources/metadata_repository").Field} Field
 * @typedef {import("@spreadsheet/global_filters/plugins/global_filters_core_plugin").FilterMatchingField} FilterMatchingField
 *
 * @typedef State
 * @property {boolean} saved
 * @property {string} label label of the filter
 * @property {"text" | "date" | "relation"} type type of the filter
 * @property {Object} text config of text filter
 * @property {Object} date config of date filter
 * @property {Object} relation config of relation filter
 * @property {Object} fieldMatchings
 */

/**
 * This is the side panel to define/edit a global filter.
 * It can be of 3 different type: text, date and relation.
 */
export default class FilterEditorSidePanel extends LegacyComponent {
    /**
     * @constructor
     */
    setup() {
        this.id = undefined;
        /** @type {State} */
        this.state = useState({
            saved: false,
            label: undefined,
            type: this.props.type,
            text: {
                defaultValue: undefined,
            },
            date: {
                defaultValue: {},
                defaultsToCurrentPeriod: false,
                type: "year", // "year" | "month" | "quarter" | "relative"
                options: [],
            },
            relation: {
                defaultValue: [],
                displayNames: [],
                relatedModel: {
                    label: undefined,
                    technical: undefined,
                },
            },
            fieldMatchings: [],
        });
        this._wrongFieldMatchingsSet = new Set();
        this.getters = this.env.model.getters;
        this.loadValues();
        this.orm = useService("orm");
        this.notification = useService("notification");

        this.relativeDateRangesTypes = RELATIVE_DATE_RANGE_TYPES;
        this.dateRangeTypes = RANGE_TYPES;
        this.superList = globalFiltersFieldMatchers;
        onWillStart(this.onWillStart);
        onMounted(this.onMounted);
    }

    /**
     * Retrieve the placeholder of the label
     */
    get placeholder() {
        return sprintf(_t("New %s filter"), this.state.type);
    }

    get missingLabel() {
        return this.state.saved && !this.state.label;
    }

    get missingModel() {
        return (
            this.state.saved &&
            this.state.type === "relation" &&
            !this.state.relation.relatedModel.technical
        );
    }

    shouldDisplayFieldMatching() {
        return (
            this.state.fieldMatchings.length &&
            (this.state.type !== "relation" || this.state.relation.relatedModel.technical)
        );
    }

    isDateTypeSelected(dateType) {
        return dateType === this.state.date.type;
    }

    /**
     * List of model names of all related models of all pivots
     * @returns {Array<string>}
     */
    get relatedModels() {
        const all = this.state.fieldMatchings.map((object) => Object.values(object.fields()));
        return [
            ...new Set(
                all
                    .flat()
                    .filter((field) => field.relation)
                    .map((field) => field.relation)
            ),
        ];
    }

    loadValues() {
        this.id = this.props.id;
        const globalFilter = this.id && this.getters.getGlobalFilter(this.id);
        if (globalFilter) {
            this.state.label = _t(globalFilter.label);
            this.state.type = globalFilter.type;
            this.state.date.type = globalFilter.rangeType;
            this.state.date.defaultsToCurrentPeriod = globalFilter.defaultsToCurrentPeriod;
            this.state.date.automaticDefaultValue = globalFilter.automaticDefaultValue;
            this.state[this.state.type].defaultValue = globalFilter.defaultValue;
            if (globalFilter.type === "relation") {
                this.state.relation.relatedModel.technical = globalFilter.modelName;
            }
        }
    }

    async _loadFieldMatchings() {
        for (const [type, el] of Object.entries(globalFiltersFieldMatchers)) {
            for (const objectId of el.geIds()) {
                const tag = await el.getTag(objectId);
                this.state.fieldMatchings.push({
                    name: el.getDisplayName(objectId),
                    tag,
                    fieldMatch: el.getFieldMatching(objectId, this.id) || {},
                    fields: () => el.getFields(objectId),
                    model: () => el.getModel(objectId),
                    payload: () => ({ id: objectId, type }),
                });
            }
        }
    }

    async onWillStart() {
        const proms = [];
        proms.push(this.fetchModelFromName());
        proms.push(
            ...Object.values(this.superList)
                .map((el) => el.waitForReady())
                .flat()
        );
        this._loadFieldMatchings();
        await Promise.all(proms);
    }

    onMounted() {
        this.el.querySelector(".o_global_filter_label").focus();
    }

    /**
     * Get the first field which could be a relation of the current related
     * model
     *
     * @param {Object.<string, Field>} fields Fields to look in
     * @returns {string|undefined}
     */
    _findRelation(fields) {
        const field = Object.values(fields).find(
            (field) =>
                field.searchable && field.relation === this.state.relation.relatedModel.technical
        );
        return field.name;
    }

    async onModelSelected({ technical, label }) {
        if (!this.state.label) {
            this.state.label = label;
        }
        if (this.state.relation.relatedModel.technical !== technical) {
            this.state.relation.defaultValue = [];
        }
        this.state.relation.relatedModel.technical = technical;
        this.state.relation.relatedModel.label = label;

        for (const [index, object] of Object.entries(this.state.fieldMatchings)) {
            const fieldName = this._findRelation(object.fields());
            this.selectedField(index, fieldName);
        }
    }

    async fetchModelFromName() {
        if (!this.state.relation.relatedModel.technical) {
            return;
        }
        const result = await this.orm.call("ir.model", "display_name_for", [
            [this.state.relation.relatedModel.technical],
        ]);
        this.state.relation.relatedModel.label = result[0] && result[0].display_name;
        if (!this.state.label) {
            this.state.label = this.state.relation.relatedModel.label;
        }
    }

    /**
     * Function that will be called by ModelFieldSelector on each fields, to
     * filter the ones that should be displayed
     * @returns {boolean}
     */
    filterModelFieldSelectorField(field) {
        const type = this.state.type;
        if (ALLOWED_FIELD_TYPES[type].includes(field.type)) {
            const relatedModel = this.state.relation.relatedModel.technical;
            if (field.searchable && (!relatedModel || field.relation === relatedModel)) {
                return true;
            }
        }
        return false;
    }

    /**
     * @param {string} index
     * @param {string|undefined} chain
     */
    selectedField(index, chain) {
        if (!chain) {
            this.state.fieldMatchings[index].fieldMatch = {};
            return;
        }
        // TODO: consider the whole chain. (need to have the whole relational field tree for this)
        const fieldName = chain.split(".")[0];
        const field = this.state.fieldMatchings[index].fields()[fieldName];
        if (field) {
            this.state.fieldMatchings[index].fieldMatch = {
                chain: fieldName,
                type: field.type,
            };
            if (this.state.type === "date") {
                this.state.fieldMatchings[index].fieldMatch.offset = 0;
            }
        }
    }

    getModelField(fieldMatch) {
        if (!fieldMatch || !fieldMatch.chain) {
            return "";
        }
        return fieldMatch.chain;
    }

    /**
     * @param {string} index
     * @param {string} offset
     */
    onSetFieldOffset(index, offset) {
        this.state.fieldMatchings[index].fieldMatch.offset = parseInt(offset);
    }

    onSave() {
        this.state.saved = true;
        if (this.missingLabel || this.missingModel) {
            this.notification.add(this.env._t("Some required fields are not valid"), {
                type: "danger",
                sticky: false,
            });
            return;
        }
        const cmd = this.id ? "EDIT_GLOBAL_FILTER" : "ADD_GLOBAL_FILTER";
        const id = this.id || uuidGenerator.uuidv4();
        const filter = {
            id,
            type: this.state.type,
            label: this.state.label,
            modelName: this.state.relation.relatedModel.technical,
            defaultValue: this.state[this.state.type].defaultValue,
            defaultValueDisplayNames: this.state[this.state.type].displayNames,
            rangeType: this.state.date.type,
            defaultsToCurrentPeriod: this.state.date.defaultsToCurrentPeriod,
        };
        // here populate the command a bit more with a key chart, pivot or list
        // (inside the command which goes against the static part but osef)
        const additionalPayload = {};
        Object.values(this.state.fieldMatchings).forEach((fm) => {
            const { type, id } = fm.payload();
            additionalPayload[type] = additionalPayload[type] || {};
            //remove reactivity
            additionalPayload[type][id] = { ...fm.fieldMatch };
        });
        const result = this.env.model.dispatch(cmd, { id, filter, ...additionalPayload });
        if (result.isCancelledBecause(CommandResult.DuplicatedFilterLabel)) {
            this.notification.add(this.env._t("Duplicated Label"), {
                type: "danger",
                sticky: false,
            });
            return;
        }
        this.env.openSidePanel("GLOBAL_FILTERS_SIDE_PANEL", {});
    }

    onCancel() {
        this.env.openSidePanel("GLOBAL_FILTERS_SIDE_PANEL", {});
    }

    onValuesSelected(value) {
        this.state.relation.defaultValue = value.map((record) => record.id);
        this.state.relation.displayNames = value.map((record) => record.display_name);
    }

    onTimeRangeChanged(defaultValue) {
        this.state.date.defaultValue = defaultValue;
    }

    onDelete() {
        if (this.id) {
            this.env.model.dispatch("REMOVE_GLOBAL_FILTER", { id: this.id });
        }
        this.env.openSidePanel("GLOBAL_FILTERS_SIDE_PANEL", {});
    }

    onDateOptionChange(ev) {
        // TODO t-model does not work ?
        this.state.date.type = ev.target.value;
        this.state.date.defaultValue = {};
    }

    toggleDefaultsToCurrentPeriod(ev) {
        this.state.date.defaultsToCurrentPeriod = ev.target.checked;
    }
}
FilterEditorSidePanel.template = "spreadsheet_edition.FilterEditorSidePanel";
FilterEditorSidePanel.components = {
    ModelFieldSelector,
    ModelSelector,
    RecordsSelector,
    DateFilterValue,
    FilterFieldOffset,
};
