/** @odoo-module alias=documents_spreadsheet.TestUtils default=0 */
import spreadsheet from "documents_spreadsheet.spreadsheet";
import pivotUtils from "documents_spreadsheet.pivot_utils";
import { createView } from "web.test_utils";
import PivotView from "web.PivotView";
import ListView from "web.ListView";
import MockServer from "web.MockServer";
import makeTestEnvironment from "web.test_env";
import LegacyRegistry from "web.Registry";
import MockSpreadsheetCollaborativeChannel from "./mock_spreadsheet_collaborative_channel";
import { getBasicPivotArch, getBasicData, getBasicListArch } from "./spreadsheet_test_data";
import { createWebClient, doAction } from "@web/../tests/webclient/helpers";
import { patchWithCleanup } from "@web/../tests/helpers/utils";
import { SpreadsheetAction } from "../src/actions/spreadsheet/spreadsheet_action";
import { SpreadsheetTemplateAction } from "../src/actions/spreadsheet_template/spreadsheet_template_action";
import { UNTITLED_SPREADSHEET_NAME } from "../src/constants";

const { Model } = spreadsheet;
const { toCartesian, toZone, isFormula } = spreadsheet.helpers;
const { jsonToBase64 } = pivotUtils;

/**
 * Get the value of the given cell
 */
export function getCellValue(model, xc, sheetId = model.getters.getActiveSheetId()) {
    const cell = model.getters.getCell(sheetId, ...toCartesian(xc));
    if (!cell) {
        return undefined;
    }
    return cell.evaluated.value;
}

/**
 * Get the computed value that would be autofilled starting from the given xc
 */
export function getAutofillValue(model, xc, { direction, steps }) {
    const content = getCellFormula(model, xc);
    const column = ["left", "right"].includes(direction);
    const increment = ["left", "top"].includes(direction) ? -steps : steps;
    return model.getters.getPivotNextAutofillValue(content, column, increment);
}

/**
 * Get the computed value that would be autofilled starting from the given xc
 */
export function getListAutofillValue(model, xc, { direction, steps }) {
    const content = getCellFormula(model, xc);
    const column = ["left", "right"].includes(direction);
    const increment = ["left", "top"].includes(direction) ? -steps : steps;
    return model.getters.getNextListValue(content, column, increment);
}

/**
 * Autofill from a zone to a cell
 */
export function autofill(model, from, to) {
    setSelection(model, from);
    const [col, row] = toCartesian(to);
    model.dispatch("AUTOFILL_SELECT", { col, row });
    model.dispatch("AUTOFILL");
}

/**
 * Set the selection
 */
export function setSelection(model, xc) {
    const zone = toZone(xc);
    const anchor = [zone.left, zone.top];
    model.dispatch("SET_SELECTION", {
        anchorZone: zone,
        anchor,
        zones: [zone],
    });
}

/**
 * Get the cell of the given xc
 */
export function getCell(model, xc, sheetId = model.getters.getActiveSheetId()) {
    return model.getters.getCell(sheetId, ...toCartesian(xc));
}

/**
 * Get the cells of the given sheet (or active sheet if not provided)
 */
export function getCells(model, sheetId = model.getters.getActiveSheetId()) {
    return model.getters.getCells(sheetId);
}

/**
 * Get the formula of the given xc
 */
export function getCellFormula(model, xc, sheetId = model.getters.getActiveSheetId()) {
    const cell = getCell(model, xc, sheetId);
    return cell && isFormula(cell) ? model.getters.getFormulaCellContent(sheetId, cell) : "";
}

/**
 * Get the content of the given xc
 */
export function getCellContent(model, xc, sheetId = undefined) {
    if (sheetId === undefined) {
        sheetId =
            model.config.mode === "headless"
                ? model.getters.getVisibleSheets()[0]
                : model.getters.getActiveSheetId();
    }
    const cell = getCell(model, xc, sheetId);
    return cell ? model.getters.getCellText(cell, sheetId, true) : "";
}

/**
 * Get the list of the merges (["A1:A2"]) of the sheet
 */
export function getMerges(model, sheetId = model.getters.getActiveSheetId()) {
    return model.exportData().sheets.find((sheet) => sheet.id === sheetId).merges;
}

/**
 * Set the content of a cell
 */
export function setCellContent(model, xc, content, sheetId = undefined) {
    if (sheetId === undefined) {
        sheetId =
            model.config.mode === "headless"
                ? model.getters.getVisibleSheets()[0]
                : model.getters.getActiveSheetId();
    }
    const [col, row] = toCartesian(xc);
    model.dispatch("UPDATE_CELL", { col, row, sheetId, content });
}

/**
 * Return the odoo spreadsheet component
 * @param {*} actionManager
 * @returns {Component}
 */
function getSpreadsheetComponent(actionManager) {
    return actionManager.spreadsheetRef.comp;
}

