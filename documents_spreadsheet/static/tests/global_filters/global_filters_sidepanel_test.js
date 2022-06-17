/** @odoo-module */
import testUtils from "web.test_utils";

import { getBasicData, getBasicPivotArch, getBasicServerData } from "@spreadsheet/../tests/utils/data";
import { click, getFixture, nextTick } from "@web/../tests/helpers/utils";
import { createSpreadsheet } from "../spreadsheet_test_utils";
import { createSpreadsheetFromPivotView } from "../utils/pivot_helpers";
import { makeFakeNotificationService } from "@web/../tests/helpers/mock_services";
import { registry } from "@web/core/registry";
import { addGlobalFilter } from "@spreadsheet/../tests/utils/commands";
import { insertPivotInSpreadsheet } from "@spreadsheet/../tests/utils/pivot";
import { insertListInSpreadsheet } from "@spreadsheet/../tests/utils/list";

let target;

const THIS_YEAR_FILTER = {
    filter: {
        type: "date",
        label: "This Year",
        rangeType: "year",
        defaultValue: { yearOffset: 0 },
        pivotFields: { 1: { field: "date", type: "date" } },
        // duplicate key to support its introduction as data, not just dispatch
        fields: { 1: { field: "date", type: "date" } },
        listFields: { 1: { field: "date", type: "date" } },
    },
};

async function selectYear(yearString) {
    const input = target.querySelector("input.o_datepicker_input.o_input.datetimepicker-input");
    // open the YearPicker
    await click(input);
    // Change input value
    await testUtils.fields.editInput(input, yearString);
    // trigger dateChange on YearPicker
    await click(input);
}

