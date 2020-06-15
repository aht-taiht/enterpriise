odoo.define('documents.systray.ActivityMenuTests', function (require) {
"use strict";

var ActivityMenu = require('mail.systray.ActivityMenu');
const { start } = require('mail/static/src/utils/test_utils.js');

var testUtils = require('web.test_utils');

QUnit.module('mail', {}, function () {

    QUnit.module('DocumentsActivityMenu', {});

    QUnit.test('activity menu widget: documents request button', async function (assert) {
        assert.expect(4);

        const { widget } = await start({
            mockRPC: function (route, args) {
                if (args.method === 'systray_get_activities') {
                    return Promise.resolve([]);
                }
                return this._super.apply(this, arguments);
            },
            intercepts: {
                do_action: function (ev) {
                    assert.strictEqual(ev.data.action, 'documents.action_request_form',
                        "should open the document request form");
                },
            },
            session: {
                async user_has_group(group) {
                    if (group === 'documents.group_documents_user') {
                        assert.step('user_has_group:documents.group_documents_user');
                        return true;
                    }
                    return this._super(...arguments);
                },
            },
        });

        const activityMenu = new ActivityMenu(widget);
        await activityMenu.appendTo($('#qunit-fixture'));

        await testUtils.dom.click(activityMenu.$('> .dropdown-toggle'));
        assert.verifySteps(['user_has_group:documents.group_documents_user']);
        assert.containsOnce(activityMenu, '.o_sys_documents_request');
        await testUtils.dom.click(activityMenu.$('.o_sys_documents_request'));

        widget.destroy();
    });
});
});
