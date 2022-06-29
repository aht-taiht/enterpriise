/** @odoo-module **/

import { device } from "web.config";
import { _t } from "web.core";
import { str_to_datetime } from "web.time";
import { session } from "@web/session";
import { KeepLast } from "@web/core/utils/concurrency";
import { intersection } from "@web/core/utils/arrays";
import { AutoComplete } from "@web/core/autocomplete/autocomplete";
import { x2ManyCommands } from "@web/core/orm_service";
import { useService } from "@web/core/utils/hooks";
import { ConfirmationDialog } from "@web/core/confirmation_dialog/confirmation_dialog";
import { FileUploader } from "@web/views/fields/file_handler";
import { ChatterContainer } from "@mail/components/chatter_container/chatter_container";
import { DocumentsInspectorField } from "./documents_inspector_field";
import { download } from "@web/core/network/download";

const { Component, markup, useEffect, useState, useRef, onPatched, onWillUpdateProps, onWillStart } = owl;

async function toggleArchive(model, resModel, resIds, doArchive) {
    const method = doArchive ? "action_archive" : "action_unarchive";
    const action = await model.orm.call(resModel, method, [resIds]);
    if (action && Object.keys(action).length !== 0) {
        model.action.doAction(action);
    }
}

export const inspectorFields = [
    "attachment_id",
    "active",
    "activity_ids",
    "available_rule_ids",
    "checksum",
    "display_name",
    "folder_id",
    "lock_uid",
    "message_attachment_count",
    "message_follower_ids",
    "message_ids",
    "mimetype",
    "name",
    "owner_id",
    "partner_id",
    "previous_attachment_ids",
    "res_id",
    "res_model",
    "res_model_name",
    "res_name",
    "tag_ids",
    "type",
    "url",
    "file_size",
];

export class DocumentsInspector extends Component {
    setup() {
        this.orm = useService("orm");
        this.action = useService("action");
        this.dialogService = useService("dialog");
        this.documentsReplaceInput = useRef("replaceFileInput");
        this.chatterContainer = useRef("chatterContainer");
        this.keepLast = new KeepLast();
        this.previewLockCount = 0;
        this.str_to_datetime = str_to_datetime;
        this.state = useState({
            previousAttachmentData: null,
            previousAttachmentDirty: true,
            showChatter: this.isMobile,
        });
        const updateLockedState = (props) => {
            this.isLocked =
                (props.selection.find((rec) => rec.data.lock_uid && rec.data.lock_uid[0] !== session.uid) && true) ||
                false;
            const folderIds = props.selection.map((rec) => rec.data.folder_id[0]);
            const folders = this.env.searchModel.getFolders().filter((folder) => folderIds.includes(folder.id));
            this.isEditDisabled = !!folders.find((folder) => !folder.has_write_access);
        };
        onWillStart(() => {
            updateLockedState(this.props);
            this.updateAttachmentHistory(null);
        });
        onWillUpdateProps((nextProps) => {
            updateLockedState(nextProps);
            this.updateAttachmentHistory(nextProps);
        });
        // Chatter
        const chatterCloseHandler = () => {
            this.state.showChatter = this.isMobile;
        };
        const chatterReloadHandler = async () => {
            const record = this.props.selection[0];
            if (!record) {
                return;
            }
            await record.load();
            await record.model.notify();
        };
        useEffect(
            (el) => {
                if (!el) {
                    return;
                }
                el.addEventListener("o-close-chatter", chatterCloseHandler);
                el.addEventListener("reload", chatterReloadHandler);
                return () => {
                    el.removeEventListener("o-close-chatter", chatterCloseHandler);
                    el.removeEventListener("reload", chatterReloadHandler);
                };
            },
            () => [this.chatterContainer.el && this.chatterContainer.el.querySelector(".o_Chatter")]
        );

        //Mobile specific
        if (!device.isMobile) {
            return;
        }
        this.inspectorMobileRef = useRef("inspectorMobile");
        this.shouldOpenInspector = false;
        onWillUpdateProps((nextProps) => {
            // Only open the inspector if there is only one selected element and
            //  it was not previously selected.
            this.shouldOpenInspector = nextProps.selection.length === 1;
        });
        onPatched(() => {
            if (!this.inspectorMobileRef.el) {
                return;
            }
            if (this.shouldOpenInspector) {
                this.inspectorMobileRef.el.setAttribute("open", "");
            }
        });
    }

