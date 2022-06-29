/** @odoo-module **/

import { patch } from '@web/core/utils/patch';
import { ListRenderer } from '@web/views/list/list_renderer';
import { useService, useBus } from "@web/core/utils/hooks";
import { _t } from "web.core";
import { removeContextUserInfo } from "../helpers";
import { SpreadsheetSelectorDialog } from "../components/spreadsheet_selector_dialog/spreadsheet_selector_dialog";
import { HandleField } from '@web/views/fields/handle/handle_field';

patch(ListRenderer.prototype, 'documents_spreadsheet_list_renderer_patch', {
    /**
     * @override
     */
    setup() {
        this._super(...arguments);
        this.dialogService = useService("dialog");

        useBus(
            this.env.bus,
            "insert-list-spreadsheet",
            this.insertListSpreadsheet.bind(this),
        );
    },

    insertListSpreadsheet() {
        const model = this.env.model.root;
        const threshold = Math.min(model.count, model.limit);
        let name = this.env.config.getDisplayName();
        const sortBy = model.orderBy[0];
        if (sortBy) {
            name += ` ${_t("by")} ` + model.fields[sortBy.name].string;
        }
        const { list, fields } = this.getListForSpreadsheet(name);
        const actionOptions = {
            preProcessingAsyncAction: "insertList",
            preProcessingAsyncActionData: { list, threshold, fields },
        };
        const params = {
            threshold,
            type: "LIST",
            name,
            actionOptions,
        };
        this.dialogService.add(SpreadsheetSelectorDialog, params);
    },

    getColumnsForSpreadsheet() {
        const fields = this.env.model.root.fields;
        return this.state.columns
            .filter(col => col.type === "field" &&
                           col.FieldComponent !== HandleField &&
                           fields[col.name].type !== 'binary')
            .map(col => ({ name: col.name, type: fields[col.name].type}));
    },

    getListForSpreadsheet(name) {
        const model = this.env.model.root;
        return {
            list: {
                model: model.resModel,
                domain: model.domain,
                orderBy: model.orderBy,
                context: removeContextUserInfo(model.context),
                columns: this.getColumnsForSpreadsheet(),
                name,
            },
            fields: model.fields,
        };
    }
});
