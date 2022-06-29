/** @odoo-module */

import { InsertListSpreadsheetMenu as LegacyInsertListSpreadsheetMenu } from "@documents_spreadsheet/assets/components/insert_list_spreadsheet_menu_legacy";
import { InsertListSpreadsheetMenu } from "@documents_spreadsheet/assets/components/insert_list_spreadsheet_menu_owl";
import { makeFakeUserService } from "@web/../tests/helpers/mock_services";
import { useLegacyViews } from "@web/../tests/legacy/legacy_setup";
import { loadJS } from "@web/core/assets";
import { dialogService } from "@web/core/dialog/dialog_service";
import { hotkeyService } from "@web/core/hotkeys/hotkey_service";
import { ormService } from "@web/core/orm_service";
import { registry } from "@web/core/registry";
import { uiService } from "@web/core/ui/ui_service";
import { viewService } from "@web/views/view_service";
import * as LegacyFavoriteMenu from "web.FavoriteMenu";
import { spreadsheetCollaborativeService } from "../../src/bundle/o_spreadsheet/collaborative/spreadsheet_collaborative_service";
import MockSpreadsheetCollaborativeChannel from "./mock_spreadsheet_collaborative_channel";

const legacyFavoriteMenuRegistry = LegacyFavoriteMenu.registry;
const serviceRegistry = registry.category("services");

export async function prepareWebClientForSpreadsheet() {
    await loadJS("/web/static/lib/Chart/Chart.js");
    serviceRegistry.add("spreadsheet_collaborative", makeFakeSpreadsheetService(), { force: true });
    serviceRegistry.add(
        "user",
        makeFakeUserService(() => true),
        { force: true }
    );
    serviceRegistry.add("hotkey", hotkeyService);
    serviceRegistry.add("dialog", dialogService);
    serviceRegistry.add("ui", uiService);
    serviceRegistry.add("view", viewService, { force: true }); // #action-serv-leg-compat-js-class
    serviceRegistry.add("orm", ormService, { force: true }); // #action-serv-leg-compat-js-class
    legacyFavoriteMenuRegistry.add(
        "insert-list-spreadsheet-menu",
        LegacyInsertListSpreadsheetMenu,
        5
    );
    registry.category("favoriteMenu").add(
        "insert-list-spreadsheet-menu",
        {
            Component: InsertListSpreadsheetMenu,
            groupNumber: 4,
            isDisplayed: ({ config, isSmall }) => 
                !isSmall && config.actionType === "ir.actions.act_window" && config.viewType === "list"
        },
        { sequence: 5 },
    );
    useLegacyViews();
}

export function makeFakeSpreadsheetService() {
    return {
        ...spreadsheetCollaborativeService,
        start() {
            const fakeSpreadsheetService = spreadsheetCollaborativeService.start(...arguments);
            fakeSpreadsheetService.getCollaborativeChannel = () =>
                new MockSpreadsheetCollaborativeChannel();
            return fakeSpreadsheetService;
        },
    };
}

/**
 * Return the odoo spreadsheet component
 * @param {*} actionManager
 * @returns {Component}
 */
export function getSpreadsheetComponent(actionManager) {
    return actionManager.spreadsheet;
}

/**
 * Return the o-spreadsheet component
 * @param {*} actionManager
 * @returns {Component}
 */
export function getOSpreadsheetComponent(actionManager) {
    return getSpreadsheetComponent(actionManager).spreadsheet;
}

/**
 * Return the o-spreadsheet Model
 */
export function getSpreadsheetActionModel(actionManager) {
    return getOSpreadsheetComponent(actionManager).model;
}

export function getSpreadsheetActionTransportService(actionManager) {
    return actionManager.transportService;
}

export function getSpreadsheetActionEnv(actionManager) {
    const model = getSpreadsheetActionModel(actionManager);
    const component = getSpreadsheetComponent(actionManager);
    const oComponent = getOSpreadsheetComponent(actionManager);
    return Object.assign(Object.create(component.env), {
        model,
        openSidePanel: oComponent.openSidePanel.bind(oComponent),
    });
}
