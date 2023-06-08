/** @odoo-module **/

import { templates } from "@web/core/assets";
import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";
import { FormViewDialog } from "@web/views/view_dialogs/form_view_dialog";

import { AccountMoveFormRenderer } from '@account/components/account_move_form/account_move_form';
import { BoxLayer } from '@account_invoice_extract/js/box_layer';

const { App, onWillUnmount, useExternalListener, useState } = owl;

/**
 * This is the renderer of the subview that adds OCR features on the attachment
 * preview. It displays boxes that have been generated by the OCR. The OCR
 * automatically selects a box, but the user can manually selects another box.
 */
export class InvoiceExtractFormRenderer extends AccountMoveFormRenderer {
    /**
     * @override
     */
    setup() {
        super.setup();

        /** @type {import("@mail/core/common/thread_service").ThreadService} */
        this.threadService = useService("mail.thread");
        this.dialog = useService("dialog");
        this.orm = useService("orm");

        this._fieldsMapping = {
            'partner_id': 'supplier',
            'ref': 'invoice_id',
            'invoice_date': 'date',
            'invoice_date_due': 'due_date',
            'currency_id': 'currency',
            'quick_edit_total_amount': 'total',
        };

        // This contain the account.move record id of the fetched data.
        // It needs to be tracked as, if another record is loaded, we should fetch the data of the new record.
        this.dataMoveId = -1;

        this.boxLayerApps = [];
        this.activeField = undefined;
        this.activeFieldEl = undefined;
        this.boxes = [];
        this.selectedBoxes = {};

        this.state = useState({
            visibleBoxes: {},
        });

        useExternalListener(window, "focusin", (event) => {
            const field_widget = event.target.closest(".o_field_widget");
            if (field_widget){
                this.onFocusFieldWidget(field_widget);
            }
        });

        useExternalListener(window, "focusout", (event) => {
            if (event.target.closest(".o_field_widget")){
                this.onBlurFieldWidget();
            }
        });

        onWillUnmount (() => {
            this.destroyBoxLayers();
        });
    }

    fetchBoxData() {
        this.dataMoveId = this.props.record.data.id;
        return this.orm.call('account.move', 'get_boxes', [this.props.record.data.id]);
    }

    /**
     * Launch an Owl App with the box layer as root component.
     */
    createBoxLayerApp(props) {
        props.onClickBoxCallback = this.onClickBox.bind(this);
        return new App(BoxLayer, {
            env: this.env,
            dev: this.env.debug,
            templates,
            props,
            translatableAttributes: ["data-tooltip"],
            translateFn: this.env._t,
        });
    }

    /**
     * Renders the box layers on @element.
     * If a box layer already exists, it is re-used.
     */
    renderBoxLayers(element) {
        const proms = [];
        // In case of img
        if (element.classList.contains('img-fluid')) {
            this.destroyBoxLayers();
            const boxLayerApp = this.createBoxLayerApp({
                boxes: this.state.visibleBoxes[0] || [],
                mode: 'img',
                pageLayer: element,
            });
            proms.push(boxLayerApp.mount(element.parentElement));
            this.boxLayerApps = [boxLayerApp];
        }
        // In case of pdf
        if (element.tagName === 'IFRAME') {
            // Dynamically add css on the pdf viewer
            const pdfDocument = element.contentDocument;
            if (!pdfDocument.querySelector('head link#box_layer')) {
                const boxLayerStylesheet = document.createElement('link');
                boxLayerStylesheet.setAttribute('id', 'box_layer');
                boxLayerStylesheet.setAttribute('rel', 'stylesheet');
                boxLayerStylesheet.setAttribute('type', 'text/css');
                boxLayerStylesheet.setAttribute('href', '/account_invoice_extract/static/src/css/box_layer.css');
                pdfDocument.querySelector('head').append(boxLayerStylesheet);
            }
            const pageLayers = pdfDocument.querySelectorAll('.page');
            for (const pageLayer of pageLayers) {
                const pageNum = pageLayer.dataset['pageNumber'] - 1;
                const boxLayerApp = this.createBoxLayerApp({
                    boxes: this.state.visibleBoxes[pageNum] || [],
                    mode: 'pdf',
                    pageLayer: pageLayer,
                });
                proms.push(boxLayerApp.mount(pageLayer));
                this.boxLayerApps.push(boxLayerApp);
            }
        }
        return Promise.all(proms);
    }

    /**
     * Renders the boxes on @attachment.
     * It also determines which boxes should be visible according to the current active field.
     */
    renderInvoiceExtract(attachment) {
        const thread = this.threadService.insert({
            id: this.props.record.resId,
            model: this.props.record.resModel,
        });
        const preview_attachment_id = thread.mainAttachment.id;
        if (
            ['in_invoice', 'in_refund', 'out_invoice', 'out_refund'].includes(this.props.record.data.move_type) &&
            this.props.record.data.state === 'draft' &&
            ['waiting_validation', 'validation_to_send'].includes(this.props.record.data.extract_state) &&
            this.props.record.data.extract_attachment_id &&
            preview_attachment_id === this.props.record.data.extract_attachment_id[0]
        ) {
            if (this.activeField !== undefined) {
                if (this.dataMoveId !== this.props.record.data.id) {
                    for (const boxesForPage of Object.values(this.boxes)) {
                        boxesForPage.length = 0;
                    }
                }
                const dataToFetch = this.boxes.length === 0 || (this.dataMoveId !== this.props.record.data.id);
                const prom = dataToFetch ? this.fetchBoxData() : new Promise(resolve => resolve([]));
                prom.then((boxes) => {
                    boxes.map(b => owl.reactive(b)).forEach((box) => {
                        if (box.page in this.boxes) {
                            this.boxes[box.page].push(box);
                        }
                        else {
                            this.boxes[box.page] = [box];
                        }
                        if (box.user_selected) {
                            this.selectedBoxes[box.feature] = box;
                        }
                    });
                    for (const [page, boxesForPage] of Object.entries(this.boxes)) {
                        if (page in this.state.visibleBoxes) {
                            this.state.visibleBoxes[page].length = 0;
                        }
                        else {
                            this.state.visibleBoxes[page] = [];
                        }

                        const visibleBoxesForPage = boxesForPage.filter((box) => {
                            return (
                                box.feature === this.activeField ||
                                (box.feature === "VAT_Number" && this.activeField === "supplier")
                            );
                        });
                        this.state.visibleBoxes[page].push(...visibleBoxesForPage);
                    }
                    this.renderBoxLayers(attachment)
                });
            }
        }
    }

