/** @odoo-module alias=documents_spreadsheet.SpreadsheetTests */

import * as legacyRegistry from "web.Registry";
import * as BusService from "bus.BusService";
import * as RamStorage from "web.RamStorage";
import * as AbstractStorageService from "web.AbstractStorageService";
import PivotView from "web.PivotView";
import {
    fields,
    nextTick,
    dom,
    createView,
} from "web.test_utils";
import {
    createSpreadsheet,
    createSpreadsheetFromPivot,
    getCellFormula,
    getCellValue,
    joinSession,
    leaveSession,
    setCellContent,
} from "./spreadsheet_test_utils";
import MockSpreadsheetCollaborativeChannel from "./mock_spreadsheet_collaborative_channel";
import { getBasicArch } from "./spreadsheet_test_data";
import spreadsheet from "documents_spreadsheet.spreadsheet";
import { createWebClient, doAction } from '@web/../tests/webclient/helpers';
import { registerCleanup } from "@web/../tests/helpers/cleanup";
import { registry } from "@web/core/registry";
import { actionService } from "@web/webclient/actions/action_service";

const { Model } = spreadsheet;
const { toCartesian } = spreadsheet.helpers;
const { cellMenuRegistry, topbarMenuRegistry } = spreadsheet.registries;

const { module, test } = QUnit;

function getConnectedUsersEl(webClient) {
    const numberUsers = $(webClient.el).find(".o_spreadsheet_number_users");
    return numberUsers[0].querySelector("i");
}

function getSynchedStatus(webClient) {
    return $(webClient.el).find(".o_spreadsheet_sync_status")[0].innerText;
}

function displayedConnectedUsers(webClient) {
    return parseInt(getConnectedUsersEl(webClient).innerText);
}

