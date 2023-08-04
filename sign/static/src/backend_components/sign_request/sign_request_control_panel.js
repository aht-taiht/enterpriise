/** @odoo-module **/

import { Component, useEffect, useComponent, markup } from "@odoo/owl";
import { useService } from "@web/core/utils/hooks";
import { ControlPanel } from "@web/search/control_panel/control_panel";
import multiFileUpload from "@sign/backend_components/multi_file_upload";

function useResendButtons() {
    const component = useComponent();
    const onClickResend = async (e) => {
        const parent = e.currentTarget.parentNode;
        const signRequestItemId = parseInt(parent.dataset.id);
        await component.orm.call(
            "sign.request.item",
            "send_signature_accesses",
            [signRequestItemId],
            { context: component.user.context }
        );
        e.target.innerText = component.env._t("Resent!");
    };
    return useEffect(
        () => {
            const status = document.querySelector("div.signer-status");
            const signerNames = status.querySelectorAll(
                ".o_sign_signer_status.o_sign_signer_waiting"
            );
            Array.from(signerNames).forEach((signerNameEl) => {
                const stateSet =
                    component.signInfo.get("requestItemStates")[signerNameEl.dataset.id];
                const title = stateSet
                    ? component.env._t("Resend the invitation")
                    : component.env._t("Send the invitation");
                const text = stateSet ? component.env._t("Resend") : component.env._t("Send");
                const button = document.createElement("button");
                button.title = title;
                button.innerText = text;
                button.className = "o_sign_resend_access_button btn btn-link ms-2 me-2";
                button.style = "vertical-align: baseline;";
                signerNameEl.insertBefore(button, signerNameEl.firstChild);
                button.addEventListener("click", onClickResend);
            });
        },
        () => []
    );
}

export class SignRequestControlPanel extends Component {
    setup() {
        this.controlPanelDisplay = {};
        this.action = useService("action");
        this.orm = useService("orm");
        this.user = useService("user");
        this.signInfo = useService("signInfo");
        this.nextTemplate = multiFileUpload.getNext();
        useResendButtons();
    }

    get markupSignerStatus() {
        return markup(this.props.signerStatus.innerHTML);
    }

    async signDocument() {
        const action = await this.orm.call("sign.request", "go_to_signable_document", [
            [this.signInfo.get("documentId")],
        ]);
        action.name = this.env._t("Sign");
        this.action.doAction(action);
    }

    async goToNextDocument() {
        multiFileUpload.removeFile(this.nextTemplate.template);
        await this.action.doAction(
            "sign.Template",
            {
                name: this.env._t('Template "%s"', this.nextTemplate.name),
                context: {
                    sign_edit_call: "sign_send_request",
                    id: this.nextTemplate.template,
                    sign_directly_without_mail: false,
                },
            },
            { clear_breadcrumbs: true }
        );
    }
}

SignRequestControlPanel.template = "sign.SignRequestControlPanel";
SignRequestControlPanel.components = {
    ControlPanel,
};
SignRequestControlPanel.props = {
    signerStatus: {
        type: Object,
        optional: true,
    },
};
