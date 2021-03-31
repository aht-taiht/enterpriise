# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

{
    'name': 'Data Cleaning (merge)',
    'version': '1.2',
    'category': 'Productivity/Data Cleaning',
    'summary': 'Find duplicate records and merge them',
    'description': """Find duplicate records and merge them""",
    'depends': ['mail', 'data_cleaning'],
    'data': [
        'security/ir.model.access.csv',
        'views/data_merge_rule_views.xml',
        'views/data_merge_model_views.xml',
        'views/data_merge_record_views.xml',
        'views/data_merge_views.xml',
        'data/mail_templates.xml',
        'data/data_merge_cron.xml',
        'data/data_merge_data.xml',
    ],
    'auto_install': True,
    'installable': True,
    'application': False,
    'post_init_hook': 'post_init',
    'assets': {
        'web.assets_backend': [
            'data_merge/static/src/scss/data_merge.scss',
            'data_merge/static/src/js/data_merge_list_view.js',
        ],
        'web.assets_qweb': [
            'data_merge/static/src/xml/**/*',
        ],
    }
}
