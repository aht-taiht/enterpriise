odoo.define('documents.DocumentViewer', function (require) {
'use strict';

const PdfManager = require('documents.component.PdfManager');
const DocumentViewer = require('@mail/js/document_viewer')[Symbol.for("default")];
const { _t } = require('web.core');
const { ComponentWrapper, WidgetAdapterMixin } = require('web.OwlCompatibility');

/**
 * This file defines the DocumentViewer for the Documents Kanban view.
 */
const DocumentsDocumentViewer = DocumentViewer.extend(WidgetAdapterMixin, {
    template: "DocumentsDocumentViewer",
    events: Object.assign({}, DocumentViewer.prototype.events, {
        'click .o_documents_pdf_manager_button': '_onClickDocumentsPdfManagerButton',
    }),
    custom_events: Object.assign({}, DocumentViewer.prototype.custom_events, {
        process_documents: '_onProcessDocuments',
        pdf_manager_error: '_onPdfManagerError', // triggered by pdf-manager-error from the owl component
    }),

    /**
     * This override changes the value of modelName used as a parameter
     * for download routes (web/image, web/content,...)
     *
     * @override
     * @param {Object} param3
     * @param {boolean} param3.openPdfManager
     * @param {Object[]} param3.rules the workflow rules that can be applied to the documents
     */
    init(parent, attachments, activeAttachmentID, { openPdfManager, hasButtonAccess, rules } = {}) {
        this._super(...arguments);
        this.modelName = 'documents.document';
        this._documents = attachments;
        this._isPdfManagerMounted = false;
        this._openPdfManager = openPdfManager;
        // array of the document ids that were generated by the pdfManager
        this._newDocumentIds = [];
        this._pdfManager = undefined;
        this._workflowRules = rules.filter((rule) => rule.create_model !== "link.to.record");
        this.hasButtonAccess = hasButtonAccess;
    },

    /**
     * @override
     */
    async start() {
        await this._super(...arguments);
        const isPdfOnly = this._documents.every(record => record.mimetype === 'application/pdf');
        if (this._openPdfManager && isPdfOnly) {
            await this._renderPdfManager(this._documents);
        }
    },

    destroy() {
        if (this._newDocumentIds.length) {
            this.trigger_up('document_viewer_attachment_changed', { documentIds: this._newDocumentIds });
        }
        this._pdfManager && this._pdfManager.destroy();
        this._super(...arguments);
    },

    //--------------------------------------------------------------------------
    // Private
    //--------------------------------------------------------------------------

    async _renderPdfManager(documents) {
        const $documentViewerElements = this.$('.o_viewer_content, .move_previous, .move_next');
        $documentViewerElements.addClass('o_hidden');
        this._pdfManager = new ComponentWrapper(this, PdfManager, {
            documents,
            rules: this._workflowRules,
        });
        await this._pdfManager.mount(this.el);
        this._isPdfManagerMounted = true;
    },

    //--------------------------------------------------------------------------
    // Handlers
    //--------------------------------------------------------------------------

    /**
     * @private
     * @param {MouseEvent} ev
     */
    async _onClickDocumentsPdfManagerButton(ev) {
        ev.stopPropagation();
        ev.preventDefault();
        await this._renderPdfManager([this.activeAttachment]);
    },

    /**
     * Prevents key interactions with the documentViewer while the pdfManager is open.
     *
     * @private
     * @override
     * @param {KeyEvent} e
     */
    _onKeyUp(e) {
        if (this._isPdfManagerMounted) {
            return;
        }
        this._super(...arguments);
    },
    /**
     * Prevents key interactions with the documentViewer while the pdfManager is open.
     *
     * @private
     * @override
     * @param {KeyEvent} e
     */
    _onKeydown(e) {
        if (this._isPdfManagerMounted) {
            return;
        }
        this._super(...arguments);
    },
    /**
     * Triggered if the pdfManager failed to upload the files.
     *
     * @private
     * @param {OdooEvent} ev
     */
    _onPdfManagerError(ev) {
        ev.stopPropagation();
        const { message } = ev.data;
        this.displayNotification({ title: _t("Error"), message });
    },
    /**
     * @private
     * @param {OdooEvent} ev
     * @param {Object} [ev.data]
     * @param {number[]} [ev.data.documentIds]
     * @param {number} [ev.data.ruleId]
     * @param {boolean} [ev.data.exit]
     */
    _onProcessDocuments(ev) {
        ev.stopPropagation();
        const { documentIds, ruleId, exit } = ev.data || {};
        if (documentIds && documentIds.length) {
            this._newDocumentIds = [...new Set(this._newDocumentIds.concat(documentIds))];
        }
        if (ruleId) {
            this.trigger_up('trigger_rule', {
                recordIds: documentIds,
                ruleId,
                preventReload: !exit,
            });
        }
        if (exit) {
            this.destroy();
        }
    },

});

return DocumentsDocumentViewer;

});
