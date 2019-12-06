odoo.define('stock_barcode.picking_client_action', function (require) {
'use strict';

var core = require('web.core');
var ClientAction = require('stock_barcode.ClientAction');
var ViewsWidget = require('stock_barcode.ViewsWidget');

var _t = core._t;

var PickingClientAction = ClientAction.extend({
    custom_events: _.extend({}, ClientAction.prototype.custom_events, {
        'picking_print_delivery_slip': '_onPrintDeliverySlip',
        'picking_print_picking': '_onPrintPicking',
        'picking_print_barcodes_zpl': '_onPrintBarcodesZpl',
        'picking_print_barcodes_pdf': '_onPrintBarcodesPdf',
        'picking_scrap': '_onScrap',
        'put_in_pack': '_onPutInPack',
        'open_package': '_onOpenPackage',
    }),

    init: function (parent, action) {
        this._super.apply(this, arguments);
        this.context = action.context;
        this.commands['O-BTN.scrap'] = this._scrap.bind(this);
        this.commands['O-BTN.validate'] = this._validate.bind(this);
        this.commands['O-BTN.cancel'] = this._cancel.bind(this);
        this.commands['O-BTN.pack'] = this._putInPack.bind(this);
        this.commands['O-BTN.print-slip'] = this._printDeliverySlip.bind(this);
        this.commands['O-BTN.print-op'] = this._printPicking.bind(this);
        if (! this.actionParams.pickingId) {
            this.actionParams.pickingId = action.context.active_id;
            this.actionParams.model = 'stock.picking';
        }
        this.methods = {
            cancel: 'action_cancel',
            validate: 'button_validate',
        };
        this.viewInfo = 'stock_barcode.stock_picking_barcode';
    },

    willStart: function () {
        var self = this;
        var res = this._super.apply(this, arguments);
        res.then(function() {
            // Get the usage of the picking type of `this.picking_id` to chose the mode between
            // `receipt`, `internal`, `delivery`.
            var picking_type_code = self.currentState.picking_type_code;
            var picking_state = self.currentState.state;
            if (picking_type_code === 'incoming') {
                self.mode = 'receipt';
            } else if (picking_type_code === 'outgoing') {
                self.mode = 'delivery';
            } else {
                self.mode = 'internal';
            }

            if (self.currentState.group_stock_multi_locations === false) {
                self.mode = 'no_multi_locations';
            }

            if (picking_state === 'done') {
                self.mode = 'done';
            } else if (picking_state === 'cancel') {
                self.mode = 'cancel';
            }
            self.allow_scrap = (
                (picking_type_code === 'incoming') && (picking_state === 'done') ||
                (picking_type_code === 'outgoing') && (picking_state !== 'done') ||
                (picking_type_code === 'internal')
            )
        });
        return res;
    },

    //--------------------------------------------------------------------------
    // Private
    //--------------------------------------------------------------------------

    /**
     * @override
     */
    _createLineCommand: function (line) {
        return [0, 0, {
            picking_id: line.picking_id,
            product_id:  line.product_id.id,
            product_uom_id: line.product_uom_id[0],
            qty_done: line.qty_done,
            location_id: line.location_id.id,
            location_dest_id: line.location_dest_id.id,
            lot_name: line.lot_name,
            lot_id: line.lot_id && line.lot_id[0],
            state: 'assigned',
            owner_id: line.owner_id && line.owner_id[0],
            package_id: line.package_id ? line.package_id[0] : false,
            result_package_id: line.result_package_id ? line.result_package_id[0] : false,
            dummy_id: line.virtual_id,
        }];
    },

    /**
     * @override
     */
    _getAddLineDefaultValues: function (currentPage) {
        const values = this._super(currentPage);
        values.default_location_dest_id = currentPage.location_dest_id;
        values.default_picking_id = this.currentState.id;
        values.default_qty_done = 1;
        return values;
    },

    /**
     * @override
     */
    _getLines: (state) => state.move_line_ids,

    /**
     * @override
     */
    _lot_name_used: function (product, lot_name) {
        var lines = this._getLines(this.currentState);
        for (var i = 0; i < lines.length; i++) {
            var line = lines[i];
            if (line.qty_done !== 0 && line.product_id.id === product.id &&
                (line.lot_name && line.lot_name === lot_name)) {
                return true;
            }
        }
        return false;
    },

    /**
     * @override
     */
    _getRecordId: function () {
        return this.actionParams.pickingId;
    },

    /**
     * @override
     */
    _getPageFields: function () {
        return [
            ['location_id', 'location_id.id'],
            ['location_name', 'location_id.display_name'],
            ['location_dest_id', 'location_dest_id.id'],
            ['location_dest_name', 'location_dest_id.display_name'],
        ];
    },

    /**
     * @override
     */
    _getWriteableFields: function () {
        return ['qty_done', 'location_id.id', 'location_dest_id.id', 'lot_name', 'lot_id.id', 'result_package_id', 'owner_id.id'];
    },

    /**
     * @override
     */
    _getLinesField: function () {
        return 'move_line_ids';
    },

    /**
     * @override
     */
    _instantiateViewsWidget: function (defaultValues, params) {
        return new ViewsWidget(
            this,
            'stock.move.line',
            'stock_barcode.stock_move_line_product_selector',
            defaultValues,
            params
        );
    },

    /**
     * @override
     */
    _isPickingRelated: function () {
        return true;
    },

    /**
     * @override
     */
    _makeNewLine: function (params) {
        var virtualId = this._getNewVirtualId();
        var currentPage = this.pages[this.currentPageIndex];
        var newLine = {
            'picking_id': this.currentState.id,
            'product_id': {
                'id': params.product.id,
                'display_name': params.product.display_name,
                'barcode': params.barcode,
                'tracking': params.product.tracking,
            },
            'product_barcode': params.barcode,
            'display_name': params.product.display_name,
            'product_uom_qty': 0,
            'product_uom_id': params.product.uom_id,
            'qty_done': params.qty_done,
            'location_id': {
                'id': currentPage.location_id,
                'display_name': currentPage.location_name,
            },
            'location_dest_id': {
                'id': currentPage.location_dest_id,
                'display_name': currentPage.location_dest_name,
            },
            'package_id': params.package_id,
            'result_package_id': params.result_package_id,
            'state': 'assigned',
            'reference': this.name,
            'virtual_id': virtualId,
            'owner_id': params.owner_id,
        };
        return newLine;
    },

    /**
     * This method could open a wizard so it takes care of removing/adding the
     * "barcode_scanned" event listener.
     *
     * @override
     */
    _validate: function () {
        const self = this;
        const superValidate = this._super.bind(this);
        this.mutex.exec(function () {
            const successCallback = function () {
                self.do_notify(_t("Success"), _t("The transfer has been validated"));
                self.trigger_up('exit');
            };
            const exitCallback = function (infos) {
                if ((infos === undefined || !infos.special) && this.dialog.$modal.is(':visible')) {
                    successCallback();
                }
                core.bus.on('barcode_scanned', self, self._onBarcodeScannedHandler);
            };

            return superValidate().then((res) => {
                if (_.isObject(res)) {
                    const options = {
                        on_close: exitCallback,
                    };
                    core.bus.off('barcode_scanned', self, self._onBarcodeScannedHandler);
                    return self.do_action(res, options);
                } else {
                    return successCallback();
                }
            });
        });
    },

    /**
     * @override
     */
    _cancel: function () {
        const superCancel = this._super.bind(this);
        this.mutex.exec(() => {
            return superCancel().then(() => {
                this.do_notify(_t("Cancel"), _t("The transfer has been cancelled"));
                this.trigger_up('exit');
            });
        });
    },

    /**
     * Makes the rpc to `button_scrap`.
     * This method opens a wizard so it takes care of removing/adding the "barcode_scanned" event
     * listener.
     *
     * @private
     */
    _scrap: function () {
        var self = this;
        this.mutex.exec(function () {
            return self._save().then(function () {
                return self._rpc({
                    'model': 'stock.picking',
                    'method': 'button_scrap',
                    'args': [[self.actionParams.pickingId]],
                }).then(function(res) {
                    var exitCallback = function () {
                        core.bus.on('barcode_scanned', self, self._onBarcodeScannedHandler);
                    };
                    var options = {
                        on_close: exitCallback,
                    };
                    core.bus.off('barcode_scanned', self, self._onBarcodeScannedHandler);
                    return self.do_action(res, options);
                });
            });
        });
    },

    /**
     *
     */
    _putInPack: function () {
        var self = this;
        if (this.currentState.group_tracking_lot === false) {
            this.do_warn(_t("Delivery Packages needs to be enabled in Inventory Settings to use packages"));
            return;
        }
        this.mutex.exec(function () {
            return self._save().then(function () {
                return self._rpc({
                    'model': 'stock.picking',
                    'method': 'put_in_pack',
                    'args': [[self.actionParams.pickingId]],
                    kwargs: {
                        context: _.extend({}, self.context || {}, {barcode_view: true})
                    },
                }).then(function (res) {
                    var def = Promise.resolve();
                    self._endBarcodeFlow();
                    if (res.type && res.type === 'ir.actions.act_window') {
                        var exitCallback = function (infos) {
                            if (infos === undefined || !infos.special) {
                                self.trigger_up('reload');
                            }
                            core.bus.on('barcode_scanned', self, self._onBarcodeScannedHandler);
                        };
                        var options = {
                            on_close: exitCallback,
                        };
                        return def.then(function () {
                            core.bus.off('barcode_scanned', self, self._onBarcodeScannedHandler);
                            return self.do_action(res, options);
                        });
                    } else {
                        return def.then(function () {
                            return self.trigger_up('reload');
                        });
                    }
                });
            });
        });
    },

    /**
     * Handles the `open_package` OdooEvent. It hides the main widget and
     * display a standard kanban view with all quants inside the package.
     *
     * @private
     * @param {OdooEvent} ev
     */
    _onOpenPackage: function (ev) {
        var self = this;

        ev.stopPropagation();
        this.linesWidget.destroy();
        this.headerWidget.toggleDisplayContext('specialized');

        var virtual_id = _.isString(ev.data.id) ? ev.data.id : false;
        this.mutex.exec(function () {
            return self._save().then(function () {
                var currentPage = self.pages[self.currentPageIndex];
                var id = ev.data.id;
                if (virtual_id) {
                    var rec = _.find(currentPage.lines, function (line) {
                        return line.dummy_id === virtual_id;
                    });
                    id = rec.id;
                }
                var package_id = _.find(currentPage.lines, function (line) {
                    return line.id === id;
                });
                package_id = package_id.package_id[0];

                var params = {
                    searchQuery: {
                        context: self.context,
                        domain: [['package_id', '=', package_id]],
                    },
                };
                self.ViewsWidget = new ViewsWidget(self, 'stock.quant', 'stock_barcode.stock_quant_barcode_kanban', {}, params, false, 'kanban');
                return self.ViewsWidget.appendTo(self.$('.o_content'));
            });
        });
    },


    _printPicking: function () {
        var self = this;
        this.mutex.exec(function () {
            return self._save().then(function () {
                return self._rpc({
                    'model': 'stock.picking',
                    'method': 'do_print_picking',
                    'args': [[self.actionParams.pickingId]],
                }).then(function(res) {
                    return self.do_action(res);
                });
            });
        });
    },

    _printDeliverySlip: function () {
        var self = this;
        this.mutex.exec(function () {
            return self._save().then(function () {
                return self.do_action(self.currentState.actionReportDeliverySlipId, {
                    'additional_context': {
                        'active_id': self.actionParams.pickingId,
                        'active_ids': [self.actionParams.pickingId],
                        'active_model': 'stock.picking',
                    }
                });
            });
        });
    },

    _printBarcodesZpl: function () {
        var self = this;
        this.mutex.exec(function () {
            return self._save().then(function () {
                return self.do_action(self.currentState.actionReportBarcodesZplId, {
                    'additional_context': {
                        'active_id': self.actionParams.pickingId,
                        'active_ids': [self.actionParams.pickingId],
                        'active_model': 'stock.picking',
                    }
                });
            });
        });
    },

    _printBarcodesPdf: function () {
        var self = this;
        this.mutex.exec(function () {
            return self._save().then(function () {
                return self.do_action(self.currentState.actionReportBarcodesPdfId, {
                    'additional_context': {
                        'active_id': self.actionParams.pickingId,
                        'active_ids': [self.actionParams.pickingId],
                        'active_model': 'stock.picking',
                    }
                });
            });
        });
    },

    /**
     * @override
     */
    _updateLineCommand: function (line) {
        return [1, line.id, {
            qty_done : line.qty_done,
            location_id: line.location_id.id,
            location_dest_id: line.location_dest_id.id,
            lot_id: line.lot_id && line.lot_id[0],
            lot_name: line.lot_name,
            owner_id: line.owner_id && line.owner_id[0],
            package_id: line.package_id ? line.package_id[0] : false,
            result_package_id: line.result_package_id ? line.result_package_id[0] : false,
        }];
    },

    //--------------------------------------------------------------------------
    // Handlers
    //--------------------------------------------------------------------------

    /**
     * Handles the `print_picking` OdooEvent. It makes an RPC call
     * to the method 'do_print_picking'.
     *
     * @private
     * @param {OdooEvent} ev
     */
    _onPrintPicking: function (ev) {
        ev.stopPropagation();
        this._printPicking();
    },

    /**
     * Handles the `print_delivery_slip` OdooEvent. It makes an RPC call
     * to the method 'do_action' on a 'ir.action_window' with the additional context
     * needed
     *
     * @private
     * @param {OdooEvent} ev
     */
    _onPrintDeliverySlip: function (ev) {
        ev.stopPropagation();
        this._printDeliverySlip();
    },

    /**
     * Handles the `print_barcodes_zpl` OdooEvent. It makes an RPC call
     * to the method 'do_print_barcodes_zpl'.
     *
     * @private
     * @param {OdooEvent} ev
     */
    _onPrintBarcodesZpl: function (ev) {
        ev.stopPropagation();
        this._printBarcodesZpl();
    },

    /**
     * Handles the `print_barcodes_pdf` OdooEvent. It makes an RPC call
     * to the method 'do_print_barcodes_zpl'.
     *
     * @private
     * @param {OdooEvent} ev
     */
    _onPrintBarcodesPdf: function (ev) {
        ev.stopPropagation();
        this._printBarcodesPdf();
    },

    /**
     * Handles the `scan` OdooEvent. It makes an RPC call
     * to the method 'button_scrap' to scrap a picking.
     *
     * @private
     * @param {OdooEvent} ev
     */
    _onScrap: function (ev) {
        ev.stopPropagation();
        this._scrap();
    },

    /**
     * Handles the `Put in pack` OdooEvent. It makes an RPC call
     * to the method 'put_in_pack' to create a pack and link move lines to it.
     *
     * @private
     * @param {OdooEvent} ev
     */
    _onPutInPack: function (ev) {
        ev.stopPropagation();
        this._putInPack();
    },
});

core.action_registry.add('stock_barcode_picking_client_action', PickingClientAction);

return PickingClientAction;

});
