/** @odoo-module */

import spreadsheet from "@spreadsheet/o_spreadsheet/o_spreadsheet_extended";
import { createView, dom } from "web.test_utils";
import { insertList } from "@documents_spreadsheet/bundle/list/list_init_callback";
import ListView from "@web/legacy/js/views/list/list_view";
import { selectCell, setCellContent } from "@spreadsheet/../tests/utils/commands";
import { getCell, getCellFormula } from "@spreadsheet/../tests/utils/getters";
import { createSpreadsheetFromListView } from "../utils/list_helpers";
import {
    getBasicData,
    getBasicListArch,
    getBasicServerData,
} from "@spreadsheet/../tests/utils/data";
import { nextTick, getFixture, click } from "@web/../tests/helpers/utils";

const { topbarMenuRegistry, cellMenuRegistry } = spreadsheet.registries;
const { toZone } = spreadsheet.helpers;

QUnit.module("document_spreadsheet > list view", {}, () => {
    QUnit.test("List export with a invisible field", async (assert) => {
        const { model } = await createSpreadsheetFromListView({
            serverData: {
                models: getBasicData(),
                views: {
                    "partner,false,list": `
                        <tree string="Partners">
                            <field name="foo" invisible="1"/>
                            <field name="bar"/>
                        </tree>`,
                    "partner,false,search": "<search/>",
                },
            },
        });
        assert.deepEqual(model.getters.getListDefinition("1").columns, ["bar"]);
    });

    QUnit.test("List export with a widget handle", async (assert) => {
        const { model } = await createSpreadsheetFromListView({
            serverData: {
                models: getBasicData(),
                views: {
                    "partner,false,list": `
                            <tree string="Partners">
                                <field name="foo" widget="handle"/>
                                <field name="bar"/>
                            </tree>`,
                    "partner,false,search": "<search/>",
                },
            },
        });
        assert.deepEqual(model.getters.getListDefinition("1").columns, ["bar"]);
    });

    QUnit.test("Open list properties properties", async function (assert) {
        const { model, env } = await createSpreadsheetFromListView();

        const dataRoot = topbarMenuRegistry.getAll().find((item) => item.id === "data");
        const children = topbarMenuRegistry.getChildren(dataRoot, env);
        const openProperties = children.find((item) => item.id === "item_list_1");
        openProperties.action(env);
        await nextTick();
        const target = getFixture();
        let title = $(target).find(".o-sidePanelTitle")[0].innerText;
        assert.equal(title, "List properties");

        const sections = $(target).find(".o_side_panel_section");
        assert.equal(sections.length, 4, "it should have 4 sections");
        const [pivotName, pivotModel, domain] = sections;

        assert.equal(pivotName.children[0].innerText, "List Name");
        assert.equal(pivotName.children[1].innerText, "(#1) Partners");

        assert.equal(pivotModel.children[0].innerText, "Model");
        assert.equal(pivotModel.children[1].innerText, "Partner (partner)");

        assert.equal(domain.children[0].innerText, "Domain");
        assert.equal(domain.children[1].innerText, "Match all records");

        // opening from a non pivot cell
        model.dispatch("SELECT_ODOO_LIST", {});
        env.openSidePanel("LIST_PROPERTIES_PANEL", {
            listId: undefined,
        });
        await nextTick();
        title = $(target).find(".o-sidePanelTitle")[0].innerText;
        assert.equal(title, "List properties");

        assert.containsOnce(target, ".o_side_panel_select");
    });

    QUnit.test("Add list in an existing spreadsheet", async (assert) => {
        const listView = await createView({
            View: ListView,
            model: "partner",
            data: getBasicData(),
            arch: getBasicListArch(),
            session: { user_has_group: async () => true },
        });
        const { list, fields } = listView._getListForSpreadsheet();
        listView.destroy();
        const { model } = await createSpreadsheetFromListView();
        const callback = insertList.bind({ isEmptySpreadsheet: false })({
            list: list,
            threshold: 10,
            fields: fields,
        });
        model.dispatch("CREATE_SHEET", { sheetId: "42", position: 1 });
        const activeSheetId = model.getters.getActiveSheetId();
        assert.deepEqual(model.getters.getSheetIds(), [activeSheetId, "42"]);
        await callback(model);
        assert.strictEqual(model.getters.getSheetIds().length, 3);
        assert.deepEqual(model.getters.getSheetIds()[0], activeSheetId);
        assert.deepEqual(model.getters.getSheetIds()[1], "42");
    });

    QUnit.test("Verify absence of pivot properties on non-pivot cell", async function (assert) {
        const { model, env } = await createSpreadsheetFromListView();
        selectCell(model, "Z26");
        const root = cellMenuRegistry.getAll().find((item) => item.id === "listing_properties");
        assert.notOk(root.isVisible(env));
    });

    QUnit.test("Re-insert a list correctly ask for lines number", async function (assert) {
        const { model, env } = await createSpreadsheetFromListView();
        selectCell(model, "Z26");
        const root = cellMenuRegistry.getAll().find((item) => item.id === "reinsert_list");
        const reinsertList = cellMenuRegistry.getChildren(root, env)[0];
        await reinsertList.action(env);
        await nextTick();
        /** @type {HTMLInputElement} */
        const input = document.body.querySelector(".modal-body input");
        assert.ok(input);
        assert.strictEqual(input.type, "number");
    });

    QUnit.test("user related context is not saved in the spreadsheet", async function (assert) {
        const context = {
            allowed_company_ids: [15],
            default_stage_id: 5,
            search_default_stage_id: 5,
            tz: "bx",
            lang: "FR",
            uid: 4,
        };
        const controller = await createView({
            View: ListView,
            arch: `
                    <tree string="Partners">
                        <field name="bar"/>
                        <field name="product_id"/>
                    </tree>
                `,
            data: getBasicData(),
            model: "partner",
            context,
        });
        const { list } = controller._getListForSpreadsheet();
        assert.deepEqual(
            list.context,
            {
                default_stage_id: 5,
                search_default_stage_id: 5,
            },
            "user related context is not stored in context"
        );
        controller.destroy();
    });

    QUnit.test("Can see record of a list", async function (assert) {
        const { webClient, model } = await createSpreadsheetFromListView();
        const listId = model.getters.getListIds()[0];
        const listModel = model.getters.getSpreadsheetListModel(listId);
        const env = {
            ...webClient.env,
            model,
            services: {
                ...model.config.evalContext.env.services,
                action: {
                    doAction: (params) => {
                        assert.step(params.res_model);
                        assert.step(params.res_id.toString());
                    },
                },
            },
        };
        selectCell(model, "A2");
        const root = cellMenuRegistry.getAll().find((item) => item.id === "list_see_record");
        await root.action(env);
        assert.verifySteps(["partner", listModel.getIdFromPosition(0).toString()]);

        selectCell(model, "A3");
        await root.action(env);
        assert.verifySteps(["partner", listModel.getIdFromPosition(1).toString()]);

        // From a cell inside a merge
        model.dispatch("ADD_MERGE", {
            sheetId: model.getters.getActiveSheetId(),
            target: [toZone("A3:B3")],
            force: true, // there are data in B3
        });
        selectCell(model, "B3");
        await root.action(env);
        assert.verifySteps(["partner", listModel.getIdFromPosition(1).toString()]);
    });

    QUnit.test(
        "See record of list is only displayed on list formula with only one list formula",
        async function (assert) {
            const { webClient, model } = await createSpreadsheetFromListView();
            const env = {
                ...webClient.env,
                model,
                services: model.config.evalContext.env.services,
            };
            setCellContent(model, "A1", "test");
            setCellContent(model, "A2", `=ODOO.LIST("1","1","foo")`);
            setCellContent(model, "A3", `=ODOO.LIST("1","1","foo")+LIST("1","1","foo")`);
            const root = cellMenuRegistry.getAll().find((item) => item.id === "list_see_record");

            selectCell(model, "A1");
            assert.strictEqual(root.isVisible(env), false);
            selectCell(model, "A2");
            assert.strictEqual(root.isVisible(env), true);
            selectCell(model, "A3");
            assert.strictEqual(root.isVisible(env), false);
        }
    );

    QUnit.test("See records is visible even if the formula is lowercase", async function (assert) {
        const { env, model } = await createSpreadsheetFromListView();
        selectCell(model, "B2");
        const root = cellMenuRegistry.getAll().find((item) => item.id === "list_see_record");
        assert.ok(root.isVisible(env));
        setCellContent(model, "B2", getCellFormula(model, "B2").replace("ODOO.LIST", "odoo.list"));
        assert.ok(root.isVisible(env));
    });

    QUnit.test("See records is not visible if the formula is in error", async function (assert) {
        const { env, model } = await createSpreadsheetFromListView();
        selectCell(model, "B2");
        const root = cellMenuRegistry.getAll().find((item) => item.id === "list_see_record");
        assert.ok(root.isVisible(env));
        setCellContent(
            model,
            "B2",
            getCellFormula(model, "B2").replace(`ODOO.LIST(1`, `ODOO.LIST("5)`)
        ); //Invalid id
        assert.ok(getCell(model, "B2").evaluated.error.message);
        assert.notOk(root.isVisible(env));
    });

    QUnit.test("Update the list title from the side panel", async function (assert) {
        assert.expect(1);

        const { model, env } = await createSpreadsheetFromListView();
        // opening from a pivot cell
        const sheetId = model.getters.getActiveSheetId();
        const listA3 = model.getters.getListIdFromPosition(sheetId, 0, 2);
        model.dispatch("SELECT_ODOO_LIST", { listId: listA3 });
        env.openSidePanel("LIST_PROPERTIES_PANEL", {
            listId: listA3,
        });
        await nextTick();
        await click(document.body.querySelector(".o_sp_en_rename"));
        document.body.querySelector(".o_sp_en_name").value = "new name";
        await dom.triggerEvent(document.body.querySelector(".o_sp_en_name"), "input");
        await click(document.body.querySelector(".o_sp_en_save"));
        assert.equal(model.getters.getListName(listA3), "new name");
    });

    QUnit.test(
        "Inserting a list preserves the ascending sorting from the list",
        async function (assert) {
            const serverData = getBasicServerData();
            serverData.models.partner.fields.foo.sortable = true;
            const { model } = await createSpreadsheetFromListView({
                serverData,
                orderBy: [{ name: "foo", asc: true }],
                linesNumber: 4,
            });
            assert.ok(getCell(model, "A2").evaluated.value <= getCell(model, "A3").evaluated.value);
            assert.ok(getCell(model, "A3").evaluated.value <= getCell(model, "A4").evaluated.value);
            assert.ok(getCell(model, "A4").evaluated.value <= getCell(model, "A5").evaluated.value);
        }
    );

    QUnit.test(
        "Inserting a list preserves the descending sorting from the list",
        async function (assert) {
            const serverData = getBasicServerData();
            serverData.models.partner.fields.foo.sortable = true;
            const { model } = await createSpreadsheetFromListView({
                serverData,
                orderBy: [{ name: "foo", asc: false }],
                linesNumber: 4,
            });
            assert.ok(getCell(model, "A2").evaluated.value >= getCell(model, "A3").evaluated.value);
            assert.ok(getCell(model, "A3").evaluated.value >= getCell(model, "A4").evaluated.value);
            assert.ok(getCell(model, "A4").evaluated.value >= getCell(model, "A5").evaluated.value);
        }
    );
});
