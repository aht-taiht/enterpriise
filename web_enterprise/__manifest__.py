# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

{
    'name': 'Web Enterprise',
    'category': 'Hidden',
    'version': '1.0',
    'description': """
Odoo Enterprise Web Client.
===========================

This module modifies the web addon to provide Enterprise design and responsiveness.
        """,
    'depends': ['web'],
    'auto_install': True,
    'data': [
        'views/webclient_templates.xml',
    ],
    'assets': {
        'web.assets_qweb': [
            'web_enterprise/static/src/legacy/xml/*',
        ],
        'web._assets_primary_variables': [
            'web_enterprise/static/src/legacy/scss/primary_variables.scss',
        ],
        'web._assets_secondary_variables': [
            'web_enterprise/static/src/legacy/scss/secondary_variables.scss',
        ],
        'web._assets_backend_helpers': [
            ('replace', 'web/static/src/legacy/scss/bootstrap_overridden.scss', 'web_enterprise/static/src/legacy/scss/bootstrap_overridden.scss'),
        ],
        'web._assets_common_styles': [
            ('replace', 'web/static/src/legacy/scss/ui_extra.scss', 'web_enterprise/static/src/legacy/scss/ui.scss'),

            'web_enterprise/static/fonts/fonts.scss',
        ],
        'web.assets_backend': [
            ('replace', 'web/static/src/legacy/scss/webclient_extra.scss', 'web_enterprise/static/src/legacy/scss/webclient.scss'),
            ('replace', 'web/static/src/legacy/scss/webclient_layout.scss', 'web_enterprise/static/src/legacy/scss/webclient_layout.scss'),

            ('replace', 'web/static/src/legacy/scss/dropdown_extra.scss', 'web_enterprise/static/src/legacy/scss/fields.scss'),
            ('replace', 'web/static/src/legacy/scss/fields_extra.scss', 'web_enterprise/static/src/legacy/scss/form_view.scss'),
            ('replace', 'web/static/src/legacy/scss/form_view_extra.scss', 'web_enterprise/static/src/legacy/scss/list_view.scss'),
            ('replace', 'web/static/src/legacy/scss/list_view_extra.scss', 'web_enterprise/static/src/legacy/scss/search_view.scss'),
            ('replace', 'web/static/src/legacy/scss/search_view_extra.scss', 'web_enterprise/static/src/legacy/scss/dropdown.scss'),

            'web_enterprise/static/src/legacy/scss/base_settings_mobile.scss',
            'web_enterprise/static/src/legacy/scss/home_menu.scss',
            'web_enterprise/static/src/legacy/scss/home_menu_layout.scss',
            'web_enterprise/static/src/legacy/scss/search_panel_mobile.scss',
            'web_enterprise/static/src/legacy/scss/menu_mobile.scss',
            'web_enterprise/static/src/legacy/scss/menu_search.scss',
            'web_enterprise/static/src/legacy/scss/control_panel_layout.scss',
            'web_enterprise/static/src/legacy/scss/control_panel_mobile.scss',
            'web_enterprise/static/src/legacy/scss/datepicker.scss',
            'web_enterprise/static/src/legacy/scss/kanban_view.scss',
            'web_enterprise/static/src/legacy/scss/touch_device.scss',
            'web_enterprise/static/src/legacy/scss/snackbar.scss',
            'web_enterprise/static/src/legacy/scss/swipe_item_mixin.scss',
            'web_enterprise/static/src/legacy/scss/form_view_mobile.scss',
            'web_enterprise/static/src/legacy/scss/kanban_view_mobile.scss',
            'web_enterprise/static/src/legacy/scss/modal_mobile.scss',
            'web_enterprise/static/src/legacy/scss/promote_studio.scss',
            'web_enterprise/static/src/legacy/scss/web_calendar_mobile.scss',
            'web/static/src/legacy/scss/navbar_mobile.scss',

            ('replace', 'web/static/src/legacy/js/chrome/web_client.js', 'web_enterprise/static/src/legacy/js/web_client.js'),
            ('replace', 'web/static/src/legacy/js/chrome/menu.js', 'web_enterprise/static/src/legacy/js/menu.js'),
            ('replace', 'web/static/src/legacy/js/fields/upgrade_fields.js', 'web_enterprise/static/src/legacy/js/apps.js'),

            'web_enterprise/static/src/legacy/js/home_menu_wrapper.js',
            'web_enterprise/static/src/legacy/js/home_menu.js',
            'web_enterprise/static/src/legacy/js/expiration_panel.js',
            'web_enterprise/static/src/legacy/js/menu_mobile.js',
            'web_enterprise/static/src/legacy/js/res_config_settings.js',
            'web_enterprise/static/src/legacy/js/search_panel_mobile.js',
            'web_enterprise/static/src/legacy/js/control_panel.js',
            'web_enterprise/static/src/legacy/js/swipe_item_mixin.js',
            'web_enterprise/static/src/legacy/js/core/**/*.js',
            'web_enterprise/static/src/legacy/js/views/**/*.js',
            'web_enterprise/static/src/legacy/js/widgets/**/*.js',
        ],
        'web.qunit_suite_tests': [
            ('remove', 'web/static/tests/fields/upgrade_fields_tests.js'),
            ('replace', 'web/static/tests/chrome/menu_tests.js', 'web_enterprise/static/tests/legacy/menu_tests.js'),

            'web_enterprise/static/tests/legacy/test_utils.js',
            'web_enterprise/static/tests/legacy/home_menu_tests.js',
            'web_enterprise/static/tests/legacy/expiration_panel_tests.js',
            'web_enterprise/static/tests/legacy/upgrade_fields_tests.js',
            'web_enterprise/static/tests/legacy/views/list_tests.js',
        ],
        'web.qunit_mobile_suite_tests': [
            'web_enterprise/static/tests/legacy/test_utils.js',
            'web_enterprise/static/tests/legacy/action_manager_mobile_tests.js',
            'web_enterprise/static/tests/legacy/control_panel_mobile_tests.js',
            'web_enterprise/static/tests/legacy/mobile_company_switcher_tests.js',
            'web_enterprise/static/tests/legacy/form_tests.js',
            'web_enterprise/static/tests/legacy/mobile_menu_tests.js',
            'web_enterprise/static/tests/legacy/relational_fields_mobile_tests.js',
            'web_enterprise/static/tests/legacy/views/basic/basic_render_mobile_tests.js',
            'web_enterprise/static/tests/legacy/views/calendar_mobile_tests.js',
            'web_enterprise/static/tests/legacy/views/kanban_mobile_tests.js',
            'web_enterprise/static/tests/legacy/views/list_mobile_tests.js',
            'web_enterprise/static/tests/legacy/base_settings_mobile_tests.js',
            'web_enterprise/static/tests/legacy/components/action_menus_mobile_tests.js',
        ],
    },
    'license': 'OEEL-1',
}
