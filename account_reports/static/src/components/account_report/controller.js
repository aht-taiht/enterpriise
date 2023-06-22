/** @odoo-module */

import { browser } from "@web/core/browser/browser";
import { session } from "@web/session";
import { useService } from "@web/core/utils/hooks";

import { AccountReportFootnoteDialog } from "@account_reports/components/account_report/footnote/dialog/footnote_dialog";

export class AccountReportController {
    constructor(action) {
        this.action = action;
        this.actionService = useService("action");
        this.dialog = useService("dialog");
        this.orm = useService("orm");
    }

    async load(env) {
        this.env = env;

        this.reportOptionsMap = {};
        this.reportInformationMap = {};
        this.lastOpenedSectionByReport = {};
        this.actionReportId = this.action.context.report_id;

        const mainReportOptions = await this.loadReportOptions(this.actionReportId);
        const cacheKey = this.getCacheKey(mainReportOptions['sections_source_id'], mainReportOptions['report_id']);

        // We need the options to be set and saved in order for the loading to work properly
        this.options = mainReportOptions;
        this.reportOptionsMap[cacheKey] = mainReportOptions;
        this.saveSessionOptions(mainReportOptions);

        const activeSectionPromise = this.displayReport(mainReportOptions['report_id']);
        this.preLoadClosedSections();
        await activeSectionPromise;
    }

    getCacheKey(sectionsSourceId, reportId) {
        return `${sectionsSourceId}_${reportId}`
    }

    async displayReport(reportId) {
        const cacheKey = await this.loadReport(reportId);
        this.options = await this.reportOptionsMap[cacheKey];
        this.data = await this.reportInformationMap[cacheKey];

        // If there is a specific order for lines in the options, we want to use it by default
        if (this.areLinesOrdered())
            await this.sortLines();

        this.assignLinesVisibility(this.lines);
        this.refreshVisibleFootnotes();
        this.saveSessionOptions(this.options);
    }

    async reload(optionPath, newOptions) {
        const rootOptionKey = optionPath.split('.')[0]

        /*
        When reloading the UI after setting an option filter, invalidate the cached options and data of all sections supporting this filter.
        This way, those sections will be reloaded (either synchronously when the user tries to access them or asynchronously via the preloading
        feature), and will then use the new filter value. This ensures the filters are always applied consistently to all sections.
        */
        for (const [cacheKey, cachedOptionsPromise] of Object.entries(this.reportOptionsMap)) {
            let cachedOptions = await cachedOptionsPromise;

            if (cachedOptions.hasOwnProperty(rootOptionKey)) {
                delete this.reportOptionsMap[cacheKey];
                delete this.reportInformationMap[cacheKey];
            }
        }

        this.saveSessionOptions(newOptions); // The new options will be loaded from the session. Saving them now ensures the new filter is taken into account.
        await this.displayReport(newOptions['report_id']);
    }

    async preLoadClosedSections() {
        let sectionLoaded = false;
        for (const section of this.options['sections']) {
            // Preload the first non-loaded section we find amongst this report's sections.
            const cacheKey = this.getCacheKey(this.options['sections_source_id'], section.id);
            if (section.id != this.options['report_id'] && !this.reportInformationMap[cacheKey]) {
                await this.loadReport(section.id, true);

                sectionLoaded = true;
                // Stop iterating and schedule next call. We don't go on in the loop in case the cache is reset and we need to restart preloading.
                break;
            }
        }

        let nextCallDelay = (sectionLoaded) ? 100 : 1000;

        const self = this;
        setTimeout(() => self.preLoadClosedSections(), nextCallDelay);
    }

