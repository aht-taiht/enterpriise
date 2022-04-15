/** @odoo-module alias=documents_spreadsheet.pivot_utils default=0 **/

import { _t } from "web.core";
import { formats } from "../o_spreadsheet/constants";
import { getOdooFunctions } from "../o_spreadsheet/odoo_functions_helpers";


export const pivotFormulaRegex = /^=.*PIVOT/;

export const PERIODS = {
  day: _t("Day"),
  week: _t("Week"),
  month: _t("Month"),
  quarter: _t("Quarter"),
  year: _t("Year"),
};

//--------------------------------------------------------------------------
// Public
//--------------------------------------------------------------------------

/**
 * Format a data
 *
 * @param {string} field fieldName:interval
 * @param {string} value
 */
export function formatDate(field, value) {
  const interval = field.split(":")[1] || "month";
  const output = formats[interval].display;
  const input = formats[interval].out;
  const date = moment(value, input);
  return date.isValid() ? date.format(output) : _t("(Undefined)");
}

/**
 * Parse a spreadsheet formula and detect the number of PIVOT functions that are
 * present in the given formula.
 *
 * @param {string} formula
 *
 * @returns {number}
 */
export function getNumberOfPivotFormulas(formula) {
  return getOdooFunctions(formula, (functionName) =>
    ["PIVOT", "PIVOT.HEADER", "PIVOT.POSITION"].includes(functionName)
  ).filter((fn) => fn.isMatched).length;
}

/**
 * Get the first Pivot function description of the given formula.
 *
 * @param {string} formula
 *
 * @returns {import("../o_spreadsheet/odoo_functions_helpers").OdooFunctionDescription|undefined}
 */
export function getFirstPivotFunction(formula) {
  return getOdooFunctions(formula, (functionName) =>
    ["PIVOT", "PIVOT.HEADER", "PIVOT.POSITION"].includes(functionName)
  ).find((fn) => fn.isMatched);
}
