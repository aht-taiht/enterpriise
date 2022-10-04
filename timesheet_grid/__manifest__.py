# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.
# YTI FIXME: This module should be named timesheet_enterprise
{
    'name': "Timesheets",
    'summary': "Track employee time on tasks",
    'description': """
* Timesheet submission and validation
* Activate grid view for timesheets
    """,
    'version': '1.0',
    'depends': ['project_enterprise', 'web_grid', 'hr_timesheet', 'timer'],
    'category': 'Services/Timesheets',
    'sequence': 65,
    'data': [
        'data/ir_cron_data.xml',
        'data/mail_template_data.xml',
        'data/timesheet_grid_data.xml',
        'security/timesheet_security.xml',
        'security/ir.model.access.csv',
        'views/hr_timesheet_views.xml',
        'views/res_config_settings_views.xml',
        'report/timesheets_analysis_report.xml',
        'wizard/timesheet_merge_wizard_views.xml',
        'wizard/project_task_create_timesheet_views.xml',
    ],
    'demo': [
        'data/timesheet_grid_demo.xml',
    ],
    'website': ' https://www.odoo.com/app/timesheet',
    'auto_install': ['web_grid', 'hr_timesheet'],
    'application': True,
    'license': 'OEEL-1',
    'pre_init_hook': 'pre_init_hook',
    'uninstall_hook': 'uninstall_hook',
    'assets': {
        'web.assets_backend': [
            'timesheet_grid/static/src/**/*',
        ],
        'web.assets_tests': [
            'timesheet_grid/static/tests/tours/timesheet_record_time.js',
        ],
        'web.qunit_suite_tests': [
            ('after', 'web_grid/static/tests/mock_server.js', 'timesheet_grid/static/tests/legacy/timesheet_uom_tests.js'),
            ('after', 'web_grid/static/tests/mock_server.js', 'timesheet_grid/static/tests/timesheet_grid_tests.js'),
            ('after', 'web_grid/static/tests/mock_server.js', 'timesheet_grid/static/tests/timesheet_timer_grid_tests.js'),
            ('after', 'web_grid/static/tests/mock_server.js', 'timesheet_grid/static/tests/task_progress_gantt_test.js'),
            "timesheet_grid/static/tests/timesheet_uom_timer_tests.js",
        ],
    }
}
