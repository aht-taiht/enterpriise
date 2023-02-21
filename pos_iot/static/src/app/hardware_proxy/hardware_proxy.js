/** @odoo-module */

import {
    HardwareProxy,
    hardwareProxyService,
} from "@point_of_sale/app/hardware_proxy/hardware_proxy";
import { browser } from "@web/core/browser/browser";
import { patch } from "@web/core/utils/patch";

patch(hardwareProxyService, "pos_iot.HardwareProxy", {
    dependencies: [...hardwareProxyService.dependencies, "orm"],
});
patch(HardwareProxy.prototype, "pos_iot.HardwareProxy", {
    setup({ orm }) {
        this._super(...arguments);
        this.orm = orm;
        this.deviceProxies = {};
        this.iotBoxes = [];
    },
    /**
     * @override
     */
    connectToPrinter() {
        this.printer = this.deviceProxies.printer;
        this.printer.pos = this.pos;
    },
    /**
     * Ping all of the IoT Boxes of the devices set on POS config and update the
     * status icon
     */
    pingBoxes() {
        this.setConnectionInfo({ status: "connecting" });
        for (const { ip, ip_url } of this.iotBoxes) {
            const timeoutController = new AbortController();
            setTimeout(() => timeoutController.abort(), 1000);
            browser
                .fetch(`${ip_url}/hw_proxy/hello`, { signal: timeoutController.signal })
                .catch(() => ({}))
                .then((response) => this.setProxyConnectionStatus(ip, response.ok || false));
        }
    },
    /**
     * Set the status of the IoT Box that has the specified url.
     *
     * @param {String} ip
     * @param {Boolean} connected
     */
    setProxyConnectionStatus(ip, connected) {
        const iotBox = this.iotBoxes.find((box) => box.ip === ip);
        if (!iotBox) {
            return;
        }
        iotBox.connected = connected;
        const disconnectedBoxes = this.iotBoxes.filter((box) => !box.connected);
        if (disconnectedBoxes.length) {
            this.setConnectionInfo({
                status: "disconnected",
                message: `${disconnectedBoxes.map((box) => box.name).join(" & ")} disconnected`,
            });
        } else {
            this.setConnectionInfo({ status: "connected" });
        }
    },
    /**
     * Check the status of the devices every 5 seconds and update the status of
     * the drivers. This status is valid only if the IoT Box is connected.
     */
    async statusLoop() {
        this.statusLoopRunning = true;
        const devices = await this.orm.searchRead(
            "iot.device",
            [
                ["id", "in", this.pos.config.iot_device_ids],
                ["connected", "=", true],
            ],
            ["type"]
        );
        const drivers = Object.fromEntries(
            devices.map((device) => [device.type, { status: "connected" }])
        );
        this.setConnectionInfo({ drivers });
        setTimeout(() => this.statusLoop(), 5000);
    },
});