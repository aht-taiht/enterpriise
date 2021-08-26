odoo.define('web_mobile.barcode_mobile_mixin', function (require) {
"use strict";

const BarcodeScanner = require('@web_enterprise/webclient/barcode/barcode_scanner');

return {
    events: {
        'click .o_mobile_barcode': 'open_mobile_scanner'
    },
    async start() {
        const res = await this._super(...arguments);
        if (!BarcodeScanner.isBarcodeScannerSupported()) {
            this.$el.find(".o_mobile_barcode").remove();
        }
        return res;
    },
    async open_mobile_scanner() {
        const barcode = await BarcodeScanner.scanBarcode();
        if (barcode) {
            this._onBarcodeScanned(barcode);
            if ('vibrate' in window.navigator) {
                window.navigator.vibrate(100);
            }
        } else {
            this.displayNotification({
                type: 'warning',
                message: 'Please, Scan again !',
            });
        }
    }
};
});
