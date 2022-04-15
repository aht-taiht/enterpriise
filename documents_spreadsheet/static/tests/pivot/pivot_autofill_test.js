/** @odoo-module alias=documents_spreadsheet.PivotAutofillTests */

import { getBasicData } from "../utils/spreadsheet_test_data";
import { selectCell, setCellContent } from "../utils/commands_helpers";
import { getCellFormula, getPivotAutofillValue } from "../utils/getters_helpers";
import { createSpreadsheetFromPivot } from "../utils/pivot_helpers";
import { waitForEvaluation } from "../spreadsheet_test_utils";

const { module, test } = QUnit;

module("documents_spreadsheet > pivot_autofill", {}, () => {
    test("Autofill pivot values", async function (assert) {
        assert.expect(28);

        const { model } = await createSpreadsheetFromPivot();

        // From value to value
        assert.strictEqual(
            getPivotAutofillValue(model, "C3", { direction: "bottom", steps: 1 }),
            getCellFormula(model, "C4")
        );
        assert.strictEqual(
            getPivotAutofillValue(model, "B4", { direction: "top", steps: 1 }),
            getCellFormula(model, "B3")
        );
        assert.strictEqual(
            getPivotAutofillValue(model, "C3", { direction: "right", steps: 1 }),
            getCellFormula(model, "D3")
        );
        assert.strictEqual(
            getPivotAutofillValue(model, "C3", { direction: "left", steps: 1 }),
            getCellFormula(model, "B3")
        );
        assert.strictEqual(
            getPivotAutofillValue(model, "C3", { direction: "bottom", steps: 2 }),
            getCellFormula(model, "C5")
        );
        assert.strictEqual(
            getPivotAutofillValue(model, "C3", { direction: "bottom", steps: 3 }),
            ""
        );
        assert.strictEqual(
            getPivotAutofillValue(model, "C3", { direction: "right", steps: 4 }),
            ""
        );
        // From value to header
        assert.strictEqual(
            getPivotAutofillValue(model, "B4", { direction: "left", steps: 1 }),
            getCellFormula(model, "A4")
        );
        assert.strictEqual(
            getPivotAutofillValue(model, "B4", { direction: "top", steps: 1 }),
            getCellFormula(model, "B3")
        );
        assert.strictEqual(
            getPivotAutofillValue(model, "B4", { direction: "top", steps: 2 }),
            getCellFormula(model, "B2")
        );
        assert.strictEqual(
            getPivotAutofillValue(model, "B4", { direction: "top", steps: 3 }),
            getCellFormula(model, "B1")
        );
        // From header to header
        assert.strictEqual(
            getPivotAutofillValue(model, "B3", { direction: "right", steps: 1 }),
            getCellFormula(model, "C3")
        );
        assert.strictEqual(
            getPivotAutofillValue(model, "B3", { direction: "right", steps: 2 }),
            getCellFormula(model, "D3")
        );
        assert.strictEqual(
            getPivotAutofillValue(model, "B3", { direction: "left", steps: 1 }),
            getCellFormula(model, "A3")
        );
        assert.strictEqual(
            getPivotAutofillValue(model, "B1", { direction: "bottom", steps: 1 }),
            getCellFormula(model, "B2")
        );
        assert.strictEqual(
            getPivotAutofillValue(model, "B3", { direction: "top", steps: 1 }),
            getCellFormula(model, "B2")
        );
        assert.strictEqual(
            getPivotAutofillValue(model, "A4", { direction: "bottom", steps: 1 }),
            getCellFormula(model, "A5")
        );
        assert.strictEqual(
            getPivotAutofillValue(model, "A4", { direction: "top", steps: 1 }),
            getCellFormula(model, "A3")
        );
        assert.strictEqual(
            getPivotAutofillValue(model, "A4", { direction: "bottom", steps: 2 }),
            ""
        );
        assert.strictEqual(getPivotAutofillValue(model, "A4", { direction: "top", steps: 3 }), "");
        // From header to value
        assert.strictEqual(
            getPivotAutofillValue(model, "B2", { direction: "bottom", steps: 1 }),
            getCellFormula(model, "B3")
        );
        assert.strictEqual(
            getPivotAutofillValue(model, "B2", { direction: "bottom", steps: 2 }),
            getCellFormula(model, "B4")
        );
        assert.strictEqual(
            getPivotAutofillValue(model, "B2", { direction: "bottom", steps: 4 }),
            ""
        );
        assert.strictEqual(
            getPivotAutofillValue(model, "A3", { direction: "right", steps: 1 }),
            getCellFormula(model, "B3")
        );
        assert.strictEqual(
            getPivotAutofillValue(model, "A3", { direction: "right", steps: 5 }),
            getCellFormula(model, "F3")
        );
        assert.strictEqual(
            getPivotAutofillValue(model, "A3", { direction: "right", steps: 6 }),
            ""
        );
        // From total row header to value
        assert.strictEqual(
            getPivotAutofillValue(model, "A5", { direction: "right", steps: 1 }),
            getCellFormula(model, "B5")
        );
        assert.strictEqual(
            getPivotAutofillValue(model, "A5", { direction: "right", steps: 5 }),
            getCellFormula(model, "F5")
        );
    });

    test("Autofill pivot values with date in rows", async function (assert) {
        assert.expect(6);

        const { model } = await createSpreadsheetFromPivot({
            serverData: {
                models: getBasicData(),
                views: {
                    "partner,false,pivot": `
                        <pivot string="Partners">
                            <field name="foo" type="col"/>
                            <field name="date" interval="month" type="row"/>
                            <field name="probability" type="measure"/>
                        </pivot>`,
                    "partner,false,search": `<search/>`,
                },
            },
        });
        assert.strictEqual(
            getPivotAutofillValue(model, "A3", { direction: "bottom", steps: 1 }),
            getCellFormula(model, "A4").replace("10/2016", "05/2016")
        );
        assert.strictEqual(
            getPivotAutofillValue(model, "A5", { direction: "bottom", steps: 1 }),
            '=PIVOT.HEADER("1","date:month","01/2017")'
        );
        assert.strictEqual(
            getPivotAutofillValue(model, "B3", { direction: "bottom", steps: 1 }),
            getCellFormula(model, "B4").replace("10/2016", "05/2016")
        );
        assert.strictEqual(
            getPivotAutofillValue(model, "B5", { direction: "bottom", steps: 1 }),
            getCellFormula(model, "B5").replace("12/2016", "01/2017")
        );
        assert.strictEqual(
            getPivotAutofillValue(model, "B5", { direction: "top", steps: 1 }),
            getCellFormula(model, "B4").replace("10/2016", "11/2016")
        );
        assert.strictEqual(getPivotAutofillValue(model, "F6", { direction: "top", steps: 1 }), "");
    });

    test("Autofill pivot values with date in cols", async function (assert) {
        assert.expect(3);

        const { model } = await createSpreadsheetFromPivot({
            serverData: {
                models: getBasicData(),
                views: {
                    "partner,false,pivot": `
                        <pivot string="Partners">
                            <field name="foo" type="row"/>
                            <field name="date" interval="day" type="col"/>
                            <field name="probability" type="measure"/>
                        </pivot>`,
                    "partner,false,search": `<search/>`,
                },
            },
        });
        assert.strictEqual(
            getPivotAutofillValue(model, "B1", { direction: "right", steps: 1 }),
            getCellFormula(model, "B1").replace("20/01/2016", "21/01/2016")
        );
        assert.strictEqual(
            getPivotAutofillValue(model, "B2", { direction: "right", steps: 1 }),
            getCellFormula(model, "B2").replace("20/01/2016", "21/01/2016")
        );
        assert.strictEqual(
            getPivotAutofillValue(model, "B3", { direction: "right", steps: 1 }),
            getCellFormula(model, "B3").replace("20/01/2016", "21/01/2016")
        );
    });

    test("Autofill pivot values with date (day)", async function (assert) {
        assert.expect(1);

        const { model } = await createSpreadsheetFromPivot({
            serverData: {
                models: getBasicData(),
                views: {
                    "partner,false,pivot": `
                        <pivot string="Partners">
                            <field name="foo" type="col"/>
                            <field name="date" interval="day" type="row"/>
                            <field name="probability" type="measure"/>
                        </pivot>`,
                    "partner,false,search": `<search/>`,
                },
            },
        });
        assert.strictEqual(
            getPivotAutofillValue(model, "A3", { direction: "bottom", steps: 1 }),
            getCellFormula(model, "A3").replace("20/01/2016", "21/01/2016")
        );
    });

    test("Autofill pivot values with date (month)", async function (assert) {
        const { model } = await createSpreadsheetFromPivot({
            serverData: {
                models: getBasicData(),
                views: {
                    "partner,false,pivot": /*xml*/`
                        <pivot string="Partners">
                            <field name="foo" type="col"/>
                            <field name="date" interval="month" type="row"/>
                            <field name="probability" type="measure"/>
                        </pivot>`,
                    "partner,false,search": `<search/>`,
                },
            },
        });
        assert.strictEqual(
            getPivotAutofillValue(model, "A3", { direction: "bottom", steps: 1 }),
            `=PIVOT.HEADER("1","date:month","05/2016")`
        );
    });


    test("Autofill pivot values with date (quarter)", async function (assert) {
        assert.expect(1);

        const { model } = await createSpreadsheetFromPivot({
            serverData: {
                models: getBasicData(),
                views: {
                    "partner,false,pivot": `
                        <pivot string="Partners">
                            <field name="foo" type="col"/>
                            <field name="date" interval="quarter" type="row"/>
                            <field name="probability" type="measure"/>
                        </pivot>`,
                    "partner,false,search": `<search/>`,
                },
            },
        });
        assert.strictEqual(
            getPivotAutofillValue(model, "A3", { direction: "bottom", steps: 1 }),
            getCellFormula(model, "A3").replace("2/2016", "3/2016")
        );
    });

    test("Autofill pivot values with date (year)", async function (assert) {
        assert.expect(1);

        const { model } = await createSpreadsheetFromPivot({
            serverData: {
                models: getBasicData(),
                views: {
                    "partner,false,pivot": `
                        <pivot string="Partners">
                            <field name="foo" type="col"/>
                            <field name="date" interval="year" type="row"/>
                            <field name="probability" type="measure"/>
                        </pivot>`,
                    "partner,false,search": `<search/>`,
                },
            },
        });
        assert.strictEqual(
            getPivotAutofillValue(model, "A3", { direction: "bottom", steps: 1 }),
            getCellFormula(model, "A3").replace("2016", "2017")
        );
    });

    test("Autofill pivot values with date (no defined interval)", async function (assert) {
        const { model } = await createSpreadsheetFromPivot({
            serverData: {
                models: getBasicData(),
                views: {
                    "partner,false,pivot": /*xml*/`
                        <pivot string="Partners">
                            <field name="foo" type="col"/>
                            <field name="date" type="row"/>
                            <field name="probability" type="measure"/>
                        </pivot>`,
                    "partner,false,search": `<search/>`,
                },
            },
        });
        assert.strictEqual(
            getPivotAutofillValue(model, "A3", { direction: "bottom", steps: 1 }),
            `=PIVOT.HEADER("1","date","05/2016")`
        );
    });

    test("Tooltip of pivot formulas", async function (assert) {
        assert.expect(8);

        const { model } = await createSpreadsheetFromPivot({
            serverData: {
                models: getBasicData(),
                views: {
                    "partner,false,pivot": `
                        <pivot string="Partners">
                            <field name="foo" type="col"/>
                            <field name="date" interval="year" type="row"/>
                            <field name="probability" type="measure"/>
                        </pivot>`,
                    "partner,false,search": `<search/>`,
                },
            },
        });
        await waitForEvaluation(model);
        assert.deepEqual(model.getters.getTooltipFormula(getCellFormula(model, "A3")), [
            { value: "2016" },
        ]);
        assert.deepEqual(model.getters.getTooltipFormula(getCellFormula(model, "B3")), [
            { value: "2016" },
        ]);
        assert.deepEqual(model.getters.getTooltipFormula(getCellFormula(model, "E3")), [
            { value: "2016" },
        ]);
        assert.deepEqual(model.getters.getTooltipFormula(getCellFormula(model, "F3")), [
            { value: "2016" },
        ]);
        assert.deepEqual(model.getters.getTooltipFormula(getCellFormula(model, "B1")), [
            { value: 1 },
        ]);
        assert.deepEqual(model.getters.getTooltipFormula(getCellFormula(model, "B2")), [
            { value: 1 },
            { value: "Probability" },
        ]);
        assert.deepEqual(model.getters.getTooltipFormula(`=PIVOT.HEADER("1")`, true), [
            { value: "Total" },
        ]);
        assert.deepEqual(model.getters.getTooltipFormula(`=PIVOT.HEADER("1")`, false), [
            { value: "Total" },
        ]);
    });

    test("Tooltip of pivot formulas with 2 measures", async function (assert) {
        assert.expect(3);

        const { model } = await createSpreadsheetFromPivot({
            serverData: {
                models: getBasicData(),
                views: {
                    "partner,false,pivot": `
                        <pivot string="Partners">
                            <field name="name" type="col"/>
                            <field name="date" interval="year" type="row"/>
                            <field name="probability" type="measure"/>
                            <field name="foo" type="measure"/>
                        </pivot>`,
                    "partner,false,search": `<search/>`,
                },
            },
        });
        await waitForEvaluation(model);
        assert.deepEqual(model.getters.getTooltipFormula(getCellFormula(model, "A3")), [
            { value: "2016" },
        ]);
        assert.deepEqual(model.getters.getTooltipFormula(getCellFormula(model, "B3")), [
            { value: "2016" },
        ]);
        assert.deepEqual(model.getters.getTooltipFormula(getCellFormula(model, "C3"), true), [
            { value: "None" },
            { value: "Foo" },
        ]);
    });

    test("Tooltip of empty pivot formula is empty", async function (assert) {
        assert.expect(1);

        const { model } = await createSpreadsheetFromPivot({
            serverData: {
                models: getBasicData(),
                views: {
                    "partner,false,pivot": `
                        <pivot string="Partners">
                            <field name="name" type="col"/>
                            <field name="date" interval="year" type="row"/>
                            <field name="probability" type="measure"/>
                            <field name="foo" type="measure"/>
                        </pivot>`,
                    "partner,false,search": `<search/>`,
                },
            },
        });
        await waitForEvaluation(model);
        selectCell(model, "A3");
        model.dispatch("AUTOFILL_SELECT", { col: 10, row: 10 });
        assert.equal(model.getters.getAutofillTooltip(), undefined);
    });

    test("Autofill content which contains pivots but which is not a pivot", async function (assert) {
        assert.expect(2);
        const { model } = await createSpreadsheetFromPivot({
            serverData: {
                models: getBasicData(),
                views: {
                    "partner,false,pivot": `
                        <pivot string="Partners">
                            <field name="foo" type="col"/>
                            <field name="date" interval="year" type="row"/>
                            <field name="probability" type="measure"/>
                        </pivot>`,
                    "partner,false,search": `<search/>`,
                },
            },
        });
        const a3 = getCellFormula(model, "A3").replace("=", "");
        const content = `=${a3} + ${a3}`;
        setCellContent(model, "F6", content);
        assert.strictEqual(
            getPivotAutofillValue(model, "F6", { direction: "bottom", steps: 1 }),
            content
        );
        assert.strictEqual(
            getPivotAutofillValue(model, "F6", { direction: "right", steps: 1 }),
            content
        );
    });
});
