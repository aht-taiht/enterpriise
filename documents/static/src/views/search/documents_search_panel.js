/** @odoo-module **/

import { SearchPanel } from "@web/search/search_panel/search_panel";

import { useAutofocus, useService } from "@web/core/utils/hooks";
import { device } from "web.config";
import { sprintf } from "web.utils";

const VALUE_SELECTOR = [".o_search_panel_category_value", ".o_search_panel_filter_value"].join();
const FOLDER_VALUE_SELECTOR = ".o_search_panel_category_value";

const { onWillStart, useState } = owl;

/**
 * This file defines the DocumentsSearchPanel component, an extension of the
 * SearchPanel to be used in the documents kanban/list views.
 */

export class DocumentsSearchPanel extends SearchPanel {
    setup() {
        super.setup(...arguments);
        this.documentState = useState(this.env.documentsStore);
        this.notification = useService("notification");
        this.orm = useService("orm");
        this.user = useService("user");
        this.action = useService("action");
        this.editionState = useState({
            section: false,
            value: false,
        });

        onWillStart(async () => {
            this.isDocumentManager = await this.user.hasGroup("documents.group_documents_manager");
        });
        useAutofocus();
    }

    /**
     * Returns the fields that are supported for creating new subsections on the fly
     */
    get supportedEditionFields() {
        if (!this.isDocumentManager) {
            return [];
        }
        return ["folder_id", "tag_ids"];
    }

    get supportedDocumentsDropFields() {
        return ["folder_id", "tag_ids"];
    }

    //---------------------------------------------------------------------
    // Edition
    //---------------------------------------------------------------------

    /**
     * Prevent calling toggleCategory if it was double clicked.
     *
     * @override
     */
    toggleCategory() {
        setTimeout(() => {
            if (!this.editionState.section) {
                super.toggleCategory(...arguments);
            }
        }, 200);
    }

    /**
     * Prevent calling toggleFilterGroup if it was double clicked.
     *
     * @override
     */
    toggleFilterGroup() {
        setTimeout(() => {
            if (!this.editionState.section) {
                super.toggleFilterGroup(...arguments);
            }
        }, 200);
    }

    toggleFilterValue(filterId, valueId, { currentTarget }) {
        setTimeout(() => {
            if (!this.editionState.section) {
                super.toggleFilterValue(filterId, valueId, { currentTarget });
            }
        }, 200);
    }

    startEdition(sectionId, initialValue, value, group) {
        const section = this.env.searchModel.getSections((s) => s.id === sectionId)[0];
        if (!this.supportedEditionFields.includes(section.fieldName) || (!value && !group)) {
            return;
        }
        this.editionState.section = sectionId;
        this.editionState.initialValue = initialValue;
        this.editionState.value = value;
        this.editionState.group = group;
    }

    isEditing(section, value, group) {
        return (
            this.editionState.section === section &&
            this.editionState.value === value &&
            this.editionState.group === group
        );
    }

    stopEdition() {
        this.editionState.section = false;
        this.editionState.initialValue = false;
        this.editionState.value = false;
        this.editionState.group = false;
    }

    async onInputKeydown(ev) {
        if (ev.key !== "Enter") {
            return;
        }
        await this.confirmEdition(ev);
    }

    _getResModelResIdFromEditionState() {
        const section = this.env.searchModel.getSections((s) => s.id === this.editionState.section)[0];
        if (this.editionState.value) {
            return [
                this.documentState.model.root.activeFields[section.fieldName].relation,
                section.values.get(this.editionState.value).id,
            ];
        } else if (this.editionState.group) {
            const resId = section.groups.get(this.editionState.group).id;
            if (section.groupBy === "facet_id") {
                return ["documents.facet", resId];
            }
        }
    }

    async _reloadSearchModel(reloadCategories) {
        const searchModel = this.env.searchModel;
        // By default the category is not reloaded.
        if (reloadCategories) {
            await searchModel._fetchSections(
                searchModel.getSections((s) => s.type === "category" && s.fieldName === "folder_id"),
                []
            );
        }
        await searchModel._notify();
    }

    async confirmEdition(ev) {
        if (!this.editionState.section || (!this.editionState.value && !this.editionState.group)) {
            return;
        }
        const newValue = ev.currentTarget.value.trim();
        if (this.editionState.initialValue === newValue) {
            this.stopEdition();
            return;
        }
        const [resModel, resId] = this._getResModelResIdFromEditionState();
        await this.orm.write(resModel, [resId], {
            name: newValue,
        });
        await this._reloadSearchModel(resModel === "documents.folder" && !this.editionState.section.enableCounters);
        this.stopEdition();
    }

