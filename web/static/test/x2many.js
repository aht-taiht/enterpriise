odoo.define('web.test.x2many', function (require) {
'use strict';

var Tour = require('web.Tour');

Tour.register({
    id:   'widget_x2many',
    name: "one2many and many2many checks",
    mode: 'test',
    path: '/web#action=test_new_api.action_discussions',

    steps: [
        {
            title:      "wait web client",
            waitFor:    '.breadcrumb:contains(Discussions)'
        },
        // create test discussion
        {
            title:      "create new discussion",
            element:    '.o_web_client:has(.breadcrumb:contains(Discussions)) button.o_list_button_add'
        },
        {
            title:      "insert title",
            element:    'input.o_form_required',
            sampleText: 'test'
        },

        // add message a

        {
            title:      "create new message a",
            waitFor:    'input.o_form_required:propValue(test)',
            element:    '.tab-pane:eq(0) .o_form_field_x2many_list_row_add a'
        },
        {
            title:      "insert body a",
            element:    '.modal textarea.o_form_textarea',
            sampleText: 'a'
        },
        {
            title:      "save new message a",
            waitFor:    '.modal textarea.o_form_textarea:propValue(a)',
            element:    '.modal .modal-footer button:contains(Save)'
        },

        // add message b
        
        {
            title:      "create new message b",
            waitNot:    '.modal',
            waitFor:    '.o_web_client:has(textarea[name="message_concat"]:propValue([test] Administrator:a))',
            element:    '.tab-pane:eq(0) .o_form_field_x2many_list_row_add a'
        },
        {
            title:      "insert body b",
            element:    '.modal textarea.o_form_textarea',
            sampleText: 'b'
        },
        {
            title:      "save new message b",
            waitFor:    '.modal textarea.o_form_textarea:propValue(b)',
            element:    '.modal .modal-footer button:contains(Save)'
        },

        // change title to trigger on change

        {
            title:      "insert title",
            waitNot:    '.modal',
            waitFor:    'textarea[name="message_concat"]:propValue([test] Administrator:a\n[test] Administrator:b)',
            element:    'input.o_form_required',
            sampleText: 'test_trigger'
        },
        {
            title:      "blur the title field",
            waitFor:    'input.o_form_required:propValue(test_trigger)',
            element:    '.o_form_field_many2one input:first',
        },
        {
            title:      "check onchange",
            waitFor:    'textarea[name="message_concat"]:propValue([test_trigger] Administrator:a\n[test_trigger] Administrator:b)',
        },

        // change message b
        
        {
            title:      "edit message b",
            waitFor:    '.tab-pane:eq(0) .o_form_field.o_view_manager_content tbody tr td:contains([test_trigger] )',
            waitNot:    '.tab-pane:eq(0) .o_form_field.o_view_manager_content tbody tr[data-id]:eq(2)',
            element:    '.tab-pane:eq(0) .o_form_field.o_view_manager_content tbody tr td:containsExact(b)'
        },
        {
            title:      "change the body",
            element:    '.modal textarea.o_form_textarea',
            sampleText: 'bbb'
        },
        {
            title:      "save changes",
            waitFor:    '.modal textarea.o_form_textarea:propValue(bbb)',
            element:    '.modal .modal-footer button:contains(Save)'
        },

        // add message c
        
        {
            title:      "create new message c",
            waitNot:    '.modal',
            waitFor:    'textarea[name="message_concat"]:propValue([test_trigger] Administrator:a\n[test_trigger] Administrator:bbb)',
            element:    '.tab-pane:eq(0) .o_form_field_x2many_list_row_add a'
        },
        {
            title:      "insert body",
            element:    '.modal textarea.o_form_textarea',
            sampleText: 'c'
        },
        {
            title:      "save new message c",
            waitFor:    '.modal textarea.o_form_textarea:propValue(c)',
            element:    '.modal .modal-footer button:contains(Save)'
        },

        // add participants

        {
            title:      "change tab to Participants",
            waitNot:    '.modal',
            waitFor:    '.tab-pane:eq(0) .o_form_field.o_view_manager_content tbody tr[data-id]:eq(2)',
            element:    '[data-toggle="tab"]:contains(Participants)'
        },
        {
            title:      "click to add participants",
            element:    '.tab-pane:eq(1).active .o_form_field_x2many_list_row_add a'
        },
        {
            title:      "select participant 1",
            element:    '.modal tbody .o_list_record_selector input[type="checkbox"]:eq(0)'
        },
        {
            title:      "select participant 2",
            waitFor:    '.modal tbody .o_list_record_selector input[type="checkbox"]:eq(0):propChecked',
            element:    '.modal tbody .o_list_record_selector input[type="checkbox"]:eq(1)'
        },
        {
            title:      "save selected participants",
            waitFor:    '.modal tbody .o_list_record_selector input[type="checkbox"]:eq(1):propChecked',
            element:    '.o_selectcreatepopup_search_select'
        },

        // save
        
        {
            title:      "save discussion",
            waitFor:    '.tab-pane:eq(1) .o_form_field.o_view_manager_content tbody tr[data-id]:eq(1)',
            waitNot:    '.tab-pane:eq(1) .o_form_field.o_view_manager_content tbody tr[data-id]:eq(2)',
            element:    'button.o_form_button_save'
        },

        // check saved data

        {
            title:      "check data 1",
            waitFor:    '.tab-pane:eq(0) .o_form_field.o_view_manager_content tbody tr[data-id]:eq(2)',
            waitNot:    '.tab-pane:eq(0) .o_form_field.o_view_manager_content tbody tr[data-id]:eq(3)',
        },
        {
            title:      "check data 2",
            waitFor:    '.tab-pane:eq(0) .o_form_field.o_view_manager_content tr:has(td:containsExact(bbb)):has(td:containsExact([test_trigger] Administrator))',
        },
        {
            title:      "check data 3",
            waitFor:    '.tab-pane:eq(1) .o_form_field.o_view_manager_content tbody tr[data-id]:eq(1)',
            waitNot:    '.tab-pane:eq(1) .o_form_field.o_view_manager_content tbody tr[data-id]:eq(2)',
        },

        // edit

        {
            title:      "edit discussion",
            element:    'button.o_form_button_edit'
        },
        {
            title:      "change tab to Participants",
            waitFor:    '.o_form_editable',
            element:    '[data-toggle="tab"]:contains(Messages)'
        },

        // add message d

        {
            title:      "create new message d",
            waitFor:    'li.active a[data-toggle="tab"]:contains(Messages)',
            element:    '.tab-pane:eq(0) .o_form_field_x2many_list_row_add a'
        },
        {
            title:      "insert body",
            element:    '.modal textarea.o_form_textarea',
            sampleText: 'd'
        },
        {
            title:      "save new message d",
            waitFor:    '.modal textarea.o_form_textarea:propValue(d)',
            element:    '.modal .modal-footer button:contains(Save)'
        },

        // add message e
        
        {
            title:      "create new message e",
            waitNot:    '.modal',
            waitFor:    '.tab-pane:eq(0) .o_form_field.o_view_manager_content tbody tr td:containsExact(d)',
            element:    '.tab-pane:eq(0) .o_form_field_x2many_list_row_add a'
        },
        {
            title:      "insert body",
            element:    '.modal textarea.o_form_textarea',
            sampleText: 'e'
        },
        {
            title:      "save new message e",
            waitFor:    '.modal textarea.o_form_textarea:propValue(e)',
            element:    '.modal .modal-footer button:contains(Save)'
        },

        // change message a

        {
            title:      "edit message a",
            waitNot:    '.modal',
            waitFor:    '.tab-pane:eq(0) .o_form_field.o_view_manager_content tbody tr td:containsExact(e)',
            element:    '.tab-pane:eq(0) .o_form_field.o_view_manager_content tbody tr td:containsExact(a)'
        },
        {
            title:      "change the body",
            element:    '.modal textarea.o_form_textarea',
            sampleText: 'aaa'
        },
        {
            title:      "save changes",
            waitFor:    '.modal textarea.o_form_textarea:propValue(aaa)',
            element:    '.modal .modal-footer button:contains(Save)'
        },

        // change message e

        {
            title:      "edit message e",
            waitNot:    '.modal',
            waitFor:    '.oe_list_field_text:contains(aaa)',
            element:    '.oe_list_field_cell:containsExact(e)'
        },

        {
            title:      "open the many2one to select an other user",
            element:    '.modal .oe_m2o_drop_down_button',
        },
        {
            title:      "select an other user",
            element:    '.ui-autocomplete li:contains(Demo User)',
        },
        {
            title:      "test one2many's line onchange after many2one",
            waitFor:    '.oe_form_char_content:contains([test_trigger] Demo User)',
        },
        {
            title:      "test one2many field not triggered onchange",
            waitFor:    'textarea[name="message_concat"]:propValueContains([test_trigger] Administrator:e)',
        },
        {
            title:      "save changes",
            element:    '.o_formdialog_save'
        },
        {
            title:      "test one2many triggered the onchange on save for the line",
            waitFor:    '.oe_list_content td.oe_list_field_cell.oe_readonly:contains([test_trigger] Demo User)',
        },
        {
            title:      "test one2many triggered the onchange on save",
            waitFor:    'textarea[name="message_concat"]:propValueContains([test_trigger] Demo User:e)',
        },

        // remove
        
        {
            title:      "remove b",
            waitNot:    '.modal',
            waitFor:    '.tab-pane:eq(0) .o_form_field.o_view_manager_content tbody tr td:contains(aaa)',
            element:    '.tab-pane:eq(0) .o_form_field.o_view_manager_content tbody tr:has(td:containsExact(bbb)) .o_list_record_delete'
        },
        {
            title:      "remove e",
            waitNot:    'tr:has(td:containsExact(bbb))',
            element:    'tr:has(td:containsExact(e)) .o_list_record_delete'
        },

        // save
        
        {
            title:      "save discussion",
            waitNot:    'tr:has(td:containsExact(e))',
            element:    'button.o_form_button_save'
        },

        // check saved data

        {
            title:      "check data 4",
            waitNot:    '.tab-pane:eq(0) .o_form_field.o_view_manager_content tbody tr:has(.o_list_record_delete):eq(4)',
        },
        {
            title:      "check data 5",
            waitFor:    '.tab-pane:eq(0) .o_form_field.o_view_manager_content tbody:has(tr td:containsExact(aaa)):has(tr td:containsExact(c)):has(tr td:containsExact(d))',
        },
        {
            title:      "check data 6",
            waitFor:    '.tab-pane:eq(0) .o_form_field.o_view_manager_content tbody tr:has(td:containsExact([test_trigger] Administrator)):has(td:containsExact(aaa))',
        },
        {
            title:      "check data 7",
            waitFor:    '.tab-pane:eq(1) .o_form_field.o_view_manager_content tbody tr[data-id]:eq(1)',
            waitNot:    '.tab-pane:eq(1) .o_form_field.o_view_manager_content tbody tr[date-id]:eq(2)',
        },

        // edit

        {
            title:      "edit discussion",
            element:    'button.o_form_button_edit'
        },

        // add message ddd
        
        {
            title:      "create new message ddd",
            waitNot:    '.modal',
            waitFor:    '.tab-pane:eq(0) .o_form_field.o_view_manager_content tbody tr:has(td:containsExact(d))',
            element:    '.tab-pane:eq(0) .o_form_field_x2many_list_row_add a'
        },
        {
            title:      "select another user",
            element:    '.modal .o_form_field_many2one .o_dropdown_button',
        },
        {
            title:      "select demo user",
            element:    'li a:contains(Demo User)',
        },
        {
            title:      "test one2many's line onchange after many2one",
            waitFor:    '.modal .o_form_field:contains([test_trigger] Demo User)',
        },
        {
            title:      "insert body",
            element:    '.modal textarea.o_form_textarea',
            sampleText: 'ddd'
        },
        {
            title:      "save new message ddd",
            waitFor:    '.modal textarea.o_form_textarea:propValue(ddd)',
            element:    '.modal .modal-footer button:contains(Save)'
        },

        // trigger onchange
        
        {
            title:      "blur the one2many",
            waitFor:    '.tab-pane:eq(0) .o_form_field.o_view_manager_content tbody:has(tr td:containsExact(ddd))',
            element:    'input.o_form_required',
        },

        // check onchange data

        {
            title:      "check data 8",
            waitFor:    'textarea[name="message_concat"]:propValueContains([test_trigger] Administrator:aaa\n[test_trigger] Administrator:c\n[test_trigger] Administrator:d\n[test_trigger] Demo User:ddd)',
        },
        {
            title:      "check data 9",
            waitFor:    '.tab-pane:eq(0) .o_form_field.o_view_manager_content tbody tr[data-id]:eq(3)',
            waitNot:    '.tab-pane:eq(0) .o_form_field.o_view_manager_content tbody tr[data-id]:eq(4)',
        },

        // cancel
        
        {
            title:      "cancel change",
            waitFor:    '.tab-pane:eq(0) .o_form_field.o_view_manager_content tbody:has(tr td:containsExact(ddd))',
            element:    '.o_form_button_cancel',
            onload: function () {
                // remove the window alert (can't click on it with JavaScript tour)
                $('.oe_form_dirty').removeClass('oe_form_dirty');
            }
        },

        /////////////////////////////////////////////////////////////////////////////////////////////
        /////////////////////////////////////////////////////////////////////////////////////////////

        {
            title:      "switch to the second form view to test one2many with editable list (toggle menu dropdown)",
            waitFor:    '.tab-pane:eq(0) .o_form_field.o_view_manager_content tbody tr[data-id]:eq(2)',
            element:    'nav .o_menu_sections li a:containsExact(Discussions)'
        },

        {
            title:      "switch to the second form view to test one2many with editable list (open submenu)",
            element:    'nav .o_menu_sections ul li a:contains(Discussions 2)'
        },
        {
            title:      "select previous created record",
            waitFor:    '.breadcrumb li:containsExact(Discussions 2)',
            element:    'td[data-field="name"]:contains(test_trigger):last',
        },
        {
            title:      "click on edit",
            waitFor:    ".o_form_button_edit",
            element:    '.o_form_button_edit',
        },

        {
            title:      "edit title",
            waitFor:    ".o_form_editable",
            element:    'input.o_form_required',
            sampleText: 'test_trigger2'
        },
        {
            title:      "click on a field of the editable list to edit content",
            waitFor:    '.o_form_editable .o_list_editable tr[data-id]:eq(1) td[data-field="body"]',
            element:    '.o_list_editable tr[data-id]:eq(1) td[data-field="body"]',
        },
        {
            title:      "change text value",
            waitFor:    '.o_list_editable_form textarea.o_form_field[data-fieldname="body"]',
            element:    'textarea.o_form_field[data-fieldname="body"]',
            sampleText: 'ccc'
        },
        {
            title:      "click on a many2one (trigger the line onchange)",
            element:    '.o_list_editable tr[data-id]:eq(1) td:eq(1)',
        },
        {
            title:      "test one2many's line onchange",
            waitFor:    '.o_list_editable tr[data-id]:eq(1) td:eq(3):contains(3)',
        },
        {
            title:      "test one2many field not triggered onchange",
            waitNot:    'textarea[name="message_concat"]:propValueContains(ccc)',
        },

        {
            title:      "open the many2one to select an other user",
            element:    '.o_list_editable_form .o_form_field_many2one .o_dropdown_button',
        },
        {
            title:      "select an other user",
            element:    '.o_web_client li a:contains(Demo User)',
        },
        {
            title:      "test one2many's line onchange after many2one",
            waitFor:    '.o_list_editable_form span.o_form_field:contains([test_trigger2] Demo User)',
        },
        {
            title:      "test one2many field not triggered onchange",
            waitNot:    'textarea[name="message_concat"]:propValueContains(ccc)',
        },
        {
            title:      "change text value",
            element:    'textarea.o_form_field[data-fieldname="body"]',
            sampleText: 'ccccc'
        },

        // check onchange

        {
            title:      "click outside to trigger one2many onchange",
            waitNot:    'textarea[name="message_concat"]:propValueContains(Demo User)',
            element:    'input.o_form_required',
        },
        {
            title:      "test one2many onchange",
            waitFor:    'textarea[name="message_concat"]:propValueContains([test_trigger2] Demo User:ccccc)',
        },

        {
            title:      "click outside to trigger one2many onchange",
            element:    '.o_form_field_many2manytags .o_dropdown_button',
        },
        {
            title:      "add a tag",
            element:    '.ui-autocomplete a:first',
        },

        // remove record

        {
            title:      "delete the last item in the editable list",
            element:    '.o_list_view tr[data-id] td.o_list_record_delete span:visible:last',
        },
        {
            title:      "test one2many onchange after delete",
            waitNot:   'textarea[name="message_concat"]:propValueContains(Administrator:d)',
        },
        
        // save
        
        {
            title:      "save discussion",
            waitNot:    'tr:has(td:containsExact(d))',
            element:    'button.o_form_button_save'
        },

        // check saved data

        {
            title:      "check data 10",
            waitFor:    '.o_form_textarea:containsExact([test_trigger2] Administrator:aaa\n[test_trigger2] Demo User:ccccc)',
        },
        {
            title:      "check data 11",
            waitFor:    '.tab-pane:eq(0) .o_form_field.o_view_manager_content tbody tr[data-id]:eq(1)',
            waitNot:    '.tab-pane:eq(0) .o_form_field.o_view_manager_content tbody tr[data-id]:eq(2)',
        },

        // edit

        {
            title:      "edit discussion",
            element:    'button.o_form_button_edit'
        },

        // add message eee

        {
            title:      "create new message eee",
            waitFor:    'li.active a[data-toggle="tab"]:contains(Messages)',
            element:    '.tab-pane:eq(0) .o_form_field_x2many_list_row_add a'
        },
        {
            title:      "change text value",
            element:    'textarea.o_form_field[data-fieldname="body"]',
            sampleText: 'eee'
        },

        // save
        
        {
            title:      "save discussion",
            waitFor:    'textarea.o_form_field[data-fieldname="body"]:propValueContains(eee)',
            element:    'button.o_form_button_save'
        },

        // check saved data

        {
            title:      "check data 12",
            waitFor:    '.o_form_textarea:containsExact([test_trigger2] Administrator:aaa\n[test_trigger2] Demo User:ccccc\n[test_trigger2] Administrator:eee)',
        },
        {
            title:      "check data 13",
            waitFor:    '.tab-pane:eq(0) .o_form_field.o_view_manager_content tbody tr[data-id]:eq(2)',
            waitNot:    '.tab-pane:eq(0) .o_form_field.o_view_manager_content tbody tr[data-id]:eq(3)',
        },
    ]
});

});
