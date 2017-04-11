odoo.define('web_mobile.datepicker', function (require) {
"use strict";

var web_datepicker = require('web.datepicker');

var mobile = require('web_mobile.rpc');

/**
 * Override odoo date-picker (bootstrap date-picker) to display mobile native
 * date picker. Because of it is better to show native mobile date-picker to
 * improve usability of Application (Due to Mobile users are used to native
 * date picker).
 */

web_datepicker.DateWidget.include({
    /**
     * @override
     */
    start: function () {
        this._super.apply(this, arguments);
        if (mobile.methods.requestDateTimePicker) {
            // `super` will initiate bootstrap date-picker object which is not
            // required in mobile application.
            if (this.picker) {
                this.picker.destroy();
            }
            this.set_readonly(true);
            this._setupMobilePicker();
        }
    },

    //--------------------------------------------------------------------------
    // Private
    //--------------------------------------------------------------------------

    /**
     * @private
     */
    _setupMobilePicker: function () {
        var self = this;
        this.$el.on('click', function () {
            mobile.methods.requestDateTimePicker({
                'value': self.get_value(),
                'type': self.type_of_date,
            }).then(function (response) {
                self.set_value(response.data);
                self.commit_value();
            });
        });
    },
});

});
