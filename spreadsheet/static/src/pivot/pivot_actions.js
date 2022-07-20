/** @odoo-module */
import spreadsheet from "@spreadsheet/o_spreadsheet/o_spreadsheet_extended";
import { getFirstPivotFunction, getNumberOfPivotFormulas } from "./pivot_helpers";

const { astToFormula } = spreadsheet;

export const SEE_RECORDS_PIVOT = async (env) => {
    const cell = env.model.getters.getActiveCell();
    const { col, row, sheetId } = env.model.getters.getCellPosition(cell.id);
    const { args, functionName } = getFirstPivotFunction(cell.content);
    const evaluatedArgs = args
        .map(astToFormula)
        .map((arg) => env.model.getters.evaluateFormula(arg));
    const pivotId = env.model.getters.getPivotIdFromPosition(sheetId, col, row);
    const { model } = env.model.getters.getPivotDefinition(pivotId);
    const pivotModel = await env.model.getters.getAsyncSpreadsheetPivotModel(pivotId);
    const slice = functionName === "ODOO.PIVOT.HEADER" ? 1 : 2;
    let argsDomain = evaluatedArgs.slice(slice);
    if (argsDomain[argsDomain.length - 2] === "measure") {
        // We have to remove the measure from the domain
        argsDomain = argsDomain.slice(0, argsDomain.length - 2);
    }
    const domain = pivotModel.getPivotCellDomain(argsDomain);
    const name = await env.model.getters.getSpreadsheetPivotDataSource(pivotId).getModelLabel();
    await env.services.action.doAction({
        type: "ir.actions.act_window",
        name,
        res_model: model,
        view_mode: "list",
        views: [[false, "list"]],
        target: "current",
        domain,
    });
};

export const SEE_RECORDS_PIVOT_VISIBLE = (env) => {
    const cell = env.model.getters.getActiveCell();
    return (
        cell &&
        cell.evaluated.value !== "" &&
        !cell.evaluated.error &&
        getNumberOfPivotFormulas(cell.content) === 1
    );
};
