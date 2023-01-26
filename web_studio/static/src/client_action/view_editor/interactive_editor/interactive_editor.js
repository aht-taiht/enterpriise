/** @odoo-module */
import { Component, toRaw } from "@odoo/owl";

import { closest, touching } from "@web/core/utils/ui";
import { useDraggable } from "@web/core/utils/draggable";
import { useOwnedDialogs, useService } from "@web/core/utils/hooks";
import { _lt, _t } from "@web/core/l10n/translation";
import { sprintf } from "@web/core/utils/strings";
import {
    isToXpathEquivalentFromXpath,
    cleanHooks,
    getActiveHook,
    getHooks,
    hookPositionTolerance,
    randomName,
} from "@web_studio/client_action/view_editor/editors/utils";
import { ConfirmationDialog } from "@web/core/confirmation_dialog/confirmation_dialog";
import {
    FieldConfigurationDialog,
    SelectionValuesEditor,
    RelationalFieldConfigurator,
    RelatedChainBuilder,
    getCurrencyField,
    openCurrencyConfirmDialog,
    FilterConfiguration,
} from "@web_studio/client_action/view_editor/interactive_editor/field_configuration/field_configuration";
import {
    getNodesFromXpath,
    countPreviousSiblings,
} from "@web_studio/client_action/view_editor/editors/xml_utils";
import { DefaultViewSidebar } from "@web_studio/client_action/view_editor/default_view_sidebar/default_view_sidebar";

const NO_M2O_AVAILABLE = _lt(`
    There are no many2one fields related to the current model.
    To create a one2many field on the current model, you must first create its many2one counterpart on the model you want to relate to.
`);

function copyElementOnDrag() {
    let element;
    let copy;

    function clone(_element) {
        element = _element;
        copy = element.cloneNode(true);
    }

    function insert() {
        if (element) {
            element.insertAdjacentElement("beforebegin", copy);
        }
    }

    function clean() {
        if (copy) {
            copy.remove();
        }
        copy = null;
        element = null;
    }

    return { clone, insert, clean };
}

export class InteractiveEditor extends Component {
    static template = "web_studio.InteractiveEditor";
    static components = {};
    static props = {
        editor: true,
        slots: { type: Object },
        editorContainerRef: { type: Object },
        rendererRef: { type: Object },
    };

