/** @odoo-module **/

import { registry } from "@web/core/registry";
import { Dropdown } from "@web/core/dropdown/dropdown";
import { DropdownItem } from "@web/core/dropdown/dropdown_item";
import { useService } from "@web/core/utils/hooks";

const { Component } = owl;

export class BankRecWidgetFormRecoModelsWidget extends Component {
    setup() {
        super.setup();
        this.actionService = useService("action");
    }

    get record() {
        return this.env.model.root;
    }

    /** Create the data to render the template **/
    getRenderValues(){
        return this.record.data.reco_models_widget;
    }

    /** The user clicked on a reco model. **/
    async selectRecoModel(reco_model_id, already_selected){
        if (already_selected) {
            this.record.update({ todo_command: `unselect_reconcile_model_button,${reco_model_id}`});
        } else {
            await this.record.update({ todo_command: `select_reconcile_model_button,${reco_model_id}`});

            const line_index = this.record.data.lines_widget.lines.slice(-1)[0].index.value;
            await this.record.update({todo_command: `mount_line_in_edit,${line_index}`});
        }
    }

    /** The user clicked to quickly create a new reco model. **/
    async _onClickCreateReconciliationModel(ev) {
        return this.actionService.doAction({
            type: "ir.actions.act_window",
            res_model: "account.reconcile.model",
            views: [[false, "form"]],
            target: "current",
            context: {
                default_match_journal_ids: this.record.data.journal_id,
            },
        });
    }

}

BankRecWidgetFormRecoModelsWidget.template = "account_accountant.bank_rec_widget_form_reco_models_widget";
BankRecWidgetFormRecoModelsWidget.components = { Dropdown, DropdownItem };

export const bankRecWidgetFormRecoModelsWidget = {
    component: BankRecWidgetFormRecoModelsWidget,
};

registry
    .category("fields")
    .add("bank_rec_widget_form_reco_models_widget", bankRecWidgetFormRecoModelsWidget);
