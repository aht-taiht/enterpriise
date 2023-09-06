/** @odoo-module */

import { browser } from "@web/core/browser/browser";
import { Domain } from "@web/core/domain";
import { registry } from "@web/core/registry";
import { ormService } from "@web/core/orm_service";
import { serializeDateTime, serializeDate, deserializeDate } from "@web/core/l10n/dates";
import {
    click,
    editInput,
    getFixture,
    getNodesTextContent,
    nextTick,
    patchWithCleanup,
    triggerEvent,
    clickOpenM2ODropdown,
} from "@web/../tests/helpers/utils";
import { toggleSearchBarMenu } from "@web/../tests/search/helpers";

import { getPyEnv } from "@bus/../tests/helpers/mock_python_environment";
import { start } from "@mail/../tests/helpers/test_utils";

import { setupTestEnv } from "@hr_timesheet/../tests/hr_timesheet_common_tests";
import { timerService } from "@timer/services/timer_service";
import { timesheetGridUOMService } from "@timesheet_grid/services/timesheet_grid_uom_service";

import { TimesheetGridSetupHelper } from "./helpers";

const { DateTime } = luxon;

let serverData, target, timesheetGridSetup;

QUnit.module("Views", (hooks) => {
    hooks.beforeEach(async () => {
        timesheetGridSetup = new TimesheetGridSetupHelper(true);
        const result = await timesheetGridSetup.setupTimesheetGrid();
        serverData = result.serverData;
        let grid = serverData.views["analytic.line,false,grid"].replace(
            'js_class="timesheet_grid"',
            'js_class="timer_timesheet_grid"'
        );
        grid = grid.replace('widget="float_time"', 'widget="timesheet_uom"');
        serverData.views["analytic.line,false,grid"] = grid;
        grid = serverData.views["analytic.line,1,grid"].replace(
            'js_class="timesheet_grid"',
            'js_class="timer_timesheet_grid"'
        );
        grid = grid.replace('widget="float_time"', 'widget="timesheet_uom"');
        serverData.views["analytic.line,1,grid"] = grid;

        target = getFixture();
        setupTestEnv();
        const serviceRegistry = registry.category("services");
        serviceRegistry.add("orm", ormService, { force: true });
        serviceRegistry.add("timer", timerService, { force: true });
        const gridComponentsRegistry = registry.category("grid_components");
        if (gridComponentsRegistry.contains("timesheet_uom")) {
            gridComponentsRegistry.remove("timesheet_uom"); // the component will be added by timesheet_grid_uom_service
        }
        serviceRegistry.add("timesheet_grid_uom", timesheetGridUOMService, { force: true });
    });

    QUnit.module("TimerTimesheetGridView");

    QUnit.test("sample data in timesheet timer grid view", async function (assert) {
        serverData.views["analytic.line,false,grid"] = serverData.views[
            "analytic.line,false,grid"
        ].replace('js_class="timer_timesheet_grid"', 'js_class="timer_timesheet_grid" sample="1"');
        const { openView } = await start({
            serverData,
            async mockRPC(route, args) {
                if (args.method === "get_running_timer") {
                    return {
                        step_timer: 30,
                    };
                } else if (args.method === "action_start_new_timesheet_timer") {
                    return false;
                } else if (args.method === "get_daily_working_hours") {
                    assert.strictEqual(args.model, "hr.employee");
                    return {};
                } else if (args.method === "get_server_time") {
                    assert.strictEqual(args.model, "timer.timer");
                    return serializeDateTime(DateTime.now());
                } else if (args.method === "get_last_validated_timesheet_date") {
                    return false;
                }
                return timesheetGridSetup.mockTimesheetGridRPC(route, args);
            },
        });

        await openView({
            res_model: "analytic.line",
            views: [[false, "grid"]],
            domain: Domain.FALSE.toString(),
            context: { group_by: ["project_id", "task_id"] },
        });

        await click(target, ".o_grid_navigation_buttons button[data-hotkey=t]");

        assert.containsOnce(
            target,
            ".o_grid_view",
            "The view should be correctly rendered with the sample data enabled when no data is found"
        );
    });

    QUnit.test("basic timesheet timer grid view", async function (assert) {
        const { openView } = await start({
            serverData,
            async mockRPC(route, args) {
                if (args.method === "get_running_timer") {
                    return {
                        step_timer: 30,
                    };
                } else if (args.method === "action_start_new_timesheet_timer") {
                    return false;
                } else if (args.method === "get_daily_working_hours") {
                    assert.strictEqual(args.model, "hr.employee");
                    return {};
                } else if (args.method === "get_server_time") {
                    assert.strictEqual(args.model, "timer.timer");
                    return serializeDateTime(DateTime.now());
                } else if (args.method === "action_timer_unlink") {
                    return null;
                } else if (args.method === "get_last_validated_timesheet_date") {
                    return "2017-01-25";
                }
                return timesheetGridSetup.mockTimesheetGridRPC(route, args);
            },
        });

        await openView({
            res_model: "analytic.line",
            views: [[false, "grid"]],
            context: { group_by: ["project_id", "task_id"] },
        });

        assert.containsOnce(target, ".timesheet-timer", "should have rendered the timer header");
        assert.containsOnce(
            target,
            ".btn_start_timer",
            "should have rendered the start timer button"
        );
        assert.containsN(target, ".o_grid_row_title", 5, "should have 5 rows rendered");
        assert.containsN(
            target,
            "button.btn_timer_line",
            5,
            "should have rendered a start button before each line"
        );
        const timerButtonsTextList = getNodesTextContent(
            target.querySelectorAll("button.btn_timer_line")
        );
        assert.deepEqual(
            timerButtonsTextList,
            timerButtonsTextList.map((text) => text.toUpperCase()),
            "The character displayed in the button should be in uppercase"
        );
        assert.containsNone(
            target,
            "button.btn_timer_line.btn-danger",
            "No row with a running timer"
        );

        await click(target, ".btn_start_timer");
        assert.containsNone(
            target,
            ".btn_start_timer",
            "The start button should no longer rendered since a timer will be running"
        );
        assert.containsOnce(
            target,
            ".btn_stop_timer",
            "A stop button should be rendered instead of the start one"
        );
        assert.strictEqual(
            document.activeElement,
            target.querySelector(".btn_stop_timer"),
            "The stop button should be focused"
        );
        assert.containsOnce(
            target,
            ".o_timer_discard button.stop-timer",
            "Cancel button should be rendered to be able to unlink the timer"
        );
        assert.containsOnce(
            target,
            ".timesheet-timer .o_field_widget[name=project_id]",
            "The project_id field should be rendered inside the timer header"
        );
        assert.containsOnce(
            target,
            ".timesheet-timer .o_field_widget[name=task_id]",
            "The task_id field should be rendered inside the timer header"
        );
        assert.containsOnce(
            target,
            ".timesheet-timer .o_field_widget[name=name]",
            "The name field should be rendered inside the timer header"
        );

        await click(target, ".btn_stop_timer");
        assert.containsOnce(
            target,
            ".btn_stop_timer",
            "A stop button should be still there since the project_id is invalid because it is required and empty"
        );
        assert.containsOnce(
            target,
            ".timesheet-timer .o_field_widget.o_field_invalid[name=project_id]",
            "The project_id field should be invalid since it is required and empty"
        );
        await click(target, ".o_timer_discard button");
        assert.containsOnce(
            target,
            ".btn_start_timer",
            "The start button should be rendered since a timer has been dropped"
        );
        assert.containsOnce(
            target,
            ".o_grid_add_line .btn-link",
            "should not have Add a line button"
        );
    });

    QUnit.test("basic timesheet timer grid view without Add a line button", async function (assert) {
        const { openView } = await start({
            serverData,
            async mockRPC(route, args) {
                if (args.method === "get_running_timer") {
                    return {
                        step_timer: 30,
                    };
                } else if (args.method === "action_start_new_timesheet_timer") {
                    return false;
                } else if (args.method === "get_daily_working_hours") {
                    assert.strictEqual(args.model, "hr.employee");
                    return {};
                } else if (args.method === "get_server_time") {
                    assert.strictEqual(args.model, "timer.timer");
                    return serializeDateTime(DateTime.now());
                } else if (args.method === "action_timer_unlink") {
                    return null;
                } else if (args.method === "get_last_validated_timesheet_date") {
                    return "2017-01-30";
                }
                return timesheetGridSetup.mockTimesheetGridRPC(route, args);
            },
        });

        await openView({
            res_model: "analytic.line",
            views: [[false, "grid"]],
            context: { group_by: ["project_id", "task_id"] },
        });

        assert.containsN(
            target,
            ".o_grid_add_line .btn-link",
            0,
            "should not have Add a line button"
        );
    });

    QUnit.test("Timer already running", async function (assert) {
        const pyEnv = getPyEnv();
        pyEnv.mockServer.models["analytic.line"].records.push({
            id: 10,
            unit_amount: 5740 / 3600, // 01:35:40
            project_id: 1,
            task_id: 1,
            name: "Description",
        });
        const { openView } = await start({
            serverData,
            async mockRPC(route, args) {
                if (args.method === "get_running_timer") {
                    return {
                        id: 10,
                        start: 5740, // 01:35:40
                        project_id: 1,
                        task_id: 1,
                        description: "Description",
                        step_timer: 30,
                    };
                } else if (args.method === "action_start_new_timesheet_timer") {
                    return false;
                } else if (args.method === "get_daily_working_hours") {
                    assert.strictEqual(args.model, "hr.employee");
                    return {};
                } else if (args.method === "get_server_time") {
                    assert.strictEqual(args.model, "timer.timer");
                    return serializeDateTime(DateTime.now());
                } else if (args.method === "get_last_validated_timesheet_date") {
                    return false;
                }
                return timesheetGridSetup.mockTimesheetGridRPC(route, args);
            },
        });

        await openView({
            res_model: "analytic.line",
            views: [[false, "grid"]],
            context: { group_by: ["project_id", "task_id"] },
        });
        await nextTick();
        assert.containsOnce(
            target,
            ".btn_stop_timer",
            "should have rendered the stop timer button"
        );
        assert.containsOnce(
            target,
            ".o_grid_row_timer .fa-stop",
            "a row should have the timer running"
        );
        assert.strictEqual(
            target.querySelector(".timesheet-timer .o_field_widget[name=project_id] input").value,
            "P1"
        );
        assert.strictEqual(
            target.querySelector(".timesheet-timer .o_field_widget[name=task_id] input").value,
            "BS task"
        );
        assert.strictEqual(
            target.querySelector(".timesheet-timer .o_field_widget[name=name] input").value,
            "Description"
        );
        await nextTick();
        assert.ok(
            target
                .querySelector(".timesheet-timer div[name=display_timer] span")
                .textContent.includes("01:35:4"),
            "timer is set"
        );
    });

    QUnit.test("stop running timer then restart new one", async function (assert) {
        const pyEnv = getPyEnv();
        pyEnv.mockServer.models["analytic.line"].records.push({
            id: 10,
            unit_amount: 5740 / 3600, // 01:35:40
            project_id: 1,
            task_id: 1,
            name: "Description",
        });
        let timerRunning = true;
        const { openView } = await start({
            serverData,
            async mockRPC(route, args) {
                if (args.method === "get_running_timer") {
                    const runningTimer = {
                        step_timer: 30,
                    };
                    if (timerRunning) {
                        return {
                            ...runningTimer,
                            id: 10,
                            start: 5740, // 01:35:40
                            project_id: 1,
                            task_id: 1,
                            description: "Description",
                        };
                    }
                    return runningTimer;
                } else if (args.method === "action_start_new_timesheet_timer") {
                    return false;
                } else if (args.method === "get_daily_working_hours") {
                    assert.strictEqual(args.model, "hr.employee");
                    return {};
                } else if (args.method === "get_server_time") {
                    assert.strictEqual(args.model, "timer.timer", "get_server_time");
                    return serializeDateTime(DateTime.now());
                } else if (args.method === "action_add_time_to_timer") {
                    return null;
                } else if (args.method === "action_timer_stop") {
                    timerRunning = false;
                    return 0.15;
                } else if (args.method === "get_last_validated_timesheet_date") {
                    return false;
                }
                return timesheetGridSetup.mockTimesheetGridRPC(route, args);
            },
        });

        await openView({
            res_model: "analytic.line",
            views: [[false, "grid"]],
            context: { group_by: ["project_id", "task_id"] },
        });
        assert.containsOnce(
            target,
            ".timesheet-timer .btn_stop_timer",
            "The stop button should be rendered since a timer is running"
        );
        await click(target, ".timesheet-timer .btn_stop_timer");
        assert.containsNone(
            target,
            ".o_grid_row_timer .fa-stop",
            "No row should have a timer running"
        );
        await click(target, ".btn_start_timer");
        assert.containsOnce(target, ".btn_stop_timer");
        assert.containsNone(
            target,
            ".o_grid_row_timer .fa-stop",
            "No row should have a timer running"
        );
        assert.strictEqual(
            target.querySelector(".timesheet-timer .o_field_widget[name=project_id] input").value,
            "",
            "project_id in the timer header should be reset"
        );
        assert.strictEqual(
            target.querySelector(".timesheet-timer .o_field_widget[name=task_id] input").value,
            "",
            "task_id in the timer header should be reset"
        );
        assert.strictEqual(
            target.querySelector(".timesheet-timer .o_field_widget[name=name] input").value,
            "",
            "name field in the timer header should be reset"
        );
        assert.ok(
            target
                .querySelector(".timesheet-timer div[name=display_timer] span")
                .textContent.includes("00:00:0"),
            "timer is reset"
        );
    });

    QUnit.test("drop running timer then restart new one", async function (assert) {
        const pyEnv = getPyEnv();
        pyEnv.mockServer.models["analytic.line"].records.push({
            id: 10,
            unit_amount: 5740 / 3600, // 01:35:40
            project_id: 1,
            task_id: 1,
            name: "Description",
        });
        let timerRunning = true;
        const { openView } = await start({
            serverData,
            async mockRPC(route, args) {
                if (args.method === "get_running_timer") {
                    const runningTimer = {
                        step_timer: 30,
                    };
                    if (timerRunning) {
                        return {
                            ...runningTimer,
                            id: 10,
                            start: 5740, // 01:35:40
                            project_id: 1,
                            task_id: 1,
                            description: "Description",
                        };
                    }
                    return runningTimer;
                } else if (args.method === "action_start_new_timesheet_timer") {
                    return false;
                } else if (args.method === "get_daily_working_hours") {
                    assert.strictEqual(args.model, "hr.employee");
                    return {};
                } else if (args.method === "get_server_time") {
                    assert.strictEqual(
                        args.model,
                        "timer.timer",
                        "get_server_time should be called"
                    );
                    return serializeDateTime(DateTime.now());
                } else if (args.method === "action_add_time_to_timer") {
                    return null;
                } else if (args.method === "action_timer_unlink") {
                    timerRunning = false;
                    return null;
                } else if (args.method === "get_last_validated_timesheet_date") {
                    return false;
                }
                return timesheetGridSetup.mockTimesheetGridRPC(route, args);
            },
        });

        await openView({
            res_model: "analytic.line",
            views: [[false, "grid"]],
            context: { group_by: ["project_id", "task_id"] },
        });

        await triggerEvent(document.activeElement, "", "keydown", { key: "Escape" });
        await nextTick();
        assert.containsNone(
            target,
            ".o_grid_row_timer .fa-stop",
            "No row should have a timer running"
        );
        assert.strictEqual(
            document.activeElement,
            target.querySelector(".btn_start_timer"),
            "start button should be focused"
        );
        await click(document.activeElement);
        assert.containsOnce(target, ".btn_stop_timer");
        assert.containsNone(
            target,
            ".o_grid_row_timer .fa-stop",
            "No row should have a timer running"
        );
        assert.strictEqual(
            target.querySelector(".timesheet-timer .o_field_widget[name=project_id] input").value,
            "",
            "project_id in the timer header should be reset"
        );
        assert.strictEqual(
            target.querySelector(".timesheet-timer .o_field_widget[name=task_id] input").value,
            "",
            "task_id in the timer header should be reset"
        );
        assert.strictEqual(
            target.querySelector(".timesheet-timer .o_field_widget[name=name] input").value,
            "",
            "name field in the timer header should be reset"
        );
        assert.ok(
            target
                .querySelector(".timesheet-timer div[name=display_timer] span")
                .textContent.includes("00:00:0"),
            "timer is reset"
        );
    });

    QUnit.test("Start buttons with groupBy", async function (assert) {
        const { openView } = await start({
            serverData,
            async mockRPC(route, args) {
                if (args.method === "get_running_timer") {
                    return {
                        step_timer: 30,
                    };
                } else if (args.method === "get_daily_working_hours") {
                    assert.strictEqual(args.model, "hr.employee");
                    return {};
                } else if (args.method === "get_last_validated_timesheet_date") {
                    return false;
                }
                return timesheetGridSetup.mockTimesheetGridRPC(route, args);
            },
        });

        await openView({
            res_model: "analytic.line",
            views: [[false, "grid"]],
        });

        await toggleSearchBarMenu(target);
        let groupBys = target.querySelectorAll("span.o_menu_item");
        let groupByProject, groupByTask;
        for (const gb of groupBys) {
            if (gb.textContent === "Task") {
                groupByTask = gb;
            } else if (gb.textContent === "Project") {
                groupByProject = gb;
            }
        }
        await click(groupByTask, "");
        await click(groupByProject, "");
        assert.containsN(
            target,
            "button.btn_timer_line",
            5,
            "The timer button should be rendered for each row displayed in the grid since the project_id is in the rowFields"
        );

        groupBys = target.querySelectorAll("span.o_menu_item");
        for (const gb of groupBys) {
            if (gb.textContent === "Project") {
                groupByProject = gb;
                break;
            }
        }
        await click(groupByProject, ""); // remove the project_id in the groupby
        assert.containsNone(
            target,
            "button.btn_timer_line",
            "The timer button should not be rendered in any row in the grid view since the project_id field is no longer in the rowFields"
        );

        groupBys = target.querySelectorAll("span.o_menu_item");
        groupByProject = groupByTask = null;
        for (const gb of groupBys) {
            if (gb.textContent === "Task") {
                groupByTask = gb;
            } else if (gb.textContent === "Project") {
                groupByProject = gb;
            }
            if (groupByProject && groupByTask) {
                break;
            }
        }
        await click(groupByTask, ""); // remove task_id in the groupby
        await click(groupByProject, ""); // add the project_id in the groupby

        assert.containsN(
            target,
            "button.btn_timer_line",
            2,
            "The timer button should be rendered for each row displayed in the grid since the project_id is in the rowFields"
        );
    });

    QUnit.test("Start button with shift", async function (assert) {
        const pyEnv = getPyEnv();
        let timesheetId = 6;
        const { openView } = await start({
            serverData,
            async mockRPC(route, args) {
                if (args.method === "get_running_timer") {
                    return {
                        step_timer: 30,
                    };
                } else if (args.method === "get_daily_working_hours") {
                    assert.strictEqual(args.model, "hr.employee");
                    return {};
                } else if (args.method === "action_start_new_timesheet_timer") {
                    return false;
                } else if (args.method === "action_add_time_to_timesheet") {
                    const { project_id, task_id } = args.args[1];
                    pyEnv.mockServer.models["analytic.line"].records.push({
                        id: timesheetId,
                        project_id,
                        task_id,
                        date: "2017-01-25",
                        unit_amount: 0.5,
                    });
                    return timesheetId++;
                } else if (args.method === "get_server_time") {
                    assert.strictEqual(args.model, "timer.timer");
                    return serializeDateTime(DateTime.now());
                } else if (args.method === "get_last_validated_timesheet_date") {
                    return false;
                }
                return timesheetGridSetup.mockTimesheetGridRPC(route, args);
            },
        });

        await openView({
            res_model: "analytic.line",
            views: [[false, "grid"]],
            context: { group_by: ["task_id", "project_id"] },
        });

        assert.strictEqual(
            // FIXME: can we assume the test are not translated?
            target.querySelector(".timesheet-timer > div > div").textContent,
            "Press Enter or [a] to launch the timerPress Shift + [A] to add 30 min",
            "The text displayed next to Start button should be the default one"
        );
        // activeElement should be the start button
        triggerEvent(document.activeElement, "", "keydown", { key: "Shift" });
        await nextTick();
        assert.strictEqual(
            target.querySelector(".timesheet-timer > div > div").textContent,
            "Press Enter or [a] to launch the timerPress Shift + [A] to add 30 min",
            "The text displayed next to Start button should be the default one"
        );

        const timerButtonsTextList = getNodesTextContent(
            target.querySelectorAll("button.btn_timer_line")
        );
        assert.deepEqual(
            timerButtonsTextList,
            timerButtonsTextList.map((text) => text.toUpperCase()),
            "The character displayed in the button should be in uppercase"
        );
        assert.containsNone(
            target,
            "button.btn_timer_line .text-lowercase",
            "The letter displayed in each button should be in uppercase"
        );
        await triggerEvent(target, ".btn_start_timer", "keydown", {
            key: "A",
            which: "65",
            shiftKey: true,
        });
        await triggerEvent(target, ".btn_start_timer", "keydown", {
            key: "A",
            which: "65",
            shiftKey: true,
        });
        await triggerEvent(target, ".btn_start_timer", "keydown", {
            key: "A",
            which: "65",
            shiftKey: true,
        });
        const cellEls = target.querySelectorAll(
            ".o_grid_row.o_grid_highlightable:not(.o_grid_row_title,.o_grid_row_total,.o_grid_column_total)"
        );
        let firstTodayCellEl;
        for (const node of cellEls) {
            if (node.querySelector(".bg-info")) {
                firstTodayCellEl = node;
                break;
            }
        }
        assert.strictEqual(firstTodayCellEl.textContent, "1:30");
        await triggerEvent(window, "", "keyup", { key: "Shift" });
        assert.strictEqual(
            target.querySelector(".timesheet-timer > div > div").textContent,
            "Press Enter or [a] to launch the timerPress Shift + [A] to add 30 min"
        );
        assert.containsN(
            target,
            "button.btn_timer_line .text-lowercase",
            5,
            "The character on the button displayed in each row should be in lowercase"
        );
        await click(target, ".timesheet-timer .btn_start_timer");
        await triggerEvent(target, ".btn_stop_timer", "keydown", { key: "Shift" });
        assert.containsN(
            target,
            "button.btn_timer_line .text-lowercase",
            5,
            "The character on the button displayed in each row should still be in lowercase"
        );
    });

    QUnit.test("Start timer from button line", async function (assert) {
        const pyEnv = getPyEnv();
        let timesheetId = 6;
        const { openView } = await start({
            serverData,
            async mockRPC(route, args) {
                if (args.method === "get_running_timer") {
                    return {
                        step_timer: 30,
                    };
                } else if (args.method === "get_daily_working_hours") {
                    assert.strictEqual(args.model, "hr.employee");
                    return {};
                } else if (args.method === "action_start_new_timesheet_timer") {
                    const { project_id, task_id } = args.args[0];
                    if (!project_id) {
                        return false;
                    }
                    const newTimesheet = {
                        id: timesheetId++,
                        project_id,
                        task_id,
                        date: serializeDateTime(DateTime.now()),
                        unit_amount: 0.0,
                    };
                    pyEnv.mockServer.models["analytic.line"].records.push(newTimesheet);
                    return newTimesheet;
                } else if (args.method === "action_add_time_to_timesheet") {
                    const { project_id, task_id } = args.args[1];
                    pyEnv.mockServer.models["analytic.line"].records.push({
                        id: timesheetId,
                        project_id,
                        task_id,
                        date: "2017-01-25",
                        unit_amount: 0.5,
                    });
                    return timesheetId++;
                } else if (args.method === "get_server_time") {
                    assert.strictEqual(args.model, "timer.timer");
                    return serializeDateTime(DateTime.now());
                } else if (args.method === "action_timer_stop") {
                    return null;
                } else if (args.method === "get_last_validated_timesheet_date") {
                    return false;
                }
                return timesheetGridSetup.mockTimesheetGridRPC(route, args);
            },
        });

        await openView({
            res_model: "analytic.line",
            views: [[false, "grid"]],
            context: { group_by: ["task_id", "project_id"] },
        });

        function getRowWithTimerRunningOrNot() {
            const timerButtons = target.querySelectorAll("button.btn_timer_line");
            const timerButtonsHasDangerClass = [];
            for (const button of timerButtons) {
                timerButtonsHasDangerClass.push(button.classList.contains("btn-danger"));
            }
            return timerButtonsHasDangerClass;
        }

        assert.containsOnce(
            target,
            ".btn_start_timer",
            "No timer running so start button should be displayed"
        );
        assert.containsNone(
            target,
            ".btn_stop_timer",
            "No timer running so stop button should not be displayed"
        );
        assert.containsN(
            target,
            ".o_grid_row_title",
            5,
            "5 rows should be displayed in the grid view"
        );
        assert.containsN(
            target,
            ".btn_timer_line",
            5,
            "A timer button should be displayed in each row"
        );
        await click(target.querySelector("button.btn_timer_line"), "");
        assert.containsNone(
            target,
            ".btn_start_timer",
            "A timer should be running and so the start button should not be displayed"
        );
        assert.containsOnce(
            target,
            ".btn_stop_timer",
            "A timer should be running and so the stop button should be displayed instead of start one"
        );
        assert.containsOnce(
            target,
            "button.btn_timer_line.btn-danger .fa-stop",
            "A row should have the timer button red with stop icon to notify the timer is running in that row"
        );
        assert.containsN(
            target,
            "button.btn_timer_line:not(.btn-danger)",
            4,
            "4 rows should not have a timer running"
        );
        assert.deepEqual(
            getRowWithTimerRunningOrNot(),
            [true, false, false, false, false],
            "Only first row should have the timer runnning"
        );
        assert.strictEqual(
            target.querySelector(".timesheet-timer .o_field_widget[name=project_id] input").value,
            "P1",
            "project_id in the timer header should be the one in the first row"
        );
        assert.strictEqual(
            target.querySelector(".timesheet-timer .o_field_widget[name=task_id] input").value,
            "",
            "task_id in the timer header should be the one in the first row (no task)"
        );
        assert.strictEqual(
            target.querySelector(".timesheet-timer .o_field_widget[name=name] input").value,
            "",
            "name field in the timer header should be empty (default value)"
        );
        assert.ok(
            target
                .querySelector(".timesheet-timer div[name=display_timer] span")
                .textContent.includes("00:00:0"),
            "timer should start to 0"
        );

        await click(target.querySelector("button.btn_timer_line:not(.btn-danger)"), "");
        assert.containsNone(
            target,
            ".btn_start_timer",
            "A timer should be running and so the start button should not be displayed"
        );
        assert.containsOnce(
            target,
            ".btn_stop_timer",
            "A timer should be running and so the stop button should be displayed instead of start one"
        );
        assert.containsOnce(
            target,
            "button.btn_timer_line.btn-danger .fa-stop",
            "A row should have the timer button red with stop icon to notify the timer is running in that row"
        );
        assert.containsN(
            target,
            "button.btn_timer_line:not(.btn-danger)",
            4,
            "4 rows should not have a timer running"
        );

        assert.deepEqual(getRowWithTimerRunningOrNot(), [false, true, false, false, false]);
        assert.strictEqual(
            target.querySelector(".timesheet-timer .o_field_widget[name=project_id] input").value,
            "P1",
            "project_id in the timer header should be the one in the first row"
        );
        assert.strictEqual(
            target.querySelector(".timesheet-timer .o_field_widget[name=task_id] input").value,
            "BS task",
            "task_id in the timer header should be the one in the first row (BS task is expected)"
        );
        assert.strictEqual(
            target.querySelector(".timesheet-timer .o_field_widget[name=name] input").value,
            "",
            "name field in the timer header should be empty (default value)"
        );
        assert.ok(
            target
                .querySelector(".timesheet-timer div[name=display_timer] span")
                .textContent.includes("00:00:0"),
            "timer should start to 0"
        );
    });

    QUnit.test("Change description running timer", async function (assert) {
        const pyEnv = getPyEnv();
        pyEnv.mockServer.models["analytic.line"].records.push({
            id: 10,
            unit_amount: 5740 / 3600, // 01:35:40
            project_id: 1,
            task_id: 1,
            name: "Description",
        });
        let timerRunning = true;
        const { openView } = await start({
            serverData,
            async mockRPC(route, args) {
                if (args.method === "get_running_timer") {
                    if (timerRunning) {
                        return {
                            id: 10,
                            start: 5740, // 01:35:40
                            project_id: 1,
                            task_id: 1,
                            description: "/",
                            step_timer: 30,
                        };
                    }
                    return {
                        step_timer: 30,
                    };
                } else if (args.method === "action_start_new_timesheet_timer") {
                    return false;
                } else if (args.method === "get_daily_working_hours") {
                    assert.strictEqual(args.model, "hr.employee");
                    return {};
                } else if (args.method === "get_server_time") {
                    assert.strictEqual(args.model, "timer.timer");
                    return serializeDateTime(DateTime.now());
                } else if (args.method === "action_timer_stop") {
                    timerRunning = false;
                    return null;
                } else if (args.method === "get_last_validated_timesheet_date") {
                    return false;
                }
                return timesheetGridSetup.mockTimesheetGridRPC(route, args);
            },
        });

        await openView({
            res_model: "analytic.line",
            views: [[false, "grid"]],
            context: { group_by: ["project_id", "task_id"] },
        });

        await editInput(target, ".timesheet-timer div[name=name] input", "Description");
        assert.strictEqual(
            target.querySelector(".timesheet-timer div[name=name] input").value,
            "Description",
            "The `Description` should correctly be written in the name description in the timer header"
        );
    });

    QUnit.test(
        "Check that individual and total overtime is properly displayed",
        async function (assert) {
            const { openView } = await start({
                serverData,
                async mockRPC(route, args) {
                    if (args.method === "get_running_timer") {
                        return {
                            step_timer: 30,
                        };
                    } else if (args.method === "action_start_new_timesheet_timer") {
                        return false;
                    } else if (args.method === "get_daily_working_hours") {
                        assert.strictEqual(args.model, "hr.employee");
                        const [serializedDateStart, serializedDateEnd] = args.args;
                        const dailyWorkingHours = {
                            [serializedDateStart]: 0,
                            [serializedDateEnd]: 0,
                        };
                        const generateNext = (dateStart) => dateStart.plus({ days: 1 });
                        const dateStart = deserializeDate(serializedDateStart);
                        const dateEnd = deserializeDate(serializedDateEnd);
                        for (
                            let currentDate = generateNext(dateStart);
                            currentDate < dateEnd;
                            currentDate = generateNext(currentDate)
                        ) {
                            dailyWorkingHours[serializeDate(currentDate)] = 7;
                        }
                        return dailyWorkingHours;
                    } else if (args.method === "get_last_validated_timesheet_date") {
                        return false;
                    }
                    return timesheetGridSetup.mockTimesheetGridRPC(route, args);
                },
            });

            await openView({
                res_model: "analytic.line",
                views: [[false, "grid"]],
                context: { group_by: ["project_id", "task_id"] },
            });

            patchWithCleanup(browser, {
                setTimeout: (fn) => fn(),
                clearTimeout: () => {},
            });
            const columnTotalEls = target.querySelectorAll(".o_grid_column_total");
            const columnTotalWithBarchartTotalTitle = {
                danger: [],
                classic: [],
                get total() {
                    return this.danger.length + this.classic.length;
                },
            };
            const emptyColumnTotalCells = [];
            let columnTotalEl;

            for (const node of columnTotalEls) {
                if (!columnTotalEl && node.querySelector(".o_grid_bar_chart_total_title")) {
                    columnTotalEl = node;
                }
                if (!node.classList.contains("o_grid_bar_chart_container")) {
                    const columnTotalTitleEl = node.querySelector(".o_grid_bar_chart_total_title");
                    if (!columnTotalTitleEl) {
                        emptyColumnTotalCells.push(node);
                    } else {
                        if (columnTotalTitleEl.querySelector("span.text-danger")) {
                            columnTotalWithBarchartTotalTitle.danger.push(node);
                        } else {
                            columnTotalWithBarchartTotalTitle.classic.push(node);
                        }
                    }
                }
            }

            assert.strictEqual(
                emptyColumnTotalCells.length,
                4,
                "4 column totals should not have any number since the employee has recorded nothing"
            );
            assert.strictEqual(
                columnTotalWithBarchartTotalTitle.total,
                4,
                "4 column totals should have a total displayed"
            );
            assert.strictEqual(
                columnTotalWithBarchartTotalTitle.danger.length,
                3,
                "3 column totals should have a total displayed in red since the employee has not done all his working hours"
            );
            assert.strictEqual(
                columnTotalWithBarchartTotalTitle.classic.length,
                1,
                "1 column totals should have a total displayed in black color since the employee has done all his working hours"
            );
            assert.containsN(
                target,
                ".o_grid_bar_chart_container .o_grid_bar_chart_overtime",
                4,
                "4 overtimes indication should be displayed in 4 cells displaying barchart total"
            );
            assert.containsN(
                target,
                ".o_grid_bar_chart_container:not(.o_grid_highlighted) .o_grid_bar_chart_overtime",
                4,
                "4 overtimes indication should be displayed in 4 cells displaying barchart total should not be visible"
            );
            await nextTick();
            await triggerEvent(columnTotalEl, "", "mouseover");
            assert.containsOnce(
                target,
                ".o_grid_bar_chart_container.o_grid_highlighted .o_grid_bar_chart_overtime",
                "The overtime of the total column hovered should be visible"
            );
        }
    );

    QUnit.test("Start timer and cancel it", async (assert) => {
        const { openView } = await start({
            serverData,
            async mockRPC(route, args) {
                if (args.method === "get_running_timer") {
                    return {
                        step_timer: 30,
                    };
                } else if (args.method === "action_start_new_timesheet_timer") {
                    return {
                        start: 0,
                        project_id: false,
                        task_id: false,
                        description: "",
                    };
                } else if (args.method === "get_daily_working_hours") {
                    assert.strictEqual(args.model, "hr.employee");
                    return {};
                } else if (args.method === "get_server_time") {
                    assert.strictEqual(args.model, "timer.timer");
                    return serializeDateTime(DateTime.now());
                } else if (args.method === "action_timer_unlink") {
                    return null;
                } else if (
                    args.method === "name_search" &&
                    ["project.project", "project.task"].includes(args.model)
                ) {
                    args.kwargs.args =
                        args.model === "project.project" ? [["allow_timesheets", "=", true]] : [];
                }
                return timesheetGridSetup.mockTimesheetGridRPC(route, args);
            },
        });

        await openView({
            res_model: "analytic.line",
            views: [[false, "grid"]],
            context: { group_by: ["project_id", "task_id"] },
        });

        assert.containsOnce(target, ".btn_start_timer", "The timer should be running.");
        await click(target, ".btn_start_timer");
        assert.containsNone(target, ".btn_start_timer", "The timer should be running.");
        assert.containsOnce(target, ".btn_stop_timer", "The stop button should be displayed.");
        assert.containsOnce(
            target,
            ".o_timer_discard button",
            "The cancel button should be displayed"
        );
        await clickOpenM2ODropdown(target, "project_id");
        await click(target.querySelector("div[name='project_id'] li > a"), "");

        assert.containsOnce(
            target,
            ".btn_timer_line.btn-danger",
            "The timer is running on the row with the project selected"
        );
        let rowTimerButton = target.querySelector(".btn_timer_line.btn-danger");
        let containerRowTimerButton = rowTimerButton.closest(".o_grid_highlightable");
        let rowTitle = target.querySelector(
            `.o_grid_row_title[data-grid-row='${containerRowTimerButton.dataset.gridRow}']`
        );
        assert.ok(
            rowTitle.textContent.indexOf("P1") !== -1,
            "The row title with the timer running should contain the project selected in the timer header."
        );
        assert.ok(
            rowTitle.textContent.indexOf("BS task") === -1,
            "The row title with the timer running should not contain a task name."
        );

        await clickOpenM2ODropdown(target, "task_id");
        await click(target.querySelector("div[name='task_id'] li > a"), "");

        assert.containsOnce(
            target,
            ".btn_timer_line.btn-danger",
            "The timer is running on the row with the project and task selected in the timer header."
        );
        rowTimerButton = target.querySelector(".btn_timer_line.btn-danger");
        containerRowTimerButton = rowTimerButton.closest(".o_grid_highlightable");
        rowTitle = target.querySelector(
            `.o_grid_row_title[data-grid-row='${containerRowTimerButton.dataset.gridRow}']`
        );
        assert.ok(
            rowTitle.textContent.indexOf("P1") !== -1,
            "The row title with the timer running should contain the project selected in the timer header."
        );
        assert.ok(
            rowTitle.textContent.indexOf("BS task") !== -1,
            "The row title with the timer running should not contain a task name."
        );

        await click(target, ".o_timer_discard button");
        assert.containsNone(target, ".btn_timer_line.btn-danger", "The timer should be cancelled");
        assert.containsNone(
            target,
            ".btn_stop_timer",
            "The stop button should no longer be displayed."
        );
        assert.containsNone(
            target,
            ".o_timer_discard button",
            "The cancel button should no longer be displayed."
        );
        assert.containsOnce(target, ".btn_start_timer", "The timer should no longer be running.");
    });

    QUnit.test(
        "Start and stop timer with GridTimerButton (keyboard shortcut)",
        async function (assert) {
            const pyEnv = getPyEnv();
            let timesheetId = 6;
            const { openView } = await start({
                serverData,
                async mockRPC(route, args) {
                    if (args.method === "get_running_timer") {
                        return {
                            step_timer: 30,
                        };
                    } else if (args.method === "get_daily_working_hours") {
                        assert.strictEqual(args.model, "hr.employee");
                        return {};
                    } else if (args.method === "action_start_new_timesheet_timer") {
                        const { project_id, task_id } = args.args[0];
                        if (!project_id) {
                            return false;
                        }
                        const newTimesheet = {
                            id: timesheetId++,
                            project_id,
                            task_id,
                            date: serializeDateTime(DateTime.now()),
                            unit_amount: 0.0,
                        };
                        pyEnv.mockServer.models["analytic.line"].records.push(newTimesheet);
                        return newTimesheet;
                    } else if (args.method === "get_server_time") {
                        assert.strictEqual(args.model, "timer.timer");
                        return serializeDateTime(DateTime.now());
                    } else if (args.method === "action_timer_stop") {
                        return 0.25;
                    }
                    return timesheetGridSetup.mockTimesheetGridRPC(route, args);
                },
            });

            await openView({
                res_model: "analytic.line",
                views: [[false, "grid"]],
            });
            await nextTick();
            assert.containsOnce(target, ".btn_start_timer", "No timer should be running.");
            const gridTimerButton = target.querySelector(".btn_timer_line[data-hotkey='A']");
            const gridTimerButtonContainer = gridTimerButton.closest(".o_grid_highlightable");
            assert.strictEqual(
                target.querySelector(
                    `.o_grid_row.o_grid_highlightable.o_grid_cell_today[data-grid-row="${gridTimerButtonContainer.dataset.gridRow}"]`
                ).textContent,
                "0:00"
            );
            await triggerEvent(document.activeElement, "", "keydown", { key: "a" });
            assert.containsNone(target, ".btn_start_timer", "A timer should be running");
            assert.containsOnce(
                target,
                ".btn_timer_line.btn-danger",
                "The row with the GridTimerButton with 'a' letter in the grid view should have the timer running"
            );
            assert.containsOnce(
                target,
                ".btn_timer_line.btn-danger[data-hotkey='A']",
                "The row with the running timer should be the one with the 'A' letter in the GridTimerButton"
            );

            await triggerEvent(document.activeElement, "", "keydown", { key: "a" });
            assert.containsOnce(target, ".btn_start_timer", "The timer should be stopped");
            assert.containsNone(
                target,
                ".btn_timer_line.fa-stop-danger",
                "The running timer in the row with the GridTimerButton with 'a' letter in the grid should be stopped"
            );
            assert.strictEqual(
                target.querySelector(
                    `.o_grid_cell_today[data-grid-row="${gridTimerButtonContainer.dataset.gridRow}"]`
                ).textContent,
                "0:15",
                "The today cell in the row with `A` button should be increased by 15 minutes."
            );
        }
    );

    QUnit.test(
        "Start timer and start another with GridTimerButton (keyboard shortcut)",
        async function (assert) {
            const pyEnv = getPyEnv();
            let timesheetId = 6;
            const { openView } = await start({
                serverData,
                async mockRPC(route, args) {
                    if (args.method === "get_running_timer") {
                        return {
                            step_timer: 30,
                        };
                    } else if (args.method === "get_daily_working_hours") {
                        assert.strictEqual(args.model, "hr.employee");
                        return {};
                    } else if (args.method === "action_start_new_timesheet_timer") {
                        const { project_id, task_id } = args.args[0];
                        if (!project_id) {
                            return false;
                        }
                        const newTimesheet = {
                            id: timesheetId++,
                            project_id,
                            task_id,
                            date: serializeDateTime(DateTime.now()),
                            unit_amount: 0.0,
                        };
                        pyEnv.mockServer.models["analytic.line"].records.push(newTimesheet);
                        return newTimesheet;
                    } else if (args.method === "get_server_time") {
                        assert.strictEqual(args.model, "timer.timer");
                        return serializeDateTime(DateTime.now());
                    } else if (args.method === "action_timer_stop") {
                        return 0.25;
                    }
                    return timesheetGridSetup.mockTimesheetGridRPC(route, args);
                },
            });

            await openView({
                res_model: "analytic.line",
                views: [[false, "grid"]],
            });

            assert.containsOnce(target, ".btn_start_timer", "No timer should be running.");
            const gridTimerButton = target.querySelector(".btn_timer_line[data-hotkey='A']");
            const gridTimerButtonContainer = gridTimerButton.closest(".o_grid_highlightable");
            assert.strictEqual(
                target.querySelector(
                    `.o_grid_cell_today[data-grid-row="${gridTimerButtonContainer.dataset.gridRow}"]`
                ).textContent,
                "0:00"
            );
            await triggerEvent(document.activeElement, "", "keydown", { key: "a" });
            assert.containsNone(target, ".btn_start_timer", "A timer should be running");
            assert.containsOnce(
                target,
                ".btn_timer_line.btn-danger",
                "The row with the GridTimerButton with 'a' letter in the grid view should have the timer running"
            );
            assert.containsOnce(
                target,
                ".btn_timer_line.btn-danger[data-hotkey='A']",
                "The row with the running timer should be the one with the 'A' letter in the GridTimerButton"
            );
            await triggerEvent(document.activeElement, "", "keydown", { key: "b" });
            assert.containsNone(target, ".btn_start_timer", "A timer should be running");
            assert.containsOnce(
                target,
                ".btn_timer_line.btn-danger",
                "The row with the GridTimerButton with 'b' letter in the grid view should have the timer running"
            );
            assert.containsOnce(
                target,
                ".btn_timer_line.btn-danger[data-hotkey='B']",
                "The row with the running timer should be the one with the 'B' letter in the GridTimerButton"
            );
            assert.strictEqual(
                target.querySelector(
                    `.o_grid_cell_today[data-grid-row="${gridTimerButtonContainer.dataset.gridRow}"]`
                ).textContent,
                "0:15",
                "The today cell in the row with `A` button should be increased by 15 minutes."
            );
        }
    );
});
