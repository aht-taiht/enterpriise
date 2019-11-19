odoo.define('planning.PlanningGanttModel', function (require) {
    "use strict";

    var GanttModel = require('web_gantt.GanttModel');
    var _t = require('web.core')._t;

    var PlanningGanttModel = GanttModel.extend({
        /**
         * @override
         */
        reload: function (handle, params) {
            if ('context' in params && params.context.planning_groupby_role && !params.groupBy.length) {
                params.groupBy.unshift('employee_id');
                params.groupBy.unshift('role_id');
            }

            return this._super(handle, params);
        },
        /**
         * @private
         * @override
         * @returns {Object[]}
         */
        _generateRows: function (params) {
            var rows = this._super(params);
            // is the data grouped by?
            if(params.groupedBy && params.groupedBy.length){
                // in the last row is the grouped by field is null
                if(rows && rows.length && rows[rows.length - 1] && !rows[rows.length - 1].resId){
                    // then make it the first one
                    rows.unshift(rows.pop());
                }
            }
            // rename 'Undefined Employee' into 'Open Shifts'
            _.each(rows, function(row){
                if(row.groupedByField === 'employee_id' && !row.resId){
                    row.name = _t('Open Shifts');
                }
            });
            return rows;
        },
    });

    return PlanningGanttModel;
});
