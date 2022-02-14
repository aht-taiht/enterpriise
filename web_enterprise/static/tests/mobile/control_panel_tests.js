/** @odoo-module **/

import { click, getFixture, triggerEvent } from "@web/../tests/helpers/utils";
import { ControlPanel } from "@web/search/control_panel/control_panel";
import { editSearch, makeWithSearch, setupControlPanelServiceRegistry } from "@web/../tests/search/helpers";
import { registry } from "@web/core/registry";
import { uiService } from "@web/core/ui/ui_service";

let serverData;
let target;

QUnit.module("Search", (hooks) => {
    hooks.beforeEach(async () => {
        setupControlPanelServiceRegistry();
        target = getFixture();
        registry.category("services").add("ui", uiService);

        serverData = {
            models: {
                foo: {
                    fields: {
                        birthday: { string: "Birthday", type: "date", store: true, sortable: true },
                        date_field: { string: "Date", type: "date", store: true, sortable: true },
                    },
                    records: [{ date_field: "2022-02-14" }],
                },
            },
            views: {
                "foo,false,search": `
                    <search>
                        <filter name="birthday" date="birthday"/>
                        <filter name="date_field" date="date_field"/>
                    </search>
                `,
            },
        };
    });

    QUnit.module("Control Panel (mobile)");

    QUnit.test("Display control panel mobile", async (assert) => {
        await makeWithSearch({
            serverData,
            resModel: "foo",
            Component: ControlPanel,
            searchMenuTypes: ["filter"],
            searchViewId: false,
        });

        assert.containsOnce(target, ".breadcrumb");
        assert.containsOnce(target, ".o_enable_searchview");
        assert.containsNone(target, ".o_searchview");
        assert.containsNone(target, ".o_toggle_searchview_full");

        await click(target, ".o_enable_searchview");

        assert.containsNone(target, ".breadcrumb");
        assert.containsOnce(target, ".o_enable_searchview");
        assert.containsOnce(target, ".o_searchview");
        assert.containsOnce(target, ".o_toggle_searchview_full");

        await click(target, ".o_toggle_searchview_full");

        assert.containsOnce(document.body, ".o_searchview.o_mobile_search");
        assert.containsN(document.body, ".o_mobile_search .o_mobile_search_button", 2);
        assert.strictEqual(
            document.body.querySelector(".o_mobile_search_header").textContent.trim(),
            "FILTER CLEAR"
        );
        assert.containsOnce(document.body, ".o_searchview.o_mobile_search .o_cp_searchview");
        assert.containsOnce(document.body, ".o_searchview.o_mobile_search .o_mobile_search_footer");

        await click(document.body.querySelector(".o_mobile_search_button"));

        assert.containsNone(target, ".breadcrumb");
        assert.containsOnce(target, ".o_enable_searchview");
        assert.containsOnce(target, ".o_searchview");
        assert.containsOnce(target, ".o_toggle_searchview_full");

        await click(target, ".o_enable_searchview");

        assert.containsOnce(target, ".breadcrumb");
        assert.containsOnce(target, ".o_enable_searchview");
        assert.containsNone(target, ".o_searchview");
        assert.containsNone(target, ".o_toggle_searchview_full");
    });

    QUnit.test("Make a simple search in mobile mode", async (assert) => {
        await makeWithSearch({
            serverData,
            resModel: "foo",
            Component: ControlPanel,
            searchMenuTypes: ["filter"],
            searchViewFields: {
                birthday: { string: "Birthday", type: "date", store: true, sortable: true },
            },
            searchViewArch: `
                <search>
                    <field name="birthday"/>
                </search>
            `,
        });
        assert.containsNone(target, ".o_searchview");

        await click(target, ".o_enable_searchview");
        assert.containsOnce(target, ".o_searchview");
        const input = target.querySelector(".o_searchview input");
        assert.containsNone(target, ".o_searchview_autocomplete");

        await editSearch(target, "2022-02-14");
        assert.strictEqual(input.value, "2022-02-14", "input value should be updated");
        assert.containsOnce(target, ".o_searchview_autocomplete");

        await triggerEvent(input, null, "keydown", { key: "Escape" });
        assert.containsNone(target, ".o_searchview_autocomplete");

        await click(target, ".o_enable_searchview");
        assert.containsNone(target, ".o_searchview");
    });
});
