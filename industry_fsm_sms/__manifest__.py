# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

{
    'name': 'FSM - SMS',
    'version': '1.0',
    'category': 'Hidden',
    'summary':  'Send text messages when fsm task stage move',
    'description': "",
    'depends': ['industry_fsm', 'project_sms'],
    'data': [
        'data/industry_fsm_sms_data.xml'
    ],
    'demo': [
        'data/industry_fsm_sms_demo.xml'
    ],
    'application': False,
    'auto_install': True,
    'license': 'LGPL-3',
}