module("documents_spreadsheet > Spreadsheet Client Action", {
    beforeEach: function () {
        this.arch = getBasicArch();
        this.data = {
            "documents.document": {
                fields: {
                    name: { string: "Name", type: "char" },
                    raw: { string: "Data", type: "text" },
                    thumbnail: { string: "Thumbnail", type: "text" },
                    favorited_ids: { string: "Name", type: "many2many" },
                    is_favorited: { string: "Name", type: "boolean" },
                },
                records: [
                    { id: 1, name: "My spreadsheet", raw: "{}", is_favorited: false },
                    { id: 2, name: "", raw: "{}", is_favorited: true },
                ],
            },
            "ir.model": {
                fields: {
                    name: { string: "Model Name", type: "char" },
                    model: { string: "Model", type: "char" },
                },
                records: [
                    {
                        id: 37,
                        name: "Product",
                        model: "product",
                    },
                    {
                        id: 544,
                        name: "partner",
                        model: "partner",
                    }
                ],
            },
            "partner": {
                fields: {
                    foo: {
                        string: "Foo",
                        type: "integer",
                        searchable: true,
                        group_operator: "sum",
                    },
                    bar: {
                        string: "Bar",
                        type: "integer",
                        searchable: true,
                        group_operator: "sum",
                    },
                    product: {
                        relation: "product",
                        string: "Product",
                        type: "many2one",
                    },
                    probability: {
                        string: "Probability",
                        type: "integer",
                        searchable: true,
                        group_operator: "avg",
                    },
                },
                records: [
                    {
                        id: 1,
                        foo: 12,
                        bar: 110,
                        product: 37,
                        probability: 10,
                    },
                    {
                        id: 2,
                        foo: 1,
                        bar: 110,
                        product: 41,
                        probability: 11,
                    },
                ],
            },
            product: {
                fields: {
                    name: { string: "Product Name", type: "char" },
                },
                records: [
                    {
                        id: 37,
                        display_name: "xphone",
                    },
                    {
                        id: 41,
                        display_name: "xpad",
                    },
                ],
            },
        };
    },
}, function () {
    module("Spreadsheet control panel");

    test("Number of connected users is correctly rendered", async function (assert) {
        assert.expect(7);
        const transportService = new MockSpreadsheetCollaborativeChannel()
        const { webClient } = await createSpreadsheet({
            transportService,
            data: this.data,
        });
        assert.equal(displayedConnectedUsers(webClient), 1, "It should display one connected user");
        assert.hasClass(getConnectedUsersEl(webClient), "fa-user", "It should display the fa-user icon");
        joinSession(transportService, { id: 1234, userId: 9999 });
        await nextTick();
        assert.equal(displayedConnectedUsers(webClient), 2, "It should display two connected users");
        assert.hasClass(getConnectedUsersEl(webClient), "fa-users", "It should display the fa-users icon");

        // The same user is connected with two different tabs.
        joinSession(transportService, { id: 4321, userId: 9999 });
        await nextTick();
        assert.equal(displayedConnectedUsers(webClient), 2, "It should display two connected users");

        leaveSession(transportService, 4321);
        await nextTick();
        assert.equal(displayedConnectedUsers(webClient), 2, "It should display two connected users");

        leaveSession(transportService, 1234);
        await nextTick();
        assert.equal(displayedConnectedUsers(webClient), 1, "It should display one connected user");
    });

    test("Sync status is correctly rendered", async function (assert) {
        assert.expect(3);
        const { webClient, model, transportService } = await createSpreadsheetFromPivot();
        await nextTick();
        assert.strictEqual(getSynchedStatus(webClient), " Saved");
        await transportService.concurrent(async () => {
            setCellContent(model, "A1", "hello");
            await nextTick();
            assert.strictEqual(getSynchedStatus(webClient), " Saving");
        });
        await nextTick();
        assert.strictEqual(getSynchedStatus(webClient), " Saved");
    });

    test("breadcrumb is rendered in control panel", async function (assert) {
        assert.expect(3);

        const actions = {
            1: {
                id: 1,
                name: "Documents",
                res_model: "documents.document",
                type: "ir.actions.act_window",
                views: [[false, "list"]],
            },
        };
        const views = {
            "documents.document,false,list": '<tree><field name="name"/></tree>',
            "documents.document,false,search": "<search></search>",
        };
        const serverData = { actions, models: this.data, views };

        const webClient = await createWebClient({
            serverData,
            legacyParams: { withLegacyMockServer: true },
        });
        await doAction(webClient, 1);
        await doAction(webClient, {
            type: "ir.actions.client",
            tag: "action_open_spreadsheet",
            params: {
            active_id: 1,
            transportService: new MockSpreadsheetCollaborativeChannel(),
            },
        });
        const breadcrumbItems = $(webClient.el).find(".breadcrumb-item");
        assert.equal(breadcrumbItems[0].querySelector("a").innerText, "Documents",
            "It should display the breadcrumb");
        assert.equal(breadcrumbItems[1].querySelector("input").value, "My spreadsheet",
            "It should display the spreadsheet title");
        assert.ok(breadcrumbItems[1].querySelector(".o_spreadsheet_favorite"),
            "It should display the favorite toggle button");
    });

    test("untitled spreadsheet", async function (assert) {
        assert.expect(2);
        const { webClient } = await createSpreadsheet({ data: this.data, spreadsheetId: 2 });
        const input = $(webClient.el).find(".breadcrumb-item input")[0];
        assert.equal(input.value, "", "It should be empty");
        assert.equal(input.placeholder, "Untitled spreadsheet", "It should display a placeholder");
        await nextTick();
    });

    test("input width changes when content changes", async function (assert) {
        assert.expect(2);
        const { webClient } = await createSpreadsheet({ data: this.data });
        const input = $(webClient.el).find(".breadcrumb-item input")[0];
        await fields.editInput(input, "My");
        let width = input.offsetWidth;
        await fields.editInput(input, "My title");
        assert.ok(width < input.offsetWidth, "It should have grown to fit content");
        width = input.offsetWidth;
        await fields.editInput(input, "");
        assert.ok(width < input.offsetWidth, "It should have the size of the placeholder text");
    });

    test("changing the input saves the name", async function (assert) {
        assert.expect(1);
        const { webClient } = await createSpreadsheet({ data: this.data, spreadsheetId: 2 });
        const input = $(webClient.el).find(".breadcrumb-item input")[0];
        await fields.editAndTrigger(input, "My spreadsheet", ["change"]);
        assert.equal(
            this.data["documents.document"].records[1].name,
            "My spreadsheet",
            "It should have updated the name"
        );
    });

    test("trailing white spaces are trimmed", async function (assert) {
        assert.expect(2);
        const { webClient } = await createSpreadsheet({ data: this.data });
        const input = $(webClient.el).find(".breadcrumb-item input")[0];
        await fields.editInput(input, "My spreadsheet  ");
        const width = input.offsetWidth;
        await dom.triggerEvent(input, "change");
        assert.equal(input.value, "My spreadsheet", "It should not have trailing white spaces");
        assert.ok(width > input.offsetWidth, "It should have resized");
    });

    test("focus sets the placeholder as value and select it", async function (assert) {
        assert.expect(4);
        const { webClient } = await createSpreadsheet({ data: this.data, spreadsheetId: 2 });
        const input = $(webClient.el).find(".breadcrumb-item input")[0];
        assert.equal(input.value, "", "It should be empty");
        await dom.triggerEvent(input, "focus");
        assert.equal(input.value, "Untitled spreadsheet", "Placeholder should have become the input value");
        assert.equal(input.selectionStart, 0, "It should have selected the value");
        assert.equal(input.selectionEnd, input.value.length, "It should have selected the value");
    });

    test("receiving bad revision reload", async function (assert) {
        assert.expect(2);
        const transportService = new MockSpreadsheetCollaborativeChannel();
        const serviceRegistry = registry.category("services");
        serviceRegistry.add("actionMain", actionService);
        const fakeActionService = {
            dependencies: ["actionMain"],
            start(env, { actionMain }) {
                return Object.assign({}, actionMain, {
                    doAction: (actionRequest, options = {}) => {
                        if (actionRequest === "reload_context") {
                            assert.step("reload");
                            return Promise.resolve();
                        }
                        return actionMain.doAction(actionRequest, options);
                    },
                });
            },
        };
        serviceRegistry.add("action", fakeActionService, { force: true });
        await createSpreadsheet({
            data: this.data,
            transportService,
        });
        transportService.broadcast({
            type: "REMOTE_REVISION",
            serverRevisionId: "an invalid revision id",
            nextRevisionId: "the next revision id",
            revision: {},
        });
        assert.verifySteps(["reload"]);
    });

    test("only white spaces show the placeholder", async function (assert) {
        assert.expect(2);
        const { webClient } = await createSpreadsheet({ data: this.data });
        const input = $(webClient.el).find(".breadcrumb-item input")[0];
        await fields.editInput(input, "  ");
        const width = input.offsetWidth;
        await dom.triggerEvent(input, "change");
        assert.equal(input.value, "", "It should be empty");
        assert.ok(width < input.offsetWidth, "It should have the placeholder size");
    });

    test("toggle favorite", async function (assert) {
        assert.expect(5);
        const { webClient } = await createSpreadsheet({
            spreadsheetId: 1,
            data: this.data,
            mockRPC: async function (route, args) {
                if (args.method === "toggle_favorited" && args.model === "documents.document") {
                    assert.step("favorite_toggled");
                    assert.deepEqual(args.args[0], [1], "It should write the correct document");
                    return true;
                }
                if (route.includes("dispatch_spreadsheet_message")) {
                    return Promise.resolve();
                }
            },
        });
        assert.containsNone(webClient, ".favorite_button_enabled");
        const favorite = $(webClient.el).find(".o_spreadsheet_favorite")[0];
        await dom.click(favorite);
        assert.containsOnce(webClient, ".favorite_button_enabled");
        assert.verifySteps(["favorite_toggled"]);
    });

    test("already favorited", async function (assert) {
        assert.expect(1);
        const { webClient } = await createSpreadsheet({
            spreadsheetId: 2,
            data: this.data,
        });
        assert.containsOnce(webClient, ".favorite_button_enabled", "It should already be favorited");
    });

    test("Spreadsheet action is named in breadcrumb", async function (assert) {
        assert.expect(2);
        const arch = `
            <pivot string="Partners">
                <field name="bar" type="col"/>
                <field name="foo" type="row"/>
                <field name="probability" type="measure"/>
            </pivot>`;
        const { webClient } = await createSpreadsheetFromPivot({
            pivotView: {
                model: "partner",
                data: this.data,
                arch,
                archs: {
                    "partner,false,pivot": arch,
                    "partner,false,search": `<search/>`,
                },
            },
        });
        await doAction(webClient, {
            name: 'Partner',
            res_model: 'partner',
            type: 'ir.actions.act_window',
            views: [[false, 'pivot']],
        });
        await nextTick();
        const items = $(webClient.el).find(".breadcrumb-item");
        const [breadcrumb1, breadcrumb2] = Array.from(items).map((item) => item.innerText);
        assert.equal(breadcrumb1, "pivot spreadsheet");
        assert.equal(breadcrumb2, "Partner");
    });

    module("Spreadsheet");

    test("relational PIVOT.HEADER with missing id", async function (assert) {
        assert.expect(2);

        const { model } = await createSpreadsheetFromPivot({
            pivotView: {
                model: "partner",
                data: this.data,
                arch: `
                <pivot string="Partners">
                    <field name="product" type="col"/>
                    <field name="bar" type="row"/>
                    <field name="probability" type="measure"/>
                </pivot>`,
            },
        });
        const sheetId = model.getters.getActiveSheetId();
        model.dispatch("UPDATE_CELL", {
            col: 4,
            row: 9,
            content: `=PIVOT.HEADER("1", "product", "1111111")`,
            sheetId,
        });
        await nextTick();
        assert.ok(model.getters.getCell(sheetId, 4, 9).error);

        // This is obviously not the desired error message. It happens because Odoo
        // RPC errors do not have a simple string message but an object with the
        // error details.
        // Will be fixed with task 2393876
        assert.equal(model.getters.getCell(sheetId, 4, 9).error, "Cannot read property 'display_name' of undefined");
    });

    test("relational PIVOT.HEADER with undefined id", async function (assert) {
        assert.expect(2);

        const { model } = await createSpreadsheetFromPivot({
            pivotView: {
                model: "partner",
                data: this.data,
                arch: `
                <pivot string="Partners">
                    <field name="foo" type="col"/>
                    <field name="product" type="row"/>
                    <field name="probability" type="measure"/>
                </pivot>`,
            },
        });
        const sheetId = model.getters.getActiveSheetId();
        model.dispatch("UPDATE_CELL", {
            col: 4,
            row: 9,
            content: `=PIVOT.HEADER("1", "product", A25)`,
            sheetId,
        });
        assert.equal(model.getters.getCell(sheetId, 0, 24), null, "the cell should be empty");
        await nextTick();
        assert.equal(model.getters.getCell(sheetId, 4, 9).value, "");
    });

    test("Reinsert a pivot", async function (assert) {
        assert.expect(1);

        const { model, env } = await createSpreadsheetFromPivot({
            pivotView: {
                model: "partner",
                data: this.data,
                arch: this.arch,
            },
        });
        const sheetId = model.getters.getActiveSheetId();
        model.dispatch("SELECT_CELL", { col: 3, row: 7 });
        const root = cellMenuRegistry.getAll().find((item) => item.id === "reinsert_pivot");
        const reinsertPivot1 = cellMenuRegistry.getChildren(root, env)[0];
        await reinsertPivot1.action(env);
        assert.equal(getCellFormula(model, "E10"), `=PIVOT("1","probability","bar","110","foo","1")`,
            "It should contain a pivot formula");
    });

    test("Reinsert a pivot in a too small sheet", async function (assert) {
        assert.expect(3);

        const { model, env } = await createSpreadsheetFromPivot({
            pivotView: {
                model: "partner",
                data: this.data,
                arch: this.arch,
            },
        });
        const sheetId = model.getters.getActiveSheetId();
        model.dispatch("CREATE_SHEET", { cols: 1, rows: 1, sheetId: "111" });
        model.dispatch("ACTIVATE_SHEET", { sheetIdFrom: sheetId, sheetIdTo: "111"});
        model.dispatch("SELECT_CELL", { col: 0, row: 0 });
        const root = cellMenuRegistry.getAll().find((item) => item.id === "reinsert_pivot");
        const reinsertPivot1 = cellMenuRegistry.getChildren(root, env)[0];
        await reinsertPivot1.action(env);
        assert.equal(model.getters.getActiveSheet().cols.length, 5);
        assert.equal(model.getters.getActiveSheet().rows.length, 5);
        assert.equal(getCellFormula(model, "B3"), `=PIVOT("1","probability","bar","110","foo","1")`,
            "It should contain a pivot formula");
    });

    test("Reinsert a pivot with new data", async function (assert) {
        assert.expect(2);

        const { model, env } = await createSpreadsheetFromPivot({
            pivotView: {
                model: "partner",
                data: this.data,
                arch: this.arch,
            },
        });
        this.data.partner.records = [...this.data.partner.records, {
            id: 3,
            foo: 1,
            bar: 7, // <- new row value in the pivot
            probability: 15,
            name: "name",
            display_name: "name",
        }];
        model.dispatch("SELECT_CELL", { col: 3, row: 7 });
        const root = cellMenuRegistry.getAll().find((item) => item.id === "reinsert_pivot");
        const reinsertPivot1 = cellMenuRegistry.getChildren(root, env)[0];
        await reinsertPivot1.action(env);
        assert.equal(getCellFormula(model, "E10"), `=PIVOT("1","probability","bar","7","foo","1")`,
            "It should contain a pivot formula");
        assert.equal(getCellFormula(model, "E11"), `=PIVOT("1","probability","bar","110","foo","1")`,
            "It should contain a new row");
    });

    test("Reinsert a pivot with an updated record", async function (assert) {
        assert.expect(6);

        const { model, env } = await createSpreadsheetFromPivot({
            pivotView: {
                model: "partner",
                data: this.data,
                arch: this.arch,
            },
        });
        const sheetId = model.getters.getActiveSheetId();
        assert.equal(/*A3*/model.getters.getCell(sheetId, 0, 2).value, 110,);
        assert.equal(/*B3*/model.getters.getCell(sheetId, 1, 2).value, 11);
        assert.equal(/*C3*/model.getters.getCell(sheetId, 2, 2).value, 10);
            // previously in group bar=110, now it's in a new group bar=99
        this.data.partner.records[0].bar = 99;
        this.data.partner.records[1].bar = 99;
        // updated measures
        this.data.partner.records[0].probability = 88;
        this.data.partner.records[1].probability = 77;
        const root = cellMenuRegistry.getAll().find((item) => item.id === "reinsert_pivot");
        const reinsertPivot1 = cellMenuRegistry.getChildren(root, env)[0];
        await reinsertPivot1.action(env);
        await nextTick();
        assert.equal(/*A3*/model.getters.getCell(sheetId, 0, 2).value, 99, "The header should have been updated");
        assert.equal(/*B3*/model.getters.getCell(sheetId, 1, 2).value, 77, "The value should have been updated");
        assert.equal(/*C3*/model.getters.getCell(sheetId, 2, 2).value, 88, "The value should have been updated");
    });

    test("Keep applying filter when pivot is re-inserted", async function (assert) {
        assert.expect(4);
        const { model, env } = await createSpreadsheetFromPivot({
            pivotView: {
                model: "partner",
                data: this.data,
                arch: `
                    <pivot>
                        <field name="bar" type="col"/>
                        <field name="product" type="row"/>
                        <field name="probability" type="measure"/>
                    </pivot>
                `,
            },
        });
        model.dispatch("ADD_PIVOT_FILTER", {
            filter: {
                id: "42",
                type: "relation",
                label: "Filter",
                fields: {
                    1: {
                        field: "product",
                        type: "many2one",
                    }
                },
            }
        });
        model.dispatch("SET_PIVOT_FILTER_VALUE", {
            id: "42",
            value: [41],
        });
        await nextTick();
        assert.equal(getCellValue(model, "B3"), "", "The value should have been filtered");
        assert.equal(getCellValue(model, "C3"), "", "The value should have been filtered");
        const root = cellMenuRegistry.getAll().find((item) => item.id === "reinsert_pivot");
        const reinsertPivot1 = cellMenuRegistry.getChildren(root, env)[0];
        await reinsertPivot1.action(env);
        await nextTick();
        assert.equal(getCellValue(model, "B3"), "", "The value should still be filtered");
        assert.equal(getCellValue(model, "C3"), "", "The value should still be filtered");
    });

    test("undo pivot reinsert", async function (assert) {
        assert.expect(2);

        const { model, env } = await createSpreadsheetFromPivot({
            pivotView: {
                model: "partner",
                data: this.data,
                arch: this.arch,
            },
        });
        const sheetId = model.getters.getActiveSheetId();
        model.dispatch("SELECT_CELL", { col: 3, row: 7 });
        const root = cellMenuRegistry.getAll().find((item) => item.id === "reinsert_pivot");
        const reinsertPivot1 = cellMenuRegistry.getChildren(root, env)[0];
        await reinsertPivot1.action(env);
        assert.equal(getCellFormula(model, "E10"), `=PIVOT("1","probability","bar","110","foo","1")`,
            "It should contain a pivot formula");
        model.dispatch("REQUEST_UNDO");
        assert.notOk(model.getters.getCell(sheetId, 4, 9), "It should have removed the re-inserted pivot");
    });

    test("reinsert pivot with anchor on merge but not top left", async function (assert) {
        assert.expect(3);

        const { model, env } = await createSpreadsheetFromPivot({
            pivotView: {
                model: "partner",
                data: this.data,
                arch: this.arch,
            },
        });
        const sheetId = model.getters.getActiveSheetId();
        assert.equal(getCellFormula(model, "B2"), `=PIVOT.HEADER("1","foo","1","measure","probability")`,
            "It should contain a pivot formula");
        model.dispatch("ADD_MERGE", { sheetId, target: [{ top: 0, bottom: 1, left: 0, right: 0}]});
        model.dispatch("SELECT_CELL", { col: 0, row: 1 }); // A1 and A2 are merged; select A2
        assert.ok(model.getters.isInMerge(sheetId, ...toCartesian("A2")));
        const root = cellMenuRegistry.getAll().find((item) => item.id === "reinsert_pivot");
        const reinsertPivot1 = cellMenuRegistry.getChildren(root, env)[0];
        await reinsertPivot1.action(env);
        assert.equal(getCellFormula(model, "B2"), `=PIVOT.HEADER("1","foo","1","measure","probability")`,
            "It should contain a pivot formula");
    });

    test("Verify pivot measures are correctly computed :)", async function (assert) {
        assert.expect(4);

        const { model } = await createSpreadsheetFromPivot({
            pivotView: {
                model: "partner",
                data: this.data,
                arch: this.arch,
            },
        });
        const sheetId = model.getters.getActiveSheetId();
        assert.equal(model.getters.getCell(sheetId, 1, 2).value, 11);
        assert.equal(model.getters.getCell(sheetId, 2, 2).value, 10);
        assert.equal(model.getters.getCell(sheetId, 1, 3).value, 11);
        assert.equal(model.getters.getCell(sheetId, 2, 3).value, 10);
    });

    test("Open pivot properties properties", async function (assert) {
        assert.expect(16);

        const { webClient, model, env } = await createSpreadsheetFromPivot({
            pivotView: {
                model: "partner",
                data: this.data,
                arch: `
                    <pivot display_quantity="true">
                        <field name="foo" type="col"/>
                        <field name="bar" type="row"/>
                        <field name="probability" type="measure"/>
                    </pivot>`,
            },
        });
        // opening from a pivot cell
        const pivotA3 = model.getters.getPivotFromPosition(0, 2);
        await model.getters.getAsyncCache(pivotA3);
        model.dispatch("SELECT_PIVOT", { pivotId: pivotA3 });
        env.openSidePanel("PIVOT_PROPERTIES_PANEL", {
            pivot: model.getters.getSelectedPivot(),
        });
        await nextTick();
        let title = $(webClient.el).find(".o-sidePanelTitle")[0].innerText;
        assert.equal(title, "Pivot properties");

        const sections = $(webClient.el).find(".o_side_panel_section");
        assert.equal(sections.length, 5, "it should have 5 sections");
        const [pivotName, pivotModel, domain, dimensions, measures] = sections;

        assert.equal(pivotName.children[0].innerText, "Pivot name");
        assert.equal(pivotName.children[1].innerText, "partner (#1)");

        assert.equal(pivotModel.children[0].innerText, "Model");
        assert.equal(pivotModel.children[1].innerText, "partner (partner)");

        assert.equal(domain.children[0].innerText, "Domain");
        assert.equal(domain.children[1].innerText, "Match all records");

        assert.equal(measures.children[0].innerText, "Measures");
        assert.equal(measures.children[1].innerText, "Count");
        assert.equal(measures.children[2].innerText, "Probability");

        assert.equal(dimensions.children[0].innerText, "Dimensions");
        assert.equal(dimensions.children[1].innerText, "Bar");
        assert.equal(dimensions.children[2].innerText, "Foo");

        // opening from a non pivot cell
        const pivotA1 = model.getters.getPivotFromPosition(0, 0);
        model.dispatch("SELECT_PIVOT", { pivotId: pivotA1 });
        env.openSidePanel("PIVOT_PROPERTIES_PANEL", {
            pivot: model.getters.getSelectedPivot(),
        });
        await nextTick();
        title = $(webClient.el).find(".o-sidePanelTitle")[0].innerText;
        assert.equal(title, "Pivot properties");

        assert.containsOnce(webClient, '.o_side_panel_select');
    });

    test("verify absence of pivots in top menu bar in a spreadsheet without a pivot", async function (assert) {
        assert.expect(1);
        const { webClient } = await createSpreadsheet({ data: this.data });
        assert.containsNone(webClient, "div[data-id='pivots']");
    });

    test("Verify presence of pivots in top menu bar in a spreadsheet with a pivot", async function (assert) {
        assert.expect(7);

        const pivotController = await createView({
            View: PivotView,
            model: "partner",
            data: this.data,
            arch: this.arch,
        });
        registerCleanup(() => pivotController.destroy());

        const { webClient, model, env } = await createSpreadsheetFromPivot({
            pivotView: {
                model: "partner",
                data: this.data,
                arch: `
                <pivot string="Partners">
                    <field name="product" type="col"/>
                    <field name="bar" type="row"/>
                    <field name="probability" type="measure"/>
                </pivot>`,
            },
        });

        const { pivot, cache } = await pivotController._getPivotForSpreadsheet();
        const sheetId = model.getters.getActiveSheetId();

        model.dispatch("BUILD_PIVOT", {
            sheetId,
            anchor: [12, 0], // this position is still free
            pivot,
            cache,
        });

        assert.ok($(webClient.el).find("div[data-id='pivots']")[0], "The 'Pivots' menu should be in the dom");

        const root = topbarMenuRegistry.getAll().find((item) => item.id === "pivots");
        const children = topbarMenuRegistry.getChildren(root, env);
        assert.equal(children.length, 5, "There should be 5 children in the menu");
        assert.equal(children[0].name, "View partner (#1)");
        assert.equal(children[1].name, "View partner (#2)");
        // bottom children
        assert.equal(children[2].name, "Refresh pivot values");
        assert.equal(children[3].name, "re-Insert Pivot");
        assert.equal(children[4].name, "Insert pivot cell");
    });

    test("Pivot focus changes on top bar menu click", async function (assert) {
        assert.expect(3);

        const pivotController = await createView({
            View: PivotView,
            model: "partner",
            data: this.data,
            arch: this.arch,
        });
        registerCleanup(() => pivotController.destroy());

        const { model, env } = await createSpreadsheetFromPivot({
            pivotView: {
                model: "partner",
                data: this.data,
                arch: `
                <pivot string="Partners">
                    <field name="product" type="col"/>
                    <field name="bar" type="row"/>
                    <field name="probability" type="measure"/>
                </pivot>`,
            },
        });

        const { pivot, cache } = await pivotController._getPivotForSpreadsheet();
        const sheetId = model.getters.getActiveSheetId();

        model.dispatch("BUILD_PIVOT", {
            sheetId,
            anchor: [12, 0], // this position is still free
            pivot,
            cache,
        });

        const root = topbarMenuRegistry.getAll().find((item) => item.id === "pivots");
        const children = topbarMenuRegistry.getChildren(root, env);

        env.openSidePanel("PIVOT_PROPERTIES_PANEL", {})
        assert.notOk(model.getters.getSelectedPivot(), "No pivot should be selected");
        children[0].action(env);
        assert.equal(model.getters.getSelectedPivot(), model.getters.getPivot(1), "The selected pivot should have id 1");
        children[1].action(env);
        assert.equal(model.getters.getSelectedPivot(), model.getters.getPivot(2), "The selected pivot should have id 2");
    });

    test("Pivot focus changes on sidepanel click", async function (assert) {
        assert.expect(6);

        const pivotController = await createView({
            View: PivotView,
            model: "partner",
            data: this.data,
            arch: this.arch,
        });
        registerCleanup(() => pivotController.destroy());

        const { webClient, model, env } = await createSpreadsheetFromPivot({
            pivotView: {
                model: "partner",
                data: this.data,
                arch: `
                <pivot string="Partners">
                    <field name="product" type="col"/>
                    <field name="bar" type="row"/>
                    <field name="probability" type="measure"/>
                </pivot>`,
            },
        });

        const { pivot, cache } = await pivotController._getPivotForSpreadsheet();
        const sheetId = model.getters.getActiveSheetId();

        model.dispatch("BUILD_PIVOT", {
            sheetId,
            anchor: [12, 0], // this position is still free
            pivot,
            cache,
        });

        env.dispatch("SELECT_CELL", { col: 11, row: 0 }) //target empty cell
        const root = cellMenuRegistry.getAll().find((item) => item.id === "pivot_properties");
        root.action(env);
        assert.notOk(model.getters.getSelectedPivot(), "No pivot should be selected");
        await nextTick();
        assert.containsN(webClient, ".o_side_panel_select", 2);
        await dom.click($(webClient.el).find(".o_side_panel_select")[0]);
        assert.equal(model.getters.getSelectedPivot(), model.getters.getPivot(1), "The selected pivot should be have the id 1");
        await nextTick();
        await dom.click($(webClient.el).find(".o_pivot_cancel"));
        assert.notOk(model.getters.getSelectedPivot(), "No pivot should be selected anymore");
        assert.containsN(webClient, ".o_side_panel_select", 2);
        await dom.click($(webClient.el).find(".o_side_panel_select")[1]);
        assert.equal(model.getters.getSelectedPivot(), model.getters.getPivot(2), "The selected pivot should be have the id 2");
    });

    test("Can refresh the pivot from the pivot properties panel", async function (assert) {
        assert.expect(1);

        const { webClient, model, env } = await createSpreadsheetFromPivot({
            pivotView: {
                model: "partner",
                data: this.data,
                arch: `
                    <pivot display_quantity="true">
                        <field name="foo" type="col"/>
                        <field name="bar" type="row"/>
                        <field name="probability" type="measure"/>
                    </pivot>`,
            },
        });
        const pivotA3 = model.getters.getPivotFromPosition(0, 2);
        model.dispatch("SELECT_PIVOT", { pivotId: pivotA3 });
        env.openSidePanel("PIVOT_PROPERTIES_PANEL", {});
        this.data.partner.records.push({
            id: 1,
            foo: 12,
            bar: 110,
            product: 37,
            probability: 10,
        },);
        await nextTick();
        await dom.click($(webClient.el).find(".o_refresh_measures")[0]);
        await nextTick();
        assert.equal(getCellValue(model, "D3"), 2);
    });

    test("Can make a copy", async function (assert) {
        assert.expect(4);
        const LocalStorageService = AbstractStorageService.extend({
            storage: new RamStorage(),
        });
        const legacyServicesRegistry = new legacyRegistry();
        legacyServicesRegistry.add("bus_service", BusService.extend({
            _poll() {}
        }));
        legacyServicesRegistry.add("local_storage", LocalStorageService);
        const spreadsheet = this.data["documents.document"].records[1];
        const { env, model } = await createSpreadsheet({
            spreadsheetId: spreadsheet.id,
            data: this.data,
            legacyServicesRegistry,
            mockRPC: async function (route, args) {
                if (args.method === "copy" && args.model === "documents.document") {
                    assert.step("copy");
                    assert.equal(
                        args.args[1].raw,
                        JSON.stringify(model.exportData()),
                        "It should copy the data"
                    );
                    assert.equal(
                        args.args[1].spreadsheet_snapshot,
                        false,
                        "It should reset the snapshot"
                    );
                }
            },
        });
        const file = topbarMenuRegistry.getAll().find((item) => item.id === "file");
        const makeCopy = file.children.find((item) => item.id === "make_copy");
        makeCopy.action(env);
        assert.verifySteps(["copy"]);
    });

    test("Check pivot measures with m2o field", async function (assert) {
        assert.expect(3);
        this.data.partner.records.push(
            {id: 3, foo: 12, bar: 110, product: 37, probability: 50},
            {id: 4, foo: 18, bar: 110, product: 41, probability: 12},
            {id: 5, foo: 18, bar: 110, product: 37, probability: 13},
            {id: 6, foo: 18, bar: 110, product: 37, probability: 14},
        )
        const { model } = await createSpreadsheetFromPivot({
          pivotView: {
            model: "partner",
            data: this.data,
            arch: `
              <pivot string="Partners">
                <field name="foo" type="col"/>
                <field name="bar" type="row"/>
                <field name="product" type="measure"/>
              </pivot>`,
          }
        });
        const sheetId = model.getters.getActiveSheetId();
        assert.equal(model.getters.getCell(sheetId, 1, 2).value, 1, "[Cell B3] There is one distinct product for 'foo - 1' and 'bar - 110'");
        assert.equal(model.getters.getCell(sheetId, 2, 2).value, 1, "[Cell C3] There is one distinct product for 'foo - 12' and 'bar - 110'");
        assert.equal(model.getters.getCell(sheetId, 3, 2).value, 2, "[Cell D3] There are two distinct products for 'foo - 18' and 'bar - 110'");
    });

    module("Global filters panel");

    test("Simple display", async function (assert) {
        assert.expect(6);

        const { webClient } = await createSpreadsheetFromPivot({
            pivotView: {
                model: "partner",
                data: this.data,
                arch: this.arch,
            },
        });
        assert.notOk($(webClient.el).find(".o_spreadsheet_global_filters_side_panel")[0]);
        const searchIcon = $(webClient.el).find(".o_topbar_filter_icon")[0];
        await dom.click(searchIcon);
        assert.ok($(webClient.el).find(".o_spreadsheet_global_filters_side_panel")[0]);
        const items = $(webClient.el).find(".o_spreadsheet_global_filters_side_panel .o-sidePanelButton");
        assert.equal(items.length, 3);
        assert.ok(items[0].classList.contains("o_global_filter_new_time"));
        assert.ok(items[1].classList.contains("o_global_filter_new_relation"));
        assert.ok(items[2].classList.contains("o_global_filter_new_text"));
    });

    test("Display with an existing 'Date' global filter", async function (assert) {
        assert.expect(4);

        const { webClient, model } = await createSpreadsheetFromPivot({
            pivotView: {
                model: "partner",
                data: this.data,
                arch: this.arch,
            },
        });
        const label = "This year";
        model.dispatch("ADD_PIVOT_FILTER", { filter: { id: "42", type: "date", label, fields: {}, defaultValue: {}}});
        const searchIcon = $(webClient.el).find(".o_topbar_filter_icon")[0];
        await dom.click(searchIcon);
        const items = $(webClient.el).find(".o_spreadsheet_global_filters_side_panel .o_side_panel_section");
        assert.equal(items.length, 2);
        const labelElement = items[0].querySelector(".o_side_panel_filter_label");
        assert.equal(labelElement.innerText, label);
        await dom.click(items[0].querySelector(".o_side_panel_filter_icon"));
        assert.ok($(webClient.el).find(".o_spreadsheet_filter_editor_side_panel"));
        assert.equal($(webClient.el).find(".o_global_filter_label")[0].value, label);
    });

    test("Create a new global filter", async function (assert) {
        assert.expect(4);

        const { webClient, model } = await createSpreadsheetFromPivot({
            pivotView: {
                model: "partner",
                data: this.data,
                arch: `
                    <pivot string="Partners">
                        <field name="foo" type="col"/>
                        <field name="bar" type="row"/>
                        <field name="probability" type="measure"/>
                    </pivot>
                `,
            },
        });
        const searchIcon = $(webClient.el).find(".o_topbar_filter_icon")[0];
        await dom.click(searchIcon);
        const newText = $(webClient.el).find(".o_global_filter_new_text")[0];
        await dom.click(newText);
        assert.equal($(webClient.el).find(".o-sidePanel").length, 1);
        const input = $(webClient.el).find(".o_global_filter_label")[0];
        await fields.editInput(input, "My Label");
        const value = $(webClient.el).find(".o_global_filter_default_value")[0];
        await fields.editInput(value, "Default Value");
        // Can't make it work with the DOM API :(
        // await dom.triggerEvent($(webClient.el).find(".o_field_selector_value"), "focusin");
        $($(webClient.el).find(".o_field_selector_value")).focusin();
        await dom.click($(webClient.el).find(".o_field_selector_select_button")[0]);
        const save = $(webClient.el).find(".o_spreadsheet_filter_editor_side_panel .o_global_filter_save")[0];
        await dom.click(save);
        assert.equal($(webClient.el).find(".o_spreadsheet_global_filters_side_panel").length, 1);
        const globalFilter = model.getters.getGlobalFilters()[0];
        assert.equal(globalFilter.label, "My Label");
        assert.equal(globalFilter.defaultValue, "Default Value");
    });

    test("Create a new relational global filter", async function (assert) {
        assert.expect(4);

        const { webClient, model } = await createSpreadsheetFromPivot({
            pivotView: {
                model: "partner",
                data: this.data,
                arch: `
                <pivot string="Partners">
                    <field name="foo" type="col"/>
                    <field name="product" type="row"/>
                    <field name="probability" type="measure"/>
                </pivot>`,
            },
        });
        const searchIcon = $(webClient.el).find(".o_topbar_filter_icon")[0];
        await dom.click(searchIcon);
        const newRelation = $(webClient.el).find(".o_global_filter_new_relation")[0];
        await dom.click(newRelation);
        let selector = `.o_field_many2one[name="ir.model"] input`;
        await dom.click($(webClient.el).find(selector)[0]);
        let $dropdown = $(selector).autocomplete('widget');
        let $target = $dropdown.find(`li:contains(Product)`).first();
        await dom.click($target);

        let save = $(webClient.el).find(".o_spreadsheet_filter_editor_side_panel .o_global_filter_save")[0];
        await dom.click(save);
        assert.equal($(webClient.el).find(".o_spreadsheet_global_filters_side_panel").length, 1);
        let globalFilter = model.getters.getGlobalFilters()[0];
        assert.equal(globalFilter.label, "Product");
        assert.deepEqual(globalFilter.defaultValue, []);
        assert.deepEqual(globalFilter.fields[1], { field: "product", type: "many2one" });
    });

    // LPE Fixme: there is a genuine bug in business code: the read_group triggered by
    // `model.dispatch("ADD_PIVOT_FILTER", { filter });`has the form [["product", "in", {…}]]
    // where in should always have an Array of ids, not an object
    QUnit.skip("Display with an existing 'Relation' global filter", async function (assert) {
        assert.expect(8);

        const { webClient, model } = await createSpreadsheetFromPivot({
          pivotView: {
              model: "partner",
              data: this.data,
              arch: `
              <pivot string="Partners">
                  <field name="foo" type="col"/>
                  <field name="bar" type="row"/>
                  <field name="probability" type="measure"/>
              </pivot>`,
            }
        });
        const label = "MyFoo";
        const pivots =model.getters.getPivots();
        model.dispatch("ADD_PIVOT", {
            anchor: [15, 15],
            pivot: { ...pivots[0], id: 2 },
        })
        const filter = {
            id: "42",
            type: "relation",
            modelName: "product",
            label,
            fields: {
                1: { type:"many2one", field:"product" }, // first pivotId
                2: { type:"many2one", field:"product" } // second pivotId
            },
            defaultValue: {},
        }
        model.dispatch("ADD_PIVOT_FILTER", { filter });
        const searchIcon = webClient.el.querySelector(".o_topbar_filter_icon");
        await dom.click(searchIcon);
        const items = webClient.el.querySelectorAll(".o_spreadsheet_global_filters_side_panel .o_side_panel_section");
        assert.equal(items.length, 2);
        const labelElement = items[0].querySelector(".o_side_panel_filter_label");
        assert.equal(labelElement.innerText, label);
        await dom.click(items[0].querySelector(".o_side_panel_filter_icon"));
        assert.ok(webClient.el.querySelectorAll(".o_spreadsheet_filter_editor_side_panel"));
        assert.equal(webClient.el.querySelector(".o_global_filter_label").value, label);
        assert.equal(webClient.el.querySelector(`.o_field_many2one[name="ir.model"] input`).value, "Product");
        const fieldsMatchingElements = webClient.el.querySelectorAll("span.o_field_selector_chain_part")
        assert.equal(fieldsMatchingElements.length, 2);
        assert.equal(fieldsMatchingElements[0].innerText, "Product");
        assert.equal(fieldsMatchingElements[1].innerText, "Product");
    });

    test("Only related models can be selected", async function (assert) {
        assert.expect(2);
        this.data["ir.model"].records.push({
            id: 36,
            name: "Apple",
            model: "apple",
        }, {
            id: 35,
            name: "Document",
            model: "documents.document",
        });
        this.data["partner"].fields.document = {
            relation: "documents.document",
            string: "Document",
            type: "many2one",
        };
        const { webClient } = await createSpreadsheetFromPivot({
            pivotView: {
                model: "partner",
                data: this.data,
                arch: `
                <pivot string="Partners">
                    <field name="foo" type="col"/>
                    <field name="product" type="row"/>
                    <field name="probability" type="measure"/>
                </pivot>`,
            },
        });
        const searchIcon = $(webClient.el).find(".o_topbar_filter_icon")[0];
        await dom.click(searchIcon);
        const newRelation = $(webClient.el).find(".o_global_filter_new_relation")[0];
        await dom.click(newRelation);
        const selector = `.o_field_many2one[name="ir.model"] input`;
        await dom.click($(webClient.el).find(selector)[0]);
        const $dropdown = $(selector).autocomplete('widget');
        const [model1, model2] = $dropdown.find(`li`);
        assert.equal(model1.innerText, "Product");
        assert.equal(model2.innerText, "Document");
    });

    test("Edit an existing global filter", async function (assert) {
        assert.expect(4);

        const { webClient, model } = await createSpreadsheetFromPivot({
            pivotView: {
                model: "partner",
                data: this.data,
                arch: this.arch,
            },
        });
        const label = "This year";
        const defaultValue = "value";
        model.dispatch("ADD_PIVOT_FILTER", { filter: { id: "42", type: "text", label, defaultValue, fields: {}}});
        const searchIcon = $(webClient.el).find(".o_topbar_filter_icon")[0];
        await dom.click(searchIcon);
        const editFilter = $(webClient.el).find(".o_side_panel_filter_icon");
        await dom.click(editFilter);
        assert.equal($(webClient.el).find(".o-sidePanel").length, 1);
        const input = $(webClient.el).find(".o_global_filter_label")[0];
        assert.equal(input.value, label);
        const value = $(webClient.el).find(".o_global_filter_default_value")[0];
        assert.equal(value.value, defaultValue);
        await fields.editInput(input, "New Label");
        $($(webClient.el).find(".o_field_selector_value")).focusin();
        await dom.click($(webClient.el).find(".o_field_selector_select_button")[0]);
        const save = $(webClient.el).find(".o_spreadsheet_filter_editor_side_panel .o_global_filter_save")[0];
        await dom.click(save);
        const globalFilter = model.getters.getGlobalFilters()[0];
        assert.equal(globalFilter.label, "New Label");
    });

    test("Default value defines value", async function (assert) {
        assert.expect(1);

        const { model } = await createSpreadsheetFromPivot({
            pivotView: {
                model: "partner",
                data: this.data,
                arch: this.arch,
            },
        });
        const label = "This year";
        const defaultValue = "value";
        model.dispatch("ADD_PIVOT_FILTER", { filter: { id: "42", type: "text", label, defaultValue, fields: {}}});
        const [filter] = model.getters.getGlobalFilters();
        assert.equal(filter.value, defaultValue);
    });

    test("Default value defines value at model loading", async function (assert) {
        assert.expect(1);
        const label = "This year";
        const defaultValue = "value";
        const model = new Model({
            globalFilters: [{ type: "text", label, defaultValue, fields: {}}]
        });
        const [filter] = model.getters.getGlobalFilters();
        assert.equal(filter.value, defaultValue);
    });

    test("Name is only fetched once", async function (assert) {
        assert.expect(6);
        const { model } = await createSpreadsheetFromPivot({
            pivotView: {
                model: "partner",
                data: this.data,
                arch: `
                    <pivot>
                        <field name="bar" type="col"/>
                        <field name="foo" type="row"/>
                        <field name="product" type="row"/>
                        <field name="probability" type="measure"/>
                    </pivot>
                `,
                mockRPC: function (route, args) {
                    if (args.method === "name_get" && args.model === "product") {
                      assert.step(`name_get_product_${args.args[0].join("-")}`);
                    }
                    if (this) {
                        return this._super(...arguments);
                    }
                },
            },
        });
        model.dispatch("ADD_PIVOT_FILTER", {
            filter: {
                id: "42",
                type: "relation",
                label: "Filter",
                fields: {
                    1: {
                        field: "product",
                        type: "many2one",
                    }
                },
            }
        });
        await nextTick();
        // It contains product twice
        assert.equal(getCellFormula(model, "A4"), `=PIVOT.HEADER("1","foo","1","product","37")`);
        assert.equal(getCellFormula(model, "A5"), `=PIVOT.HEADER("1","foo","1","product","41")`);
        assert.equal(getCellFormula(model, "A7"), `=PIVOT.HEADER("1","foo","12","product","37")`);
        assert.equal(getCellFormula(model, "A8"), `=PIVOT.HEADER("1","foo","12","product","41")`);
        model.dispatch("SET_PIVOT_FILTER_VALUE", {
            id: "42",
            value: [17],
        });
        await nextTick();

        // But it only fetches names once
        assert.verifySteps([
            "name_get_product_37-41",
        ]);
    });

    test("Name is not fetched if related record is not assigned", async function (assert) {
        assert.expect(6);
        this.data.partner.records[0].product = false;
        const { model } = await createSpreadsheetFromPivot({
            pivotView: {
                model: "partner",
                data: this.data,
                arch: `
                    <pivot>
                        <field name="bar" type="col"/>
                        <field name="foo" type="row"/>
                        <field name="product" type="row"/>
                        <field name="probability" type="measure"/>
                    </pivot>
                `,
                mockRPC: function (route, args) {
                    if (args.method === "name_get" && args.model === "product") {
                        assert.step(`name_get_product_${args.args[0]}`);
                    }
                    if (this) {
                        return this._super(...arguments);
                    }
                },
            },
        });
        model.dispatch("ADD_PIVOT_FILTER", {
            filter: {
                id: "42",
                type: "relation",
                label: "Filter",
                fields: {
                    1: {
                        field: "product",
                        type: "many2one",
                    }
                },
            }
        });
        await nextTick();
        // It contains undefined headers
        assert.equal(getCellFormula(model, "A4"), `=PIVOT.HEADER("1","foo","1","product","41")`);
        assert.equal(getCellFormula(model, "A5"), `=PIVOT.HEADER("1","foo","1","product","false")`);
        assert.equal(getCellFormula(model, "A7"), `=PIVOT.HEADER("1","foo","12","product","41")`);
        assert.equal(getCellFormula(model, "A8"), `=PIVOT.HEADER("1","foo","12","product","false")`);
        model.dispatch("SET_PIVOT_FILTER_VALUE", {
            id: "42",
            value: [17],
        });
        await nextTick();

        // It only fetch names for defined records
        assert.verifySteps([
            "name_get_product_41",
        ]);
    });

    test("Open pivot dialog and insert a value, with UNDO/REDO", async function (assert) {
        assert.expect(4);

        const { model, env } = await createSpreadsheetFromPivot({
            pivotView: {
                model: "partner",
                data: this.data,
                arch: this.arch,
            },
        });
        model.dispatch("SELECT_CELL", { col: 3, row: 7 });
        const sheetId = model.getters.getActiveSheetId();
        const root = cellMenuRegistry.getAll().find((item) => item.id === "insert_pivot_cell");
        const insertValue = cellMenuRegistry.getChildren(root, env)[0];
        await insertValue.action(env);
        await nextTick();
        assert.containsOnce(document.body, ".o_pivot_table_dialog");
        await dom.click(document.body.querySelectorAll(".o_pivot_table_dialog tr th")[1]);
        assert.equal(getCellFormula(model, "D8"), getCellFormula(model, "B1"));
        model.dispatch("REQUEST_UNDO");
        assert.equal(model.getters.getCell(sheetId, 3, 7), undefined);
        model.dispatch("REQUEST_REDO");
        assert.equal(getCellFormula(model, "D8"), getCellFormula(model, "B1"));
    });

    test("Insert missing value modal can show only the values not used in the current sheet", async function (assert) {
        assert.expect(4);

        const { model, env } = await createSpreadsheetFromPivot({
            pivotView: {
                model: "partner",
                data: this.data,
                arch: this.arch,
            },
        });
        const missingValue = getCellFormula(model, "B3");
        model.dispatch("SELECT_CELL", { col: 1, row: 2 });
        model.dispatch("DELETE_CONTENT", { sheetId: model.getters.getActiveSheetId(), target: model.getters.getSelectedZones() });
        model.dispatch("SELECT_CELL", { col: 3, row: 7 });
        const root = cellMenuRegistry.getAll().find((item) => item.id === "insert_pivot_cell");
        const insertValue = cellMenuRegistry.getChildren(root, env)[0];
        await insertValue.action(env);
        await nextTick();
        assert.containsOnce(document.body, ".o_missing_value");
        await dom.click(document.body.querySelector("input#missing_values"));
        await nextTick();
        assert.containsOnce(document.body, ".o_missing_value");
        assert.containsN(document.body, ".o_pivot_table_dialog th", 4);
        await dom.click(document.body.querySelector(".o_missing_value"));
        assert.equal(getCellFormula(model, "D8"), missingValue);
    });

    test("Insert missing pivot value with two level of grouping", async function (assert) {
        assert.expect(4);

        const { model, env } = await createSpreadsheetFromPivot({
            pivotView: {
                model: "partner",
                data: this.data,
                arch: `
                <pivot string="Partners">
                    <field name="foo" type="col"/>
                    <field name="bar" type="row"/>
                    <field name="product" type="row"/>
                    <field name="probability" type="measure"/>
                </pivot>`,
            },
        });
        model.dispatch("SELECT_CELL", { col: 1, row: 4 });
        model.dispatch("DELETE_CONTENT", { sheetId: model.getters.getActiveSheetId(), target: model.getters.getSelectedZones() });
        model.dispatch("SELECT_CELL", { col: 3, row: 7 });
        const root = cellMenuRegistry.getAll().find((item) => item.id === "insert_pivot_cell");
        const insertValue = cellMenuRegistry.getChildren(root, env)[0];
        await insertValue.action(env);
        await nextTick();
        assert.containsOnce(document.body, ".o_missing_value");
        await dom.click(document.body.querySelector("input#missing_values"));
        await nextTick();
        assert.containsOnce(document.body, ".o_missing_value");
        assert.containsN(document.body, ".o_pivot_table_dialog td", 2);
        assert.containsN(document.body, ".o_pivot_table_dialog th", 5);
    });

    test("Insert missing value modal can show only the values not used in the current sheet with multiple levels", async function (assert) {
        assert.expect(4);

        const { model, env } = await createSpreadsheetFromPivot({
            pivotView: {
                model: "partner",
                data: this.data,
                arch: `
                    <pivot string="Partners">
                        <field name="foo" type="col"/>
                        <field name="product" type="col"/>
                        <field name="bar" type="row"/>
                        <field name="probability" type="measure"/>
                    </pivot>`,
            },
        });
        const missingValue = getCellFormula(model, "C4");
        model.dispatch("SELECT_CELL", { col: 2, row: 3 });
        model.dispatch("DELETE_CONTENT", { sheetId: model.getters.getActiveSheetId(), target: model.getters.getSelectedZones() });
        model.dispatch("SELECT_CELL", { col: 9, row: 9 });
        const root = cellMenuRegistry.getAll().find((item) => item.id === "insert_pivot_cell");
        const insertValue = cellMenuRegistry.getChildren(root, env)[0];
        await insertValue.action(env);
        await nextTick();
        assert.containsOnce(document.body, ".o_missing_value");
        await dom.click(document.body.querySelector("input#missing_values"));
        await nextTick();
        assert.containsOnce(document.body, ".o_missing_value");
        assert.containsN(document.body, ".o_pivot_table_dialog th", 5);
        await dom.click(document.body.querySelector(".o_missing_value"));
        assert.equal(getCellFormula(model, "J10"), missingValue);
    });

    test("Insert missing pivot value give the focus to the canvas when model is closed", async function (assert) {
        assert.expect(2);

        const { model, env } = await createSpreadsheetFromPivot({
            pivotView: {
                model: "partner",
                data: this.data,
                arch: `
                <pivot string="Partners">
                    <field name="foo" type="col"/>
                    <field name="bar" type="row"/>
                    <field name="product" type="row"/>
                    <field name="probability" type="measure"/>
                </pivot>`,
            },
        });
        model.dispatch("SELECT_CELL", { col: 3, row: 7 });
        const root = cellMenuRegistry.getAll().find((item) => item.id === "insert_pivot_cell");
        const insertValue = cellMenuRegistry.getChildren(root, env)[0];
        await insertValue.action(env);
        await nextTick();
        assert.containsOnce(document.body, ".o_pivot_table_dialog");
        await dom.click(document.body.querySelectorAll(".o_pivot_table_dialog tr th")[1]);
        assert.equal(document.activeElement.tagName, "CANVAS");
    });

    test("One col header as missing value should be displayed", async function (assert) {
        assert.expect(1);

        const { model, env } = await createSpreadsheetFromPivot({
            pivotView: {
                model: "partner",
                data: this.data,
                arch: `
                <pivot string="Partners">
                    <field name="foo" type="col"/>
                    <field name="bar" type="row"/>
                    <field name="product" type="row"/>
                    <field name="probability" type="measure"/>
                </pivot>`,
            },
        });
        model.dispatch("SELECT_CELL", { col: 1, row: 0 });
        model.dispatch("DELETE_CONTENT", { sheetId: model.getters.getActiveSheetId(), target: model.getters.getSelectedZones() });
        const root = cellMenuRegistry.getAll().find((item) => item.id === "insert_pivot_cell");
        const insertValue = cellMenuRegistry.getChildren(root, env)[0];
        await insertValue.action(env);
        await nextTick();
        await dom.click(document.body.querySelector("input#missing_values"));
        await nextTick();
        assert.containsOnce(document.body, ".o_missing_value");
    });

    test("One row header as missing value should be displayed", async function (assert) {
        assert.expect(1);

        const { model, env } = await createSpreadsheetFromPivot({
            pivotView: {
                model: "partner",
                data: this.data,
                arch: `
                <pivot string="Partners">
                    <field name="foo" type="col"/>
                    <field name="bar" type="row"/>
                    <field name="product" type="row"/>
                    <field name="probability" type="measure"/>
                </pivot>`,
            },
        });
        model.dispatch("SELECT_CELL", { col: 0, row: 2 });
        model.dispatch("DELETE_CONTENT", { sheetId: model.getters.getActiveSheetId(), target: model.getters.getSelectedZones() });
        const root = cellMenuRegistry.getAll().find((item) => item.id === "insert_pivot_cell");
        const insertValue = cellMenuRegistry.getChildren(root, env)[0];
        await insertValue.action(env);
        await nextTick();
        await dom.click(document.body.querySelector("input#missing_values"));
        await nextTick();
        assert.containsOnce(document.body, ".o_missing_value");
    });

    test("A missing col in the total measures with a pivot of two GB of cols", async function (assert) {
        assert.expect(2);

        const { model, env } = await createSpreadsheetFromPivot({
            pivotView: {
                model: "partner",
                data: this.data,
                arch: `
                <pivot string="Partners">
                    <field name="bar" type="col"/>
                    <field name="product" type="col"/>
                    <field name="probability" type="measure"/>
                    <field name="foo" type="measure"/>
                </pivot>`,
            },
        });
        await nextTick();
        await nextTick();
        model.dispatch("SELECT_CELL", { col: 5, row: 3 });
        model.dispatch("DELETE_CONTENT", { sheetId: model.getters.getActiveSheetId(), target: model.getters.getSelectedZones() });
        const root = cellMenuRegistry.getAll().find((item) => item.id === "insert_pivot_cell");
        const insertValue = cellMenuRegistry.getChildren(root, env)[0];
        await insertValue.action(env);
        await nextTick();
        await dom.click(document.body.querySelector("input#missing_values"));
        await nextTick();
        assert.containsOnce(document.body, ".o_missing_value");
        assert.containsN(document.body, ".o_pivot_table_dialog th", 4);
    });
});