    async addNewSectionValue(section, parentValue) {
        const resModel = section.fieldName === "folder_id" ? "documents.folder" : "documents.tag";
        const defaultName = resModel === "documents.folder" ? this.env._t("New Workspace") : this.env._t("New Tag");
        const createValues = {
            name: defaultName,
        };
        if (resModel === "documents.folder") {
            createValues.parent_folder_id = parentValue;
        } else if (resModel === "documents.tag") {
            createValues.facet_id = parentValue;
            // There is a unicity constraint on the name of the tag, so we need to make sure that the name is unique.
            const group = section.groups.get(parentValue);
            const groupValues = [...group.values.values()];
            let index = 2;
            while (groupValues.find(v => v.display_name === createValues.name)) {
                createValues.name = defaultName + ` (${index++})`;
            }
        }
        await this.orm.create(resModel, [createValues], {
            context: {
                create_from_search_panel: true,
            },
        });
        await this._reloadSearchModel(resModel === "documents.folder" && !section.enableCounters);
        if (resModel === "documents.folder") {
            this.state.expanded[section.id][parentValue] = true;
        }
        this.render(true);
    }

    async editSectionValue(section) {
        const [resModel, resId] = this._getResModelResIdFromEditionState();
        this.action.doAction({
            res_model: resModel,
            res_id: resId,
            name: this.env._t("Edit"),
            type: "ir.actions.act_window",
            target: "new",
            views: [[false, "form"]],
        }, {
            onClose: this._reloadSearchModel.bind(this, true),
        });
    }

    async removeSectionValue(section) {
        const [resModel, resId] = this._getResModelResIdFromEditionState();
        if (resModel !== "documents.folder") {
            await this.orm.unlink(resModel, [resId]);
            await this._reloadSearchModel(resModel === "documents.folder" && !section.enableCounters);
        } else {
            this.action.doAction("documents.documents_folder_deletion_wizard_action", {
                additionalContext: {
                    default_folder_id: resId,
                },
                onClose: () => {
                    this._reloadSearchModel(true).then(this.render.bind(this, true));
                },
            });
        }
        this.stopEdition();
    }

    //---------------------------------------------------------------------
    // Data Transfer
    //---------------------------------------------------------------------

    /**
     * Gives the "dragover" class to the given element or remove it if none
     * is provided.
     * @private
     * @param {HTMLElement} [newDragFocus]
     */
    updateDragOverClass(newDragFocus) {
        const allSelected = this.root.el.querySelectorAll(":scope .o_drag_over_selector");
        for (const selected of allSelected) {
            selected.classList.remove("o_drag_over_selector");
        }
        if (newDragFocus) {
            newDragFocus.classList.add("o_drag_over_selector");
        }
    }

    isValidDragTransfer(section, value, target, dataTransfer) {
        if (dataTransfer.types.includes("o_documents_data")) {
            return (
                value.id &&
                target &&
                target.closest(VALUE_SELECTOR) &&
                this.supportedDocumentsDropFields.includes(section.fieldName)
            );
        } else if (dataTransfer.types.includes("o_documents_drag_folder")) {
            return (
                section.fieldName === "folder_id" &&
                this.draggingFolder.id !== value.id &&
                this.draggingFolder.parent_folder_id !== value.id &&
                target &&
                target.closest(FOLDER_VALUE_SELECTOR)
            );
        }
        return false;
    }

    onDragStartFolder(value, ev) {
        if (!value.id || !this.isDocumentManager) {
            return;
        }
        ev.dataTransfer.setData("o_documents_drag_folder", "");
        const newElement = document.createElement("span");
        newElement.classList.add("o_documents_drag_icon");
        newElement.innerText = value.display_name;
        document.body.append(newElement);
        ev.dataTransfer.setDragImage(newElement, -5, -5);
        this.draggingFolder = value;
        setTimeout(() => newElement.remove());
    }

    /**
     * @param {Object} section
     * @param {Object} value
     * @param {DragEvent} ev
     */
    onDragEnter(section, value, ev) {
        if (!this.isValidDragTransfer(section, value, ev.currentTarget, ev.dataTransfer)) {
            this.updateDragOverClass(null);
            return;
        }
        this.updateDragOverClass(ev.currentTarget);
        if (value.childrenIds && value.childrenIds.length) {
            this.state.expanded[section.id][value.id] = true;
        }
    }

    onDragLeave(section, { relatedTarget, dataTransfer }) {
        if (!this.isValidDragTransfer(section, { id: -1 }, relatedTarget, dataTransfer)) {
            this.updateDragOverClass(null);
        }
    }