    async loadReport(reportId, preloading=false) {
        const busEventPayload = { data: {id: `_account_reports_load_report_${reportId}`, params: {}}, settings: {} };
        if (!preloading)
            this.env.bus.trigger("RPC:REQUEST", busEventPayload); // Block UI; see comment in loadReportOptions for explanation

        const options = await this.loadReportOptions(reportId, preloading); // This also sets the promise in the cache
        const reportToDisplayId = options['report_id']; // Might be different from reportId, in case the report to open uses sections

        const cacheKey = this.getCacheKey(options['sections_source_id'], reportToDisplayId)
        if (!this.reportInformationMap[cacheKey]) {
            this.reportInformationMap[cacheKey] = this.orm.silent.call(
                "account.report",
                "get_report_information",
                [
                    reportToDisplayId,
                    options,
                ],
                {
                    context: this.action.context,
                },
            );
        }

        await this.reportInformationMap[cacheKey];

        if (!preloading) {
            this.env.bus.trigger("RPC:RESPONSE", busEventPayload); // Unblock UI
            if (options['sections'].length)
                this.lastOpenedSectionByReport[options['sections_source_id']] = options['selected_section_id'];
        }

        return cacheKey;
    }

    async loadReportOptions(reportId, preloading=false) {
        const loadOptions = this.hasSessionOptions() ? this.sessionOptions() : {};
        const cacheKey = this.getCacheKey(loadOptions['sections_source_id'] || reportId, reportId);

        if (!this.reportOptionsMap[cacheKey]) {
            // The options for this section are not loaded nor loading. Let's load them !

            const busEventPayload = { data: {id: `_account_reports_load_report_options_${reportId}`, params: {}}, settings: {} };
            if (preloading)
                loadOptions['selected_section_id'] = reportId;
            else {
                /* This event will block the UI. We have to do this manually like that, calling orm.silent.call instead of relying directly
                on orm.call, because it is possible that a call starts as a silent preloading, and then needs to become a regular blocking
                call because the user tries to access the section before the call has resolved.
                The only way to do that is to explicitly send RPC:REQUEST and RPC:RESPONSE events like this.
                */
                this.env.bus.trigger("RPC:REQUEST", busEventPayload);

                /* Reopen the last opened section by default (cannot be done through regular caching, because composite reports' options are not
                cached (since they always reroute). */
                if (this.lastOpenedSectionByReport[reportId])
                    loadOptions['selected_section_id'] = this.lastOpenedSectionByReport[reportId];
            }

            this.reportOptionsMap[cacheKey] = this.orm.silent.call(
                "account.report",
                "get_options",
                [
                   reportId,
                   loadOptions,
                ],
                {
                   context: this.action.context,
                },
            );

            // Wait for the result, and check the report hasn't been rerouted to a section or variant; fix the cache if it has
            let reportOptions = await this.reportOptionsMap[cacheKey];

            if (!preloading)
                this.env.bus.trigger("RPC:RESPONSE", busEventPayload); // Unblock the UI

            // In case of a reroute, also set the cached options into the reroute target's key
            const loadedOptionsCacheKey = this.getCacheKey(reportOptions['sections_source_id'], reportOptions['report_id']);
            if (loadedOptionsCacheKey !== cacheKey) {
                /* We delete the rerouting report from the cache, to avoid redoing this reroute when reloading the cached options, as it would mean
                route reports can never be opened directly if they open some variant by default.*/
                delete this.reportOptionsMap[cacheKey];
                this.reportOptionsMap[loadedOptionsCacheKey] = reportOptions;
                return reportOptions;
            }
        }

        return this.reportOptionsMap[cacheKey];
    }

    //------------------------------------------------------------------------------------------------------------------
    // Generic data getters
    //------------------------------------------------------------------------------------------------------------------
    get buttons() {
        return this.options.buttons;
    }

    get caretOptions() {
        return this.data.caret_options;
    }

    get columnHeadersRenderData() {
        return this.data.column_headers_render_data;
    }

    get columnGroupsTotals() {
        return this.data.column_groups_totals;
    }

    get context() {
        return this.data.context;
    }

    get filters() {
        return this.data.filters;
    }

    get footnotes() {
        return this.data.footnotes;
    }

    get groups() {
        return this.data.groups;
    }

    get lines() {
        return this.data.lines;
    }

    get warnings() {
        return this.data.warnings;
    }

    get linesOrder() {
        return this.data.lines_order;
    }

    get report() {
        return this.data.report;
    }

    get visibleFootnotes() {
        return this.data.visible_footnotes;
    }

    //------------------------------------------------------------------------------------------------------------------
    // Generic data setters
    //------------------------------------------------------------------------------------------------------------------
    set footnotes(value) {
        this.data.footnotes = value;
    }

