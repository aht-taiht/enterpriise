# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

{
    'name': 'Snail Mail Follow-Up',
    'version': '1.0',
    'category': 'Accounting/Accounting',
    'summary': "Extension to send follow-up documents by post",
    'description': """
Extension to send follow-up documents by post
    """,
    'depends': ['snailmail_account', 'account_followup'],
    'data': [
        'security/ir.model.access.csv',
        'data/account_followup_data.xml',
        'views/account_followup_views.xml',
        'views/assets.xml',
        'wizard/followup_send_views.xml',
    ],
    'demo': ['data/account_followup_demo.xml'],
    'auto_install': True,
    'license': 'OEEL-1',
    'assets': {
        'web.assets_backend': [
            'snailmail_account_followup/static/src/js/**/*',
            'snailmail_account_followup/static/src/xml/**/*',
        ],
        'snailmail_account_followup.followup_report_assets_snailmail': [
            ('include', 'web._assets_helpers'),
            'web/static/src/libs/bootstrap/pre_variables.scss',
            'web/static/lib/bootstrap/scss/_variables.scss',
        ],
    }
}