    setup() {
        this.defaultSidebar = DefaultViewSidebar;

        this.action = useService("action");
        this.orm = useService("orm");
        this.addDialog = useOwnedDialogs();
        this.notification = useService("notification");
        /* DagDrop: from sidebar to View, and within the view */
        const getNearestHook = this.getNearestHook.bind(this);
        // Those are fine because editor defines the t-key
        const prepareForDrag = this.props.editor.prepareForDrag;
        const isValidHook = this.props.editor.isValidHook || (() => true);
        const styleNearestHook =
            this.props.editor.styleNearestHook ||
            ((ref, hook) => {
                hook.classList.add("o_web_studio_nearest_hook");
            });

        function removeBootStrapClasses(element) {
            const bootstrapClasses = Array.from(element.classList).filter(
                (c) => c.startsWith("position-") || c.startsWith("w-") || c.startsWith("h-")
            );
            if (!bootstrapClasses.length) {
                return () => {};
            }
            element.classList.remove(...bootstrapClasses);
            return () => {
                element.classList.add(...bootstrapClasses);
            };
        }

        let cleanUps;
        const copyOnDrag = copyElementOnDrag();
        useDraggable({
            ref: this.props.editorContainerRef,
            elements: ".o-draggable",
            onWillStartDrag: ({ element }) => {
                cleanUps = [];
                if (element.closest(".o_web_studio_component")) {
                    copyOnDrag.clone(element);
                }
            },
            onDragStart: ({ element }) => {
                cleanUps.push(removeBootStrapClasses(element));
                copyOnDrag.insert();
                if (prepareForDrag) {
                    cleanUps.push(
                        prepareForDrag({
                            element,
                            viewEditorModel: this.viewEditorModel,
                            ref: this.props.editorContainerRef,
                        })
                    );
                }
            },
            onDrag: ({ x, y, element }) => {
                cleanHooks(this.viewRef.el);
                element.classList.remove("o-draggable--drop-ready");
                const hook = getNearestHook(element, { x, y });
                if (!hook) {
                    return;
                }
                if (!isValidHook({ hook, element, viewEditorModel: this.viewEditorModel })) {
                    return;
                }
                styleNearestHook(this.props.rendererRef, hook);
                element.classList.add("o-draggable--drop-ready");
            },
            onDrop: ({ element }) => {
                const targetHook = getActiveHook(this.viewRef.el);
                if (!targetHook) {
                    return;
                }
                const { xpath, position, type, infos } = targetHook.dataset;
                const droppedData = element.dataset;

                const isNew = element.classList.contains("o_web_studio_component");
                const structure = isNew ? droppedData.structure : "field"; // only fields can be moved

                if (isNew) {
                    this.addStructure(structure, droppedData.drop, {
                        xpath,
                        position,
                        type,
                        infos,
                    });
                } else {
                    this.moveStructure(structure, droppedData, { xpath, position });
                }
            },
            onDragEnd: ({ element }) => {
                cleanHooks(this.viewRef.el);
                if (cleanUps) {
                    cleanUps.forEach((c) => c());
                    cleanUps = null;
                }
                copyOnDrag.clean();
            },
        });

        this.applyAutoClick = () => {
            if (!this.autoClick) {
                return;
            }

            const { targetInfo, tag, attrs } = this.autoClick;

            // First step: locate node in new arch
            let xpathToClick = targetInfo.xpath;
            if (tag) {
                // We are trying to select a new node of which targetInfo could be its parent
                if (targetInfo.position !== "inside") {
                    xpathToClick = xpathToClick.split("/").slice(0, -1).join("/");
                }

                const attrForXpath = Object.entries(attrs)
                    .filter(([, value]) => !!value)
                    .map(([attName, value]) => {
                        return `@${attName}='${value}'`;
                    })
                    .join(" and ");
                const nodeXpath = `${tag}[${attrForXpath}]`;
                const fullXpath = `${xpathToClick}/${nodeXpath}`;

                const nodes = getNodesFromXpath(fullXpath, toRaw(this.viewEditorModel).xmlDoc);
                this.autoClick = null; // Early reset of that variable
                if (nodes.length !== 1) {
                    return;
                }
                const atPosition = countPreviousSiblings(nodes[0]) + 1;
                xpathToClick = `${xpathToClick}/${tag}[${atPosition}]`;
            }

            // Second step: locate corresponding dom element
            const domEl = this.props.rendererRef.el.querySelector(
                `[data-studio-xpath='${xpathToClick}'], [studioxpath='${xpathToClick}']`
            );
            if (domEl) {
                domEl.click();
            }
        };
    }

    get viewEditorModel() {
        return this.env.viewEditorModel;
    }

    get viewRef() {
        return this.viewEditorModel.viewRef;
    }

    getNearestHook(draggedEl, { x, y }) {
        const viewRefEl = this.viewRef.el;
        cleanHooks(viewRefEl);

        const mouseToleranceRect = {
            x: x - hookPositionTolerance,
            y: y - hookPositionTolerance,
            width: hookPositionTolerance * 2,
            height: hookPositionTolerance * 2,
        };

        const touchingEls = touching(getHooks(viewRefEl), mouseToleranceRect);
        const closestHookEl = closest(touchingEls, { x, y });

        return closestHookEl;
    }

    openViewInForm() {
        return this.action.doAction(
            {
                type: "ir.actions.act_window",
                res_model: "ir.ui.view",
                res_id: this.env.viewEditorModel.mainView.id,
                views: [[false, "form"]],
                target: "current",
            },
            { clearBreadcrumbs: true }
        );
    }

    openDefaultValues() {
        const resModel = this.env.viewEditorModel.resModel;
        this.action.doAction(
            {
                name: _t("Default Values"),
                type: "ir.actions.act_window",
                res_model: "ir.default",
                target: "current",
                views: [
                    [false, "list"],
                    [false, "form"],
                ],
                domain: [["field_id.model", "=", resModel]],
            },
            { clearBreadcrumbs: true }
        );
    }

    setAutoClick(targetInfo, nodeDescr) {
        if (!targetInfo) {
            this.autoClick = null;
            return;
        }
        if (targetInfo && !nodeDescr) {
            this.autoClick = {
                targetInfo,
            };
            return;
        }
        let nameAttr = nodeDescr.attrs.name;
        if (nodeDescr.tag === "field" && !nameAttr) {
            nameAttr = nodeDescr.field_description.name;
        }
        this.autoClick = {
            targetInfo,
            tag: nodeDescr.tag,
            attrs: { name: nameAttr },
        };
    }

