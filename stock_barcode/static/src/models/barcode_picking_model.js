/** @odoo-module **/

import BarcodeModel from '@stock_barcode/models/barcode_model';
import {_t} from "web.core";
import { sprintf } from '@web/core/utils/strings';

export default class BarcodePickingModel extends BarcodeModel {
    constructor(params) {
        super(...arguments);
        this.formViewReference = 'stock_barcode.stock_picking_barcode';
        this.lineModel = 'stock.move.line';
        this.lineFormViewReference = 'stock_barcode.stock_move_line_product_selector';
        this.validateMessage = _t("The transfer has been validated");
        this.validateMethod = 'button_validate';
    }

    setData(data) {
        super.setData(...arguments);
        // Manage extra information for locations
        this.currentDestLocationId = this._defaultDestLocationId();
        if (this.pageLines.length > 0) {
            this.currentDestLocationId = this.pageLines[0].location_dest_id;
        }
        this.locationList = [];
        this.destLocationList = [];
        data.data.source_location_ids.forEach(id => {
            this.locationList.push(this.cache.getRecord('stock.location', id));
        });
        data.data.destination_locations_ids.forEach(id => {
            this.destLocationList.push(this.cache.getRecord('stock.location', id));
        });
    }

    async changeDestinationLocation(id, moveScannedLineOnly) {
        this.currentDestLocationId = id;
        if (moveScannedLineOnly && this.previousScannedLines.length) {
            this.currentDestLocationId = id;
            for (const line of this.previousScannedLines) {
                // If the line is complete, we move it...
                if (!line.product_uom_qty || line.qty_done >= line.product_uom_qty) {
                    line.location_dest_id = id;
                    this._markLineAsDirty(line);
                } else { // ... otherwise, we split it to a new line.
                    const newLine = Object.assign({}, line, this._getNewLineDefaultValues());
                    this.currentState.lines.push(newLine);
                    newLine.qty_done = line.qty_done;
                    line.qty_done = 0;
                    this._markLineAsDirty(newLine);
                }
            }
        } else {
            // If the button was used to change the location, if will change the
            // destination location of all the page's move lines.
            for (const line of this.pageLines) {
                line.location_dest_id = id;
                this._markLineAsDirty(line);
            }
        }
        // Forget what lines have been scanned.
        this.scannedLinesVirtualId = [];
        this.lastScannedPackage = false;

        await this.save();
        this._groupLinesByPage(this.currentState);
        for (let i = 0; i < this.pages.length; i++) {
            const page = this.pages[i];
            if (page.sourceLocationId === this.currentLocationId &&
                page.destinationLocationId === this.currentDestLocationId) {
                this.pageIndex = i;
                break;
            }
        }
        this.selectedLineVirtualId = false;
    }

    getQtyDone(line) {
        return line.qty_done;
    }

    getQtyDemand(line) {
        return line.product_uom_qty;
    }

    nextPage() {
        this.highlightDestinationLocation = false;
        return super.nextPage(...arguments);
    }

    previousPage() {
        this.highlightDestinationLocation = false;
        return super.previousPage(...arguments);
    }

    async updateLine(line, args) {
        await super.updateLine(...arguments);
        let {result_package_id} = args;
        if (result_package_id) {
            if (typeof result_package_id === 'number') {
                result_package_id = this.cache.getRecord('stock.quant.package', result_package_id);
            }
            line.result_package_id = result_package_id;
        }
    }

    updateLineQty(virtualId, qty = 1) {
        this.actionMutex.exec(() => {
            const line = this.pageLines.find(l => l.virtual_id === virtualId);
            this.updateLine(line, {qty_done: qty});
            this.trigger('update');
        });
    }

    get barcodeInfo() {
        if (this.isCancelled || this.isDone) {
            return {
                class: this.isDone ? 'picking_already_done' : 'picking_already_cancelled',
                message: this.isDone ?
                    _t("This picking is already done") :
                    _t("This picking is cancelled"),
                warning: true,
            };
        }
        return super.barcodeInfo;
    }

