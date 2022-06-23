/** @odoo-module */

import { DataSources } from "@spreadsheet/data_sources/data_sources";
import CommandResult from "@spreadsheet/o_spreadsheet/cancelled_reason";
import spreadsheet from "@spreadsheet/o_spreadsheet/o_spreadsheet_extended";
import { createSpreadsheetWithPivot } from "@spreadsheet/../tests/utils/pivot";
import { setCellContent } from "@spreadsheet/../tests/utils/commands";
import { getCellContent } from "@spreadsheet/../tests/utils/getters";

const { Model } = spreadsheet;

/**
 * @param {object} params
 * @param {string} params.arch
 * @param {string} params.formula
 * @param {string} params.convert
 * @returns {string}
 */
async function convertFormula(params) {
    const { model } = await createSpreadsheetWithPivot({ arch: params.arch });

    const proms = [];
    for (const pivotId of model.getters.getPivotIds()) {
        proms.push(model.getters.getSpreadsheetPivotModel(pivotId).prepareForTemplateGeneration());
    }
    await Promise.all(proms);
    setCellContent(model, "A1", `=${params.formula}`);
    model.dispatch(params.convert);
    // Remove the equal sign
    return getCellContent(model, "A1").slice(1);
}

QUnit.module("documents_spreadsheet > pivot_templates", {}, function () {
    QUnit.module("Template");

    QUnit.test(
        "Dispatch template command is not allowed if cache is not loaded",
        async function (assert) {
            const { model: m1 } = await createSpreadsheetWithPivot();
            const model = new Model(m1.exportData(), {
                dataSources: new DataSources(m1.config.dataSources._orm),
            });
            assert.deepEqual(model.dispatch("CONVERT_PIVOT_TO_TEMPLATE").reasons, [
                CommandResult.PivotCacheNotLoaded,
            ]);
            assert.deepEqual(model.dispatch("CONVERT_PIVOT_FROM_TEMPLATE").reasons, [
                CommandResult.PivotCacheNotLoaded,
            ]);
        }
    );

    QUnit.test("Don't change formula if not many2one", async function (assert) {
        const formula = `ODOO.PIVOT("1","probability","foo","12","bar","110")`;
        const result = await convertFormula({
            formula,
            convert: "CONVERT_PIVOT_TO_TEMPLATE",
        });
        assert.equal(result, formula);
    });

    QUnit.test(
        "Adapt formula from absolute to relative with many2one in col",
        async function (assert) {
            const arch = /*xml*/ `
                <pivot>
                    <field name="product_id" type="col"/>
                    <field name="bar" type="row"/>
                    <field name="probability" type="measure"/>
                </pivot>`;
            let result = await convertFormula({
                arch,
                formula: `ODOO.PIVOT("1","probability","product_id","37","bar","110")`,
                convert: "CONVERT_PIVOT_TO_TEMPLATE",
            });
            assert.equal(
                result,
                `ODOO.PIVOT("1","probability","product_id",ODOO.PIVOT.POSITION("1","product_id",1),"bar","110")`
            );

            result = await convertFormula({
                arch,
                formula: `ODOO.PIVOT.HEADER("1","product_id","37","bar","110")`,
                convert: "CONVERT_PIVOT_TO_TEMPLATE",
            });
            assert.equal(
                result,
                `ODOO.PIVOT.HEADER("1","product_id",ODOO.PIVOT.POSITION("1","product_id",1),"bar","110")`
            );

            result = await convertFormula({
                arch,
                formula: `ODOO.PIVOT("1","probability","product_id","41","bar","110")`,
                convert: "CONVERT_PIVOT_TO_TEMPLATE",
            });
            assert.equal(
                result,
                `ODOO.PIVOT("1","probability","product_id",ODOO.PIVOT.POSITION("1","product_id",2),"bar","110")`
            );

            result = await convertFormula({
                arch,
                formula: `ODOO.PIVOT.HEADER("1","product_id","41","bar","110")`,
                convert: "CONVERT_PIVOT_TO_TEMPLATE",
            });
            assert.equal(
                result,
                `ODOO.PIVOT.HEADER("1","product_id",ODOO.PIVOT.POSITION("1","product_id",2),"bar","110")`
            );
        }
    );

    QUnit.test("Adapt formula from absolute to relative with integer ids", async function (assert) {
        const arch = /*xml*/ `
                <pivot>
                    <field name="bar" type="col"/>
                    <field name="product_id" type="row"/>
                    <field name="probability" type="measure"/>
                </pivot>`;
        let result = await convertFormula({
            arch,
            formula: `ODOO.PIVOT("1","probability","product_id",37,"bar","110")`,
            convert: "CONVERT_PIVOT_TO_TEMPLATE",
        });
        assert.equal(
            result,
            `ODOO.PIVOT("1","probability","product_id",ODOO.PIVOT.POSITION("1","product_id",1),"bar","110")`
        );
        result = await convertFormula({
            arch,
            formula: `ODOO.PIVOT.HEADER("1","product_id",41,"bar","110")`,
            convert: "CONVERT_PIVOT_TO_TEMPLATE",
        });
        assert.equal(
            result,
            `ODOO.PIVOT.HEADER("1","product_id",ODOO.PIVOT.POSITION("1","product_id",2),"bar","110")`
        );
    });

    QUnit.test(
        "Adapt formula from absolute to relative with many2one in row",
        async function (assert) {
            const arch = /*xml*/ `
                <pivot>
                    <field name="bar" type="col"/>
                    <field name="product_id" type="row"/>
                    <field name="probability" type="measure"/>
                </pivot>`;

            let result = await convertFormula({
                arch,
                formula: `ODOO.PIVOT("1","probability","product_id","37","bar","110")`,
                convert: "CONVERT_PIVOT_TO_TEMPLATE",
            });
            assert.equal(
                result,
                `ODOO.PIVOT("1","probability","product_id",ODOO.PIVOT.POSITION("1","product_id",1),"bar","110")`
            );

            result = await convertFormula({
                arch,
                formula: `ODOO.PIVOT("1","probability","product_id","41","bar","110")`,
                convert: "CONVERT_PIVOT_TO_TEMPLATE",
            });
            assert.equal(
                result,
                `ODOO.PIVOT("1","probability","product_id",ODOO.PIVOT.POSITION("1","product_id",2),"bar","110")`
            );

            result = await convertFormula({
                arch,
                formula: `ODOO.PIVOT("1","probability","product_id","41","bar","110")`,
                convert: "CONVERT_PIVOT_TO_TEMPLATE",
            });
            assert.equal(
                result,
                `ODOO.PIVOT("1","probability","product_id",ODOO.PIVOT.POSITION("1","product_id",2),"bar","110")`
            );

            result = await convertFormula({
                arch,
                formula: `ODOO.PIVOT.HEADER("1","product_id","41","bar","110")`,
                convert: "CONVERT_PIVOT_TO_TEMPLATE",
            });
            assert.equal(
                result,
                `ODOO.PIVOT.HEADER("1","product_id",ODOO.PIVOT.POSITION("1","product_id",2),"bar","110")`
            );
        }
    );

    QUnit.test(
        "Adapt formula from relative to absolute with many2one in col",
        async function (assert) {
            const arch = /*xml*/ `
                <pivot>
                    <field name="product_id" type="col"/>
                    <field name="bar" type="row"/>
                    <field name="probability" type="measure"/>
                </pivot>`;
            let result = await convertFormula({
                arch,
                formula: `ODOO.PIVOT("1","probability","product_id",ODOO.PIVOT.POSITION("1","product_id", 1),"bar","110")`,
                convert: "CONVERT_PIVOT_FROM_TEMPLATE",
            });
            assert.equal(result, `ODOO.PIVOT("1","probability","product_id","37","bar","110")`);

            result = await convertFormula({
                arch,
                formula: `ODOO.PIVOT.HEADER("1","product_id",ODOO.PIVOT.POSITION("1","product_id",1),"bar","110")`,
                convert: "CONVERT_PIVOT_FROM_TEMPLATE",
            });
            assert.equal(result, `ODOO.PIVOT.HEADER("1","product_id","37","bar","110")`);

            result = await convertFormula({
                arch,
                formula: `ODOO.PIVOT("1","probability","product_id",ODOO.PIVOT.POSITION("1","product_id", 2),"bar","110")`,
                convert: "CONVERT_PIVOT_FROM_TEMPLATE",
            });
            assert.equal(result, `ODOO.PIVOT("1","probability","product_id","41","bar","110")`);

            result = await convertFormula({
                arch,
                formula: `ODOO.PIVOT.HEADER("1","product_id",ODOO.PIVOT.POSITION("1","product_id", 2),"bar","110")`,
                convert: "CONVERT_PIVOT_FROM_TEMPLATE",
            });
            assert.equal(result, `ODOO.PIVOT.HEADER("1","product_id","41","bar","110")`);
        }
    );

    QUnit.test("Will ignore overflowing template position", async function (assert) {
        const arch = /*xml*/ `
                <pivot>
                    <field name="bar" type="col"/>
                    <field name="product_id" type="row"/>
                    <field name="probability" type="measure"/>
                </pivot>`;
        const result = await convertFormula({
            arch,
            formula: `ODOO.PIVOT("1","probability","product_id",ODOO.PIVOT.POSITION("1","product_id", 9999),"bar","110")`,
            convert: "CONVERT_PIVOT_FROM_TEMPLATE",
        });
        assert.equal(result, "");
    });

    QUnit.test(
        "Adapt formula from relative to absolute with many2one in row",
        async function (assert) {
            const arch = /*xml*/ `
            <pivot>
                <field name="bar" type="col"/>
                <field name="product_id" type="row"/>
                <field name="probability" type="measure"/>
            </pivot>`;
            let result = await convertFormula({
                arch,
                formula: `ODOO.PIVOT("1","probability","product_id",ODOO.PIVOT.POSITION("1","product_id",1),"bar","110")`,
                convert: "CONVERT_PIVOT_FROM_TEMPLATE",
            });
            assert.equal(result, `ODOO.PIVOT("1","probability","product_id","37","bar","110")`);

            result = await convertFormula({
                arch,
                formula: `ODOO.PIVOT.HEADER("1","product_id",ODOO.PIVOT.POSITION("1","product_id",1),"bar","110")`,
                convert: "CONVERT_PIVOT_FROM_TEMPLATE",
            });
            assert.equal(result, `ODOO.PIVOT.HEADER("1","product_id","37","bar","110")`);

            result = await convertFormula({
                arch,
                formula: `ODOO.PIVOT("1","probability","product_id",ODOO.PIVOT.POSITION("1","product_id",2),"bar","110")`,
                convert: "CONVERT_PIVOT_FROM_TEMPLATE",
            });
            assert.equal(result, `ODOO.PIVOT("1","probability","product_id","41","bar","110")`);

            result = await convertFormula({
                arch,
                formula: `ODOO.PIVOT.HEADER("1","product_id",ODOO.PIVOT.POSITION("1","product_id",2),"bar","110")`,
                convert: "CONVERT_PIVOT_FROM_TEMPLATE",
            });
            assert.equal(result, `ODOO.PIVOT.HEADER("1","product_id","41","bar","110")`);
        }
    );

    QUnit.test("Adapt pivot as function arg from relative to absolute", async function (assert) {
        const arch = /*xml*/ `
            <pivot>
                <field name="bar" type="col"/>
                <field name="product_id" type="row"/>
                <field name="probability" type="measure"/>
            </pivot>`;
        const result = await convertFormula({
            arch,
            formula: `SUM(
                ODOO.PIVOT("1","probability","product_id",ODOO.PIVOT.POSITION("1","product_id",1),"bar","110"),
                ODOO.PIVOT("1","probability","product_id",ODOO.PIVOT.POSITION("1","product_id",2),"bar","110")
            )`,
            convert: "CONVERT_PIVOT_FROM_TEMPLATE",
        });
        assert.equal(
            result,
            `SUM(ODOO.PIVOT("1","probability","product_id","37","bar","110"),ODOO.PIVOT("1","probability","product_id","41","bar","110"))`
        );
    });

    QUnit.test("Adapt pivot as operator arg from relative to absolute", async function (assert) {
        const arch = /*xml*/ `
            <pivot>
                <field name="bar" type="col"/>
                <field name="product_id" type="row"/>
                <field name="probability" type="measure"/>
            </pivot>`;
        const result = await convertFormula({
            arch,
            formula: `
                ODOO.PIVOT("1","probability","product_id",ODOO.PIVOT.POSITION("1","product_id",1),"bar","110")
                +
                ODOO.PIVOT("1","probability","product_id",ODOO.PIVOT.POSITION("1","product_id",2),"bar","110")
            `,
            convert: "CONVERT_PIVOT_FROM_TEMPLATE",
        });
        assert.equal(
            result,
            `ODOO.PIVOT("1","probability","product_id","37","bar","110")+ODOO.PIVOT("1","probability","product_id","41","bar","110")`
        );
    });

    QUnit.test(
        "Adapt pivot as unary operator arg from relative to absolute",
        async function (assert) {
            const arch = /*xml*/ `
            <pivot>
                <field name="bar" type="col"/>
                <field name="product_id" type="row"/>
                <field name="probability" type="measure"/>
            </pivot>`;
            const result = await convertFormula({
                arch,
                formula: `
                    -ODOO.PIVOT("1","probability","product_id",ODOO.PIVOT.POSITION("1","product_id",1),"bar","110")
                `,
                convert: "CONVERT_PIVOT_FROM_TEMPLATE",
            });
            assert.equal(result, `-ODOO.PIVOT("1","probability","product_id","37","bar","110")`);
        }
    );

    QUnit.test("Adapt pivot as operator arg from absolute to relative", async function (assert) {
        const arch = /*xml*/ `
            <pivot>
                <field name="bar" type="col"/>
                <field name="product_id" type="row"/>
                <field name="probability" type="measure"/>
            </pivot>`;
        const result = await convertFormula({
            arch,
            formula: `
                ODOO.PIVOT("1","probability","product_id","37","bar","110")
                +
                ODOO.PIVOT("1","probability","product_id","41","bar","110")
            `,
            convert: "CONVERT_PIVOT_TO_TEMPLATE",
        });
        assert.equal(
            result,
            `ODOO.PIVOT("1","probability","product_id",ODOO.PIVOT.POSITION("1","product_id",1),"bar","110")+ODOO.PIVOT("1","probability","product_id",ODOO.PIVOT.POSITION("1","product_id",2),"bar","110")`
        );
    });

    QUnit.test(
        "Adapt pivot as unary operator arg from absolute to relative",
        async function (assert) {
            const arch = /*xml*/ `
            <pivot>
                <field name="bar" type="col"/>
                <field name="product_id" type="row"/>
                <field name="probability" type="measure"/>
            </pivot>`;
            const result = await convertFormula({
                arch,
                formula: `
                -ODOO.PIVOT("1","probability","product_id","37","bar","110")
            `,
                convert: "CONVERT_PIVOT_TO_TEMPLATE",
            });
            assert.equal(
                result,
                `-ODOO.PIVOT("1","probability","product_id",ODOO.PIVOT.POSITION("1","product_id",1),"bar","110")`
            );
        }
    );

    QUnit.test("Adapt pivot as function arg from absolute to relative", async function (assert) {
        const arch = /*xml*/ `
            <pivot>
                <field name="bar" type="col"/>
                <field name="product_id" type="row"/>
                <field name="probability" type="measure"/>
            </pivot>`;
        const result = await convertFormula({
            arch,
            formula: `
                SUM(
                    ODOO.PIVOT("1","probability","product_id","37","bar","110"),
                    ODOO.PIVOT("1","probability","product_id","41","bar","110")
                )
            `,
            convert: "CONVERT_PIVOT_TO_TEMPLATE",
        });
        assert.equal(
            result,
            `SUM(ODOO.PIVOT("1","probability","product_id",ODOO.PIVOT.POSITION("1","product_id",1),"bar","110"),ODOO.PIVOT("1","probability","product_id",ODOO.PIVOT.POSITION("1","product_id",2),"bar","110"))`
        );
    });

    QUnit.test("Computed ids are not changed", async function (assert) {
        const arch = /*xml*/ `
            <pivot>
                <field name="bar" type="col"/>
                <field name="product_id" type="row"/>
                <field name="probability" type="measure"/>
            </pivot>`;
        const result = await convertFormula({
            arch,
            formula: `ODOO.PIVOT("1","probability","product_id",A2,"bar","110")`,
            convert: "CONVERT_PIVOT_TO_TEMPLATE",
        });
        assert.equal(result, `ODOO.PIVOT("1","probability","product_id",A2,"bar","110")`);
    });
});
