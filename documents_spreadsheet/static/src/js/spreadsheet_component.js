odoo.define("documents_spreadsheet.SpreadsheetComponent", function (require) {
    "use strict";

    const Dialog = require("web.OwlDialog");
    const spreadsheet = require("documents_spreadsheet.spreadsheet_extended");

    const Spreadsheet = spreadsheet.Spreadsheet;
    const { useState, useRef, useSubEnv } = owl.hooks;

    class SpreadsheetComponent extends owl.Component {
        constructor(parent, props) {
            super(...arguments);
            useSubEnv({
                newSpreadsheet: this.newSpreadsheet.bind(this),
                makeCopy: this.makeCopy.bind(this),
                saveData: this.saveData.bind(this),

            });
            this.state = useState({
                dialog: {
                    isDisplayed: false,
                    title: undefined,
                },
            });
            this.spreadsheet = useRef("spreadsheet");
            this.dialogContent = undefined;
            this.confirmDialog = () => true;
            this.data = props.data;
            this.res_id = props.res_id;
        }
        mounted() {
            window.onbeforeunload = () => {
                this.saveData();
            };
        }
        willUnmount() {
            window.onbeforeunload = null;
        }
        /**
         * Open a dialog to ask a confirmation to the user.
         *
         * @param {CustomEvent} ev
         * @param {string} ev.detail.content Content to display
         * @param {Function} ev.detail.confirm Callback if the user press 'Confirm'
         */
        askConfirmation(ev) {
            this.dialogContent = ev.detail.content;
            this.confirmDialog = () => {
                ev.detail.confirm();
                this.closeDialog();
            };
            this.state.dialog.isDisplayed = true;
        }
        /**
         * Close the dialog.
         */
        closeDialog() {
            this.dialogContent = undefined;
            this.confirmDialog = () => true;
            this.state.dialog.title = undefined;
            this.state.dialog.isDisplayed = false;
        }
        /**
         * Retrieve the spreadsheet_data and the thumbnail associated to the
         * current spreadsheet
         */
        getSaveData() {
            const spreadsheet_data = JSON.stringify(this.spreadsheet.comp.model.exportData());
            const canvas = this.spreadsheet.comp.grid.comp.canvas.el;
            const canvasResizer = document.createElement("canvas");
            canvasResizer.width = 100;
            canvasResizer.height = 100;
            const canvasCtx = canvasResizer.getContext("2d");
            canvasCtx.drawImage(canvas, 0, 0, 100, 100);
            const thumbnail = canvasResizer.toDataURL().replace("data:image/png;base64,", "");
            return { spreadsheet_data, thumbnail };
        }
        /**
         * Make a copy of the current document
         */
        makeCopy() {
            const { spreadsheet_data, thumbnail } = this.getSaveData();
            this.saveData();
            this.trigger("make_copy", { spreadsheet_data, thumbnail });
        }
        /**
         * Create a new spreadsheet
         */
        newSpreadsheet() {
            this.saveData();
            this.trigger("new_spreasheet");
        }
        /**
         * Open a dialog to display a message to the user.
         *
         * @param {CustomEvent} ev
         * @param {string} ev.detail.content Content to display
         */
        notifyUser(ev) {
            this.dialogContent = ev.detail.content;
            this.confirmDialog = this.closeDialog;
            this.state.dialog.isDisplayed = true;
        }
        /**
         * Saves the spreadsheet data in the database
         *
         */
        saveData() {
            const { spreadsheet_data, thumbnail } = this.getSaveData();
            return this.rpc({
                model: "documents.document",
                method: "write",
                args: [[this.res_id], { raw: spreadsheet_data, thumbnail }],
            });
        }
    }

    SpreadsheetComponent.template = "documents_spreadsheet.SpreadsheetComponent";
    SpreadsheetComponent.components = { Spreadsheet, Dialog };

    return SpreadsheetComponent;
});
