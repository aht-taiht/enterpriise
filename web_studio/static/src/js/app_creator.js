odoo.define('web_studio.AppCreator', function (require) {
    "use strict";

    const AbstractAction = require('web.AbstractAction');
    const { action_registry } = require('web.core');
    const { COLORS, BG_COLORS, ICONS } = require('web_studio.utils');
    const { FieldMany2One } = require('web.relational_fields');
    const IconCreator = require('web_studio.IconCreator');
    const StandaloneFieldManagerMixin = require('web.StandaloneFieldManagerMixin');
    const { useFocusOnUpdate, useExternalListener } = require('web.custom_hooks');

    const { ComponentAdapter, ComponentWrapper, WidgetAdapterMixin } = require('web.OwlCompatibility');

    const { Component, useState } = owl;

    const AppCreatorWrapper = AbstractAction.extend(StandaloneFieldManagerMixin, WidgetAdapterMixin, {

        /**
         * This widget is directly bound to its inner owl component and its sole purpose
         * is to instanciate it with the adequate properties: it will manually
         * mount the component when attached to the dom, will dismount it when detached
         * and destroy it when destroyed itself.
         * @constructor
         */
        init() {
            this._super(...arguments);
            StandaloneFieldManagerMixin.init.call(this);
            this.appCreatorComponent = new ComponentWrapper(this, AppCreator, { model: this.model });
        },

        async start() {
            await this._super(...arguments);
            return this.appCreatorComponent.mount(this.el);
        },

        destroy() {
            WidgetAdapterMixin.destroy.call(this);
            this._super();
        },

        //--------------------------------------------------------------------------
        // Handlers
        //--------------------------------------------------------------------------


        /**
         * Overriden to register widgets on the fly since they have been instanciated
         * by the Component.
         * @override
         */
        _onFieldChanged(ev) {
            const targetWidget = ev.data.__targetWidget;
            this._registerWidget(ev.data.dataPointID, targetWidget.name, targetWidget);
            StandaloneFieldManagerMixin._onFieldChanged.apply(this, arguments);
        },
    });

    /**
     * App creator
     *
     * Action handling the complete creation of a new app. It requires the user
     * to enter an app name, to customize the app icon (@see IconCreator) and
     * to finally enter a menu name, with the option to bind the default app
     * model to an existing one.
     *
     * TODO: this component is bound to an action adapter since the action manager
     * cannot yet handle owl component. This file must be reviewed as soon as
     * the action manager is updated.
     * @extends Component
     */
    class AppCreator extends Component {
        constructor() {
            super(...arguments);
            // TODO: Many2one component directly attached in XML. For now we have
            // to toggle it manually according to the state changes.
            this.state = useState({
                step: 'welcome',
                appName: "",
                menuName: "",
                modelChoice: false,
                modelId: false,
                iconData: {
                    backgroundColor: BG_COLORS[5],
                    color: COLORS[4],
                    iconClass: ICONS[0],
                    type: 'custom_icon',
                },
            });

            this.FieldMany2One = FieldMany2One;

            this.focusOnUpdate = useFocusOnUpdate();
            this.invalid = useState({
                appName: false,
                menuName: false,
                modelId: false,
            });
            useExternalListener(window, 'keydown', this._onKeydown);
        }

        async willStart() {
            if (this.env.isDebug()) {
                const recordId = await this.props.model.makeRecord('ir.actions.act_window', [{
                    name: 'model',
                    relation: 'ir.model',
                    type: 'many2one',
                    domain: [['transient', '=', false], ['abstract', '=', false]]
                }]);
                this.record = this.props.model.get(recordId);
            }
        }

        //--------------------------------------------------------------------------
        // Getters
        //--------------------------------------------------------------------------

        /**
         * @returns {boolean}
         */
        get isReady() {
            return (
                    this.state.step === 'welcome'
                ) || (
                    this.state.step === 'app' &&
                    this.state.appName
                ) || (
                    this.state.step === 'model' &&
                    this.state.menuName &&
                    (
                        !this.state.modelChoice ||
                        this.state.modelId
                    )
                );
        }

        //--------------------------------------------------------------------------
        // Private
        //--------------------------------------------------------------------------

        /**
         * Switch the current step and clean all invalid keys.
         * @private
         * @param {string} step
         */
        _changeStep(step) {
            this.state.step = step;
            for (const key in this.invalid) {
                this.invalid[key] = false;
            }
            this.focusOnUpdate();
        }

        /**
         * @private
         * @returns {Promise}
         */
        async _createNewApp() {
            this.env.services.blockUI();

            const iconValue = this.state.iconData.type === 'custom_icon' ?
                // custom icon data
                [this.state.iconData.iconClass, this.state.iconData.color, this.state.iconData.backgroundColor] :
                // attachment
                this.state.iconData.uploaded_attachment_id;

            const result = await this.rpc({
                route: '/web_studio/create_new_menu',
                params: {
                    app_name: this.state.appName,
                    menu_name: this.state.menuName,
                    model_id: this.state.modelChoice && this.state.modelId,
                    is_app: true,
                    icon: iconValue,
                    context: this.env.session.user_context,
                },
            }).guardedCatch(() => this.env.services.unblockUI());
            this.trigger('new-app-created', result);
            this.env.services.unblockUI();
        }

        //--------------------------------------------------------------------------
        // Handlers
        //--------------------------------------------------------------------------

        /**
         * @private
         * @param {Event} ev
         */
        _onChecked(ev) {
            this.state.modelChoice = ev.currentTarget.checked;
            if (!ev.currentTarget.checked) {
                this.invalid.modelId = false;
            }
        }

        /**
         * @private
         * @param {OwlEvent} ev
         */
        _onModelIdChanged(ev) {
            this.state.modelId = ev.detail.changes.model.id;
            this.invalid.modelId = isNaN(this.state.modelId);
        }

        /**
         * @private
         * @param {OwlEvent} ev
         */
        _onIconChanged(ev) {
            for (const key in this.state.iconData) {
                delete this.state.iconData[key];
            }
            Object.assign(this.state.iconData, ev.detail);
        }

        /**
         * @private
         * @param {InputEvent} ev
         */
        _onInput(ev) {
            const input = ev.currentTarget;
            if (this.invalid[input.id]) {
                this.invalid[input.id] = !input.value;
            }
            this.state[input.id] = input.value;
        }

        /**
         * @private
         * @param {KeyboardEvent} ev
         */
        _onKeydown(ev) {
            if (
                ev.key === 'Enter' && !(
                    ev.target.classList &&
                    ev.target.classList.contains('o_web_studio_app_creator_previous')
                )
            ) {
                ev.preventDefault();
                this._onNext();
            }
        }

        /**
         * @private
         */
        async _onNext() {
            switch (this.state.step) {
                case 'welcome':
                    this._changeStep('app');
                    break;
                case 'app':
                    if (!this.state.appName) {
                        this.invalid.appName = true;
                    } else {
                        this._changeStep('model');
                    }
                    break;
                case 'model':
                    if (!this.state.menuName) {
                        this.invalid.menuName = true;
                    }
                    if (this.state.modelChoice && !this.state.modelId) {
                        this.invalid.modelId = true;
                    }
                    const isValid = Object.values(this.invalid).reduce(
                        (valid, key) => valid && !key,
                        true
                    );
                    if (isValid) {
                        this._createNewApp();
                    }
                    break;
            }
        }

        /**
         * @private
         */
        _onPrevious() {
            switch (this.state.step) {
                case 'app':
                    this._changeStep('welcome');
                    break;
                case 'model':
                    this._changeStep('app');
                    break;
            }
        }
    }

    AppCreator.components = { ComponentAdapter, IconCreator };
    AppCreator.props = {
        model: Object,
    };
    AppCreator.template = 'AppCreator';

    action_registry.add('action_web_studio_app_creator', AppCreatorWrapper);

    return AppCreatorWrapper;
});
