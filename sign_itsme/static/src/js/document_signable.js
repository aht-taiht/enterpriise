/** @odoo-module **/

import ajax from "web.ajax";
import session from "web.session";
import config from "web.config";
import { _t, qweb } from "web.core";
import { SignableDocument, SignInfoDialog, ThankYouDialog } from '@sign/js/common/document_signable';

function deleteQueryParamFromURL(param) {
    let url = new URL(location.href);
    url.searchParams.delete(param);
    window.history.replaceState(null, '', url);
}

const ItsmeDialog = SignInfoDialog.extend({
    template: "sign_itsme.itsme_dialog",
    events: {
        "click .itsme_confirm": function() {
            this.onItsmeClick.bind(this.getParent())()
        },
        "click .itsme_cancel": function() {
            this.close();
        }
    },

    onItsmeClick: async function () {
        const route = "/sign/sign/" + this.requestID + "/" + this.accessToken;
        const params = {
            signature: this.signInfo.signatureValues
        };
        return session.rpc(route, params).then(({success, authorization_url, message}) => {
            if (success) {
                window.location.replace(authorization_url);
            } else {
                this.openErrorDialog (
                    message,
                    () => {
                        window.location.reload();
                    }
                );
            }
        });
    },

    renderElement: function () {
        this._super.apply(this, arguments);
        this.$modal.addClass("o_sign_thank_you_dialog");
        this.$modal.find("button.btn-close").addClass("invisible");
    },

    init: function (parent, requestID, requestToken, signature, newSignItems, options) {
        options = options || {};
        if (config.device.isMobile) {
            options.fullscreen = true;
        }
        options.title = _t("Confirm your identity");
        options.size = options.size || "medium";
        options.renderFooter = false;
        this._super(parent, options);
        this.requestID = requestID;
        this.requestToken = requestToken;
        this.signature = signature;
        this.newSignItems = newSignItems;
        this.buttons = [];
     }
});

SignableDocument.include({
    start: async function () {
        const res = this._super(this, arguments);
        // Check if it's possible to add my templates.xml file content inside the XML file that is loaded in sign module so we don't have to load 2 XML files
        await ajax.loadXML("/sign_itsme/static/src/xml/templates.xml", qweb);
        this.showThankYouDialog = this.$("#o_sign_show_thank_you_dialog").length > 0;
        this.errorMessage = this.$("#o_sign_show_error_message").val();
        if (this.errorMessage) {
            this.openErrorDialog(this.errorMessage, () => {
                deleteQueryParamFromURL('error_message');
            })
        }
        if (this.showThankYouDialog) {
            this.openThankYouDialog();
        }
        return res;
    },
    getAuthDialog: function () {
        if (this.authMethod === 'itsme') {
            return new ItsmeDialog (
                this,
                this.requestID,
                this.accessToken,
                this.signInfo.signatureValues,
                this.signInfo.newSignItems,
                {
                    nextSign: this.name_list.length
                }
            );
        }

        return this._super(this, arguments);
    }
});

ThankYouDialog.include({
    viewDocument: function() {
        if (this.getParent().showThankYouDialog) {
            deleteQueryParamFromURL('show_thank_you_dialog')
            return this.close();
        }
        return this._super(this, arguments);
    }
})
