/* @odoo-module */

import { patch } from "@web/core/utils/patch";
import { date_to_str } from "@web/legacy/js/core/time";
import { MockServer } from "@web/../tests/helpers/mock_server";

/**
 * @typedef {Object} CallData
 * @property {string} direction
 * @property {number|undefined} partner_id
 * @property {string} phone_number
 * @property {string} state
 */

patch(MockServer.prototype, {
    /**
     * @override
     */
    async _performRPC(_route, { model, method, args, kwargs }) {
        if (model !== "voip.call") {
            return super._performRPC(...arguments);
        }
        delete kwargs.context;
        switch (method) {
            case "abort_call":
                return this._mockVoipCallAbortCall(...args, kwargs);
            case "create_and_format":
                return this._mockVoipCallCreateAndFormat(...args, kwargs);
            case "end_call":
                return this._mockVoipCallEndCall(...args, kwargs);
            case "start_call":
                return this._mockVoipCallStartCall(...args, kwargs);
            default:
                return super._performRPC(...arguments);
        }
    },
    /**
     * @param {number[]} param0
     * @returns {Object[]}
     */
    _mockVoipCallAbortCall(ids) {
        this.pyEnv["voip.call"].write(ids, { state: "aborted" });
        return this._mockVoipCall_FormatCalls(ids);
    },
    /**
     * @param {Object} param0
     * @param {number|undefined} param0.res_id
     * @param {string|undefined} param0.res_model
     * @param {CallData} param0.kwargs
     * @returns {Object[]}
     */
    _mockVoipCallCreateAndFormat({ res_id, res_model, ...kwargs }) {
        // recipient finding logic based on (res_model, res_id) not mocked
        return this._mockVoipCall_FormatCalls(this.pyEnv["voip.call"].create(kwargs));
    },
    /**
     * @param {number[]} param0
     * @param {string|undefined} activity_name
     * @returns {Object[]}
     */
    _mockVoipCallEndCall(ids, activity_name) {
        this.pyEnv["voip.call"].write(ids, {
            end_date: date_to_str(new Date()),
            state: "terminated",
        });
        if (activity_name) {
            this.pyEnv["voip.call"].write(ids, { activity_name });
        }
        return this._mockVoipCall_FormatCalls(ids);
    },
    /**
     * @param {number[]} param0
     * @returns {Object[]}
     */
    _mockVoipCallStartCall(ids) {
        this.pyEnv["voip.call"].write(ids, {
            start_date: date_to_str(new Date()),
            state: "ongoing",
        });
        return this._mockVoipCall_FormatCalls(ids);
    },
    _mockVoipCall_ComputeDisplayName(calls) {
        const getName = (call) => {
            if (call.activity_name) {
                return call.activity_name;
            }
            const preposition = call.direction === "incoming" ? "from" : "to";
            switch (call.state) {
                case "aborted":
                    return `Aborted call to ${call.phone_number}`;
                case "missed":
                    return `Missed call from ${call.phone_number}`;
                case "rejected":
                    return `Rejected call ${preposition} ${call.phone_number}`;
                case "terminated":
                    if (call.partner_id) {
                        const [partner] = this.getRecords("res.partner", [
                            ["id", "=", call.partner_id],
                        ]);
                        return `Call ${preposition} ${partner.name}`;
                    }
                    return `Call ${preposition} ${call.phone_number}`;
                default:
                    return "";
            }
        };
        for (const call of calls) {
            call.display_name = getName(call);
        }
    },
    /**
     * @param {number[]|number} ids
     * @returns {Object[]}
     */
    _mockVoipCall_FormatCalls(ids) {
        if (!Array.isArray(ids)) {
            ids = [ids];
        }
        const records = this.getRecords("voip.call", [["id", "in", ids]]);
        this._mockVoipCall_ComputeDisplayName(records);
        const formattedCalls = [];
        for (const call of records) {
            const data = {
                id: call.id,
                creationDate: call.create_date,
                direction: call.direction,
                displayName: call.display_name,
                endDate: call.end_date,
                phoneNumber: call.phone_number,
                startDate: call.start_date,
                state: call.state,
            };
            if (Number.isInteger(call.partner_id)) {
                data.partner = this._mockResPartnerMailPartnerFormat([call.partner_id]).get(
                    call.partner_id
                );
            }
            formattedCalls.push(data);
        }
        return formattedCalls;
    },
});
