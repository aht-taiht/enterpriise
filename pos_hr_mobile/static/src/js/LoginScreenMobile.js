odoo.define('pos_hr_mobile.LoginScreen', function (require) {
    "use strict";

    const Registries = require('point_of_sale.Registries');
    const LoginScreen = require('pos_hr.LoginScreen');
    const BarcodeScanner = require('@web_enterprise/webclient/barcode/barcode_scanner');

    const LoginScreenMobile = LoginScreen => class extends LoginScreen {
        constructor() {
            super(...arguments);
            this.hasMobileScanner = BarcodeScanner.isBarcodeScannerSupported();
        }

        async open_mobile_scanner() {
            const data = await BarcodeScanner.scanBarcode();
            if (data) {
                this.env.pos.barcode_reader.scan(data);
                mobile.methods.vibrate({'duration': 100});
            } else {
                mobile.methods.showToast({'message': 'Please, Scan again !!'});
            }
        }
    };
    Registries.Component.extend(LoginScreen, LoginScreenMobile);

    return LoginScreen;
});