    set columnGroupsTotals(value) {
        this.data.column_groups_totals = value;
    }

    set lines(value) {
        this.data.lines = value;
        this.assignLinesVisibility(this.lines);
    }

    set linesOrder(value) {
        this.data.lines_order = value;
    }

    set visibleFootnotes(value) {
        this.data.visible_footnotes = value;
    }

    //------------------------------------------------------------------------------------------------------------------
    // Helpers
    //------------------------------------------------------------------------------------------------------------------
    get hasGrowthComparisonColumn() {
        return Boolean(this.options.show_growth_comparison);
    }

    get hasCustomSubheaders() {
        return this.columnHeadersRenderData.custom_subheaders.length > 0;
    }

    get hasDebugColumn() {
        return Boolean(this.options.show_debug_column);
    }

    get hasStringDate() {
        return "date" in this.options && "string" in this.options.date;
    }

    get hasVisibleFootnotes() {
        return this.visibleFootnotes.length > 0;
    }

    //------------------------------------------------------------------------------------------------------------------
    // Options
    //------------------------------------------------------------------------------------------------------------------
    async _updateOption(operationType, optionPath, optionValue=null, reloadUI=false) {
        const optionKeys = optionPath.split(".");

        let currentOptionKey = null;
        let option = this.options;

        while (optionKeys.length > 1) {
            currentOptionKey = optionKeys.shift();
            option = option[currentOptionKey];

            if (option  === undefined)
                throw new Error(`Invalid option key in _updateOption(): ${ currentOptionKey } (${ optionPath })`);
        }

        switch (operationType) {
            case "update":
                option[optionKeys[0]] = optionValue;
                break;
            case "toggle":
                option[optionKeys[0]] = !option[optionKeys[0]];
                break;
            default:
                throw new Error(`Invalid operation type in _updateOption(): ${ operationType }`);
        }

        if (reloadUI)
            await this.reload(optionPath, this.options);
    }

    async updateOption(optionPath, optionValue, reloadUI=false) {
        await this._updateOption('update', optionPath, optionValue, reloadUI);
    }

    async toggleOption(optionPath, reloadUI=false) {
        await this._updateOption('toggle', optionPath, null, reloadUI);
    }

    async switchToSection(reportId) {
        this.saveSessionOptions({...this.options, 'selected_section_id': reportId});
        this.displayReport(reportId);
    }

    //------------------------------------------------------------------------------------------------------------------
    // Session options
    //------------------------------------------------------------------------------------------------------------------
    sessionOptionsID() {
        /* Options are stored by action report (so, the report that was targetted by the original action triggering this flow).
        This allows a more intelligent reloading of the previous options during user navigation (especially concerning sections and variants;
        you expect your report to open by default the same section as last time you opened it in this http session).
        */
        return `account.report:${ this.actionReportId }:${ session.company_id }`;
    }

    useSessionOptions() {
        const ignoreSession = this.action.params && this.action.params.ignore_session;

        return ignoreSession !== "write" && ignoreSession !== "both";
    }

    hasSessionOptions() {
        return (this.useSessionOptions()) ? Boolean(browser.sessionStorage.getItem(this.sessionOptionsID())) : false;
    }

    saveSessionOptions(options) {
        if (this.useSessionOptions())
            browser.sessionStorage.setItem(this.sessionOptionsID(), JSON.stringify(options));
    }

    sessionOptions() {
        return JSON.parse(browser.sessionStorage.getItem(this.sessionOptionsID()));
    }

    //------------------------------------------------------------------------------------------------------------------
    // Lines
    //------------------------------------------------------------------------------------------------------------------
    lineHasDebugData(lineIndex) {
        return 'debug_popup_data' in this.lines[lineIndex];
    }

    lineHasGrowthComparisonData(lineIndex) {
        return Boolean(this.lines[lineIndex].growth_comparison_data);
    }

    isNextLineChild(index, lineId) {
        return index < this.lines.length && this.lines[index].id.startsWith(lineId);
    }

    isNextLineDirectChild(index, lineId) {
        return index < this.lines.length && this.lines[index].parent_id === lineId;
    }

    isTotalLine(lineIndex) {
        return this.lines[lineIndex].id.includes("|total~~");
    }