    get resIds() {
        return this.props.selection.map((rec) => rec.resId);
    }

    get isMobile() {
        return device.isMobile;
    }

    updateAttachmentHistory(nextProps) {
        const props = nextProps || this.props;
        const record = props.selection[0];
        if (props.selection.length !== 1) {
            this.state.showChatter = this.isMobile;
        }
        if (!record || props.selection.length !== 1 || !record.data.previous_attachment_ids.count) {
            this.keepLast.add(Promise.resolve());
            this.state.previousAttachmentData = null;
            return;
        }
        const previousRecord = this.props.selection.length === 1 && this.props.selection[0];
        if (
            nextProps &&
            previousRecord &&
            previousRecord.resId === record.resId &&
            !this.state.previousAttachmentDirty
        ) {
            return;
        }
        this.keepLast.add(
            this.orm
                .searchRead(
                    "ir.attachment",
                    [["id", "in", record.data.previous_attachment_ids.records.map((rec) => rec.resId)]],
                    ["name", "create_date", "create_uid"],
                    {
                        order: "create_date desc",
                    }
                )
                .then((result) => {
                    this.state.previousAttachmentData = result;
                    this.state.previousAttachmentDirty = false;
                })
        );
    }

    getCurrentFolder() {
        return this.env.searchModel.getSelectedFolder();
    }

    getFolderDescription() {
        return markup(this.getCurrentFolder().description);
    }

    /**
     * Returns an object with additional data for our record
     */
    getRecordAdditionalData(record) {
        const additionalData = {
            isGif: new RegExp("image.*(gif)").test(record.data.mimetype),
            isImage: new RegExp("image.*(jpeg|jpg|png)").test(record.data.mimetype),
            isYoutubeVideo: false,
            youtubeToken: undefined,
        };
        if (record.data.url && record.data.url.length) {
            const youtubeUrlMatch = record.data.url.match(
                "youtu(?:.be|be.com)/(?:.*v(?:/|=)|(?:.*/)?)([a-zA-Z0-9-_]{11})"
            );
            if (youtubeUrlMatch && youtubeUrlMatch.length > 1) {
                additionalData.isYoutubeVideo = true;
                additionalData.youtubeToken = youtubeUrlMatch[1];
            }
        }
        return additionalData;
    }

    /**
     * Returns the classes to give to the file preview
     */
    getPreviewClasses(record, additionalData) {
        const nbPreviews = this.props.selection.length;
        const classes = ["o_document_preview"];
        if (record.data.type === "empty") {
            classes.push("o_document_request_preview");
        }
        if (nbPreviews === 1) {
            classes.push("o_documents_single_preview");
        }
        if (additionalData.isImage || additionalData.isYoutubeVideo) {
            classes.push("o_documents_preview_image");
        } else {
            classes.push("o_documents_preview_mimetype");
        }
        if (additionalData.isYoutubeVideo || additionalData.isGif) {
            classes.push("o_non_image_preview");
        }
        return classes.join(" ");
    }

    isPdfOnly() {
        return this.props.selection.every((record) => record.data.mimetype === "application/pdf");
    }

    download(records) {
        if (records.length === 1) {
            download({
                data: {},
                url: `/documents/content/${records[0].resId}`,
            });
        } else {
            download({
                data: {
                    file_ids: records.map(rec => rec.resId),
                    zip_name: `documents-${moment().format("YYYY-MM-DD")}.zip`,
                },
                url: "/document/zip",
            });
        }
    }

    onDownload() {
        if (!this.props.selection.length) {
            return;
        }
        this.download(this.props.selection);
    }

