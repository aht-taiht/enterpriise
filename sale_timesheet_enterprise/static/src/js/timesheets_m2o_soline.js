/** @odoo-module alias=sale_timesheet_enterprise.TimesheetM2OSOLine **/
import fieldRegistry from 'web.field_registry';
import TimesheetM2OWidget from 'timesheet_grid.TimesheetM2OWidget';
import { _t } from 'web.core';
import { sprintf } from "@web/core/utils/strings";


const TimesheetM2OSOLine = TimesheetM2OWidget.extend({

    /**
     * @constructor
     */
    init: function (parent, value, rowIndex, workingHoursData) {
        this.modelName = 'sale.order.line';
        this.fieldName = 'so_line';

        this._super.apply(this, arguments);
        const uomName = this.cacheUnit ? this.cacheUnit.toLowerCase() : '';
        this.title = sprintf(_t(
            'Difference between the number of %s ordered on the sales order item and the number of %s delivered.'),
            uomName, uomName
        );
    },
});


fieldRegistry.add('timesheets_m2o_soline', TimesheetM2OSOLine);

export default TimesheetM2OSOLine;
