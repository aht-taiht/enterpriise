/** @odoo-module */

import { _t, _lt } from "@web/legacy/js/services/core";
import * as spreadsheet from "@odoo/o-spreadsheet";
import { REINSERT_LIST_CHILDREN } from "../list/list_actions";
import { INSERT_PIVOT_CELL_CHILDREN, REINSERT_PIVOT_CHILDREN } from "../pivot/pivot_actions";
const { topbarMenuRegistry } = spreadsheet.registries;

//--------------------------------------------------------------------------
// Spreadsheet context menu items
//--------------------------------------------------------------------------

topbarMenuRegistry.addChild("new_sheet", ["file"], {
    name: _lt("New"),
    sequence: 10,
    isVisible: (env) => !env.isDashboardSpreadsheet,
    execute: (env) => env.newSpreadsheet(),
    icon: "o-spreadsheet-Icon.NEW",
});
topbarMenuRegistry.addChild("make_copy", ["file"], {
    name: _lt("Make a copy"),
    sequence: 20,
    isVisible: (env) => !env.isDashboardSpreadsheet,
    execute: (env) => env.makeCopy(),
    icon: "o-spreadsheet-Icon.COPY_FILE",
});
topbarMenuRegistry.addChild("save_as_template", ["file"], {
    name: _lt("Save as template"),
    sequence: 40,
    isVisible: (env) => !env.isDashboardSpreadsheet,
    execute: (env) => env.saveAsTemplate(),
    icon: "o-spreadsheet-Icon.SAVE",
});
topbarMenuRegistry.addChild("download", ["file"], {
    name: _lt("Download"),
    sequence: 50,
    execute: (env) => env.download(),
    isReadonlyAllowed: true,
    icon: "o-spreadsheet-Icon.DOWNLOAD",
});

topbarMenuRegistry.addChild("clear_history", ["file"], {
    name: _lt("Clear history"),
    sequence: 60,
    isVisible: (env) => env.debug,
    execute: (env) => {
        env.model.session.snapshot(env.model.exportData());
        env.model.garbageCollectExternalResources();
        window.location.reload();
    },
    icon: "o-spreadsheet-Icon.CLEAR_HISTORY",
});

topbarMenuRegistry.addChild("download_as_json", ["file"], {
    name: _lt("Download as JSON"),
    sequence: 70,
    isVisible: (env) => env.debug,
    execute: (env) => env.downloadAsJson(),
    isReadonlyAllowed: true,
    icon: "o-spreadsheet-Icon.DOWNLOAD_AS_JSON",
});

topbarMenuRegistry.addChild("data_sources_data", ["data"], (env) => {
    const pivots = env.model.getters.getPivotIds();
    const children = pivots.map((pivotId, index) => ({
        id: `item_pivot_${pivotId}`,
        name: env.model.getters.getPivotDisplayName(pivotId),
        sequence: 100 + index,
        execute: (env) => {
            env.model.dispatch("SELECT_PIVOT", { pivotId: pivotId });
            env.openSidePanel("PIVOT_PROPERTIES_PANEL", {});
        },
        icon: "o-spreadsheet-Icon.PIVOT",
        separator: index === env.model.getters.getPivotIds().length - 1,
    }));
    const lists = env.model.getters.getListIds().map((listId, index) => {
        return {
            id: `item_list_${listId}`,
            name: env.model.getters.getListDisplayName(listId),
            sequence: 100 + index + pivots.length,
            execute: (env) => {
                env.model.dispatch("SELECT_ODOO_LIST", { listId: listId });
                env.openSidePanel("LIST_PROPERTIES_PANEL", {});
            },
            icon: "o-spreadsheet-Icon.LIST",
            separator: index === env.model.getters.getListIds().length - 1,
        };
    });
    return children.concat(lists).concat([
        {
            id: "refresh_all_data",
            name: _t("Refresh all data"),
            sequence: 1000,
            execute: (env) => {
                env.model.dispatch("REFRESH_ALL_DATA_SOURCES");
            },
            separator: true,
            icon: "o-spreadsheet-Icon.REFRESH_DATA",
        },
    ]);
});

topbarMenuRegistry.addChild("insert_pivot", ["data"], {
    name: _t("Insert pivot"),
    sequence: 1020,
    icon: "o-spreadsheet-Icon.INSERT_PIVOT",
    isVisible: (env) => env.model.getters.getPivotIds().length,
});

topbarMenuRegistry.addChild("reinsert_pivot", ["data", "insert_pivot"], {
    id: "reinsert_pivot",
    name: _t("Re-insert pivot"),
    sequence: 1,
    children: [REINSERT_PIVOT_CHILDREN],
    isVisible: (env) => env.model.getters.getPivotIds().length,
});
topbarMenuRegistry.addChild("insert_pivot_cell", ["data", "insert_pivot"], {
    id: "insert_pivot_cell",
    name: _t("Insert pivot cell"),
    sequence: 2,
    children: [INSERT_PIVOT_CELL_CHILDREN],
    isVisible: (env) => env.model.getters.getPivotIds().length,
});

topbarMenuRegistry.addChild("reinsert_list", ["data"], {
    id: "reinsert_list",
    name: _t("Re-insert list"),
    sequence: 1021,
    children: [REINSERT_LIST_CHILDREN],
    isVisible: (env) => env.model.getters.getListIds().length,
    icon: "o-spreadsheet-Icon.INSERT_LIST",
});
