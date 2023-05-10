/** @odoo-module **/

import { CallbackRecorder } from "@web/webclient/actions/action_hook";
import { getDefaultConfig } from "@web/views/view";
import { EmbeddedView } from "@knowledge/views/embedded_view";
import { PromptEmbeddedViewNameDialog } from "@knowledge/components/prompt_embedded_view_name_dialog/prompt_embedded_view_name_dialog";
import { useOwnDebugContext } from "@web/core/debug/debug_context";
import { useService } from "@web/core/utils/hooks";
import {
    Component,
    onWillStart,
    useSubEnv } from "@odoo/owl";
import { decodeDataBehaviorProps, encodeDataBehaviorProps } from "@knowledge/js/knowledge_utils";

const EMBEDDED_VIEW_LIMITS = {
    kanban: 20,
    list: 40,
};

/**
 * Wrapper for the embedded view, manage the toolbar and the embedded view props
 */
export class EmbeddedViewManager extends Component {
    setup() {
        // allow access to the SearchModel exported state which contain facets
        this.__getGlobalState__ = new CallbackRecorder();

        this.actionService = useService('action');
        this.dialogService = useService('dialog');
        this.notification = useService("notification");

        useOwnDebugContext(); // define a debug context when the developer mode is enable
        const config = {
            ...getDefaultConfig(),
            disableSearchBarAutofocus: true,
        };

        /**
         * @param {ViewType} viewType
         * @param {Object} [props={}]
         */
        const switchView = (viewType, props = {}) => {
            if (this.action.type !== "ir.actions.act_window") {
                throw new Error('Can not open the view: The action is not an "ir.actions.act_window"');
            }
            if (props.resId) {
                this.action.res_id = props.resId;
            }
            this.action.globalState = this.getEmbeddedViewGlobalState();
            this.actionService.doAction(this.action, {
                viewType: viewType,
            });
        };

        const services = this.env.services;
        const extendedServices = Object.create(services);
        extendedServices.action = Object.create(services.action);
        extendedServices.action.switchView = switchView;

        useSubEnv({
            config,
            services: extendedServices,
        });
        onWillStart(this.onWillStart.bind(this));
    }

    /**
     * Extract the SearchModel state of the embedded view
     *
     * @returns {Object} globalState
     */
    getEmbeddedViewGlobalState() {
        const callbacks = this.__getGlobalState__.callbacks;
        let globalState;
        if (callbacks.length) {
            globalState = callbacks.reduce((res, callback) => {
                return { ...res, ...callback() };
            }, {});
        }
        return { searchModel: globalState && globalState.searchModel };
    }

    /**
     * Save the search favorite in the view arch.
     */
    async onSaveKnowledgeFavorite(favorite) {
        if (this.props.readonly) {
            this.notification.add(this.env._t("You can not save favorite on this article"), {
                type: "danger",
            });
            return;
        }
        const data = decodeDataBehaviorProps(this.props.el.getAttribute("data-behavior-props"));
        const favorites = data.favorites || [];
        favorites.push(favorite);
        data.favorites = favorites;
        this.props.el.setAttribute("data-behavior-props", encodeDataBehaviorProps(data));
        await this.props.record.askChanges();
    }

    /**
     * Delete the search favorite from the view arch.
     */
    async onDeleteKnowledgeFavorite(searchItem) {
        if (this.props.readonly) {
            this.notification.add(this.env._t("You can not delete favorite from this article"), {
                type: "danger",
            });
            return;
        }

        const data = decodeDataBehaviorProps(this.props.el.getAttribute("data-behavior-props"));
        const favorites = data.favorites || [];
        data.favorites = favorites.filter((favorite) => favorite.name != searchItem.description);
        this.props.el.setAttribute("data-behavior-props", encodeDataBehaviorProps(data));
        await this.props.record.askChanges();
    }

    /**
     * Recover the action from its parsed state (attrs of the Behavior block)
     * and setup the embedded view props
     */
    onWillStart () {
        const { action, context, viewType } = this.props;
        this.env.config.setDisplayName(action.display_name);
        this.env.config.views = action.views;
        const ViewProps = {
            resModel: action.res_model,
            context: context,
            domain: action.domain || [],
            type: viewType,
            loadIrFilters: true,
            loadActionMenus: true,
            __getGlobalState__: this.__getGlobalState__,
            globalState: { searchModel: context.knowledge_search_model_state },
            /**
             * @param {integer} recordId
             */
            selectRecord: recordId => {
                const [formViewId] = this.action.views.find((view) => {
                    return view[1] === 'form';
                }) || [false];
                this.actionService.doAction({
                    type: 'ir.actions.act_window',
                    res_model: action.res_model,
                    views: [[formViewId, 'form']],
                    res_id: recordId,
                });
            },
            createRecord: async () => {
                const [formViewId] = this.action.views.find((view) => {
                    return view[1] === 'form';
                }) || [false];
                this.actionService.doAction({
                    type: 'ir.actions.act_window',
                    res_model: action.res_model,
                    views: [[formViewId, 'form']],
                });
            },
        };
        if (action.search_view_id) {
            ViewProps.searchViewId = action.search_view_id[0];
        }
        if (context.orderBy) {
            try {
                ViewProps.orderBy = JSON.parse(context.orderBy);
            } catch {};
        }
        if (this.props.viewType in EMBEDDED_VIEW_LIMITS) {
            ViewProps.limit = EMBEDDED_VIEW_LIMITS[this.props.viewType];
        }
        ViewProps.irFilters = this._loadKnowledgeFavorites();
        ViewProps.onSaveKnowledgeFavorite = this.onSaveKnowledgeFavorite.bind(this);
        ViewProps.onDeleteKnowledgeFavorite = this.onDeleteKnowledgeFavorite.bind(this);

        this.EmbeddedView = EmbeddedView;
        this.EmbeddedViewProps = ViewProps;
        this.action = action;
    }

    /**
     * Rename an embedded view
     */
    _onRenameBtnClick () {
        this.dialogService.add(PromptEmbeddedViewNameDialog, {
            isNew: false,
            defaultName: this.props.getTitle(),
            viewType: this.props.viewType,
            save: name => {
                this.props.setTitle(name);
            },
            close: () => {}
        });
    }

    /**
     * Open an embedded view (fullscreen)
     */
    _onOpenBtnClick () {
        if (this.action.type !== "ir.actions.act_window") {
            throw new Error('Can not open the view: The action is not an "ir.actions.act_window"');
        }
        const props = {};
        if (this.action.context.orderBy) {
            try {
                props.orderBy = JSON.parse(this.action.context.orderBy);
            } catch {};
        }
        this.action.globalState = this.getEmbeddedViewGlobalState();
        this.actionService.doAction(this.action, {
            viewType: this.props.viewType,
            props
        });
    }

    /**
     * Load search favorites from the view arch.
     */
    _loadKnowledgeFavorites() {
        const data = decodeDataBehaviorProps(this.props.el.getAttribute("data-behavior-props"));
        const favorites = data.favorites || [];

        return favorites.map((favorite) => {
            favorite.isActive = favorite.isActive || false;
            favorite.context = JSON.stringify(favorite.context);
            return favorite;
        });
    }
}

EmbeddedViewManager.template = 'knowledge.EmbeddedViewManager';
EmbeddedViewManager.props = {
    el: { type: HTMLElement },
    action: { type: Object },
    context: { type: Object },
    viewType: { type: String },
    setTitle: { type: Function },
    getTitle: { type: Function },
    readonly: { type: Boolean },
    record: { type: Object },
};
