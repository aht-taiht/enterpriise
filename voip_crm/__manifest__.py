# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

{
    'name': "VOIP for crm",

    'summary': """
        Link between voip and crm""",

    'description': """
        Allow to add the lead partner to phonecall list
    """,

    'category': 'Sales',
    'version': '1.0',

    # any module necessary for this one to work correctly
    'depends': ['base', 'crm', 'voip'],
    'auto-install': True,
    # always loaded
    'data': [
        'views/crm_lead_views.xml'
    ],
    'application': False,
    'license': 'OEEL-1',
}