    async addField(droppedData, targetInfo) {
        const data = JSON.parse(droppedData);
        const isExistingField = "fieldName" in data;

        let newNode;
        if (!isExistingField) {
            newNode = await this.getNewFieldNode(data);
        } else {
            newNode = {
                tag: "field",
                attrs: { name: data.fieldName },
            };
        }
        if (!newNode) {
            return;
        }
        if (!isExistingField) {
            this.viewEditorModel.setRenameableField(newNode.field_description?.name, true);
        }

        if (this.viewEditorModel.viewType === "kanban") {
            newNode.attrs.display = "full";
        }

        if (this.viewEditorModel.viewType === "list") {
            newNode.attrs.optional = "show";
        }

        const operation = {
            node: newNode,
            target: this.viewEditorModel.getFullTarget(targetInfo.xpath),
            position: targetInfo.position,
            type: "add",
        };
        this.setAutoClick(targetInfo, newNode);
        return this.viewEditorModel.doOperation(operation);
    }

    async addStructure(structure, droppedData, targetInfo) {
        if (structure === "field" && !["groupBy", "filter"].includes(targetInfo.type)) {
            // AddField in form,list,kanban
            return this.addField(droppedData, targetInfo);
        }

        if (["notebook", "group", "separator"].includes(structure)) {
            // Add specific structure that don't need configuration (form, search)
            const operation = {
                node: {
                    tag: structure,
                    attrs: {
                        name: randomName(`studio_${structure}`),
                    },
                },
                target: this.viewEditorModel.getFullTarget(targetInfo.xpath),
                position: targetInfo.position,
                type: "add",
            };
            this.setAutoClick(targetInfo, operation.node);
            return this.viewEditorModel.doOperation(operation);
        }

        if (structure === "filter") {
            // For search editor
            const filterData = await new Promise((resolve) => {
                this.addDialog(FieldConfigurationDialog, {
                    env: this.env,
                    title: _t("New Filter"),
                    size: "md",
                    confirm: (data) => resolve(data),
                    cancel: () => resolve(false),
                    Component: FilterConfiguration,
                    componentProps: { resModel: this.viewEditorModel.resModel },
                });
            });
            if (!filterData) {
                return;
            }
            const node = {
                tag: "filter",
                attrs: {
                    domain: filterData.domain,
                    name: randomName("studio_filter"),
                    string: filterData.filterLabel,
                },
            };
            const operation = {
                node,
                target: this.viewEditorModel.getFullTarget(targetInfo.xpath),
                position: targetInfo.position,
                type: "add",
            };
            this.setAutoClick(targetInfo, operation.node);
            return this.viewEditorModel.doOperation(operation);
        }

        if (
            this.viewEditorModel.viewType === "search" &&
            structure === "field" &&
            ["groupBy", "filter"].includes(targetInfo.type)
        ) {
            // Add field as a filter or as a groupBy, for search editor
            const fieldName = JSON.parse(droppedData).fieldName;
            const fieldGet = this.viewEditorModel.fields[fieldName];
            const willBeGroupBy = targetInfo.type === "groupBy";

            const node = {
                tag: "filter",
                attrs: {
                    name: randomName(`studio_${willBeGroupBy ? "group" : "filter"}_by`),
                    string: fieldGet.string,
                },
            };

            if (willBeGroupBy) {
                node.attrs.context = `{'group_by': '${fieldName}'}`;
                if (targetInfo.infos && JSON.parse(targetInfo.infos).create_group) {
                    node.attrs.create_group = true;
                }
            } else {
                node.attrs.date = fieldName;
            }
            const operation = {
                node,
                target: this.viewEditorModel.getFullTarget(targetInfo.xpath),
                position: targetInfo.position,
                type: "add",
            };
            this.setAutoClick(targetInfo, operation.node);
            return this.viewEditorModel.doOperation(operation);
        }
    }