    get canBeProcessed() {
        return !['cancel', 'done'].includes(this.record.state);
    }

    get canCreateNewLot() {
        return this.record.use_create_lots;
    }

    get destLocation() {
        return this.cache.getRecord('stock.location', this.currentDestLocationId);
    }

    get displayCancelButton() {
        return !['done', 'cancel'].includes(this.record.state);
    }

    get displayDestinationLocation() {
        return this.groups.group_stock_multi_locations &&
            ['incoming', 'internal'].includes(this.record.picking_type_code);
    }

    get displayResultPackage() {
        return true;
    }

    get displaySourceLocation() {
        return super.displaySourceLocation &&
            ['internal', 'outgoing'].includes(this.record.picking_type_code);
    }

    get highlightNextButton() {
        if (!this.pageLines.length) {
            return false;
        }
        for (const line of this.pageLines) {
            if (line.product_uom_qty && line.qty_done < line.product_uom_qty) {
                return false;
            }
        }
        return Boolean(this.pageLines.length);
    }

    get highlightValidateButton() {
        return this.highlightNextButton;
    }

    get informationParams() {
        return {
            model: this.params.model,
            view: this.formViewReference,
            params: { currentId: this.params.id },
        };
    }

    get isDone() {
        return this.record.state === 'done';
    }

    get isCancelled() {
        return this.record.state === 'cancel';
    }

    get printButtons() {
        return [
            {
                name: _t("Print Picking Operations"),
                class: 'o_print_picking',
                method: 'do_print_picking',
            }, {
                name: _t("Print Delivery Slip"),
                class: 'o_print_delivery_slip',
                method: 'action_print_delivery_slip',
            }, {
                name: _t("Print Barcodes ZPL"),
                class: 'o_print_barcodes_zpl',
                method: 'action_print_barcode_zpl',
            }, {
                name: _t("Print Barcodes PDF"),
                class: 'o_print_barcodes_pdf',
                method: 'action_print_barcode_pdf',
            },
        ];
    }

    get selectedLine() {
        const selectedLine = super.selectedLine;
        if (selectedLine && selectedLine.location_dest_id === this.currentDestLocationId) {
            return selectedLine;
        }
        return false;
    }

    get useExistingLots() {
        return this.record.use_existing_lots;
    }

    // -------------------------------------------------------------------------
    // Private
    // -------------------------------------------------------------------------

    _getNewLineDefaultContext() {
        const picking = this.cache.getRecord(this.params.model, this.params.id);
        return {
            default_company_id: picking.company_id,
            default_location_id: this.location.id,
            default_location_dest_id: this.destLocation.id,
            default_picking_id: this.params.id,
            default_qty_done: 1,
        };
    }

    async _cancel() {
        await this.save();
        await this.orm.call(
            this.params.model,
            'action_cancel',
            [[this.params.id]]
        );
        this._cancelNotification();
        this.trigger('history-back');
    }

    _cancelNotification() {
        this.notification.add(_t("The transfer has been cancelled"));
    }

    async _changePage(pageIndex) {
        await super._changePage(...arguments);
        this.currentDestLocationId = this.pages[this.pageIndex].destinationLocationId;
        this.highlightDestinationLocation = false;
    }

    _convertDataToFieldsParams(args) {
        const params = {
            lot_name: args.lotName,
            product_id: args.product,
            qty_done: args.qty,
        };
        if (args.lot) {
            params.lot_id = args.lot;
        }
        if (args.package) {
            params.package_id = args.package;
        }
        if (args.resultPackage) {
            params.result_package_id = args.resultPackage;
        }
        if (args.owner) {
            params.owner_id = args.owner;
        }
        return params;
    }

