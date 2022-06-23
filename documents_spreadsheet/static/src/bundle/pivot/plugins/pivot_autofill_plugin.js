/** @odoo-module */

import core from "web.core";
import spreadsheet from "@spreadsheet/o_spreadsheet/o_spreadsheet_extended";
import { formats } from "@spreadsheet/helpers/constants";
import {
    getFirstPivotFunction,
    getNumberOfPivotFormulas,
    makePivotFormula,
} from "@spreadsheet/pivot/pivot_helpers";

const { astToFormula } = spreadsheet;
const _t = core._t;

/**
 * @typedef CurrentElement
 * @property {Array<string>} cols
 * @property {Array<string>} rows
 *
 * @typedef TooltipFormula
 * @property {string} value
 *
 * @typedef GroupByDate
 * @property {boolean} isDate
 * @property {string|undefined} group
 */

export default class PivotAutofillPlugin extends spreadsheet.UIPlugin {
    // ---------------------------------------------------------------------
    // Getters
    // ---------------------------------------------------------------------

    /**
     * Get the next value to autofill of a pivot function
     *
     * @param {string} formula Pivot formula
     * @param {boolean} isColumn True if autofill is LEFT/RIGHT, false otherwise
     * @param {number} increment number of steps
     *
     * @returns {string}
     */
    getPivotNextAutofillValue(formula, isColumn, increment) {
        if (getNumberOfPivotFormulas(formula) !== 1) {
            return formula;
        }
        const { functionName, args } = getFirstPivotFunction(formula);
        const evaluatedArgs = args
            .map(astToFormula)
            .map((arg) => this.getters.evaluateFormula(arg));
        const pivotId = evaluatedArgs[0];
        const model = this.getters.getSpreadsheetPivotModel(pivotId);
        for (let i = evaluatedArgs.length - 1; i > 0; i--) {
            const fieldName = evaluatedArgs[i].toString();
            if (
              fieldName.startsWith("#") &&
              ((isColumn && model.isColumnGroupBy(fieldName)) ||
                (!isColumn && model.isRowGroupBy(fieldName)))
            ) {
              evaluatedArgs[i + 1] =
                parseInt(evaluatedArgs[i + 1], 10) + increment;
              if (evaluatedArgs[i + 1] < 0) {
                return formula;
              }
              if (functionName === "ODOO.PIVOT") {
                return makePivotFormula("ODOO.PIVOT", evaluatedArgs);
              } else if (functionName === "ODOO.PIVOT.HEADER") {
                return makePivotFormula("ODOO.PIVOT.HEADER", evaluatedArgs);
              }
              return formula;
            }
        }
        let builder;
        if (functionName === "ODOO.PIVOT") {
            builder = this._autofillPivotValue.bind(this);
        } else if (functionName === "ODOO.PIVOT.HEADER") {
            if (evaluatedArgs.length === 1) {
                // Total
                if (isColumn) {
                    // LEFT-RIGHT
                    builder = this._autofillPivotRowHeader.bind(this);
                } else {
                    // UP-DOWN
                    builder = this._autofillPivotColHeader.bind(this);
                }
            } else if (this.getters.getPivotDefinition(pivotId).rowGroupBys.includes(evaluatedArgs[1])) {
                builder = this._autofillPivotRowHeader.bind(this);
            } else {
                builder = this._autofillPivotColHeader.bind(this);
            }
        }
        if (builder) {
            return builder(pivotId, evaluatedArgs, isColumn, increment);
        }
        return formula;
    }

    /**
     * Compute the tooltip to display from a Pivot formula
     *
     * @param {string} formula Pivot formula
     * @param {boolean} isColumn True if the direction is left/right, false
     *                           otherwise
     *
     * @returns {Array<TooltipFormula>}
     */
    getTooltipFormula(formula, isColumn) {
        if (getNumberOfPivotFormulas(formula) !== 1) {
            return [];
        }
        const { functionName, args } = getFirstPivotFunction(formula);
        const evaluatedArgs = args
            .map(astToFormula)
            .map((arg) => this.getters.evaluateFormula(arg));
        const pivotId = evaluatedArgs[0];
        if (functionName === "ODOO.PIVOT") {
            return this._tooltipFormatPivot(pivotId, evaluatedArgs, isColumn);
        } else if (functionName === "ODOO.PIVOT.HEADER") {
            return this._tooltipFormatPivotHeader(pivotId, evaluatedArgs);
        }
        return [];
    }

