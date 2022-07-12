/** @odoo-module **/

import { AutoComplete } from "@web/core/autocomplete/autocomplete";
import { useService } from "@web/core/utils/hooks";
import { fuzzyLookup } from "@web/core/utils/search";
import { _t } from "@web/core/l10n/translation";

const { Component, useState, onWillStart, onWillUpdateProps } = owl;

export class ModelSelector extends Component {
    setup() {
        this.orm = useService("orm");
        this.state = useState({
            autocompleteValue: this.props.value || "",
        });

        onWillStart(async () => {
            this.models = await this.orm.call("ir.model", "display_name_for", [this.props.models]);
            this.models = this.models.map((record) => ({
                label: record.display_name,
                technical: record.model,
                classList: {
                    [`o_sp_selector_${record.model}`]: 1,
                },
            }));
        });

        onWillUpdateProps((nextProps) => {
            this.state.autocompleteValue = nextProps.value || this.state.autocompleteValue;
        });
    }

    get placeholder() {
        return _t("Start typing to search more...");
    }

    get sources() {
        return [this.optionsSource];
    }
    get optionsSource() {
        return {
            placeholder: _t("Loading..."),
            options: this.loadOptionsSource.bind(this),
        };
    }

    onSelect(option) {
        this.state.autocompleteValue = "";
        this.props.onModelSelected({
            label: option.label,
            technical: option.technical,
        });
    }

    onInput({ inputValue }) {
        this.state.autocompleteValue = inputValue;
    }

    filterModels(name) {
        if (!name) {
            return this.models.slice(0, 8);
        }
        return fuzzyLookup(name, this.models, (model) => model.technical + model.label).slice(0, 8);
    }

    loadOptionsSource(request) {
        const options = this.filterModels(request);

        if (!options.length) {
            options.push({
                label: _t("No records"),
                classList: "o_m2o_no_result",
                unselectable: true,
            });
        }
        return options;
    }
}

ModelSelector.template = "spreadsheet_edition.ModelSelector";
ModelSelector.components = { AutoComplete };
ModelSelector.props = {
    onModelSelected: Function,
    value: { type: String, optional: true },
    models: Array,
};