/**
 * Return the o-spreadsheet component
 * @param {*} actionManager
 * @returns {Component}
 */
function getOSpreadsheetComponent(actionManager) {
    return getSpreadsheetComponent(actionManager).spreadsheet.comp;
}

/**
 * Return the o-spreadsheet Model
 */
function getSpreadsheetActionModel(actionManager) {
    return getOSpreadsheetComponent(actionManager).model;
}

function getSpreadsheetActionEnv(actionManager) {
    const model = getSpreadsheetActionModel(actionManager);
    const component = getSpreadsheetComponent(actionManager);
    const oComponent = getOSpreadsheetComponent(actionManager);
    return {
        ...component.env,
        getters: model.getters,
        dispatch: model.dispatch,
        services: model.config.evalContext.env.services,
        openSidePanel: oComponent.openSidePanel.bind(oComponent),
    };
}

export async function createSpreadsheetAction(actionTag, params = {}) {
    let { spreadsheetId, data, arch, mockRPC, legacyServicesRegistry, webClient } = params;
    let spreadsheetAction;
    const SpreadsheetActionComponent =
        actionTag === "action_open_spreadsheet" ? SpreadsheetAction : SpreadsheetTemplateAction;
    patchWithCleanup(SpreadsheetActionComponent.prototype, {
        setup() {
            this._super();
            spreadsheetAction = this;
        },
    });
    const serverData = { models: data, views: arch };
    if (!webClient) {
        webClient = await createWebClient({
            serverData,
            mockRPC,
            legacyParams: {
                withLegacyMockServer: true,
                serviceRegistry: legacyServicesRegistry,
            },
        });
    }

    const transportService = params.transportService || new MockSpreadsheetCollaborativeChannel();
    await doAction(webClient, {
        type: "ir.actions.client",
        tag: actionTag,
        params: {
            spreadsheet_id: spreadsheetId,
            transportService,
        },
    });
    return {
        webClient,
        model: getSpreadsheetActionModel(spreadsheetAction),
        env: getSpreadsheetActionEnv(spreadsheetAction),
    };
}

export async function createSpreadsheet(params = {}) {
    if (!params.spreadsheetId) {
        const documents = params.data["documents.document"].records;
        const spreadsheetId = Math.max(...documents.map((d) => d.id)) + 1;
        documents.push({
            id: spreadsheetId,
            name: UNTITLED_SPREADSHEET_NAME,
            raw: "{}",
        });
        params = { ...params, spreadsheetId };
    }
    return createSpreadsheetAction("action_open_spreadsheet", params);
}

export async function createSpreadsheetTemplate(params = {}) {
    if (!params.spreadsheetId) {
        const templates = params.data["spreadsheet.template"].records;
        const spreadsheetId = Math.max(...templates.map((d) => d.id)) + 1;
        templates.push({
            id: spreadsheetId,
            name: "test template",
            data: jsonToBase64({}),
        });
        params = { ...params, spreadsheetId };
    }
    return createSpreadsheetAction("action_open_template", params);
}

/**
 * Create a spreadsheet model from a List controller
 */
export async function createSpreadsheetFromList(params = {}) {
    let { actions, listView, webClient, linesNumber } = params;
    if (linesNumber === undefined) {
        linesNumber = 10;
    }
    if (!listView) {
        listView = {};
    }
    let spreadsheetAction = {};
    patchWithCleanup(SpreadsheetAction.prototype, {
        mounted() {
            this._super();
            spreadsheetAction = this;
        },
    });
    listView = {
        arch: getBasicListArch(),
        data: getBasicData(),
        model: listView.model || "partner",
        ...listView,
    };
    const { data } = listView;
    const controller = await createView({
        View: ListView,
        ...listView,
    });
    const documents = data["documents.document"].records;
    const id = Math.max(...documents.map((d) => d.id)) + 1;
    documents.push({
        id,
        name: "pivot spreadsheet",
        raw: "{}",
    });
    if (listView.services) {
        const serviceRegistry = new LegacyRegistry();
        for (const sname in listView.services) {
            serviceRegistry.add(sname, listView.services[sname]);
        }
    }

    if (!webClient) {
        const serverData = { models: data, views: listView.archs };
        webClient = await createWebClient({
            serverData,
            legacyParams: { withLegacyMockServer: true },
            mockRPC: listView.mockRPC,
        });
    }
    if (actions) {
        await actions(controller);
    }
    const transportService = new MockSpreadsheetCollaborativeChannel();

    const list = controller._getListForSpreadsheet();
    const initCallback = controller._getCallbackListInsertion(list, linesNumber, true);
    await doAction(webClient, {
        type: "ir.actions.client",
        tag: "action_open_spreadsheet",
        params: {
            spreadsheet_id: id,
            transportService,
            initCallback,
        },
    });
    const spreadSheetComponent = spreadsheetAction.spreadsheetRef.comp;
    const oSpreadsheetComponent = spreadSheetComponent.spreadsheet.comp;
    const model = oSpreadsheetComponent.model;
    const env = Object.assign(spreadSheetComponent.env, {
        getters: model.getters,
        dispatch: model.dispatch,
        services: model.config.evalContext.env.services,
        openSidePanel: oSpreadsheetComponent.openSidePanel.bind(oSpreadsheetComponent),
    });
    return {
        webClient,
        env,
        model,
        transportService,
        get spreadsheetAction() {
            return spreadsheetAction;
        },
    };
}