    // ---------------------------------------------------------------------
    // Autofill
    // ---------------------------------------------------------------------

    /**
     * Get the next value to autofill from a pivot value ("=PIVOT()")
     *
     * Here are the possibilities:
     * 1) LEFT-RIGHT
     *  - Working on a date value, with one level of group by in the header
     *      => Autofill the date, without taking care of headers
     *  - Targeting a row-header
     *      => Creation of a PIVOT.HEADER with the value of the current rows
     *  - Targeting outside the pivot (before the row header and after the
     *    last col)
     *      => Return empty string
     *  - Targeting a value cell
     *      => Autofill by changing the cols
     * 2) UP-DOWN
     *  - Working on a date value, with one level of group by in the header
     *      => Autofill the date, without taking care of headers
     *  - Targeting a col-header
     *      => Creation of a PIVOT.HEADER with the value of the current cols,
     *         with the given increment
     *  - Targeting outside the pivot (after the last row)
     *      => Return empty string
     *  - Targeting a value cell
     *      => Autofill by changing the rows
     *
     * @param {string} pivotId Id of the pivot
     * @param {Array<string>} args args of the pivot formula
     * @param {boolean} isColumn True if the direction is left/right, false
     *                           otherwise
     * @param {number} increment Increment of the autofill
     *
     * @private
     *
     * @returns {string}
     */
    _autofillPivotValue(pivotId, args, isColumn, increment) {
        const currentElement = this._getCurrentValueElement(pivotId, args);
        const pivotModel = this.getters.getSpreadsheetPivotModel(pivotId);
        const table = pivotModel.getTableStructure();
        const isDate = pivotModel.isGroupedOnlyByOneDate(isColumn ? "COLUMN" : "ROW");
        let cols = [];
        let rows = [];
        let measure;
        if (isColumn) {
            // LEFT-RIGHT
            rows = currentElement.rows;
            if (isDate) {
                // Date
                const group = pivotModel.getGroupOfFirstDate("COLUMN");
                cols = currentElement.cols;
                cols[0] = this._incrementDate(cols[0], group, increment);
                measure = cols.pop();
            } else {
                const currentColIndex = table.getColMeasureIndex(currentElement.cols);
                if (currentColIndex === -1) {
                    return "";
                }
                const nextColIndex = currentColIndex + increment;
                if (nextColIndex === -1) {
                    // Targeting row-header
                    return this._autofillRowFromValue(pivotId, currentElement);
                }
                if (nextColIndex < -1 || nextColIndex >= table.getColWidth()) {
                    // Outside the pivot
                    return "";
                }
                // Targeting value
                const measureCell = table.getCellFromMeasureRowAtIndex(nextColIndex);
                cols = [...measureCell.values];
                measure = cols.pop();
            }
        } else {
            // UP-DOWN
            cols = currentElement.cols;
            if (isDate) {
                // Date
                if (currentElement.rows.length === 0) {
                    return "";
                }
                const group = pivotModel.getGroupOfFirstDate("ROW");
                rows = currentElement.rows;
                rows[0] = this._incrementDate(rows[0], group, increment);
            } else {
                const currentRowIndex = table.getRowIndex(currentElement.rows);
                if (currentRowIndex === -1) {
                    return "";
                }
                const nextRowIndex = currentRowIndex + increment;
                if (nextRowIndex < 0) {
                    // Targeting col-header
                    return this._autofillColFromValue(pivotId, nextRowIndex, currentElement);
                }
                if (nextRowIndex >= table.getRowHeight()) {
                    // Outside the pivot
                    return "";
                }
                // Targeting value
                rows = [...table.getCellsFromRowAtIndex(nextRowIndex).values];
            }
            measure = cols.pop();
        }
        return makePivotFormula("ODOO.PIVOT", this._buildArgs(pivotId, measure, rows, cols));
    }
    /**
     * Get the next value to autofill from a pivot header ("=PIVOT.HEADER()")
     * which is a col.
     *
     * Here are the possibilities:
     * 1) LEFT-RIGHT
     *  - Working on a date value, with one level of group by in the header
     *      => Autofill the date, without taking care of headers
     *  - Targeting outside (before the first col after the last col)
     *      => Return empty string
     *  - Targeting a col-header
     *      => Creation of a PIVOT.HEADER with the value of the new cols
     * 2) UP-DOWN
     *  - Working on a date value, with one level of group by in the header
     *      => Replace the date in the headers and autocomplete as usual
     *  - Targeting a cell (after the last col and before the last row)
     *      => Autofill by adding the corresponding rows
     *  - Targeting a col-header (after the first col and before the last
     *    col)
     *      => Creation of a PIVOT.HEADER with the value of the new cols
     *  - Targeting outside the pivot (before the first col of after the
     *    last row)
     *      => Return empty string
     *
     * @param {string} pivotId Id of the pivot
     * @param {Array<string>} args args of the pivot.header formula
     * @param {boolean} isColumn True if the direction is left/right, false
     *                           otherwise
     * @param {number} increment Increment of the autofill
     *
     * @private
     *
     * @returns {string}
     */
    _autofillPivotColHeader(pivotId, args, isColumn, increment) {
        const pivotModel = this.getters.getSpreadsheetPivotModel(pivotId);
        const table = pivotModel.getTableStructure();
        const currentElement = this._getCurrentHeaderElement(pivotId, args);
        const currentIndex = table.getColMeasureIndex(currentElement.cols);
        const isDate = pivotModel.isGroupedOnlyByOneDate("COLUMN");
        if (isColumn) {
            // LEFT-RIGHT
            let groupValues;
            if (isDate) {
                // Date
                const group = pivotModel.getGroupOfFirstDate("COLUMN");
                groupValues = currentElement.cols;
                groupValues[0] = this._incrementDate(groupValues[0], group, increment);
            } else {
                const colIndex = currentElement.cols.length - 1;
                const nextIndex = currentIndex + increment;
                if (
                    currentIndex === -1 ||
                    nextIndex < 0 ||
                    nextIndex >= table.getColHeight()
                ) {
                    // Outside the pivot
                    return "";
                }
                // Targeting a col.header
                groupValues = [];
                const currentCols = table.getCellFromMeasureRowWithDomain(currentElement.cols);
                for (let i = 0; i <= colIndex;i++) {
                    groupValues.push(currentCols.values[i]);
                }
            }
            return makePivotFormula("ODOO.PIVOT.HEADER", this._buildArgs(pivotId, undefined, [], groupValues));
        } else {
            // UP-DOWN
            const colIndex = currentElement.cols.length - 1;
            const nextIndex = colIndex + increment;
            const groupLevels = pivotModel.getNumberOfColGroupBys();
            if (nextIndex < 0 || nextIndex >= groupLevels + 1 + table.getRowHeight()) {
                // Outside the pivot
                return "";
            }
            if (nextIndex >= groupLevels + 1) {
                // Targeting a value
                const rowIndex = nextIndex - groupLevels - 1;
                const measureCell = table.getCellFromMeasureRowAtIndex(currentIndex);
                const cols = [...measureCell.values];
                const measure = cols.pop();
                const rows = [...table.getCellsFromRowAtIndex(rowIndex).values];
                return makePivotFormula("ODOO.PIVOT", this._buildArgs(pivotId, measure, rows, cols));
            } else {
                // Targeting a col.header
                const cols = [];
                const currentCols = table.getCellFromMeasureRowWithDomain(currentElement.cols);
                for (let i = 0; i <= nextIndex;i++) {
                    cols.push(currentCols.values[i]);
                }
                return makePivotFormula("ODOO.PIVOT.HEADER", this._buildArgs(pivotId, undefined, [], cols));
            }
        }
    }
    /**
     * Get the next value to autofill from a pivot header ("=PIVOT.HEADER()")
     * which is a row.
     *
     * Here are the possibilities:
     * 1) LEFT-RIGHT
     *  - Targeting outside (LEFT or after the last col)
     *      => Return empty string
     *  - Targeting a cell
     *      => Autofill by adding the corresponding cols
     * 2) UP-DOWN
     *  - Working on a date value, with one level of group by in the header
     *      => Autofill the date, without taking care of headers
     *  - Targeting a row-header
     *      => Creation of a PIVOT.HEADER with the value of the new rows
     *  - Targeting outside the pivot (before the first row of after the
     *    last row)
     *      => Return empty string
     *
     * @param {string} pivotId Id of the pivot
     * @param {Array<string>} args args of the pivot.header formula
     * @param {boolean} isColumn True if the direction is left/right, false
     *                           otherwise
     * @param {number} increment Increment of the autofill
     *
     * @private
     *
     * @returns {string}
     */
    _autofillPivotRowHeader(pivotId, args, isColumn, increment) {
        const pivotModel = this.getters.getSpreadsheetPivotModel(pivotId);
        const table = pivotModel.getTableStructure();
        const currentElement = this._getCurrentHeaderElement(pivotId, args);
        const currentIndex = table.getRowIndex(currentElement.rows);
        const isDate = pivotModel.isGroupedOnlyByOneDate("ROW");
        if (isColumn) {
            const colIndex = increment - 1;
            // LEFT-RIGHT
            if (colIndex < 0 || colIndex >= table.getColWidth()) {
                // Outside the pivot
                return "";
            }
            const measureCell = table.getCellFromMeasureRowAtIndex(colIndex);
            const values = [...measureCell.values];
            const measure = values.pop();
            return makePivotFormula("ODOO.PIVOT", 
                this._buildArgs(pivotId, measure, currentElement.rows, values)
            );
        } else {
            // UP-DOWN
            let rows;
            if (isDate) {
                // Date
                const group = pivotModel.getGroupOfFirstDate("ROW");
                rows = currentElement.rows;
                rows[0] = this._incrementDate(rows[0], group, increment);
            } else {
                const nextIndex = currentIndex + increment;
                if (currentIndex === -1 || nextIndex < 0 || nextIndex >= table.getRowHeight()) {
                    return "";
                }
                rows = [...table.getCellsFromRowAtIndex(nextIndex).values];
            }
            return makePivotFormula("ODOO.PIVOT.HEADER", this._buildArgs(pivotId, undefined, rows, []));
        }
    }
    /**
     * Create a col header from a value
     *
     * @param {string} pivotId Id of the pivot
     * @param {number} nextIndex Index of the target column
     * @param {CurrentElement} currentElement Current element (rows and cols)
     *
     * @private
     *
     * @returns {string}
     */
    _autofillColFromValue(pivotId, nextIndex, currentElement) {
        const pivotModel = this.getters.getSpreadsheetPivotModel(pivotId);
        const table = pivotModel.getTableStructure();
        const groupIndex = table.getColMeasureIndex(currentElement.cols);
        if (groupIndex < 0) {
            return "";
        }
        const levels = pivotModel.getNumberOfColGroupBys();
        const index = levels + 1 + nextIndex;
        if (index < 0 || index >= levels + 1) {
            return "";
        }
        const cols = [];
        for (let i = 0; i <= index;i++) {
            cols.push(currentElement.cols[i]);
        }
        return makePivotFormula("ODOO.PIVOT.HEADER", this._buildArgs(pivotId, undefined, [], cols));
    }
    /**
     * Create a row header from a value
     *
     * @param {string} pivotId Id of the pivot
     * @param {CurrentElement} currentElement Current element (rows and cols)
     *
     * @private
     *
     * @returns {string}
     */
    _autofillRowFromValue(pivotId, currentElement) {
        const rows = currentElement.rows;
        if (!rows) {
            return "";
        }
        return makePivotFormula("ODOO.PIVOT.HEADER", this._buildArgs(pivotId, undefined, rows, []));
    }
    /**
     * Parse the arguments of a pivot function to find the col values and
     * the row values of a PIVOT.HEADER function
     *
     * @param {string} pivotId Id of the pivot
     * @param {Array<string>} args Args of the pivot.header formula
     *
     * @private
     *
     * @returns {CurrentElement}
     */
    _getCurrentHeaderElement(pivotId, args) {
        const definition = this.getters.getPivotDefinition(pivotId);
        const values = this._parseArgs(args.slice(1));
        const cols = this._getFieldValues(
            [...definition.colGroupBys, "measure"],
            values
        );
        const rows = this._getFieldValues(definition.rowGroupBys, values);
        return { cols, rows };
    }
    /**
     * Parse the arguments of a pivot function to find the col values and
     * the row values of a PIVOT function
     *
     * @param {string} pivotId Id of the pivot
     * @param {Array<string>} args Args of the pivot formula
     *
     * @private
     *
     * @returns {CurrentElement}
     */
    _getCurrentValueElement(pivotId, args) {
        const definition = this.getters.getPivotDefinition(pivotId);
        const values = this._parseArgs(args.slice(2));
        const cols = this._getFieldValues(definition.colGroupBys, values);
        cols.push(args[1]); // measure
        const rows = this._getFieldValues(definition.rowGroupBys, values);
        return { cols, rows };
    }
    /**
     * Return the values for the fields which are present in the list of
     * fields
     *
     * ex: fields: ["create_date"]
     *     values: { create_date: "01/01", stage_id: 1 }
     *      => ["01/01"]
     *
     * @param {Array<string>} fields List of fields
     * @param {Object} values Association field-values
     *
     * @private
     * @returns {Array<string>}
     */
    _getFieldValues(fields, values) {
        return fields.filter((field) => field in values).map((field) => values[field]);
    }
    /**
     * Increment a date with a given increment and interval (group)
     *
     * @param {string} date
     * @param {string} group (day, week, month, ...)
     * @param {number} increment
     *
     * @private
     * @returns {string}
     */
    _incrementDate(date, group, increment) {
        const format = formats[group].out;
        const interval = formats[group].interval;
        const dateMoment = moment(date, format);
        return dateMoment.isValid() ? dateMoment.add(increment, interval).format(format) : date;
    }
    /**
     * Create a structure { field: value } from the arguments of a pivot
     * function
     *
     * @param {Array<string>} args
     *
     * @private
     * @returns {Object}
     */
    _parseArgs(args) {
        const values = {};
        for (let i = 0; i < args.length; i += 2) {
            values[args[i]] = args[i + 1];
        }
        return values;
    }

