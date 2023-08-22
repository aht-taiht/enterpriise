# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

{
    'name': "Event Barcode Scanning",
    'summary': "Add barcode scanning feature to event management.",
    'version': '1.0',
    'description': """
This module adds support for barcodes scanning to the Event management system.
A barcode is generated for each attendee and printed on the badge. When scanned,
the registration is confirmed.
    """,
    'category': 'Marketing/Events',
    'depends': ['barcodes', 'event'],
    'data': [
        'report/event_event_report.xml',
        'report/event_registration_report.xml',
        'views/event_event_views.xml',
        'views/event_registration_views.xml',
        'views/event_report_templates.xml',
        'views/res_config_settings_views.xml',
    ],
    'license': 'OEEL-1',
    'assets': {
        'web.assets_backend': [
            'event_barcode/static/src/**/*',
        ],
        'web.report_assets_common': [
            '/event_barcode/static/src/scss/event_full_page_ticket_report.scss',
        ],
    }
}
