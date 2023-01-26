/** @odoo-module **/

import { Component, reactive, useExternalListener, useState } from "@odoo/owl";
import { useAutofocus, useService } from "@web/core/utils/hooks";
import { BG_COLORS, COLORS, ICONS } from "@web_studio/utils";
import { ModelConfigurator } from "@web_studio/client_action/model_configurator/model_configurator";
import { IconCreator } from "../icon_creator/icon_creator";
import { MenuCreator, MenuCreatorModel } from "@web_studio/client_action/menu_creator/menu_creator";

class AppCreatorState {
    /**
     * @param {Function} onFinished
     */
    constructor({ onFinished }) {
        this._onFinished = onFinished;
        // ==================== Misc ====================
        this.step = "welcome";

        // ================== Fields ==================
        this.fieldsValidators = {
            appName: () => !!this.data.appName,
            menu: (_this) => _this.menuCreatorModel.isValid,
        };
        this.menuCreatorModel = reactive(new MenuCreatorModel());

        this.data = {
            appName: "",
            iconData: {
                backgroundColor: BG_COLORS[5],
                color: COLORS[4],
                iconClass: ICONS[0],
                type: "custom_icon",
            },
            menu: this.menuCreatorModel.data,
            modelOptions: [],
        };

        // ================== Steps ==================
        this._steps = {
            welcome: {
                next: () => "app",
            },
            app: {
                previous: "welcome",
                next: () => "model",
                fields: ["appName"],
            },
            model: {
                previous: "app",
                next: (data) => {
                    return data.menu.modelChoice === "new" ? "model_configuration" : "";
                },
                fields: ["menu"],
            },
            model_configuration: {
                previous: "model",
            },
        };
    }

    //--------------------------------------------------------------------------
    // Getters
    //--------------------------------------------------------------------------

    get step() {
        return this._step;
    }

    set step(step) {
        this._step = step;
        this.showValidation = false;
    }

    get nextStep() {
        const next = this._next;
        return this._stepInvalidFields.length ? false : next;
    }

    get hasPrevious() {
        return "previous" in this._currentStep;
    }

    //--------------------------------------------------------------------------
    // Public
    //--------------------------------------------------------------------------

    isFieldValid(fieldName) {
        return this.showValidation ? this.fieldsValidators[fieldName](this) : true;
    }

    next() {
        this.showValidation = true;
        const invalidFields = this._stepInvalidFields;
        if (invalidFields.length) {
            return;
        }
        const next = this._next;
        if (next) {
            this.step = next;
        } else {
            return this._onFinished();
        }
    }

    previous() {
        if (this._currentStep.previous) {
            this.step = this._currentStep.previous;
        }
    }

    //--------------------------------------------------------------------------
    // Private
    //--------------------------------------------------------------------------

    get _currentStep() {
        return this._steps[this._step];
    }

    get _next() {
        return this._currentStep.next ? this._currentStep.next(this.data) : "";
    }

    get _stepInvalidFields() {
        return (this._currentStep.fields || []).filter((fName) => {
            return !this.fieldsValidators[fName](this);
        });
    }
}

export class AppCreator extends Component {
    static template = "web_studio.AppCreator";
    static components = { IconCreator, ModelConfigurator, MenuCreator };
    static props = {
        onNewAppCreated: { type: Function },
    };

    setup() {
        this.state = useState(
            new AppCreatorState({
                onFinished: this.createNewApp.bind(this),
            })
        );

        this.uiService = useService("ui");
        this.rpc = useService("rpc");
        this.user = useService("user");

        useAutofocus();
        useExternalListener(window, "keydown", this.onKeydown);
    }

    /**
     * @returns {Promise}
     */
    async createNewApp() {
        this.uiService.block();
        const data = this.state.data;
        const iconData = data.iconData;

        const iconValue =
            iconData.type === "custom_icon"
                ? // custom icon data
                  [iconData.iconClass, iconData.color, iconData.backgroundColor]
                : // attachment
                  iconData.uploaded_attachment_id;

        try {
            const result = await this.rpc("/web_studio/create_new_app", {
                app_name: data.appName,
                menu_name: data.menu.menuName,
                model_choice: data.menu.modelChoice,
                model_id: data.menu.modelChoice && data.menu.modelId[0],
                model_options: data.modelOptions,
                icon: iconValue,
                context: this.user.context,
            });
            await this.props.onNewAppCreated(result);
        } finally {
            this.uiService.unblock();
        }
    }

    //--------------------------------------------------------------------------
    // Handlers
    //--------------------------------------------------------------------------

    /**
     * @param {KeyboardEvent} ev
     */
    onKeydown(ev) {
        if (
            ev.key === "Enter" &&
            !(
                ev.target.classList &&
                ev.target.classList.contains("o_web_studio_app_creator_previous")
            )
        ) {
            ev.preventDefault();
            this.state.next();
        }
    }

    /**
     * Handle the confirmation of options in the modelconfigurator
     * @param {Object} options
     */
    onConfirmOptions(options) {
        const mappedOptions = Object.entries(options)
            .filter((opt) => opt[1].value)
            .map((opt) => opt[0]);

        this.state.data.modelOptions = mappedOptions;
        return this.state.next();
    }
}
