/** @odoo-module */

import { CalendarCommonPopover } from "@web/views/calendar/calendar_common/calendar_common_popover";
import { CalendarCommonRenderer } from "@web/views/calendar/calendar_common/calendar_common_renderer";
import { CalendarController } from '@web/views/calendar/calendar_controller';
import { CalendarRenderer } from '@web/views/calendar/calendar_renderer';
import { calendarView } from '@web/views/calendar/calendar_view';
import { ConfirmationDialog } from "@web/core/confirmation_dialog/confirmation_dialog";
import { ItemCalendarModel } from "@knowledge/views/item_calendar/item_calendar_model";
import { registry } from "@web/core/registry";
import { onWillUpdateProps } from "@odoo/owl";

export class KnowledgeArticleItemsCalendarController extends CalendarController {
    static template = "knowledge.ArticleItemsCalendarController";

    setup() {
        super.setup();
        onWillUpdateProps((nextProps) => {
            // Udpate the model if the itemCalendarProps were updated
            if (JSON.stringify(this.props.itemCalendarProps) !== JSON.stringify(nextProps.itemCalendarProps)) {
                this.updateModel(nextProps.itemCalendarProps);
            }
        });
    }

    get showSideBar() {
        // Hide sideabar when the view is embedded
        return !this.env.isEmbeddedView && super.showSideBar;
    }

    /**
     * Create a new article item and open it. If no record is given, creates it
     * without any start/stop date properties.
     * @param {Object} record: calendar record used to create the item with
     * properties.
     */
    async createRecord(record) {
        if (this.model.canCreate) {
            const createValues = {
                is_article_item: true,
                parent_id: this.props.context.active_id || false,
            };
            if (record) {
                const rawRecord = this.model.buildRawRecord(record);
                Object.assign(createValues, rawRecord);
            }
            const articleId = await this.orm.call('knowledge.article', 'article_create', [], createValues);

            this.action.doAction(
                await this.orm.call('knowledge.article', 'action_home_page', [articleId]),
                {}
            );
        }
    }

    /**
     * Send the item to the trash
     */
    deleteRecord(record) {
        this.displayDialog(ConfirmationDialog, {
            title: this.env._t("Confirmation"),
            body: this.env._t("Are you sure you want to send this article to the trash?"),
            confirm: async () => {
                await this.orm.call(
                    'knowledge.article',
                    'action_send_to_trash',
                    [record.id],
                );
                this.model.load();
            },
            confirmLabel: this.env._t("Send to trash"),
            cancel: () => {
                // `ConfirmationDialog` needs this prop to display the cancel
                // button but we do nothing on cancel.
            },
        });
    }

    /**
     * Set model meta variables to make the model work with the properties
     */
    onWillStartModel() {
        if (this.props.itemCalendarProps) {
            this.model.meta.canCreate = this.env.knowledgeArticleUserCanWrite;
            this.updateModel(this.props.itemCalendarProps);
        } else {
            this.model.meta.invalid = true;
        }
    }

    /**
     * Udpate the model field mappings and other meta variables using the given
     * modelProps.
     */
    updateModel(modelProps) {
        this.model.meta.fieldMapping.date_start = modelProps.dateStartPropertyId;
        this.model.meta.fieldMapping.date_stop = modelProps.dateStopPropertyId;
        this.model.meta.fieldMapping.color = modelProps.colorPropertyId;
        this.model.meta.propertiesDateType = modelProps.dateType;
        if (modelProps.scale) {
            this.model.meta.scale = modelProps.scale;
        }
    }
}

class KnowledgeArticleItemsCommonPopover extends CalendarCommonPopover {}
KnowledgeArticleItemsCommonPopover.subTemplates = {
    ...CalendarCommonPopover.subTemplates,
    body: "knowledge.ArticleItemsCalendarCommonPopover.body",
    footer: "knowledge.ArticleItemsCalendarCommonPopover.footer",
};

class KnowledgeArticleItemsCommonRenderer extends CalendarCommonRenderer {}
KnowledgeArticleItemsCommonRenderer.components = {
    ...CalendarCommonRenderer.components,
    Popover: KnowledgeArticleItemsCommonPopover,
};

class KnowledgeArticleItemsCalendarRenderer extends CalendarRenderer {}
KnowledgeArticleItemsCalendarRenderer.components = {
    ...CalendarRenderer.components,
    day: KnowledgeArticleItemsCommonRenderer,
    week: KnowledgeArticleItemsCommonRenderer,
    month: KnowledgeArticleItemsCommonRenderer,
};

registry.category("views").add('knowledge_article_view_calendar_embedded', {
    ...calendarView,
    Controller: KnowledgeArticleItemsCalendarController,
    Model: ItemCalendarModel,
    Renderer: KnowledgeArticleItemsCalendarRenderer,
});