/**
 * Create a spreadsheet model from a Pivot controller
 * @param {*} params
 * the pivot data
 */
export async function createSpreadsheetFromPivot(params = {}) {
    let { actions, pivotView, webClient } = params;
    if (!pivotView) {
        pivotView = {};
    }
    let spreadsheetAction = {};
    patchWithCleanup(SpreadsheetAction.prototype, {
        setup() {
            this._super();
            spreadsheetAction = this;
        },
    });
    pivotView = {
        arch: getBasicPivotArch(),
        data: getBasicData(),
        model: pivotView.model || "partner",
        ...pivotView,
    };
    const { data } = pivotView;
    const controller = await createView({
        View: PivotView,
        ...pivotView,
    });
    const documents = data["documents.document"].records;
    const id = Math.max(...documents.map((d) => d.id)) + 1;
    documents.push({
        id,
        name: "pivot spreadsheet",
        raw: "{}",
    });
    if (pivotView.services) {
        const serviceRegistry = new LegacyRegistry();
        for (const sname in pivotView.services) {
            serviceRegistry.add(sname, pivotView.services[sname]);
        }
    }

    if (!webClient) {
        const serverData = { models: data, views: pivotView.archs };
        webClient = await createWebClient({
            serverData,
            legacyParams: { withLegacyMockServer: true },
            mockRPC: pivotView.mockRPC,
        });
    }
    if (actions) {
        await actions(controller);
    }
    const transportService = new MockSpreadsheetCollaborativeChannel();

    const pivot = controller._getPivotForSpreadsheet();
    const initCallback = await controller._getCallbackBuildPivot(pivot, true);
    await doAction(webClient, {
        type: "ir.actions.client",
        tag: "action_open_spreadsheet",
        params: {
            spreadsheet_id: id,
            transportService,
            initCallback,
        },
    });
    const spreadSheetComponent = spreadsheetAction.spreadsheetRef.comp;
    const oSpreadsheetComponent = spreadSheetComponent.spreadsheet.comp;
    const model = oSpreadsheetComponent.model;
    const env = Object.assign(spreadSheetComponent.env, {
        getters: model.getters,
        dispatch: model.dispatch,
        services: model.config.evalContext.env.services,
        openSidePanel: oSpreadsheetComponent.openSidePanel.bind(oSpreadsheetComponent),
    });
    return {
        webClient,
        env,
        model,
        transportService,
        get spreadsheetAction() {
            return spreadsheetAction;
        },
    };
}

/**
 * Setup a realtime collaborative test environment, with the given data
 */
export function setupCollaborativeEnv(data) {
    const mockServer = new MockServer(data, {});
    const env = makeTestEnvironment({}, mockServer.performRpc.bind(mockServer));
    env.delayedRPC = env.services.rpc;
    const network = new MockSpreadsheetCollaborativeChannel();
    const model = new Model();
    const alice = new Model(model.exportData(), {
        evalContext: { env },
        transportService: network,
        client: { id: "alice", name: "Alice" },
    });
    const bob = new Model(model.exportData(), {
        evalContext: { env },
        transportService: network,
        client: { id: "bob", name: "Bob" },
    });
    const charlie = new Model(model.exportData(), {
        evalContext: { env },
        transportService: network,
        client: { id: "charlie", name: "Charlie" },
    });
    return { network, alice, bob, charlie, rpc: env.services.rpc };
}

export function joinSession(spreadsheetChannel, client) {
    spreadsheetChannel.broadcast({
        type: "CLIENT_JOINED",
        client: {
            position: {
                sheetId: "1",
                col: 1,
                row: 1,
            },
            name: "Raoul Grosbedon",
            ...client,
        },
    });
}

export function leaveSession(spreadsheetChannel, clientId) {
    spreadsheetChannel.broadcast({
        type: "CLIENT_LEFT",
        clientId,
    });
}

QUnit.assert.spreadsheetIsSynchronized = function (users, callback, expected) {
    for (const user of users) {
        const actual = callback(user);
        if (!QUnit.equiv(actual, expected)) {
            const userName = user.getters.getClient().name;
            return this.pushResult({
                result: false,
                actual,
                expected,
                message: `${userName} does not have the expected value`,
            });
        }
    }
    this.pushResult({ result: true });
};
