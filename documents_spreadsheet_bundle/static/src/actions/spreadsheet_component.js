/** @odoo-module alias=documents_spreadsheet.SpreadsheetComponent */

import { _t } from "web.core";
import Dialog from "web.OwlDialog";
import { useSetupAction } from "@web/webclient/actions/action_hook";
import { useService } from "@web/core/utils/hooks";

import { DEFAULT_LINES_NUMBER } from "../o_spreadsheet/constants";

import spreadsheet from "../o_spreadsheet/o_spreadsheet_extended";
import CachedRPC from "../o_spreadsheet/cached_rpc";
import { legacyRPC, jsonToBase64 } from "../o_spreadsheet/helpers";

const { Component, useExternalListener, useRef, useState, useSubEnv } = owl;
const uuidGenerator = new spreadsheet.helpers.UuidGenerator();

const { Spreadsheet, Model } = spreadsheet;

export default class SpreadsheetComponent extends Component {
  setup() {
    this.orm = useService("orm");
    const rpc = legacyRPC(this.orm);
    this.cacheRPC = new CachedRPC(rpc);
    const user = useService("user");
    this.ui = useService("ui");
    useSubEnv({
      newSpreadsheet: this.newSpreadsheet.bind(this),
      saveAsTemplate: this._saveAsTemplate.bind(this),
      makeCopy: this.makeCopy.bind(this),
      download: this._download.bind(this),
      delayedRPC: this.cacheRPC.delayedRPC.bind(this.cacheRPC),
      getLinesNumber: this._getLinesNumber.bind(this),
      notifyUser: this.notifyUser.bind(this),
      editText: this.editText.bind(this),
      askConfirmation: this.askConfirmation.bind(this),
    });
    useSetupAction({
      beforeLeave: this._onLeave.bind(this),
    });
    this.state = useState({
      dialog: {
        isDisplayed: false,
        title: undefined,
        isEditText: false,
        inputContent: undefined,
        isEditInteger: false,
        inputIntegerContent: undefined,
      },
    });
    this.spreadsheet = useRef("spreadsheet");
    this.dialogContent = undefined;
    this.pivot = undefined;
    this.confirmDialog = () => true;
    this.data = this.props.data;
    this.stateUpdateMessages = this.props.stateUpdateMessages;
    this.res_id = this.props.res_id;
    this.client = {
      id: uuidGenerator.uuidv4(),
      name: user.name,
      userId: user.uid,
    };
    this.isReadonly = this.props.isReadonly;
    useExternalListener(window, "beforeunload", this._onLeave.bind(this));
  }

  get model() {
    return this.spreadsheet.comp.model;
  }

  mounted() {
    this.model.on("update", this, () =>
      this.trigger("spreadsheet-sync-status", {
        synced: this.model.getters.isFullySynchronized(),
        numberOfConnectedUsers: this.getConnectedUsers(),
      })
    );
    if (this.props.showFormulas) {
      this.model.dispatch("SET_FORMULA_VISIBILITY", { show: true });
    }
    if (this.props.initCallback) {
      this.props.initCallback(this.model);
    }
    if (this.props.download) {
      this._download();
    }
  }
  /**
   * Return the number of connected users. If one user has more than
   * one open tab, it's only counted once.
   * @return {number}
   */
  getConnectedUsers() {
    return new Set(
      [...this.model.getters.getConnectedClients().values()].map(
        (client) => client.userId
      )
    ).size;
  }

  willUnmount() {
    this._onLeave();
  }
  /**
   * Open a dialog to ask a confirmation to the user.
   *
   * @param {string} content Content to display
   * @param {Function} confirm Callback if the user press 'Confirm'
   */
  askConfirmation(content, confirm) {
    this.dialogContent = content;
    this.confirmDialog = () => {
      confirm();
      this.closeDialog();
    };
    this.state.dialog.isDisplayed = true;
  }