QUnit.module(
    "documents_spreadsheet > global_filters side panel",
    {
        beforeEach: function () {
            target = getFixture();
        },
    },
    () => {
        QUnit.test("Simple display", async function (assert) {
            assert.expect(6);

            await createSpreadsheetFromPivotView();
            assert.notOk($(target).find(".o_spreadsheet_global_filters_side_panel")[0]);
            const searchIcon = $(target).find(".o_topbar_filter_icon")[0];
            await testUtils.dom.click(searchIcon);
            assert.ok($(target).find(".o_spreadsheet_global_filters_side_panel")[0]);
            const items = $(target).find(
                ".o_spreadsheet_global_filters_side_panel .o-sidePanelButton"
            );
            assert.equal(items.length, 3);
            assert.ok(items[0].classList.contains("o_global_filter_new_time"));
            assert.ok(items[1].classList.contains("o_global_filter_new_relation"));
            assert.ok(items[2].classList.contains("o_global_filter_new_text"));
        });

        QUnit.test("Display with an existing 'Date' global filter", async function (assert) {
            assert.expect(4);

            const { model } = await createSpreadsheetFromPivotView();
            const label = "This year";
            await addGlobalFilter(model, {
                filter: { id: "42", type: "date", rangeType:"year", label, pivotFields: {}, defaultValue: {} },
            });
            const searchIcon = $(target).find(".o_topbar_filter_icon")[0];
            await testUtils.dom.click(searchIcon);
            const items = $(target).find(
                ".o_spreadsheet_global_filters_side_panel .o_side_panel_section"
            );
            assert.equal(items.length, 2);
            const labelElement = items[0].querySelector(".o_side_panel_filter_label");
            assert.equal(labelElement.innerText, label);
            await testUtils.dom.click(items[0].querySelector(".o_side_panel_filter_icon.fa-cog"));
            assert.ok($(target).find(".o_spreadsheet_filter_editor_side_panel"));
            assert.equal($(target).find(".o_global_filter_label")[0].value, label);
        });

        QUnit.test("Create a new global filter", async function (assert) {
            assert.expect(4);

            const { model } = await createSpreadsheetFromPivotView();
            const searchIcon = $(target).find(".o_topbar_filter_icon")[0];
            await testUtils.dom.click(searchIcon);
            const newText = $(target).find(".o_global_filter_new_text")[0];
            await testUtils.dom.click(newText);
            assert.equal($(target).find(".o-sidePanel").length, 1);
            const input = $(target).find(".o_global_filter_label")[0];
            await testUtils.fields.editInput(input, "My Label");
            const value = $(target).find(".o_global_filter_default_value")[0];
            await testUtils.fields.editInput(value, "Default Value");
            // Can't make it work with the DOM API :(
            // await testUtils.dom.triggerEvent($(target).find(".o_field_selector_value"), "focusin");
            $($(target).find(".o_field_selector_value")).focusin();
            await testUtils.dom.click($(target).find(".o_field_selector_select_button")[0]);
            const save = $(target).find(
                ".o_spreadsheet_filter_editor_side_panel .o_global_filter_save"
            )[0];
            await testUtils.dom.click(save);
            assert.equal($(target).find(".o_spreadsheet_global_filters_side_panel").length, 1);
            const globalFilter = model.getters.getGlobalFilters()[0];
            assert.equal(globalFilter.label, "My Label");
            assert.equal(globalFilter.defaultValue, "Default Value");
        });

        QUnit.test("Create a new relational global filter", async function (assert) {
            assert.expect(4);

            const { model } = await createSpreadsheetFromPivotView({
                serverData: {
                    models: getBasicData(),
                    views: {
                        "partner,false,pivot": `
                            <pivot string="Partners">
                                <field name="foo" type="col"/>
                                <field name="product_id" type="row"/>
                                <field name="probability" type="measure"/>
                            </pivot>`,
                        "partner,false,search": `<search/>`,
                    },
                },
            });
            const searchIcon = $(target).find(".o_topbar_filter_icon")[0];
            await testUtils.dom.click(searchIcon);
            const newRelation = $(target).find(".o_global_filter_new_relation")[0];
            await testUtils.dom.click(newRelation);
            let selector = `.o_field_many2one[name="ir.model"] input`;
            await testUtils.dom.click($(target).find(selector)[0]);
            let $dropdown = $(selector).autocomplete("widget");
            let $target = $dropdown.find(`li:contains(Product)`).first();
            await testUtils.dom.click($target);

            let save = $(target).find(
                ".o_spreadsheet_filter_editor_side_panel .o_global_filter_save"
            )[0];
            await testUtils.dom.click(save);
            assert.equal($(target).find(".o_spreadsheet_global_filters_side_panel").length, 1);
            let globalFilter = model.getters.getGlobalFilters()[0];
            assert.equal(globalFilter.label, "Product");
            assert.deepEqual(globalFilter.defaultValue, []);
            assert.deepEqual(globalFilter.pivotFields[1], {
                field: "product_id",
                type: "many2one",
            });
        });

        QUnit.test(
            "Prevent selection of a Field Matching before the Related model",
            async function (assert) {
                assert.expect(2);
                await createSpreadsheetFromPivotView({
                    serverData: {
                        models: getBasicData(),
                        views: {
                            "partner,false,pivot": `
                                <pivot string="Partners">
                                    <field name="foo" type="col"/>
                                    <field name="product_id" type="row"/>
                                    <field name="probability" type="measure"/>
                                </pivot>`,
                            "partner,false,search": `<search/>`,
                        },
                    },
                    mockRPC: async function (route, args) {
                        if (args.method === "search_read" && args.model === "ir.model") {
                            return [{ name: "Product", model: "product" }];
                        }
                    },
                });
                await testUtils.dom.click(".o_topbar_filter_icon");
                await testUtils.dom.click(".o_global_filter_new_relation");
                let relatedModelSelector = `.o_field_many2one[name="ir.model"] input`;
                let fieldMatchingSelector = `.o_pivot_field_matching`;
                assert.containsNone(target, fieldMatchingSelector);
                await testUtils.dom.click(target.querySelector(relatedModelSelector));
                let $dropdown = $(relatedModelSelector).autocomplete("widget");
                let $target = $dropdown.find(`li:contains(Product)`).first();
                await testUtils.dom.click($target);
                assert.containsOnce(target, fieldMatchingSelector);
            }
        );

        QUnit.test("Display with an existing 'Relation' global filter", async function (assert) {
            assert.expect(8);

            const { model } = await createSpreadsheetFromPivotView();
            await insertPivotInSpreadsheet(model, { arch: getBasicPivotArch() });
            const label = "MyFoo";
            const filter = {
                id: "42",
                type: "relation",
                modelName: "product",
                label,
                pivotFields: {
                    1: { type: "many2one", field: "product_id" }, // first pivotId
                    2: { type: "many2one", field: "product_id" }, // second pivotId
                },
                defaultValue: [],
            };
            await addGlobalFilter(model, { filter });
            const searchIcon = target.querySelector(".o_topbar_filter_icon");
            await testUtils.dom.click(searchIcon);
            const items = target.querySelectorAll(
                ".o_spreadsheet_global_filters_side_panel .o_side_panel_section"
            );
            assert.equal(items.length, 2);
            const labelElement = items[0].querySelector(".o_side_panel_filter_label");
            assert.equal(labelElement.innerText, label);
            await testUtils.dom.click(items[0].querySelector(".o_side_panel_filter_icon.fa-cog"));
            assert.ok(target.querySelectorAll(".o_spreadsheet_filter_editor_side_panel"));
            assert.equal(target.querySelector(".o_global_filter_label").value, label);
            assert.equal(
                target.querySelector(`.o_field_many2one[name="ir.model"] input`).value,
                "Product"
            );
            const fieldsMatchingElements = target.querySelectorAll(
                "span.o_field_selector_chain_part"
            );
            assert.equal(fieldsMatchingElements.length, 2);
            assert.equal(fieldsMatchingElements[0].innerText, "Product");
            assert.equal(fieldsMatchingElements[1].innerText, "Product");
        });

        QUnit.test("Only related models can be selected", async function (assert) {
            assert.expect(2);
            const data = getBasicData();
            data["ir.model"].records.push(
                {
                    id: 36,
                    name: "Apple",
                    model: "apple",
                },
                {
                    id: 35,
                    name: "Document",
                    model: "documents.document",
                }
            );
            data["partner"].fields.document = {
                relation: "documents.document",
                string: "Document",
                type: "many2one",
            };
            await createSpreadsheetFromPivotView({
                serverData: {
                    models: data,
                    views: {
                        "partner,false,pivot": `
                            <pivot string="Partners">
                                <field name="foo" type="col"/>
                                <field name="product_id" type="row"/>
                                <field name="probability" type="measure"/>
                            </pivot>`,
                        "partner,false,search": `<search/>`,
                    },
                },
            });
            const searchIcon = $(target).find(".o_topbar_filter_icon")[0];
            await testUtils.dom.click(searchIcon);
            const newRelation = $(target).find(".o_global_filter_new_relation")[0];
            await testUtils.dom.click(newRelation);
            const selector = `.o_field_many2one[name="ir.model"] input`;
            await testUtils.dom.click($(target).find(selector)[0]);
            const $dropdown = $(selector).autocomplete("widget");
            const [model1, model2] = $dropdown.find(`li`);
            assert.equal(model1.innerText, "Product");
            assert.equal(model2.innerText, "Document");
        });

        QUnit.test("Edit an existing global filter", async function (assert) {
            assert.expect(4);

            const { model } = await createSpreadsheetFromPivotView();
            const label = "This year";
            const defaultValue = "value";
            await addGlobalFilter(model, {
                filter: { id: "42", type: "text", label, defaultValue, pivotFields: {} },
            });
            const searchIcon = $(target).find(".o_topbar_filter_icon")[0];
            await testUtils.dom.click(searchIcon);
            const editFilter = $(target).find(".o_side_panel_filter_icon.fa-cog");
            await testUtils.dom.click(editFilter);
            assert.equal($(target).find(".o-sidePanel").length, 1);
            const input = $(target).find(".o_global_filter_label")[0];
            assert.equal(input.value, label);
            const value = $(target).find(".o_global_filter_default_value")[0];
            assert.equal(value.value, defaultValue);
            await testUtils.fields.editInput(input, "New Label");
            $($(target).find(".o_field_selector_value")).focusin();
            await testUtils.dom.click($(target).find(".o_field_selector_select_button")[0]);
            const save = $(target).find(
                ".o_spreadsheet_filter_editor_side_panel .o_global_filter_save"
            )[0];
            await testUtils.dom.click(save);
            const globalFilter = model.getters.getGlobalFilters()[0];
            assert.equal(globalFilter.label, "New Label");
        });

        QUnit.test(
            "Trying to duplicate a filter label will trigger a toaster",
            async function (assert) {
                assert.expect(4);
                const mock = (message) => {
                    assert.step(`create (${message})`);
                    return () => {};
                };
                const uniqueFilterName = "UNIQUE_FILTER";
                registry
                    .category("services")
                    .add("notification", makeFakeNotificationService(mock), {
                        force: true,
                    });
                const { model } = await createSpreadsheetFromPivotView({
                    serverData: {
                        models: getBasicData(),
                        views: {
                            "partner,false,pivot": `
                            <pivot>
                                <field name="bar" type="col"/>
                                <field name="product_id" type="row"/>
                                <field name="probability" type="measure"/>
                            </pivot>`,
                            "partner,false,search": `<search/>`,
                        },
                    },
                });
                model.dispatch("ADD_GLOBAL_FILTER", {
                    filter: {
                        id: "42",
                        type: "relation",
                        label: uniqueFilterName,
                        modelName: "product",
                        pivotFields: {
                            1: {
                                field: "product",
                                type: "many2one",
                            },
                        },
                    },
                });
                const searchIcon = $(target).find(".o_topbar_filter_icon")[0];
                await testUtils.dom.click(searchIcon);
                const newText = $(target).find(".o_global_filter_new_text")[0];
                await testUtils.dom.click(newText);
                assert.equal($(target).find(".o-sidePanel").length, 1);
                const input = $(target).find(".o_global_filter_label")[0];
                await testUtils.fields.editInput(input, uniqueFilterName);
                const value = $(target).find(".o_global_filter_default_value")[0];
                await testUtils.fields.editInput(value, "Default Value");
                // Can't make it work with the DOM API :(
                // await testUtils.dom.triggerEvent($(target).find(".o_field_selector_value"), "focusin");
                $($(target).find(".o_field_selector_value")).focusin();
                await testUtils.dom.click($(target).find(".o_field_selector_select_button")[0]);
                const save = $(target).find(
                    ".o_spreadsheet_filter_editor_side_panel .o_global_filter_save"
                )[0];
                await testUtils.dom.click(save);
                assert.verifySteps([
                    "create (New spreadsheet created in Documents)",
                    "create (Duplicated Label)",
                ]);
            }
        );

        QUnit.test("Create a new relational global filter with a pivot", async function (assert) {
            const spreadsheetData = {
                pivots: {
                    1: {
                        id: 1,
                        colGroupBys: ["foo"],
                        domain: [],
                        measures: [{ field: "probability", operator: "avg" }],
                        model: "partner",
                        rowGroupBys: ["bar"],
                        context: {},
                    },
                },
            };
            const serverData = getBasicServerData();
            serverData.models["documents.document"].records.push({
                id: 45,
                raw: JSON.stringify(spreadsheetData),
                name: "Spreadsheet",
                handler: "spreadsheet",
            });
            const { model } = await createSpreadsheet({
                serverData,
                spreadsheetId: 45,
            });
            const searchIcon = target.querySelector(".o_topbar_filter_icon");
            await click(searchIcon);
            const newRelation = target.querySelector(".o_global_filter_new_relation");
            await click(newRelation);
            let selector = `.o_field_many2one[name="ir.model"] input`;
            await click(target.querySelector(selector));
            let $dropdown = $(selector).autocomplete("widget");
            let $target = $dropdown.find(`li:contains(Product)`).first();
            await click($target[0]);

            let save = target.querySelector(
                ".o_spreadsheet_filter_editor_side_panel .o_global_filter_save"
            );
            await click(save);
            assert.equal(
                target.querySelectorAll(".o_spreadsheet_global_filters_side_panel").length,
                1
            );
            let globalFilter = model.getters.getGlobalFilters()[0];
            assert.equal(globalFilter.label, "Product");
            assert.deepEqual(globalFilter.defaultValue, []);
            assert.deepEqual(globalFilter.pivotFields[1], {
                field: "product_id",
                type: "many2one",
            });
        });

        QUnit.test(
            "Create a new relational global filter with a list snapshot",
            async function (assert) {
                const spreadsheetData = {
                    lists: {
                        1: {
                            id: 1,
                            columns: ["foo", "contact_name"],
                            domain: [],
                            model: "partner",
                            orderBy: [],
                            context: {},
                        },
                    },
                };
                const serverData = getBasicServerData();
                serverData.models["documents.document"].records.push({
                    id: 45,
                    raw: JSON.stringify(spreadsheetData),
                    name: "Spreadsheet",
                    handler: "spreadsheet",
                });
                const { model } = await createSpreadsheet({
                    serverData,
                    spreadsheetId: 45,
                });
                const searchIcon = target.querySelector(".o_topbar_filter_icon");
                await click(searchIcon);
                const newRelation = target.querySelector(".o_global_filter_new_relation");
                await click(newRelation);
                let selector = `.o_field_many2one[name="ir.model"] input`;
                await click(target.querySelector(selector));
                let $dropdown = $(selector).autocomplete("widget");
                let $target = $dropdown.find(`li:contains(Product)`).first();
                await click($target[0]);

                let save = target.querySelector(
                    ".o_spreadsheet_filter_editor_side_panel .o_global_filter_save"
                );
                await click(save);
                assert.equal(
                    target.querySelectorAll(".o_spreadsheet_global_filters_side_panel").length,
                    1
                );
                let globalFilter = model.getters.getGlobalFilters()[0];
                assert.equal(globalFilter.label, "Product");
                assert.deepEqual(globalFilter.defaultValue, []);
                assert.deepEqual(globalFilter.listFields["1"], {
                    field: "product_id",
                    type: "many2one",
                });
            }
        );

        QUnit.test("Create a new date filter", async function (assert) {
            assert.expect(18);

            const { model } = await createSpreadsheetFromPivotView();
            insertListInSpreadsheet(model, {
                model: "partner",
                columns: ["foo", "bar", "date", "product_id"],
            });
            await nextTick();
            await click(target.querySelector(".o_topbar_filter_icon"));
            await click(target.querySelector(".o_global_filter_new_time"));
            assert.equal(target.querySelectorAll(".o-sidePanel").length, 1);

            const label = $(target).find(".o_global_filter_label")[0];
            await testUtils.fields.editInput(label, "My Label");

            const range = $(target).find(".o_input:nth-child(2)")[0];
            await testUtils.fields.editAndTrigger(range, "month", ["change"]);

            await click(target.querySelector(".date_filter_values .o_input"));

            assert.equal(target.querySelectorAll(".date_filter_values select.o_input").length, 1);
            const month = target.querySelector(".date_filter_values select.o_input");
            assert.equal(month.length, 13);
            const year = target.querySelector(".o_datepicker_input");
            assert.equal(year.value, '');

            // start with year as setting the month will set a default year if not defined
            await selectYear('2022');
            assert.equal(year.value, '2022');

            await testUtils.fields.editAndTrigger(month, "october", ["change"]);
            assert.equal(month.value, "october")

            // pivot
            $($(target).find(".o_field_selector_value")[0]).focusin();
            await click(target.querySelector(".o_field_selector_select_button[data-name='date']"));

            //list
            $($(target).find(".o_field_selector_value")[1]).focusin();
            await click(
                target.querySelector(
                    ".o_field_selector_popover:not(.d-none) .o_field_selector_select_button[data-name='date']"
                )
            );

            await click(
                target.querySelector(
                    ".o_spreadsheet_filter_editor_side_panel .o_global_filter_save"
                )
            );
            assert.equal(
                target.querySelectorAll(".o_spreadsheet_global_filters_side_panel").length,
                1
            );

            const globalFilter = model.getters.getGlobalFilters()[0];
            assert.equal(globalFilter.label, "My Label");
            assert.equal(globalFilter.defaultValue.yearOffset, 0);
            assert.equal(globalFilter.defaultValue.period, "october");
            assert.equal(globalFilter.rangeType, "month");
            assert.equal(globalFilter.type, "date");
            const currentYear = new Date().getFullYear();
            const computedPivotDomain = model.getters.getPivotComputedDomain("1");
            assert.deepEqual(computedPivotDomain[0], "&");
            assert.deepEqual(computedPivotDomain[1], ["date", ">=", currentYear + "-10-01"]);
            assert.deepEqual(computedPivotDomain[2], ["date", "<=", currentYear + "-10-31"]);
            const computedListDomain = model.getters.getListComputedDomain("1");
            assert.deepEqual(computedListDomain[0], "&");
            assert.deepEqual(computedListDomain[1], ["date", ">=", currentYear + "-10-01"]);
            assert.deepEqual(computedListDomain[2], ["date", "<=", currentYear + "-10-31"]);
        });

        QUnit.test("Create a new date filter without specifying the year", async function (assert) {
            assert.expect(9);
            const { model } = await createSpreadsheetFromPivotView({
                serverData: {
                    models: getBasicData(),
                    views: {
                        "partner,false,pivot": `
                            <pivot string="Partners">
                                <field name="date" interval="month" type="row"/>
                                <field name="id" type="col"/>
                                <field name="probability" type="measure"/>
                            </pivot>`,
                        "partner,false,search": `<search/>`,
                    },
                },
            });
            await nextTick();
            const searchIcon = $(target).find(".o_topbar_filter_icon")[0];
            await testUtils.dom.click(searchIcon);
            const newDate = $(target).find(".o_global_filter_new_time")[0];
            await testUtils.dom.click(newDate);
            assert.equal($(target).find(".o-sidePanel").length, 1);

            const label = $(target).find(".o_global_filter_label")[0];
            await testUtils.fields.editInput(label, "My Label");

            const range = $(target).find(".o_input:nth-child(2)")[0];
            await testUtils.fields.editAndTrigger(range, "month", ["change"]);

            const filterValues = $(target).find(".date_filter_values .o_input")[0];
            await testUtils.dom.click(filterValues);

            assert.equal($(target).find(".date_filter_values select.o_input").length, 1);
            const month = $(target).find(".date_filter_values select.o_input")[0];
            assert.equal(month.length, 13);
            const year = target.querySelector(".o_datepicker_input");
            assert.equal(year.text, undefined);

            await testUtils.fields.editAndTrigger(month, "november", ["change"]);
            // intentionally skip the year input

            $($(target).find(".o_field_selector_value")[0]).focusin();
            await testUtils.dom.click(
                $(target).find(".o_field_selector_select_button[data-name='date']")[0]
            );

            const save = $(target).find(
                ".o_spreadsheet_filter_editor_side_panel .o_global_filter_save"
            )[0];
            await testUtils.dom.click(save);

            const globalFilter = model.getters.getGlobalFilters()[0];
            assert.equal(globalFilter.label, "My Label");
            assert.equal(globalFilter.defaultValue.yearOffset, 0);
            assert.equal(globalFilter.defaultValue.period, "november");
            assert.equal(globalFilter.rangeType, "month");
            assert.equal(globalFilter.type, "date");
        });

        QUnit.test("Choose any year in a year picker", async function (assert) {
            const { model } = await createSpreadsheetFromPivotView();
            await addGlobalFilter(model, THIS_YEAR_FILTER);
    
            const searchIcon = target.querySelector(".o_topbar_filter_icon");
            await testUtils.dom.click(searchIcon);
            await nextTick();
    
            const pivots = target.querySelectorAll(".pivot_filter_section");
            assert.containsOnce(target, ".pivot_filter_section");
            assert.containsOnce(target, "i.o_side_panel_filter_icon.fa-cog");
            assert.containsOnce(target, "i.o_side_panel_filter_icon.fa-times");
            assert.equal(
                pivots[0].querySelector(".o_side_panel_filter_label").textContent,
                THIS_YEAR_FILTER.filter.label
            );
    
            assert.containsOnce(pivots[0], ".pivot_filter_input input.o_datepicker_input");
            const year = pivots[0].querySelector(
                ".pivot_filter_input input.o_datepicker_input"
            );
    
            const this_year = luxon.DateTime.local().year;
            assert.equal(year.value, String(this_year));
    
            await selectYear(String(this_year - 127));
            assert.equal(year.value, String(this_year - 127));
            assert.deepEqual(model.getters.getGlobalFilterValue(THIS_YEAR_FILTER.filter.id), {
                yearOffset: -127,
            });
    
            await selectYear(String(this_year + 32));
            assert.equal(year.value, String(this_year + 32));
            assert.deepEqual(model.getters.getGlobalFilterValue(THIS_YEAR_FILTER.filter.id), {
                yearOffset: 32,
            });
        });

        QUnit.test("Readonly user can update text filter values", async function (assert) {
            assert.expect(6);
            const { model } = await createSpreadsheetFromPivotView({
                serverData: {
                    models: getBasicData(),
                    views: {
                        "partner,false,pivot": `
                            <pivot string="Partners">
                                <field name="name" type="col"/>
                                <field name="date" interval="month" type="row"/>
                                <field name="probability" type="measure"/>
                            </pivot>`,
                        "partner,false,search": `<search/>`,
                    },
                },
            });
            await addGlobalFilter(model, {
                filter: {
                    id: "42",
                    type: "text",
                    label: "Text Filter",
                    defaultValue: "abc",
                    pivotFields: {},
                    listFields: {},
                },
            });
            model.updateMode("readonly");
            await nextTick();

            const searchIcon = target.querySelector(".o_topbar_filter_icon");
            await testUtils.dom.click(searchIcon);

            const pivots = target.querySelectorAll(".pivot_filter_section");
            assert.containsOnce(target, ".pivot_filter_section");
            assert.containsNone(target, "i.o_side_panel_filter_icon.fa-cog");
            assert.containsOnce(target, "i.o_side_panel_filter_icon.fa-times");
            assert.equal(
                pivots[0].querySelector(".o_side_panel_filter_label").textContent,
                "Text Filter"
            );

            const input = pivots[0].querySelector(".pivot_filter_input input");
            assert.equal(input.value, "abc");

            await testUtils.fields.editAndTrigger(input, "something", ["change"]);

            assert.equal(model.getters.getGlobalFilterValue("42"), "something");
        });

        QUnit.test("Readonly user can update date filter values", async function (assert) {
            assert.expect(11);
            const { model } = await createSpreadsheetFromPivotView({
                arch: `
                    <pivot string="Partners">
                        <field name="name" type="col"/>
                        <field name="date" interval="month" type="row"/>
                        <field name="probability" type="measure"/>
                    </pivot>
                `,
            });
            await addGlobalFilter(model, {
                filter: {
                    id: "43",
                    type: "date",
                    label: "Date Filter",
                    rangeType: "quarter",
                    defaultValue: { yearOffset: 0, period: "fourth_quarter" },
                    pivotFields: { 1: { field: "date", type: "date" } },
                    listFields: {},
                },
            });
            model.updateMode("readonly");
            await nextTick();

            const searchIcon = target.querySelector(".o_topbar_filter_icon");
            await testUtils.dom.click(searchIcon);
            await nextTick();

            const pivots = target.querySelectorAll(".pivot_filter_section");
            assert.containsOnce(target, ".pivot_filter_section");
            assert.containsNone(target, "i.o_side_panel_filter_icon.fa-cog");
            assert.containsOnce(target, "i.o_side_panel_filter_icon.fa-times");
            assert.equal(
                pivots[0].querySelector(".o_side_panel_filter_label").textContent,
                "Date Filter"
            );

            assert.containsOnce(pivots[0], ".pivot_filter_input div.date_filter_values select");
            const quarter = pivots[0].querySelector(
                ".pivot_filter_input div.date_filter_values select"
            );
            assert.containsOnce(pivots[0], ".pivot_filter_input input.o_datepicker_input");
            const year = pivots[0].querySelector(
                ".pivot_filter_input input.o_datepicker_input"
            );

            const this_year = luxon.DateTime.local().year;
            assert.equal(quarter.value, "fourth_quarter");
            assert.equal(year.value, String(this_year));
            await testUtils.fields.editSelect(quarter, "second_quarter");
            await selectYear(String(this_year - 1));

            assert.equal(quarter.value, "second_quarter");
            assert.equal(year.value, String(this_year - 1));

            assert.deepEqual(model.getters.getGlobalFilterValue("43"), {
                period: "second_quarter",
                yearOffset: -1,
            });
        });

        QUnit.test("Readonly user can update relation filter values", async function (assert) {
            const tagSelector = ".o_field_many2manytags .badge";
            const { model } = await createSpreadsheetFromPivotView();
            await addGlobalFilter(model, {
                filter: {
                    id: "42",
                    type: "relation",
                    label: "Relation Filter",
                    modelName: "product",
                    defaultValue: [41],
                    pivotFields: { 1: { field: "product_id", type: "many2one" } },
                    listFields: {},
                },
            });
            assert.equal(model.getters.getGlobalFilters().length, 1);
            model.updateMode("readonly");
            await nextTick();

            const searchIcon = target.querySelector(".o_topbar_filter_icon");
            await testUtils.dom.click(searchIcon);

            const pivot = target.querySelector(".pivot_filter_section");
            assert.containsOnce(target, ".pivot_filter_section");
            assert.containsNone(target, "i.o_side_panel_filter_icon.fa-cog");
            assert.containsOnce(target, "i.o_side_panel_filter_icon.fa-times");
            assert.equal(
                pivot.querySelector(".o_side_panel_filter_label").textContent,
                "Relation Filter"
            );
            assert.containsOnce(pivot, tagSelector);
            assert.deepEqual(
                [...pivot.querySelectorAll(tagSelector)].map((el) => el.textContent.trim()),
                ["xpad"]
            );

            await testUtils.dom.click(
                pivot.querySelector(".pivot_filter_input input.ui-autocomplete-input")
            );
            await testUtils.dom.click(document.querySelector("ul.ui-autocomplete li:first-child"));

            assert.containsN(pivot, tagSelector, 2);
            assert.deepEqual(
                [...pivot.querySelectorAll(tagSelector)].map((el) => el.textContent.trim()),
                ["xpad", "xphone"]
            );
            assert.deepEqual(model.getters.getGlobalFilterValue("42"), [41, 37]);
        });

        QUnit.test("Can clear a text filter values", async function (assert) {
            const { model } = await createSpreadsheetFromPivotView();
            await addGlobalFilter(model, {
                filter: {
                    id: "42",
                    type: "text",
                    label: "Text Filter",
                    defaultValue: "",
                    pivotFields: {},
                    listFields: {},
                },
            });
            const searchIcon = target.querySelector(".o_topbar_filter_icon");
            await click(searchIcon);
    
            const pivots = target.querySelectorAll(".pivot_filter_section");
            const input = pivots[0].querySelector(".pivot_filter_input input");
            assert.equal(input.value, "");
            assert.containsOnce(target, "i.o_side_panel_filter_icon.fa-cog");
            // no default value
            assert.containsNone(target, "i.o_side_panel_filter_icon.fa-times");
    
            await testUtils.fields.editAndTrigger(input, "something", ["change"]);
            assert.containsOnce(target, "i.o_side_panel_filter_icon.fa-times");
    
            await click(target.querySelector("i.o_side_panel_filter_icon.fa-times"));
            assert.containsNone(target, "i.o_side_panel_filter_icon.fa-times");
            assert.equal(input.value, "");
        })
    
        QUnit.test("Can clear a date filter values", async function (assert) {
            const { model } = await createSpreadsheetFromPivotView();
            await addGlobalFilter(model, {
                filter: {
                    id: "43",
                    type: "date",
                    label: "Date Filter",
                    rangeType: "quarter",
                    defaultValue: { yearOffset: undefined, period: undefined },
                    pivotFields: { 1: { field: "date", type: "date" } },
                    listFields: {},
                },
            });
            const searchIcon = target.querySelector(".o_topbar_filter_icon");
            await click(searchIcon);
            const pivots = target.querySelectorAll(".pivot_filter_section");
            const quarter = pivots[0].querySelector(
                ".pivot_filter_input div.date_filter_values select"
            );
            const year = pivots[0].querySelector(
                ".pivot_filter_input input.o_datepicker_input"
            );
            const this_year = luxon.DateTime.local().year;
            assert.equal(quarter.value, "empty");
            assert.equal(year.value, "");
            assert.containsOnce(target, "i.o_side_panel_filter_icon.fa-cog");
            // no default value
            assert.containsNone(target, "i.o_side_panel_filter_icon.fa-times");
    
            await testUtils.fields.editSelect(quarter, "second_quarter");
            await selectYear(String(this_year - 1));
    
            assert.equal(quarter.value, "second_quarter");
            assert.equal(year.value, String(this_year - 1));
    
            assert.containsOnce(target, "i.o_side_panel_filter_icon.fa-times");
    
            await click(target.querySelector("i.o_side_panel_filter_icon.fa-times"));
            assert.containsNone(target, "i.o_side_panel_filter_icon.fa-times");
            assert.equal(quarter.value, "empty");
            assert.equal(year.value, "");
        })
    
        QUnit.test("Can clear a relation filter values", async function (assert) {
            const tagSelector = ".o_field_many2manytags .badge";
            const { model } = await createSpreadsheetFromPivotView();
            await addGlobalFilter(model, {
                filter: {
                    id: "42",
                    type: "relation",
                    label: "Relation Filter",
                    modelName: "product",
                    defaultValue: [],
                    pivotFields: { 1: { field: "product_id", type: "many2one" } },
                    listFields: {},
                },
            });
            assert.equal(model.getters.getGlobalFilters().length, 1);
    
            const searchIcon = target.querySelector(".o_topbar_filter_icon");
            await testUtils.dom.click(searchIcon);
    
            const pivot = target.querySelector(".pivot_filter_section");
            assert.containsOnce(target, ".pivot_filter_section");
            assert.containsOnce(target, "i.o_side_panel_filter_icon.fa-cog");
            assert.containsNone(target, "i.o_side_panel_filter_icon.fa-times");
            assert.equal(
                pivot.querySelector(".o_side_panel_filter_label").textContent,
                "Relation Filter"
            );
            assert.containsNone(pivot, tagSelector);
            assert.deepEqual(
                [...pivot.querySelectorAll(tagSelector)].map((el) => el.textContent.trim()),
                []
            );
    
            await testUtils.dom.click(
                pivot.querySelector(".pivot_filter_input input.ui-autocomplete-input")
            );
            await testUtils.dom.click(document.querySelector("ul.ui-autocomplete li:first-child"));
    
            assert.containsOnce(pivot, tagSelector);
            assert.deepEqual(
                [...pivot.querySelectorAll(tagSelector)].map((el) => el.textContent.trim()),
                ["xphone"]
            );
            assert.containsOnce(target, "i.o_side_panel_filter_icon.fa-times");
    
            // clear filter
            await click(target.querySelector("i.o_side_panel_filter_icon.fa-times"));
            assert.containsNone(target, "i.o_side_panel_filter_icon.fa-times");
            assert.containsNone(pivot, tagSelector);
            assert.deepEqual(
                [...pivot.querySelectorAll(tagSelector)].map((el) => el.textContent.trim()),
                []
            );
        })

        QUnit.test(
            "Changing the range of a date global filter reset the default value",
            async function (assert) {
                assert.expect(1);

                const { model } = await createSpreadsheetFromPivotView();
                await addGlobalFilter(model, {
                    filter: {
                        id: "42",
                        type: "date",
                        rangeType: "month",
                        label: "This month",
                        pivotFields: {
                            1: { field: "date", type: "date" },
                        },
                        defaultValue: {
                            period: "january",
                        },
                    },
                });
                const searchIcon = $(target).find(".o_topbar_filter_icon")[0];
                await testUtils.dom.click(searchIcon);
                const editFilter = $(target).find(".o_side_panel_filter_icon.fa-cog");
                await testUtils.dom.click(editFilter);
                const options = $(target).find(
                    ".o_spreadsheet_filter_editor_side_panel .o_side_panel_section"
                )[1];
                await testUtils.fields.editSelect(options.querySelector("select"), "year");
                await testUtils.dom.click($(target).find(".o_global_filter_save")[0]);
                await nextTick();
                assert.deepEqual(model.getters.getGlobalFilters()[0].defaultValue, {});
            }
        );

        QUnit.test(
            "Changing the range of a date global filter reset the current value",
            async function (assert) {
                const { model } = await createSpreadsheetFromPivotView();
                await addGlobalFilter(model, {
                    filter: {
                        id: "42",
                        type: "date",
                        rangeType: "month",
                        label: "This month",
                        pivotFields: {
                        1: { field: "date", type: "date" },
                        },
                        defaultValue: {
                        period: "january",
                        },
                    },
                });
                const searchIcon = target.querySelector(".o_topbar_filter_icon");
                await testUtils.dom.click(searchIcon);

                // Edit filter value in filters list
                const optionInFilterList = target.querySelector(".pivot_filter select");
                await testUtils.fields.editSelect(optionInFilterList, "february");
                const editFilter = target.querySelector(".o_side_panel_filter_icon.fa-cog");

                // Edit filter range and save
                await testUtils.dom.click(editFilter);
                const timeRangeOption = target.querySelectorAll(
                    ".o_spreadsheet_filter_editor_side_panel .o_side_panel_section"
                )[1];
                const selectField = timeRangeOption.querySelector('select')
                await testUtils.fields.editSelect(selectField, "quarter");
                const quarterOption = target.querySelectorAll(
                    ".o_spreadsheet_filter_editor_side_panel .o_side_panel_section"
                )[2];
                quarterOption
                    .querySelector("select option[value='first_quarter']")
                    .setAttribute("selected", "1");
                await testUtils.dom.triggerEvent(quarterOption.querySelector("select"), "change");
                await testUtils.nextTick();

                await testUtils.dom.click(target.querySelector(".o_global_filter_save"));
                await testUtils.nextTick();

                assert.deepEqual(model.getters.getGlobalFilter(42).defaultValue, {
                    period: "first_quarter",
                    yearOffset: 0,
                });
                assert.deepEqual(
                    model.getters.getGlobalFilterValue(42),
                    model.getters.getGlobalFilter(42).defaultValue
                );
            }
        );
    }
);
