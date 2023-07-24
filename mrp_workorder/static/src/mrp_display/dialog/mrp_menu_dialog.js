/** @odoo-module */

import { Dialog } from "@web/core/dialog/dialog";
import { _t } from "@web/core/l10n/translation";
import { useService } from "@web/core/utils/hooks";
import { MrpWorkcenterDialog } from "./mrp_workcenter_dialog";
import { MrpQualityCheckSelectDialog } from "./mrp_check_select_dialog";

import { Component } from "@odoo/owl";

export class MrpMenuDialog extends Component {
    static props = {
        close: Function,
        groups: Object,
        params: Object,
        record: Object,
        reload: Function,
        title: String,
    };
    static template = "mrp_workorder.MrpDisplayMenuDialog";
    static components = { Dialog };

    setup() {
        this.orm = useService("orm");
        this.action = useService("action");
        this.dialogService = useService("dialog");
    }

    async callAction(method) {
        const action = await this.orm.call(this.props.record.resModel, method, [
            [this.props.record.resId],
        ]);
        this.action.doAction(action, {
            onClose: async () => {
                await this.props.reload();
            }
        });
        this.props.close();
    }

    moveToWorkcenter() {
        function _moveToWorkcenter(workcenter) {
            this.props.record.update({ workcenter_id: [workcenter.id, workcenter.display_name] });
            this.props.record.save();
            this.props.close();
        }
        const params = {
            title: _t("Select a new work center"),
            confirm: _moveToWorkcenter.bind(this),
            workcenters: this.props.params.workcenters,
        };
        this.dialogService.add(MrpWorkcenterDialog, params);
    }

    openMO() {
        this.action.doAction({
            'type': 'ir.actions.act_window',
            'res_model': this.props.record.resModel,
            'views': [[false, 'form']],
            'res_id': this.props.record.resId,
        });
        this.props.close();
    }

    block() {
        const options = {
            additionalContext: { default_workcenter_id: this.props.record.data.workcenter_id[0] },
            onClose: async () => {
                await this.props.reload();
            }
        };
        this.action.doAction('mrp.act_mrp_block_workcenter_wo', options);
        this.props.close();
    }

    updateStep(){
        this.proposeChange('update_step');
    }

    addStep(){
        this.proposeChange('add_step');
    }

    removeStep(){
        this.proposeChange('remove_step');
    }

    setPicture(){
        this.proposeChange('set_picture');
    }

    proposeChange(type){
        const params = {
            title: _t("Select the concerning quality check"),
            confirm: this.proposeChangeForCheck.bind(this),
            checks: this.props.params.checks,
            type,
        };
        this.dialogService.add(MrpQualityCheckSelectDialog, params);
    }

    async proposeChangeForCheck(type, check) {
        let action;
        if (type === 'add_step'){
            await this.orm.write("mrp.workorder", [this.props.record.resId], { current_quality_check_id: check.id });
            action = await this.orm.call(
                "mrp.workorder",
                "action_add_step",
                [[this.props.record.resId]],
            );
        } else {
            action = await this.orm.call(
                "mrp.workorder",
                "action_propose_change",
                [[this.props.record.resId], type, check.id],
            );
        }
        await this.action.doAction(action, {
            onClose: async () => {
                await this.props.reload();
            }
        });
        this.props.close();
    }
}