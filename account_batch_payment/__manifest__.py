# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.
{
    'name': 'Batch Payment',
    'version': '1.0',
    'category': 'Accounting/Accounting',
    'description': """
Batch Payments
=======================================
Batch payments allow grouping payments.

They are used namely, but not only, to group several cheques before depositing them in a single batch to the bank.
The total amount deposited will then appear as a single transaction on your bank statement.
When you reconcile, simply select the corresponding batch payment to reconcile all the payments in the batch.
    """,
    'website': 'https://www.odoo.com/page/accounting',
    'depends': ['account'],
    'data': [
        'security/account_batch_payment_security.xml',
        'security/ir.model.access.csv',
        'data/account_batch_payment_data.xml',
        'report/account_batch_payment_reports.xml',
        'report/account_batch_payment_report_templates.xml',
        'views/account_batch_payment_views.xml',
        'views/account_payment_views.xml',
        'views/account_journal_views.xml',
        'wizard/download_wizard_views.xml',
        'wizard/batch_error_views.xml',
    ],
    'test': [],
    'installable': True,
    'license': 'OEEL-1',
    'assets': {
        'web.report_assets_common': [
            'account_batch_payment/static/src/scss/**/*',
        ],
        'web.assets_backend': [
            'account_batch_payment/static/src/css/account_reconciliation.css',
            'account_batch_payment/static/src/js/account_batch_payment_reconciliation.js',
        ],
        'web.qunit_suite_tests': [
            ('after', 'web/static/tests/views/kanban_tests.js', 'account_batch_payment/static/src/css/account_reconciliation.css'),
            ('after', 'web/static/tests/views/kanban_tests.js', 'account_batch_payment/static/test/reconciliation_tests.js'),
        ],
        'web.assets_qweb': [
            'account_batch_payment/static/src/xml/**/*',
        ],
    }
}
