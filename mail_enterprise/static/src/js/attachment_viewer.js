/** @odoo-module **/

import { replace } from '@mail/model/model_field_command';

import core from 'web.core';
import Widget from 'web.Widget';
import { hidePDFJSButtons } from '@web/legacy/js/libs/pdfjs';

var QWeb = core.qweb;

var AttachmentViewer = Widget.extend({
    className: 'o_attachment_preview_container',
    events: {
        'click .arrow.o_move_next': '_onClickNext',
        'click .arrow.o_move_previous': '_onClickPrevious',
    },
    /**
     * The AttachmentViewer takes an array of objects describing attachments in
     * argument and first attachment of the array is display first.
     *
     * @constructor
     * @override
     * @param {Widget} parent
     * @param {Thread} thread
     */
    init: function (parent, thread) {
        this._super.apply(this, arguments);
        this.thread = thread;
        this.attachments = this.thread.attachmentsInWebClientView;
        this._setActive();
    },
    /**
     * Render attachment.
     *
     * @override
     */
    start: function () {
        this._renderAttachment();
        return this._super.apply(this, arguments);
    },

    //--------------------------------------------------------------------------
    // Public
    //--------------------------------------------------------------------------

    /**
     * Update attachments list and activeAttachment.

     * @param {Thread} thread
     */
    updateContents(thread) {
        this.thread = thread;
        this.attachments = this.thread.attachmentsInWebClientView;
        this._setActive();
        this._renderAttachment();
    },

    //--------------------------------------------------------------------------
    // Private
    //--------------------------------------------------------------------------

    /**
     * Render template
     *
     * @private
     */
    _renderAttachment: function () {
        this.$el.empty();
        this.$el.append(QWeb.render('mail_enterprise.AttachmentPreview', { thread: this.thread }));
        if (this.thread.mainAttachment && this.thread.mainAttachment.isPdf) {
            hidePDFJSButtons(this.el);
        }
    },

    /**
     * @private
     */
    _setActive: function () {
        if (!this.thread.mainAttachment && this.thread.attachmentsInWebClientView.length > 0) {
            this._switch_main_attachment(0);
        }
    },

    //--------------------------------------------------------------------------
    // Handlers
    //--------------------------------------------------------------------------
    /**
    * Sets the attachment at position index as the new main attachment of
    * the related model, and display it.
    **/
    _switch_main_attachment: function (index) {
        var self = this;
        this.thread.update({ mainAttachment: replace(this.thread.attachmentsInWebClientView[index]) });
        this._rpc({
            model: 'ir.attachment',
            method: 'register_as_main_attachment',
            args: [[this.thread.mainAttachment['id']]],
        }).then(
            function() {
                self._renderAttachment();
            }
        );
    },

    /**
     * On click move to next attachment.
     *
     * @private
     * @param {MouseEvent} ev
     */
    _onClickNext: function (ev) {
        ev.preventDefault();
        var index = _.findIndex(this.thread.attachmentsInWebClientView, this.thread.mainAttachment);
        index = index === this.thread.attachmentsInWebClientView.length - 1 ? 0 : index + 1;
        this._switch_main_attachment(index);
    },
    /**
     * On click move to previous attachment.
     *
     * @private
     * @param {MouseEvent} ev
     */
    _onClickPrevious: function (ev) {
        ev.preventDefault();
        var index = _.findIndex(this.thread.attachmentsInWebClientView, this.thread.mainAttachment);
        index = index === 0 ? this.thread.attachmentsInWebClientView.length - 1 : index - 1;
        this._switch_main_attachment(index);
    },
});

export default AttachmentViewer;
