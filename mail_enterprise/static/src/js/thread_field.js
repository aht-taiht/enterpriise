odoo.define('mail_enterprise.ThreadField', function (require) {
"use strict";

var ThreadField = require('mail.ThreadField');

ThreadField.include({

    //--------------------------------------------------------------------------
    // Private
    //--------------------------------------------------------------------------

    /**
    * Override the thread rendering to warn the FormRenderer about attachments.
    * This is used by the FormRenderer to display an attachment preview.
    *
    * @override
    * @private
    */
    _fetchAndRenderThread: function () {
        var self = this;
        return this._super.apply(this, arguments).then(function () {
            if (self._threadWidget.attachments.length) {
                self.trigger_up('preview_attachment');
            }
        });
    },
});

var Chatter = require('mail.Chatter');

Chatter.include({
    custom_events: _.extend({}, Chatter.prototype.custom_events, {
        preview_attachment: '_onAttachmentPreview',
    }),

    /**
     * @private
     * @param {OdooEvent} ev
     */
    _onAttachmentPreview: function (ev) {
        if (this._areAttachmentsLoaded){
            ev.data.attachments = this.attachments;
        } else {
            ev.stopPropagation();
            return this._fetchAttachments().then(this.trigger_up.bind(this, 'preview_attachment'));
        }
    },
});
});
