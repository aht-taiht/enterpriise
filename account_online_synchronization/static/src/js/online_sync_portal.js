odoo.define('account_online_synchronization.online_sync_portal', function (require) {
    'use strict';

    const publicWidget = require('web.public.widget');
    const { loadJS } = require('@web/core/assets');
    /* global OdooFin */

    publicWidget.registry.OnlineSyncPortal = publicWidget.Widget.extend({
        selector: '.oe_online_sync',
        events: _.extend({}, {
            'click #renew_consent_button': '_onRenewConsent',
        }),

        OdooFinConnector: function (parent, action) {
            // Ensure that the proxyMode is valid
            const modeRegexp = /^[a-z0-9-_]+$/i;
            if (!modeRegexp.test(action.params.proxyMode)) {
                return;
            }
            const url = 'https://' + action.params.proxyMode + '.odoofin.com/proxy/v1/odoofin_link';

            loadJS(url)
                .then(() => {
                    // Create and open the iframe
                    const params = {
                        data: action.params,
                        proxyMode: action.params.proxyMode,
                        onEvent: function (event, data) {
                            switch (event) {
                                case 'success':
                                    const processUrl = window.location.pathname + '/complete' + window.location.search;
                                    $('.js_reconnect').toggleClass('d-none');
                                    $.post(processUrl, {csrf_token: odoo.csrf_token});
                                default:
                                    return;
                            }
                        },
                    };
                    OdooFin.create(params);
                    OdooFin.open();
                });
            return;
        },

        /**
         * @private
         * @param {Event} ev
         */
        _onRenewConsent: async function (ev) {
            ev.preventDefault();
            const action = JSON.parse($(ev.currentTarget).attr('iframe-params'));
            return this.OdooFinConnector(this, action);
        },
    });

    return {
        OnlineSyncPortal: publicWidget.registry.OnlineSyncPortal,
    };

});