    isLoadMoreLine(lineIndex) {
        return this.lines[lineIndex].id.includes("|load_more~~");
    }

    isLoadedLine(lineIndex) {
        const lineID = this.lines[lineIndex].id;
        const nextLineIndex = lineIndex + 1;

        return this.isNextLineChild(nextLineIndex, lineID) && !this.isTotalLine(nextLineIndex) && !this.isLoadMoreLine(nextLineIndex);
    }

    async replaceLineWith(replaceIndex, newLines) {
        await this.insertLines(replaceIndex, 1, newLines);
    }

    async insertLinesAfter(insertIndex, newLines) {
        await this.insertLines(insertIndex + 1, 0, newLines);
    }

    async insertLines(lineIndex, deleteCount, newLines) {
        this.lines.splice(lineIndex, deleteCount, ...newLines);

        if (this.areLinesOrdered())
            await this.sortLines();
    }

    //------------------------------------------------------------------------------------------------------------------
    // Unfolded/Folded lines
    //------------------------------------------------------------------------------------------------------------------
    unfoldLoadedLine(lineIndex) {
        const lineId = this.lines[lineIndex].id;
        let nextLineIndex = lineIndex + 1;

        while (this.isNextLineChild(nextLineIndex, lineId)) {
            if (this.isNextLineDirectChild(nextLineIndex, lineId))
                this.lines[nextLineIndex].visible = true;

            nextLineIndex += 1;
        }
    }

    async unfoldNewLine(lineIndex) {
        const newLines = await this.orm.call(
            "account.report",
            "get_expanded_lines",
            [
                this.options['report_id'],
                this.options,
                this.lines[lineIndex].id,
                this.lines[lineIndex].groupby,
                this.lines[lineIndex].expand_function,
                this.lines[lineIndex].progress,
                0,
            ],
        );

        this.assignLinesVisibility(newLines);
        this.insertLinesAfter(lineIndex, newLines);

        if (this.filters.show_totals)
            this.lines[lineIndex + newLines.length + 1].visible = true;
    }

    async unfoldLine(lineIndex) {
        const targetLine = this.lines[lineIndex];

        if (this.isLoadedLine(lineIndex))
            this.unfoldLoadedLine(lineIndex);
        else
            await this.unfoldNewLine(lineIndex);

        targetLine.unfolded = true;

        this.refreshVisibleFootnotes();

        // Update options
        if (!this.options.unfolded_lines.includes(targetLine.id))
            this.options.unfolded_lines.push(targetLine.id);

        this.saveSessionOptions(this.options);
    }

    foldLine(lineIndex) {
        const targetLine = this.lines[lineIndex];

        let foldedLinesIDs = new Set([targetLine.id]);
        let nextLineIndex = lineIndex + 1;

        while (this.isNextLineChild(nextLineIndex, targetLine.id)) {
            this.lines[nextLineIndex].unfolded = false;
            this.lines[nextLineIndex].visible = false;

            foldedLinesIDs.add(this.lines[nextLineIndex].id);

            nextLineIndex += 1;
        }

        targetLine.unfolded = false;

        this.refreshVisibleFootnotes();

        // Update options
        this.options.unfolded_lines = this.options.unfolded_lines.filter(
            unfoldedLineID => !foldedLinesIDs.has(unfoldedLineID)
        );

        this.saveSessionOptions(this.options);
    }

    //------------------------------------------------------------------------------------------------------------------
    // Ordered lines
    //------------------------------------------------------------------------------------------------------------------
    linesCurrentOrderByColumn(columnIndex) {
        if (this.areLinesOrderedByColumn(columnIndex))
            return this.options.order_column.direction;

        return "default";
    }

    areLinesOrdered() {
        return this.linesOrder != null && this.options.order_column != null;
    }

    areLinesOrderedByColumn(columnIndex) {
        return this.areLinesOrdered() && this.options.order_column.expression_label === this.options.columns[columnIndex].expression_label;
    }

    async sortLinesByColumnAsc(columnIndex) {
        this.options.order_column = {
            expression_label: this.options.columns[columnIndex].expression_label,
            direction: "ASC",
        };

        await this.sortLines();
        this.saveSessionOptions(this.options);
    }