    async onShare() {
        const action = await this.orm.call("documents.share", "open_share_popup", [
            {
                document_ids: [x2ManyCommands.replaceWith(this.resIds)],
                folder_id: this.env.searchModel.getSelectedFolderId(),
                type: "ids",
            },
        ]);
        this.action.doAction(action, {
            fullscreen: this.isMobile,
        });
    }

    async onReplace(ev) {
        if (!ev.target.files.length) {
            return;
        }
        const record = this.props.selection[0];
        await this.env.bus.trigger("documents-upload-files", {
            files: ev.target.files,
            folderId: this.env.searchModel.getSelectedFolderId() || (record.data.folder_id && record.data.folder_id[0]),
            recordId: this.props.selection[0].resId,
            params: {
                tagIds: this.env.searchModel.getSelectedTagIds(),
                extraHandler: () => {
                    this.state.previousAttachmentDirty = true;
                },
            },
        });
        ev.target.value = "";
    }

    async onLock() {
        await this.doLockAction(async () => {
            const record = this.props.selection[0];
            await this.orm.call("documents.document", "toggle_lock", this.resIds);
            await record.load();
            await record.model.notify();
        });
    }

    async _toggleArchive(state) {
        const record = this.props.selection[0];
        await toggleArchive(record.model, record.resModel, this.resIds, state);
        await record.model.load();
        await record.model.notify();
    }

    async onArchive() {
        await this._toggleArchive(true);
    }

    async onUnarchive() {
        await this._toggleArchive(false);
    }

    async onDelete() {
        await this.props.selection[0].model.root.deleteRecords(this.props.selection);
    }

    getFieldProps(fieldName, additionalProps) {
        const props = {
            record: this.props.selection[0],
            name: fieldName,
            selection: this.props.selection,
            inspectorReadonly: this.isLocked || this.isEditDisabled,
            lockAction: this.doLockAction.bind(this),
        };
        if (additionalProps) {
            Object.assign(props, additionalProps);
        }
        return props;
    }

    _getCommonM2M(field) {
        const selection = this.props.selection;
        let commonData = selection[0].data[field].records.map((rec) => rec.resId);
        for (let idx = 1; idx < selection.length; idx++) {
            if (commonData.length === 0) {
                break;
            }
            commonData = intersection(
                commonData,
                selection[idx].data[field].records.map((rec) => rec.resId)
            );
        }
        return commonData.map((id) => selection[0].data[field].records.find((data) => data.resId === id));
    }

    getCommonTags() {
        const searchModelTags = this.env.searchModel.getTags().reduce((res, tag) => {
            res[tag.id] = tag;
            return res;
        }, {});
        return this._getCommonM2M("tag_ids")
            .filter((rec) => searchModelTags[rec.resId])
            .map((rec) => {
                const tag = searchModelTags[rec.resId];
                return {
                    id: rec.resId,
                    name: tag.display_name,
                    group_name: tag.group_name,
                };
            });
    }

    getCommonRules() {
        let commonRules = this._getCommonM2M("available_rule_ids");
        if (this.props.selection.length > 1) {
            commonRules = commonRules.filter((rule) => !rule.data.limited_to_single_record);
        }
        return commonRules;
    }

    getAdditionalTags(commonTags) {
        return this.env.searchModel.getTags().filter((tag) => {
            return !commonTags.find((cTag) => cTag.id === tag.id);
        });
    }

    async removeTag(tag) {
        const record = this.props.selection[0];
        record.model.root._multiSave(record, {
            tag_ids: [x2ManyCommands.forget(tag.id)],
        });
    }

    async addTag(tag, { input }) {
        const record = this.props.selection[0];
        record.model.root._multiSave(record, {
            tag_ids: [x2ManyCommands.linkTo(tag.value)],
        });
        input.focus();
    }

