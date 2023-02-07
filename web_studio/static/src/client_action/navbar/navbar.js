/** @odoo-module **/
import { onMounted } from "@odoo/owl";

import { registry } from "@web/core/registry";
import { useService, useBus } from "@web/core/utils/hooks";
import { EnterpriseNavBar } from "@web_enterprise/webclient/navbar/navbar";
import { NotEditableActionError } from "../../studio_service";
import { HomeMenuCustomizer } from "./home_menu_customizer/home_menu_customizer";
import { useStudioServiceAsReactive } from "@web_studio/studio_service";

const menuButtonsRegistry = registry.category("studio_navbar_menubuttons");
export class StudioNavbar extends EnterpriseNavBar {
    setup() {
        super.setup();
        this.studio = useStudioServiceAsReactive();
        this.actionManager = useService("action");
        this.user = useService("user");
        this.dialogManager = useService("dialog");
        this.notification = useService("notification");
        onMounted(() => {
            this.env.bus.off("HOME-MENU:TOGGLED", this);
            this._updateMenuAppsIcon();
        });

        useBus(menuButtonsRegistry, "UPDATE", () => this.render());
    }
    onMenuToggle() {
        this.studio.toggleHomeMenu();
    }
    closeStudio() {
        this.studio.leave();
    }
    async onNavBarDropdownItemSelection(menu) {
        if (menu.actionID) {
            try {
                await this.studio.open(this.studio.MODES.EDITOR, menu.actionID);
            } catch (e) {
                if (e instanceof NotEditableActionError) {
                    const options = { type: "danger" };
                    this.notification.add(
                        this.env._t("This action is not editable by Studio"),
                        options
                    );
                    return;
                }
                throw e;
            }
        }
    }
    get hasBackgroundAction() {
        return this.studio.editedAction || this.studio.MODES.APP_CREATOR === this.studio.mode;
    }
    get isInApp() {
        return this.studio.mode === this.studio.MODES.EDITOR;
    }
    _onNotesClicked() {
        // LPE fixme: dbuuid should be injected into session_info python side
        const action = {
            type: "ir.actions.act_url",
            url: `http://pad.odoo.com/p/customization-${this.user.db.uuid}`,
        };
        // LPE Fixme: this could be either the local AM or the GlobalAM
        // we don(t care i-here as we open an url anyway)
        this.actionManager.doAction(action);
    }

    get menuButtons() {
        return Object.fromEntries(menuButtonsRegistry.getEntries());
    }
}
StudioNavbar.template = "web_studio.StudioNavbar";
StudioNavbar.components.HomeMenuCustomizer = HomeMenuCustomizer;