    /**
     * Determines the DOM element on which the boxes must be rendered, then render them.
     */
    showBoxesForField(fieldName) {
        // Case pdf (iframe)
        const iframe = document.querySelector('.o_attachment_preview iframe');
        if (iframe) {
            const iframeDoc = iframe.contentDocument;
            if (iframeDoc) {
                this.renderInvoiceExtract(iframe);
                return;
            }
        }
        // Case img
        const attachment = document.getElementById('attachment_img');
        if (attachment && attachment.complete) {
            this.renderInvoiceExtract(attachment);
            return;
        }
    }

    resetActiveField() {
        Object.values(this.state.visibleBoxes).forEach(boxesForPage => {
            boxesForPage.length = 0;
        });
        this.activeField = undefined;
        this.activeFieldEl = undefined;
        this.destroyBoxLayers();
    }

    destroyBoxLayers() {
        for (const boxLayerApp of this.boxLayerApps) {
            boxLayerApp.destroy();
        }
        this.boxLayerApps = [];
    }

    openCreatePartnerDialog(context) {
        this.dialog.add(
            FormViewDialog,
            {
                resModel: 'res.partner',
                context: context,
                title: this.env._t("Create"),
                onRecordSaved: (record) => {
                    this.props.record.update({ partner_id: [record.data.id] });
                },
            }
        );
    }

    /**
     * Updates the field's value according to @newFieldValue.
     */
    handleFieldChanged(fieldName, newFieldValue, boxText) {
        let changes = {};
        switch (fieldName) {
            case 'date':
                changes = { invoice_date: registry.category("parsers").get("date")(newFieldValue.split(' ')[0]) };
                break;
            case 'supplier':
                if (Number.isFinite(newFieldValue) && newFieldValue !== 0) {
                    changes = { partner_id: [newFieldValue] };
                }
                else {
                    const context = {'default_name': boxText};
                    if (this.selectedBoxes['VAT_Number']) {
                        context['default_vat'] = this.selectedBoxes['VAT_Number'].text;
                    }
                    this.openCreatePartnerDialog(context);
                    return;
                }
                break;
            case 'VAT_Number':
                if (Number.isFinite(newFieldValue) && newFieldValue !== 0) {
                    changes = { partner_id: [newFieldValue] };
                }
                else {
                    const context = {'default_vat': boxText};
                    if (this.selectedBoxes['supplier']) {
                        context['default_name'] = this.selectedBoxes['supplier'].text;
                    }
                    this.openCreatePartnerDialog(context);
                    return;
                }
                break;
            case 'due_date':
                changes = { invoice_date_due: registry.category("parsers").get("date")(newFieldValue.split(' ')[0]) };
                break;
            case 'invoice_id':
                changes =  ['out_invoice', 'out_refund'].includes(this.props.record.context.default_move_type) ? { name: newFieldValue } : { ref: newFieldValue };
                break;
            case 'currency':
                changes = { currency_id: [newFieldValue] };
                break;
            case 'total':
                changes = { quick_edit_total_amount: Number(newFieldValue) };
                break;
        }
        this.props.record.update(changes)
    }

    //--------------------------------------------------------------------------
    // Handlers
    //--------------------------------------------------------------------------

    /**
     * Called when a field widget gains focus.
     * It serves as the entry point to render the boxes of the focused field.
     */
    onFocusFieldWidget(field_widget) {
        const fieldName = this._fieldsMapping[field_widget.getAttribute('name')];

        if (fieldName === undefined) {
            this.resetActiveField();
            return;
        }

        this.activeField = fieldName;
        this.activeFieldEl = field_widget;

        this.showBoxesForField(fieldName);
    }

    /**
     * Called when a field widget loses focus.
     * It hides all boxes.
     */
    onBlurFieldWidget() {
        this.resetActiveField();
    }

    async onClickBox(boxId, boxPage) {
        const box = this.boxes[boxPage].find(box => box.id === boxId);
        const fieldName = box.feature;

        // Unselect the previously selected box
        if (this.selectedBoxes[fieldName]) {
            this.selectedBoxes[fieldName].user_selected = false;
        }

        // Select the new box
        box.user_selected = true;
        this.selectedBoxes[fieldName] = box;

        // Update the selected box in database
        const newFieldValue = await this.orm.call(
            'account.move',
            'set_user_selected_box',
            [[this.dataMoveId], boxId],
        )

        // Update the field's value
        this.handleFieldChanged(fieldName, newFieldValue, box.text);

        if (['date', 'due_date'].includes(box.feature)) {
            // For the date fields, we want to hide the calendar tooltip
            // This is achieved by simulating an 'ESC' keypress
            this.activeFieldEl.querySelector('input').dispatchEvent(new KeyboardEvent('keydown', {
                key: 'Escape',
            }));
        }
    }
};
