# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

{
    'name': 'Barcode for Batch Transfer',
    'version': '1.0',
    'category': 'Inventory/Inventory',
    'summary': "Add the support of batch transfers into the barcode view",
    'description': "",
    'depends': ['stock_barcode', 'stock_picking_batch'],
    'data': [
        'security/ir.model.access.csv',
        'views/stock_barcode_picking.xml',
        'views/stock_barcode_picking_batch.xml',
        'views/stock_move_line_views.xml',
        'views/stock_quant_package_views.xml',
        'wizard/stock_barcode_picking_batch_group_pickings.xml',
        'data/data.xml',
    ],
    'demo': [
        'data/stock_barcode_picking_batch_demo.xml',
    ],
    'application': False,
    'auto_install': True,
    'assets': {
        'web.assets_backend': [
            'stock_barcode_picking_batch/static/src/js/stock_barcode_picking_batch.js',
            'stock_barcode_picking_batch/static/src/js/client_action/lines_widget.js',
            'stock_barcode_picking_batch/static/src/js/client_action/picking_batch_client_action.js',
            'stock_barcode_picking_batch/static/src/js/client_action/picking_batch_create_client_action.js',
            'stock_barcode_picking_batch/static/src/js/client_action/settings_widget.js',
            'stock_barcode_picking_batch/static/src/js/client_action/stock_barcode_picking_batch_kanban_record.js',
            'stock_barcode_picking_batch/static/src/js/tours/tour_helper_stock_barcode_picking_batch.js',
            'stock_barcode_picking_batch/static/src/js/tours/tour_test_barcode_batch_flows.js',
            'stock_barcode_picking_batch/static/src/scss/client_action.scss',
        ],
        'web.assets_qweb': [
            'stock_barcode_picking_batch/static/src/xml/**/*',
        ],
    }
}