    async getNewFieldNode(data) {
        const string = sprintf(_t("New %s"), data.string);

        const newNode = {
            field_description: {
                field_description: string,
                name: randomName(`x_studio_${data.fieldType}_field`),
                type: data.fieldType,
                model_name: this.viewEditorModel.resModel,
                special: data.special,
            },
            tag: "field",
            attrs: { widget: data.widget },
        };

        if (data.special === "lines") {
            return newNode;
        }

        const fieldType = data.fieldType;
        if (fieldType === "selection" && data.widget === "priority") {
            // should not be translated at the creation
            newNode.field_description.selection = [
                ["0", "Normal"],
                ["1", "Low"],
                ["2", "High"],
                ["3", "Very High"],
            ];
            return newNode;
        }

        if (["selection", "one2many", "many2one", "many2many", "related"].includes(fieldType)) {
            if (fieldType === "one2many") {
                const count = await this.orm.searchCount("ir.model.fields", [
                    ["relation", "=", this.viewEditorModel.resModel],
                    ["ttype", "=", "many2one"],
                ]);
                if (!count) {
                    this.addDialog(ConfirmationDialog, {
                        title: _t("No related many2one fields found"),
                        body: NO_M2O_AVAILABLE,
                        confirm: async () => {},
                    });
                    return;
                }
            }

            const fieldParams = await this.openFieldConfiguration(fieldType);
            if (!fieldParams) {
                return;
            }
            if (fieldType === "selection") {
                newNode.field_description.selection = fieldParams.selection;
            }
            if (fieldType === "one2many") {
                newNode.field_description.relation_field_id = fieldParams.relationId[0];
            }
            if (fieldType === "many2many" || fieldType === "many2one") {
                newNode.field_description.relation_id = fieldParams.relationId[0];
            }
            if (fieldType === "related") {
                Object.assign(newNode.field_description, fieldParams.relatedParams);
                if (!newNode.field_description.related) {
                    delete newNode.field_description.related;
                }
            }
        }

        if (fieldType === "monetary") {
            if (!this.hasCurrencyField()) {
                const currencyDescription = await openCurrencyConfirmDialog(
                    this.addDialog,
                    this.viewEditorModel.resModel
                );
                if (!currencyDescription) {
                    return;
                }
                Object.assign(newNode.field_description, currencyDescription);
            }
        }

        if (fieldType === "integer") {
            newNode.field_description.default_value = "0";
        }

        return newNode;
    }

    openFieldConfiguration(fieldType) {
        let dialogProps;
        if (fieldType === "selection") {
            dialogProps = {
                Component: SelectionValuesEditor,
                isDialog: true,
            };
        } else if (["one2many", "many2many", "many2one"].includes(fieldType)) {
            dialogProps = {
                Component: RelationalFieldConfigurator,
                componentProps: { fieldType, resModel: this.viewEditorModel.resModel },
            };
        } else if (fieldType === "related") {
            dialogProps = {
                Component: RelatedChainBuilder,
                componentProps: {
                    resModel: this.viewEditorModel.resModel,
                    shouldOpenCurrencyDialog: !this.hasCurrencyField(),
                },
            };
        }

        const fieldParams = new Promise((resolve, reject) => {
            this.addDialog(FieldConfigurationDialog, {
                env: this.env,
                fieldType,
                confirm: async (params) => {
                    resolve(params);
                },
                cancel: () => resolve(false),
                ...dialogProps,
            });
        });
        return fieldParams;
    }

    moveStructure(structure, droppedData, targetInfo) {
        if (structure !== "field") {
            throw Error("Moving anything else than a field is not supported");
        }

        if (
            isToXpathEquivalentFromXpath(
                targetInfo.position,
                targetInfo.xpath,
                droppedData.studioXpath
            )
        ) {
            return;
        }

        const name = droppedData.fieldName || droppedData.name; // fixme, the second one is for list view
        const operation = {
            type: "move",
            node: {
                tag: "field",
                attrs: { name },
            },
            target: this.viewEditorModel.getFullTarget(targetInfo.xpath),
            position: targetInfo.position,
        };
        const subViewXpath = this.viewEditorModel.getSubviewXpath();
        if (subViewXpath) {
            operation.node.subview_xpath = subViewXpath;
        }

        if (this.viewEditorModel.activeNodeXpath === droppedData.studioXpath) {
            this.setAutoClick(targetInfo, operation.node);
        }
        this.viewEditorModel.doOperation(operation);
    }

    hasCurrencyField() {
        return getCurrencyField(this.viewEditorModel.fields);
    }
}