  /**
   * Ask the user to edit a text
   *
   * @param {string} title Title of the popup
   * @param {string} placeholder Placeholder of the text input
   * @param {Function} callback Callback to call with the entered text
   */
  editText(title, placeholder, callback) {
    this.dialogContent = undefined;
    this.state.dialog.title = title && title.toString();
    this.state.dialog.isEditText = true;
    this.state.inputContent = placeholder;
    this.confirmDialog = () => {
      this.closeDialog();
      callback(this.state.inputContent);
    };
    this.state.dialog.isDisplayed = true;
  }
  _getLinesNumber(callback) {
    this.dialogContent = _t("Select the number of records to insert");
    this.state.dialog.title = _t("Re-insert list");
    this.state.dialog.isEditInteger = true;
    this.state.dialog.inputIntegerContent = DEFAULT_LINES_NUMBER;
    this.confirmDialog = () => {
      this.closeDialog();
      callback(this.state.dialog.inputIntegerContent);
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
    this.state.dialog.isEditText = false;
    this.state.dialog.isEditInteger = false;
    this.spreadsheet.comp.focusGrid();
  }
  /**
   * Retrieve the spreadsheet_data and the thumbnail associated to the
   * current spreadsheet
   */
  getSaveData() {
    const data = this.spreadsheet.comp.model.exportData();
    return {
      data,
      revisionId: data.revisionId,
      thumbnail: this.getThumbnail(),
    };
  }

  getThumbnail() {
    const dimensions = spreadsheet.SPREADSHEET_DIMENSIONS;
    const canvas = this.spreadsheet.comp.grid.comp.canvas.el;
    const canvasResizer = document.createElement("canvas");
    const size = this.props.thumbnailSize;
    canvasResizer.width = size;
    canvasResizer.height = size;
    const canvasCtx = canvasResizer.getContext("2d");
    // use only 25 first rows in thumbnail
    const sourceSize = Math.min(
      25 * dimensions.DEFAULT_CELL_HEIGHT,
      canvas.width,
      canvas.height
    );
    canvasCtx.drawImage(
      canvas,
      dimensions.HEADER_WIDTH - 1,
      dimensions.HEADER_HEIGHT - 1,
      sourceSize,
      sourceSize,
      0,
      0,
      size,
      size
    );
    return canvasResizer.toDataURL().replace("data:image/png;base64,", "");
  }
  /**
   * Make a copy of the current document
   */
  makeCopy() {
    const { data, thumbnail } = this.getSaveData();
    this.trigger("make-copy", {
      data,
      thumbnail,
    });
  }
  /**
   * Create a new spreadsheet
   */
  newSpreadsheet() {
    this.trigger("new-spreadsheet");
  }

  /**
   * Downloads the spreadsheet in xlsx format
   */
  async _download() {
    this.ui.block();
    try {
      const { files } = await this.spreadsheet.comp.env.exportXLSX();
      this.trigger("download", {
        name: this.props.name,
        files,
      });
    } finally {
      this.ui.unblock();
    }
  }

  /**
   * @private
   * @returns {Promise}
   */
  async _saveAsTemplate() {
    const model = new Model(this.spreadsheet.comp.model.exportData(), {
      mode: "headless",
      evalContext: { env: this.env },
    });
    await model.waitForIdle();
    model.dispatch("CONVERT_PIVOT_TO_TEMPLATE");
    const data = model.exportData();
    const name = this.props.name;
    this.trigger("do-action", {
      action: "documents_spreadsheet.save_spreadsheet_template_action",
      options: {
        additional_context: {
          default_template_name: `${name} - Template`,
          default_data: jsonToBase64(data),
          default_thumbnail: this.getThumbnail(),
        },
      },
    });
  }
  /**
   * Open a dialog to display a message to the user.
   *
   * @param {string} content Content to display
   */
  notifyUser(content) {
    this.dialogContent = content;
    this.confirmDialog = this.closeDialog;
    this.state.dialog.isDisplayed = true;
  }

  _onLeave() {
    if (this.alreadyLeft) {
      return;
    }
    this.alreadyLeft = true;
    this.spreadsheet.comp.model.off("update", this);
    if (!this.isReadonly) {
      this.trigger("spreadsheet-saved", this.getSaveData());
    }
  }
}

SpreadsheetComponent.template = "documents_spreadsheet.SpreadsheetComponent";
SpreadsheetComponent.components = { Spreadsheet, Dialog };
Spreadsheet._t = _t;
SpreadsheetComponent.props = {
    name: String,
    data: Object,
    thumbnailSize: Number,
    isReadonly: Boolean,
    snapshotRequested: Boolean,
    showFormulas: Boolean,
    download: Boolean,
    stateUpdateMessages: Array,
    initCallback: {
        optional: true,
        type: Function,
    },
    transportService: {
        optional: true,
        type: Object
    }
}
SpreadsheetComponent.defaultProps = {
    isReadonly: false,
    download: false,
    snapshotRequested: false,
    showFormulas: false,
    stateUpdateMessages: [],
}
