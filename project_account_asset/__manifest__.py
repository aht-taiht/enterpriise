# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.


{
    'name': 'Project Accounting Assets',
    'version': '1.0',
    'category': 'Project/assets',
    'summary': 'Project accounting assets',
    'description': 'Bridge created to add the number of assets linked to an AA to a project form',
    'depends': ['project', 'account_asset'],
    'data': [
        'views/project_project_views.xml',
    ],
    'demo': [],
    'installable': True,
    'auto_install': True,
    'license': 'OEEL-1',
}
