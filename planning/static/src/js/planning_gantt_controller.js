/** @odoo-module alias=planning.PlanningGanttController **/

import GanttController from 'web_gantt.GanttController';
import { _t } from 'web.core';
import Dialog from 'web.Dialog';
import { FormViewDialog } from 'web.view_dialogs';

var PlanningGanttController = GanttController.extend({
    events: Object.assign({}, GanttController.prototype.events, {
        'click .o_gantt_button_copy_previous_week': '_onCopyWeekClicked',
        'click .o_gantt_button_send_all': '_onSendAllClicked',
    }),
    buttonTemplateName: 'PlanningGanttView.buttons',

    //--------------------------------------------------------------------------
    // Public
    //--------------------------------------------------------------------------

    _renderButtonQWebParameter: function () {
        return Object.assign({}, this._super(...arguments), {
            activeActions: this.activeActions
        });
    },

    //--------------------------------------------------------------------------
    // Private
    //--------------------------------------------------------------------------

    /**
     * @override
     */
    _onAddClicked: function (ev) {
        ev.preventDefault();
        const { startDate, stopDate } = this.model.get();
        const today = moment().startOf('date'); // for the context we want the beginning of the day and not the actual hour.
        if (startDate.isSameOrBefore(today, 'day') && stopDate.isSameOrAfter(today, 'day')) {
            // get the today date if the interval dates contain the today date.
            const context = this._getDialogContext(today);
            for (const k in context) {
                context[`default_${k}`] = context[k];
            }
            this._onCreate(context);
            return;
        }
        this._super(...arguments);
    },

    /**
     * Opens dialog to add/edit/view a record
     * Override required to execute the reload of the gantt view when an action is performed on a
     * single record.
     *
     * @private
     * @param {integer|undefined} resID
     * @param {Object|undefined} context
     */
    _openDialog: function (resID, context) {
        var self = this;
        var record = resID ? _.findWhere(this.model.get().records, {id: resID,}) : {};
        var title = resID ? record.display_name : _t("Open");

        const dialog = new FormViewDialog(this, {
            title: _.str.sprintf(title),
            res_model: this.modelName,
            view_id: this.dialogViews[0][0],
            res_id: resID,
            readonly: !this.is_action_enabled('edit'),
            deletable: this.is_action_enabled('edit') && resID,
            context: _.extend({}, this.context, context),
            on_saved: this.reload.bind(this, {}),
            on_remove: this._onDialogRemove.bind(this, resID),
        });
        dialog.on('closed', this, function(ev){
            // we reload as record can be created or modified (sent, unpublished, ...)
            self.reload();
        });
        dialog.on('execute_action', this, function(e) {
            const action_name = e.data.action_data.name || e.data.action_data.special;
            const event_data = _.clone(e.data);

            if (action_name === "unlink") {
                e.stopPropagation();
                const message = _t('Are you sure that you want to do delete this shift?');

                Dialog.confirm(self, message, {
                    confirm_callback: function(evt) {
                        self.trigger_up('execute_action', event_data);
                        _.delay(function() { self.dialog.destroy() }, 100);
                    },
                    cancel_callback: function(evt) {
                        self.dialog.$footer.find('button').removeAttr('disabled');
                    }
                });
            }
        });

        self.dialog = dialog.open();
        return self.dialog;
    },

    //--------------------------------------------------------------------------
    // Handlers
    //--------------------------------------------------------------------------

    /**
     * @private
     * @param {MouseEvent} ev
     */
    _onCopyWeekClicked: function (ev) {
        ev.preventDefault();
        var state = this.model.get();
        var self = this;
        self._rpc({
            model: self.modelName,
            method: 'action_copy_previous_week',
            args: [
                self.model.convertToServerTime(state.startDate),
                this.model._getDomain(),
            ],
            context: _.extend({}, self.context || {}),
        })
        .then(function (result) {
            let notificationOptions = {
                type: 'success',
                message: `<i class="fa fa-fw fa-check"/> ${_t("The shifts from the previous week have successfully been copied.")}`,
            };
            if (!result) {
                notificationOptions = {
                    type: 'danger',
                    message: _t('There are no shifts to copy or the previous shifts were already copied.'),
                };
            }
            self.displayNotification(notificationOptions);
            self.reload();
        });
    },
    /**
     * @private
     * @param {MouseEvent} ev
     */
    _onSendAllClicked: function (ev) {
        ev.preventDefault();
        var self = this;
        var state = this.model.get();

        if (!state.records || state.records.length === 0) {
            this.displayNotification({
                type: 'danger',
                message: _t("There are no shifts to send or publish.")
            });
            return;
        }

        var additional_context = _.extend({}, this.context, {
           'default_start_datetime': this.model.convertToServerTime(state.startDate),
           'default_end_datetime': this.model.convertToServerTime(state.stopDate),
           'default_slot_ids': _.pluck(this.model.get().records, 'id'),
           'scale': state.scale,
           'active_domain': this.model.domain,
           'active_ids': this.model.get().records,
           'default_employee_ids': _.filter(_.pluck(self.initialState.rows, 'resId'), Boolean),
        });
        return this.do_action('planning.planning_send_action', {
            additional_context: additional_context,
            on_close: function () {
                self.reload();
            }
        });
    },
    /**
     * @private
     * @override
     * @param {MouseEvent} ev
     */
    _onScaleClicked: function (ev) {
        this._super.apply(this, arguments);
        var $button = $(ev.currentTarget);
        var scale = $button.data('value');
        if (scale !== 'week') {
            this.$('.o_gantt_button_copy_previous_week').hide();
        } else {
            this.$('.o_gantt_button_copy_previous_week').show();
        }
    },
});

export default PlanningGanttController;
