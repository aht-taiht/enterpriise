# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

{
    'name': 'Indian Payroll',
    'countries': ['in'],
    'category': 'Human Resources/Payroll',
    'depends': ['hr_payroll', 'l10n_in'],
    'description': """
Indian Payroll Salary Rules.
============================

    -Configuration of hr_payroll for India localization
    -All main contributions rules for India payslip.
    * New payslip report
    * Employee Contracts
    * Allow to configure Basic / Gross / Net Salary
    * Employee PaySlip
    * Allowance / Deduction
    * Integrated with Leaves Management
    * Medical Allowance, Travel Allowance, Child Allowance, ...
    - Payroll Advice and Report
    - Yearly Salary by Head and Yearly Salary by Employee Report
    """,
    'data': [
        'data/report_paperformat.xml',
        'views/l10n_in_hr_payroll_report.xml',
        'data/res_partner_data.xml',
        'data/hr_salary_rule_category_data.xml',
        'data/hr_payroll_structure_type_data.xml',
        'data/hr_payroll_structure_data.xml',
        'data/salary_rules/hr_salary_rule_stipend_data.xml',
        'data/salary_rules/hr_salary_rule_ind_emp_data.xml',
        'data/salary_rules/hr_salary_rule_with_pf_data.xml',
        'data/salary_rules/hr_salary_rule_without_pf_data.xml',
        'data/salary_rules/hr_salary_rule_worker_data.xml',
        'data/hr_contract_type_data.xml',
        'data/hr_rule_parameters_data.xml',
        'data/ir_sequence_data.xml',
        'views/hr_contract_views.xml',
        'views/res_users_views.xml',
        'views/hr_employee_views.xml',
        'views/res_config_settings_views.xml',
        'views/hr_payroll_advice_views.xml',
        'views/hr_payslip_run_views.xml',
        'security/ir.model.access.csv',
        'views/report_payslip_details_template.xml',
        'views/report_hr_salary_employee_bymonth_template.xml',
        'wizard/hr_salary_employee_bymonth_view.xml',
        'wizard/hr_yearly_salary_detail_view.xml',
        'views/report_hr_yearly_salary_detail_template.xml',
        'views/report_payroll_advice_template.xml',
    ],
    'license': 'OEEL-1',
}