    _createCommandVals(line) {
        const values = {
            dummy_id: line.virtual_id,
            location_id: line.location_id,
            location_dest_id: line.location_dest_id,
            lot_name: line.lot_name,
            lot_id: line.lot_id,
            package_id: line.package_id,
            picking_id: line.picking_id,
            product_id: line.product_id,
            product_uom_id: line.product_uom_id,
            owner_id: line.owner_id,
            qty_done: line.qty_done,
            result_package_id: line.result_package_id,
            state: 'assigned',
        };
        for (const [key, value] of Object.entries(values)) {
            values[key] = this._fieldToValue(value);
        }
        return values;
    }

    _createLinesState() {
        const lines = [];
        const picking = this.cache.getRecord(this.params.model, this.params.id);
        for (const id of picking.move_line_ids) {
            const smlData = this.cache.getRecord('stock.move.line', id);
            // Checks if this line is already in the picking's state to get back
            // its `virtual_id` (and so, avoid to set a new `virtual_id`).
            const prevLine = this.currentState && this.currentState.lines.find(l => l.id === id);
            const previousVirtualId = prevLine && prevLine.virtual_id;
            smlData.virtual_id = Number(smlData.dummy_id) || previousVirtualId || this._uniqueVirtualId;
            smlData.product_id = this.cache.getRecord('product.product', smlData.product_id);
            smlData.product_uom_id = this.cache.getRecord('uom.uom', smlData.product_uom_id);
            smlData.lot_id = smlData.lot_id && this.cache.getRecord('stock.production.lot', smlData.lot_id);
            smlData.owner_id = smlData.owner_id && this.cache.getRecord('res.partner', smlData.owner_id);
            smlData.package_id = smlData.package_id && this.cache.getRecord('stock.quant.package', smlData.package_id);
            smlData.result_package_id = smlData.result_package_id && this.cache.getRecord('stock.quant.package', smlData.result_package_id);
            lines.push(Object.assign({}, smlData));
        }
        // Sorts lines by source location (important to have a deterministic pages' order).
        lines.sort((l1, l2) => l1.location_id < l2.location_id ? -1 : 0);
        return lines;
    }

    _defaultLocationId() {
        return this.record.location_id;
    }

    _defaultDestLocationId() {
        return this.record.location_dest_id;
    }

    /**
     * @override
     */
    _defineLocationId() {
        super._defineLocationId();
        const page = this.pages[this.pageIndex];
        if (page.lines.length) {
            this.currentDestLocationId = page.lines[0].location_dest_id;
        } else {
            this.currentDestLocationId = this._defaultDestLocationId();
        }
    }

    _getCommands() {
        return Object.assign(super._getCommands(), {
            'O-BTN.pack': this._putInPack.bind(this),
            'O-CMD.cancel': this._cancel.bind(this),
        });
    }

    _getDefaultMessageType() {
        if (this.groups.group_stock_multi_locations && (
            !this.highlightSourceLocation || this.highlightDestinationLocation
            ) && ['outgoing', 'internal'].includes(this.record.picking_type_code)) {
            return 'scan_src';
        }
        return 'scan_product';
    }

    _getLocationMessage() {
        if (this.groups.group_stock_multi_locations) {
            if (this.record.picking_type_code === 'outgoing') {
                return 'scan_product_or_src';
            } else {
                return 'scan_product_or_dest';
            }
        }
        return 'scan_product';
    }

    _getModelRecord() {
        return this.cache.getRecord(this.params.model, this.params.id);
    }

    _getNewLineDefaultValues() {
        const defaultValues = super._getNewLineDefaultValues();
        return Object.assign(defaultValues, {
            location_dest_id: this.destLocation.id,
            product_uom_qty: false,
            qty_done: 0,
            picking_id: this.params.id,
        });
    }

    _getFieldToWrite() {
        return [
            'location_id',
            'location_dest_id',
            'lot_id',
            'lot_name',
            'package_id',
            'owner_id',
            'qty_done',
            'result_package_id',
        ];
    }

