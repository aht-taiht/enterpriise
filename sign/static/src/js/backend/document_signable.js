/** @odoo-module **/

"use strict";

import core from "web.core";
import config from "web.config";
import { sprintf } from "@web/core/utils/strings";
import { DocumentAction } from "@sign/js/backend/document";
import { SignableDocument, ThankYouDialog } from "@sign/js/common/document_signable";
import { multiFileUpload } from "@sign/js/backend/multi_file_upload";

const { _t } = core;

ThankYouDialog.include({
  init: function (parent, options) {
    this._super.apply(this, arguments);
    const nextTemplate = multiFileUpload.getNext();
    if (nextTemplate && nextTemplate.template) {
      this.options.buttons.push({
        text: _t("Next Template"),
        classes: "btn-primary",
        click: (e) => {
          multiFileUpload.removeFile(nextTemplate.template);
          this.do_action(
            {
              type: "ir.actions.client",
              tag: "sign.Template",
              name: sprintf(_t(`Template "%s"`), nextTemplate.name),
              context: {
                sign_edit_call: "sign_send_request",
                id: nextTemplate.template,
                sign_directly_without_mail: false,
              },
            },
            { clear_breadcrumbs: true }
          );
        },
      });
    }
  },

  goToNext: async function (id, token) {
    const action = await this._rpc({
      model: "sign.request",
      method: "go_to_signable_document",
      args: [parseInt(id)],
    })
    this.do_action(action, { clear_breadcrumbs: true });
  },

  downloadDocument: function () {
    this._rpc({
      model: "sign.request",
      method: "get_completed_document",
      args: [this.parent.requestID],
    }).then((action) => {
      this.do_action(action, { clear_breadcrumbs: true });
    });
  },
});

SignableDocument.include({
  init: function () {
    this._super.apply(this, arguments);
    this.events = Object.assign(this.events || {}, {
      "click .o_sign_edit_button": 'toggleToolBar',
    });
  },

  get_pdfiframe_class: function () {
    const PDFIframeWithToolbar = this._super.apply(this, arguments).extend({
      getToolbarTypesArray: function() {
        return Object.values(this.types).filter((v) => v["editWhileSigningAllowed"]);
      },

      postItemClone: function (signItems) {
        signItems.forEach(($signItem) => {
          this.postItemDrop($signItem);
        })
      },

      postItemDrop: function ($signItem) {
        this.registerCreatedSignItemEvents(
          $signItem,
          $signItem.data('typeData'),
          true
        );
        this.checkSignItemsCompletion();
      },

      _doPDFFullyLoaded: function () {
        this._super.apply(this, arguments);

        // add field type toolbar for edit mode while signing
        if (!this.readonlyFields &&
          this.templateEditable &&
          !config.device.isMobile
        ) {
          this.currentRole = this.role;
          this.parties = {};
          this.parties[this.role] = {'name': this.roleName};
          this.isSignItemEditable = true;

          this.$fieldTypeToolbar.toggleClass('d-flex d-none');
          this.$iframe.parents('.o_action').find('.o_sign_edit_button').toggleClass('d-none');
        }
      },

      enableCustom: function ($signatureItem) {
        // allow new added sign items to be deleted by the fa-times button
        const $configArea = $signatureItem.find(".o_sign_config_area");
        $configArea
          .find(".fa-times")
          .off("click").on("click", () => {
            delete this.signatureItems[$signatureItem.data("item-id")];
            this.deleteSignItem($signatureItem);
            this.checkSignItemsCompletion();
          });

        this._super.apply(this, arguments);
      },
    })
    return PDFIframeWithToolbar
  },

  toggleToolBar: function (e) {
    this.iframeWidget.$("#outerContainer").toggleClass("o_sign_field_type_toolbar_visible");
    this.iframeWidget.$fieldTypeToolbar.toggleClass('d-flex d-none');
    this.iframeWidget.signatureItemNav.$el.toggleClass("o_sign_field_type_toolbar_visible");
  },
});

const SignableDocumentAction = DocumentAction.extend({
  get_document_class: function () {
    return SignableDocument;
  },
});

core.action_registry.add("sign.SignableDocument", SignableDocumentAction);