    getTagAutocompleteProps(additionalTags) {
        return {
            value: "",
            onSelect: this.addTag.bind(this),
            sources: [
                {
                    options: (request) => {
                        request = request.toLowerCase();
                        return additionalTags
                            .filter((tag) =>
                                (tag.group_name + " > " + tag.display_name).toLowerCase().includes(request)
                            )
                            .map((tag) => {
                                return {
                                    id: tag.id,
                                    value: tag.id,
                                    label: tag.group_name + " > " + tag.display_name,
                                };
                            });
                    },
                },
            ],
            placeholder: _t(" + Add a tag"),
        };
    }

    async onClickResModel() {
        const record = this.props.selection[0];
        const action = await this.orm.call(record.data.res_model, "get_formview_action", [[record.data.res_id]], {
            context: record.model.user.context,
        });
        await this.action.doAction(action);
    }

    async triggerRule(rule) {
        await this.env.bus.trigger("documents-trigger-rule", {
            documents: this.props.selection,
            ruleId: rule.resId,
        });
    }

    async onDeletePreviousAttachment(attachmentId) {
        if (this.deleting) {
            return;
        }
        await this.doLockAction(async () => {
            this.deleting = true;
            await this.orm.unlink("ir.attachment", [attachmentId]);
            const record = this.props.selection[0];
            const model = this.props.selection[0].model;
            await record.load();
            this.state.previousAttachmentDirty = true;
            await model.notify();
            this.deleting = false;
        });
    }

    async onDownloadPreviousAttachment(attachmentId) {
        window.location = `/web/content/${attachmentId}?download=true`;
    }

    async onRestorePreviousAttachment(attachmentId) {
        const record = this.props.selection[0];
        await this.doLockAction(async () => {
            await this.orm.write("documents.document", [record.resId], {
                attachment_id: attachmentId,
            });
            await record.load();
            this.state.previousAttachmentDirty = true;
            await record.model.notify();
        });
    }

    openPreview(isPdfSplit = false) {
        if ((isPdfSplit && !this.isPdfOnly()) || this.previewLockCount) {
            return;
        }
        this.env.bus.trigger("documents-open-preview", {
            documents: this.props.selection.filter((rec) => rec.isViewable()),
            isPdfSplit,
            rules: this.getCommonRules(),
            hasPdfSplit: !this.isLocked && !this.isEditDisabled,
        });
    }

    async onEditModel() {
        const record = this.props.selection[0];
        let defaultResourceRef = false;
        if (record.data.res_model && record.data.res_id) {
            defaultResourceRef = `${record.data.res_model},${record.data.res_id}`;
        }
        const models = await this.orm.searchRead("ir.model", [["model", "=", record.data.res_model]], ["id"], {
            limit: 1,
        });
        this.action.doAction(
            {
                name: _t("Edit the linked record"),
                type: "ir.actions.act_window",
                res_model: "documents.link_to_record_wizard",
                views: [[false, "form"]],
                target: "new",
                context: {
                    default_document_ids: [record.resId],
                    default_resource_ref: defaultResourceRef,
                    default_is_readonly_model: true,
                    default_model_id: models[0].id,
                },
            },
            {
                onClose: async () => {
                    await record.model.load();
                    record.model.notify();
                },
            }
        );
    }

    onDeleteModel() {
        const recordId = this.props.selection[0].resId;
        const model = this.props.selection[0].model;
        this.dialogService.add(ConfirmationDialog, {
            body: _t("Do you really want to unlink this record?"),
            confirm: async () => {
                await this.orm.call("documents.workflow.rule", "unlink_record", [[recordId]]);
                await model.load();
                model.notify();
            },
        });
    }

    async doLockAction(func) {
        this.previewLockCount++;
        await func();
        this.previewLockCount--;
    }
}

DocumentsInspector.components = {
    AutoComplete,
    ChatterContainer,
    DocumentsInspectorField,
    FileUploader,
};

if (device.isMobile) {
    DocumentsInspector.template = "documents.DocumentsInspectorMobile";
} else {
    DocumentsInspector.template = "documents.DocumentsInspector";
}
