odoo.define('account_accountant.MoveLineListView', function (require) {
"use strict";

    var AttachmentViewer = require('mail_enterprise.AttachmentViewer');
    var config = require('web.config');
    var core = require('web.core');
    var ListController = require('web.ListController');
    var ListModel = require('web.ListModel');
    var ListRenderer = require('web.ListRenderer');
    var ListView = require('web.ListView');
    var viewRegistry = require('web.view_registry');

    var _t = core._t;

    var AccountMoveListModel = ListModel.extend({
        /**
         * Overridden to fetch extra fields even if `move_attachment_ids` is
         * invisible in the view.
         *
         * @override
         * @private
         */
        _fetchRelatedData: function (list, toFetch, fieldName) {
            if (fieldName === 'move_attachment_ids' && config.device.size_class >= config.device.SIZES.XXL) {
                var fieldsInfo = list.fieldsInfo[list.viewType][fieldName];
                // force to fetch extra fields
                fieldsInfo.__no_fetch = false;
                fieldsInfo.relatedFields = {
                    mimetype: {type: 'char'},
                };
            }
            return this._super.apply(this, arguments);
        },
    });

    var AccountMoveListController = ListController.extend({
        custom_events: _.extend({}, ListController.prototype.custom_events, {
            row_selected: '_onRowSelected',
        }),

        /**
         * @override
         */
        init: function () {
            this._super.apply(this, arguments);

            this.currentAttachments = [];

        },

        //--------------------------------------------------------------------------
        // Private
        //--------------------------------------------------------------------------

        /**
         * Overridden to add an attachment preview container.
         *
         * @override
         * @private
         */
        _update: function () {
            var self = this;
            return this._super.apply(this, arguments).then(function () {
                self.$('.o_content').addClass('o_move_line_list_view');
                self.currentAttachments = [];
                if (self.$attachmentPreview) {
                    self.$attachmentPreview.remove();
                }
                if (config.device.size_class >= config.device.SIZES.XXL) {
                    self.$attachmentPreview = $('<div>', {
                        class: 'o_attachment_preview',
                    }).append($('<p>', {
                        class: 'o_move_line_empty',
                        text: _t("Edit a line to preview its attachments."),
                    }));
                    self.$attachmentPreview.appendTo(self.$('.o_content'));
                }
            });
        },
        /**
         * Renders a preview of a record attachments.
         *
         * @param {string} recordId
         * @private
         */
        _renderAttachmentPreview: function (recordId) {
            var self = this;
            var record = this.model.get(recordId);
            var types = ['pdf', 'image'];
            var attachments = record.data.move_attachment_ids.data.map(function (attachment) {
                return {
                    id: attachment.res_id,
                    filename: attachment.data.filename,
                    mimetype: attachment.data.mimetype,
                    url: '/web/content/' + attachment.res_id + '?download=true',
                };
            });
            attachments = _.filter(attachments, function (attachment) {
                var match = attachment.mimetype.match(types.join('|'));
                attachment.type = match ? match[0] : false;
                return match;
            });
            var prom;
            if (!_.isEqual(_.pluck(this.currentAttachments, 'id'), _.pluck(attachments, 'id'))) {
                if (this.attachmentViewer) {
                    this.attachmentViewer.updateContents(attachments);
                } else {
                    this.attachmentViewer = new AttachmentViewer(this, attachments);
                }
                prom = this.attachmentViewer.appendTo(this.$attachmentPreview.empty()).then(function () {
                    self.$attachmentPreview.resizable({
                        handles: 'w',
                        minWidth: 400,
                        maxWidth: 900,
                    });
                });
            }
            return Promise.resolve(prom).then(function () {
                self.currentAttachments = attachments;
                if (!attachments.length) {
                    var $empty = $('<p>', {
                        class: 'o_move_line_without_attachment',
                        text: _t("There is no attachment linked to this move."),
                    });
                    self.$attachmentPreview.empty().append($empty);
                }
            });
        },

        //--------------------------------------------------------------------------
        // Handlers
        //--------------------------------------------------------------------------

        /**
         * @private
         * @param {OdooEvent} ev
         * @param {string} ev.data.recordId
         */
        _onRowSelected: function (ev) {
            if (config.device.size_class >= config.device.SIZES.XXL) {
                this._renderAttachmentPreview(ev.data.recordId);
            }
        },
    });
    var AccountMoveListRenderer = ListRenderer.extend({

        //--------------------------------------------------------------------------
        // Private
        //--------------------------------------------------------------------------

        /**
         *
         * @param {integer} rowIndex
         * @private
         * @override
         */
        _selectRow: function (rowIndex) {
            var self = this;
            var recordId = this._getRecordID(rowIndex);
            var currentRow = this.currentRow; // currentRow is updated in _super
            return this._super.apply(this, arguments).then(function () {
                if (rowIndex !== currentRow) {
                    self.trigger_up('row_selected', {
                        recordId: recordId,
                    });
                }
            });
        },
    });

    var AccountMoveListView = ListView.extend({
        config: _.extend({}, ListView.prototype.config, {
            Controller: AccountMoveListController,
            Model: AccountMoveListModel,
            Renderer: AccountMoveListRenderer,
        }),
    });

    viewRegistry.add('account_move_line_list', AccountMoveListView);

    return AccountMoveListView;
});

