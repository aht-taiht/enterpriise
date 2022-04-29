# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

{
    'name': 'Salary Configurator - Payroll',
    'category': 'Human Resources',
    'summary': 'Adds a Gross to Net Salary Simulaton',
    'depends': [
        'hr_contract_salary',
        'hr_payroll',
    ],
    'data': [
        'data/hr_contract_salary_resume_data.xml',
        'views/menuitems.xml',
        'views/hr_contract_views.xml',
    ],
    'license': 'OEEL-1',
    'auto_install': True,
    'assets': {
        'web.assets_frontend': [
            'hr_contract_salary_payroll/static/src/js/*.js',
        ],
        'web.assets_backend': [
            'hr_contract_salary_payroll/static/src/js/tours/*.js',
        ],
        'web.assets_tests': [
            'hr_contract_salary_payroll/static/tests/**/*.js',
        ],
    }
}