    // ---------------------------------------------------------------------
    // Tooltips
    // ---------------------------------------------------------------------

    /**
     * Get the tooltip for a pivot formula
     *
     * @param {string} pivotId Id of the pivot
     * @param {Array<string>} args
     * @param {boolean} isColumn True if the direction is left/right, false
     *                           otherwise
     * @private
     *
     * @returns {Array<TooltipFormula>}
     */
    _tooltipFormatPivot(pivotId, args, isColumn) {
        const tooltips = [];
        const definition = this.getters.getPivotDefinition(pivotId);
        const model = this.getters.getSpreadsheetPivotModel(pivotId);
        const values = this._parseArgs(args.slice(2));
        for (let [fieldName, value] of Object.entries(values)) {
            if (
                (isColumn && model.isColumnGroupBy(fieldName)) ||
                (!isColumn && model.isRowGroupBy(fieldName))
            ) {
                tooltips.push({ value: model.getPivotHeaderValue([fieldName, value])});
            }
        }
        if (definition.measures.length !== 1 && isColumn) {
            const measure = args[1];
            tooltips.push({
                value: model.getGroupByDisplayLabel("measure", measure),
            });
        }
        return tooltips;
    }
    /**
     * Get the tooltip for a pivot header formula
     *
     * @param {string} pivotId Id of the pivot
     * @param {Array<string>} args
     *
     * @private
     *
     * @returns {Array<TooltipFormula>}
     */
    _tooltipFormatPivotHeader(pivotId, args) {
        const tooltips = [];
        const values = this._parseArgs(args.slice(1));
        const model = this.getters.getSpreadsheetPivotModel(pivotId);
        if (Object.keys(values).length === 0) {
            return [{ value: _t("Total") }];
        }
        for (let [fieldName, value] of Object.entries(values)) {
            tooltips.push({ value: model.getPivotHeaderValue([fieldName, value])});
        }
        return tooltips;
    }

    // ---------------------------------------------------------------------
    // Helpers
    // ---------------------------------------------------------------------

    /**
     * Create the args from pivot, measure, rows and cols
     * if measure is undefined, it's not added
     *
     * @param {string} pivotId Id of the pivot
     * @param {string} measure
     * @param {Object} rows
     * @param {Object} cols
     *
     * @private
     * @returns {Array<string>}
     */
    _buildArgs(pivotId, measure, rows, cols) {
        const { rowGroupBys, measures } = this.getters.getPivotDefinition(pivotId);
        const args = [pivotId];
        if (measure) {
            args.push(measure);
        }
        for (let index in rows) {
            args.push(rowGroupBys[index]);
            args.push(rows[index]);
        }
        if (cols.length === 1 && measures.map((x) => x.field).includes(cols[0])) {
            args.push("measure");
            args.push(cols[0]);
        } else {
            const pivotModel = this.getters.getSpreadsheetPivotModel(pivotId);
            for (let index in cols) {
                args.push(pivotModel.getGroupByAtIndex("COLUMN", index) || "measure");
                args.push(cols[index]);
            }
        }
        return args;
    }
}

PivotAutofillPlugin.getters = ["getPivotNextAutofillValue", "getTooltipFormula"];