    async sortLinesByColumnDesc(columnIndex) {
        this.options.order_column = {
            expression_label: this.options.columns[columnIndex].expression_label,
            direction: "DESC",
        };

        await this.sortLines();
        this.saveSessionOptions(this.options);
    }

    sortLinesByDefault() {
        delete this.options.order_column;
        delete this.linesOrder;

        this.saveSessionOptions(this.options);
    }

    async sortLines() {
        this.linesOrder = await this.orm.call(
            "account.report",
            "sort_lines",
            [
                this.lines,
                this.options,
                true,
            ],
            {
                context: this.action.context,
            },
        );
    }

    //------------------------------------------------------------------------------------------------------------------
    // Footnotes
    //------------------------------------------------------------------------------------------------------------------
    async refreshFootnotes() {
        this.footnotes = await this.orm.call(
            "account.report",
            "get_footnotes",
            [
                this.action.context.report_id,
                this.options,
            ],
        );

        this.refreshVisibleFootnotes();
    }

    async addFootnote(lineID) {
        this.dialog.add(AccountReportFootnoteDialog, {
            lineID: lineID,
            reportID: this.options.report_id,
            footnoteID: this.footnotes[lineID] ? this.footnotes[lineID].id : null,
            context: this.context,
            text: this.footnotes[lineID] ? this.footnotes[lineID].text : "",
            refresh: this.refreshFootnotes.bind(this),
        });
    }

    async deleteFootnote(footnote) {
        await this.orm.call(
            "account.report.footnote",
            "unlink",
            [
                footnote.id,
            ],
            {
                context: this.context,
            },
        );

        await this.refreshFootnotes();
    }

    //------------------------------------------------------------------------------------------------------------------
    // Visibility
    //------------------------------------------------------------------------------------------------------------------
    refreshVisibleFootnotes() {
        let visibleFootnotes = [];

        this.lines.forEach(line => {
            if (this.footnotes[line.id] && line.visible) {
                const number = visibleFootnotes.length + 1;

                visibleFootnotes.push({
                    ...this.footnotes[line.id],
                    "href": `footnote_${number}`,
                });

                line["visible_footnote"] = {
                    "number": number,
                    "href": `#footnote_${number}`,
                };
            }

            if (line.visible_footnote && (!this.footnotes[line.id] || !line.visible))
                delete line.visible_footnote;
        });

        this.visibleFootnotes = visibleFootnotes;
    }

    /**
        Defines which lines should be visible in the provided list of lines (depending on what is folded).
    **/
    assignLinesVisibility(linesToAssign) {
        let needHidingChildren = new Set();

        linesToAssign.forEach((line) => {
            line.visible = !needHidingChildren.has(line.parent_id);

            if (!line.visible || (line.unfoldable &! line.unfolded))
                needHidingChildren.add(line.id);
        });
    }

    //------------------------------------------------------------------------------------------------------------------
    // Server calls
    //------------------------------------------------------------------------------------------------------------------
    async reportAction(ev, action, actionParam = null, callOnSectionsSource = false) {
        ev.preventDefault();
        ev.stopPropagation();

        let actionOptions = this.options;
        if (callOnSectionsSource) {
            // When calling the sections source, we want to keep track of all unfolded lines of all sections
            const allUnfoldedLines =  this.options.sections.length ? [] : [...this.options['unfolded_lines']]

            for (const sectionData of this.options['sections']) {
                const cacheKey = this.getCacheKey(this.options['sections_source_id'], sectionData['id']);
                const sectionOptions = await this.reportOptionsMap[cacheKey];
                if (sectionOptions)
                    allUnfoldedLines.push(...sectionOptions['unfolded_lines']);
            }

            actionOptions = {...this.options, unfolded_lines: allUnfoldedLines};
        }

        const dispatchReportAction = await this.orm.call(
            "account.report",
            "dispatch_report_action",
            [
                callOnSectionsSource ? this.options['sections_source_id'] : this.options['report_id'],
                actionOptions,
                action,
                actionParam,
            ],
        );

        return dispatchReportAction ? this.actionService.doAction(dispatchReportAction) : null;
    }
}