    async onDrop(section, value, ev) {
        this.updateDragOverClass(null);
        if (this.isValidDragTransfer(section, value, ev.relatedTarget, ev.dataTransfer)) {
            return;
        }
        if (ev.dataTransfer.types.includes("o_documents_data")) {
            await this.onDropDocuments(section, value, ev);
        } else if (ev.dataTransfer.types.includes("o_documents_drag_folder")) {
            await this.onDropFolder(section, value, ev);
        }
    }

    async onDropFolder(section, value, ev) {
        if (
            !this.isValidDragTransfer(section, value, ev.currentTarget, ev.dataTransfer) ||
            this.draggingFolder.id === value.id
        ) {
            return;
        }
        // Dropping a folder into another one makes the dropped folder a child of the parent
        await this.orm.call("documents.folder", "set_parent_folder", [[this.draggingFolder.id], value.id]);
        await this._reloadSearchModel(true);
        this.render(true);
    }

    /**
     * Allows the selected kanban cards to be dropped in folders (workspaces) or tags.
     * @private
     * @param {Object} section
     * @param {Object} value
     * @param {DragEvent} ev
     */
    async onDropDocuments(section, value, { currentTarget, dataTransfer }) {
        if (
            currentTarget.classList.contains("active") || // prevents dropping in the current folder
            !this.isValidDragTransfer(section, value, currentTarget, dataTransfer)
        ) {
            return;
        }
        if (section.fieldName === "folder_id") {
            const currentFolder = this.env.searchModel.getSelectedFolder();
            if ((currentFolder.id && !currentFolder.has_write_access) || !value.has_write_access) {
                return this.notification.add(
                    this.env._t("You don't have the rights to move documents to that workspace"),
                    {
                        title: this.env._t("Access Error"),
                        type: "warning",
                    }
                );
            }
        }
        const data = JSON.parse(dataTransfer.getData("o_documents_data"));
        if (data.lockedCount) {
            return this.notification.add(
                sprintf(this.env._t("%s file(s) not moved because they are locked by another user"), data.lockedCount),
                {
                    title: this.env._t("Partial transfer"),
                    type: "warning",
                }
            );
        }
        if (section.fieldName === "folder_id") {
            this.env.searchModel.updateRecordFolderId(data.recordIds, value.id);
        } else {
            this.env.searchModel.updateRecordTagId(data.recordIds, value.id);
        }
    }

    /**
     * Handles the resize feature on the sidebar
     *
     * @private
     * @param {MouseEvent} ev
     */
    _onStartResize(ev) {
        // Only triggered by left mouse button
        if (ev.button !== 0) {
            return;
        }

        const initialX = ev.pageX;
        const initialWidth = this.root.el.offsetWidth;
        const resizeStoppingEvents = ["keydown", "mousedown", "mouseup"];

        // Mousemove event : resize header
        const resizePanel = (ev) => {
            ev.preventDefault();
            ev.stopPropagation();
            const delta = ev.pageX - initialX;
            const newWidth = Math.max(10, initialWidth + delta);
            this.root.el.style["min-width"] = `${newWidth}px`;
        };
        document.addEventListener("mousemove", resizePanel, true);

        // Mouse or keyboard events : stop resize
        const stopResize = (ev) => {
            // Ignores the initial 'left mouse button down' event in order
            // to not instantly remove the listener
            if (ev.type === "mousedown" && ev.button === 0) {
                return;
            }
            ev.preventDefault();
            ev.stopPropagation();

            document.removeEventListener("mousemove", resizePanel, true);
            resizeStoppingEvents.forEach((stoppingEvent) => {
                document.removeEventListener(stoppingEvent, stopResize, true);
            });
            // we remove the focus to make sure that the there is no focus inside
            // the panel. If that is the case, there is some css to darken the whole
            // thead, and it looks quite weird with the small css hover effect.
            document.activeElement.blur();
        };
        // We have to listen to several events to properly stop the resizing function. Those are:
        // - mousedown (e.g. pressing right click)
        // - mouseup : logical flow of the resizing feature (drag & drop)
        // - keydown : (e.g. pressing 'Alt' + 'Tab' or 'Windows' key)
        resizeStoppingEvents.forEach((stoppingEvent) => {
            document.addEventListener(stoppingEvent, stopResize, true);
        });
    }
}

DocumentsSearchPanel.modelExtension = "DocumentsSearchPanel";

if (!device.isMobile) {
    DocumentsSearchPanel.template = "documents.SearchPanel";
    DocumentsSearchPanel.subTemplates = {
        category: "documents.SearchPanel.Category",
        filtersGroup: "documents.SearchPanel.FiltersGroup",
    };
}