    _getSaveCommand() {
        const commands = this._getSaveLineCommand();
        if (commands.length) {
            return {
                route: '/stock_barcode/save_barcode_data',
                params: {
                    model: this.params.model,
                    res_id: this.params.id,
                    write_field: 'move_line_ids',
                    write_vals: commands,
                },
            };
        }
        return {};
    }

    _incrementTrackedLine() {
        return !(this.record.use_create_lots || this.record.use_existing_lots);
    }

    _lineIsNotComplete(line) {
        return line.product_uom_qty && line.qty_done < line.product_uom_qty;
    }

    _moveEntirePackage() {
        return this.record.picking_type_entire_packs;
    }

    async _processLocation(barcodeData) {
        await super._processLocation(...arguments);
        if (barcodeData.destLocation) {
            await this._processLocationDestination(barcodeData);
            this.trigger('update');
        }
    }

    async _processLocationDestination(barcodeData) {
        this.highlightDestinationLocation = true;
        await this.changeDestinationLocation(barcodeData.destLocation.id, true);
        this.trigger('update');
        barcodeData.stopped = true;
    }

    async _putInPack() {
        if (!this.groups.group_tracking_lot) {
            return this.notification.add(
                _t("To use packages, enable 'Delivery Packages' from the settings"),
                { type: 'danger'}
            );
        }
        await this.save();
        const result = await this.orm.call(
            this.params.model,
            'action_put_in_pack',
            [[this.params.id]],
            { context: { barcode_view: true } }
        );
        if (typeof result === 'object') {
            this.trigger('process-action', result);
        } else {
            this.trigger('refresh');
        }
    }

    async _scanNewPackage(barcodeData, default_name) {
        // If no existing package found, put in pack in a new package.
        await this.save();
        const res = await this.orm.call(
            this.params.model,
            'action_put_in_pack',
            [[this.params.id]],
            { context: { barcode_view: true, default_name } }
        );
        if (typeof res === 'object') {
            this.trigger('process-action', res);
        } else {
            this.trigger('refresh');
        }
        barcodeData.stopped = true;
    }

    _setLocationFromBarcode(result, location) {
        if (this.record.picking_type_code === 'outgoing') {
            result.location = location;
        } else if (this.record.picking_type_code === 'incoming') {
            result.destLocation = location;
        } else if (this.previousScannedLines.length) {
            result.destLocation = location;
        } else {
            result.location = location;
        }
        return result;
    }

    _shouldSearchForAnotherLine(line, barcodeData) {
        return super._shouldSearchForAnotherLine(...arguments) || (
            barcodeData.product.tracking !== 'none' && barcodeData.lotNumber &&
            line.lot_name && barcodeData.lotNumber != line.lot_name
        );
    }

    _updateLineQty(line, args) {
        if (line.product_id.tracking === 'serial' && line.qty_done > 0 && (this.record.use_create_lots || this.record.use_existing_lots)) {
            return;
        }
        if (args.qty_done) {
            if (args.uom) {
                // An UoM was passed alongside the quantity, needs to check it's
                // compatible with the product's UoM.
                const productUOM = this.cache.getRecord('uom.uom', line.product_id.uom_id);
                if (args.uom.category_id !== productUOM.category_id) {
                    // Not the same UoM's category -> Can't be converted.
                    const message = sprintf(
                        _t("Scanned quantity uses %s as Unit of Measure, but this UoM is not compatible with the product's one (%s)."),
                        args.uom.name, productUOM.name
                    );
                    return this.notification.add(message, { title: _t("Wrong Unit of Measure"), type: 'danger' });
                } else if (args.uom.id !== productUOM.id) {
                    // Compatible but not the same UoM => Need a conversion.
                    args.qty_done = (args.qty_done / args.uom.factor) * productUOM.factor;
                }
            }
            line.qty_done += args.qty_done;
        }
    }

    _updateLotName(line, lotName) {
        line.lot_name = lotName;
    }
}
