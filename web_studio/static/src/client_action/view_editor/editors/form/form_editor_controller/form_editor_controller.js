/** @odoo-module */

import { useState, onMounted, onPatched } from "@odoo/owl";
import { formView } from "@web/views/form/form_view";

function rebindLegacyDatapoint(datapoint, basicModel, evalContext) {
    const newDp = {};

    const descrs = Object.getOwnPropertyDescriptors(datapoint);
    Object.defineProperties(newDp, descrs);

    const getRecordEvalContext = basicModel._getRecordEvalContext.bind(basicModel);
    basicModel._getRecordEvalContext = (record, forDomain) => {
        if (record.id === "__can'ttouchthis__") {
            return evalContext;
        }
        return getRecordEvalContext(record, forDomain);
    };
    newDp.id = "__can'ttouchthis__";
    newDp.evalModifiers = basicModel._evalModifiers.bind(basicModel, newDp);
    newDp.getContext = basicModel._getContext.bind(basicModel, newDp);
    newDp.getDomain = basicModel._getDomain.bind(basicModel, newDp);
    newDp.getFieldNames = basicModel._getFieldNames.bind(basicModel, newDp);
    newDp.isDirty = basicModel.isDirty.bind(basicModel, newDp.id);
    newDp.isNew = basicModel.isNew.bind(basicModel, newDp.id);
    return newDp;
}

function applyParentRecordOnModel(model, parentRecord) {
    const legacyHandle = parentRecord.__bm_handle__;
    const legacyDp = parentRecord.model.__bm__.localData[legacyHandle];
    const evalContext = parentRecord.model.__bm__._getRecordEvalContext(legacyDp);

    const load = model.load;
    model.load = async (...args) => {
        const res = await load.call(model, ...args);
        const localData = model.__bm__.localData;

        const parentDp = rebindLegacyDatapoint(legacyDp, model.__bm__, evalContext);
        localData[parentDp.id] = parentDp;

        const rootDp = localData[model.root.__bm_handle__];
        rootDp.parentID = parentDp.id;
        return res;
    };
}

export class FormEditorController extends formView.Controller {
    setup() {
        super.setup();
        this.mailTemplate = null;
        this.hasFileViewerInArch = false;

        this.viewEditorModel = useState(this.env.viewEditorModel);

        if (this.props.parentRecord) {
            applyParentRecordOnModel(this.model, this.props.parentRecord);
        }

        onMounted(() => {
            const xpath = this.viewEditorModel.lastActiveNodeXpath;
            if (xpath && xpath.includes("notebook")) {
                const tabXpath = xpath.match(/.*\/page\[\d+\]/)[0];
                const tab = document.querySelector(`[data-studio-xpath='${tabXpath}'] a`);
                if (tab) {
                    // store the targetted element to restore it after being patched
                    this.notebookElementData = {
                        xpath,
                        restore: Boolean(this.viewEditorModel.activeNodeXpath),
                        sidebarTab: this.viewEditorModel.sidebarTab,
                        isTab: xpath.length === tabXpath.length,
                    };
                    tab.click();
                }
            } else {
                this.notebookElementData = null;
            }
        });

        onPatched(() => {
            if (this.notebookElementData) {
                if (
                    this.notebookElementData.isTab &&
                    this.viewEditorModel.lastActiveNodeXpath !== this.notebookElementData.xpath
                ) {
                    return;
                }
                if (this.notebookElementData.restore) {
                    this.env.config.onNodeClicked(this.notebookElementData.xpath);
                } else {
                    // no element was currently highlighted, the editor sidebar must display the stored tab
                    this.viewEditorModel.resetSidebar(this.notebookElementData.sidebarTab);
                }
                this.notebookElementData = null;
            }
        });
    }
}
FormEditorController.props = {
    ...formView.Controller.props,
    parentRecord: { type: [Object, { value: null }], optional: true },
};
