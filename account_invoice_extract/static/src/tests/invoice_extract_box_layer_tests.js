odoo.define('account_invoice_extract.BoxLayerTests', function (require) {
"use strict";

var invoiceExtractTestUtils = require('account_invoice_extract.testUtils');

var testUtils = require('web.test_utils');

QUnit.module('account_invoice_extract', {}, function () {
QUnit.module('BoxLayer', {}, function () {

    QUnit.test('basic rendering', function (assert) {
        assert.expect(27);
        var res = invoiceExtractTestUtils.createBoxLayer();
        var parent = res.parent;

        assert.strictEqual($('.boxLayer').length, 1,
            "should display a box layer");

        var $boxes = $('.boxLayer').find('.o_invoice_extract_box');
        assert.strictEqual($boxes.length, 5,
            "should have 5 boxes on the box layer");

        // box 1
        assert.strictEqual($('.o_invoice_extract_box[data-id=1]').length,
            1, "should have box with ID 1");
        assert.strictEqual($('.o_invoice_extract_box[data-id=1]').data('field-name'),
            'VAT_Number', "should have correct field name for box with ID 1");
        assert.ok($('.o_invoice_extract_box[data-id=1]').hasClass('o_hidden'),
            "should hide box with ID 1 by default");
        assert.notOk($('.o_invoice_extract_box[data-id=1]').hasClass('ocr_chosen'),
            "should not have box 1 as ocr chosen");
        assert.notOk($('.o_invoice_extract_box[data-id=1]').hasClass('selected'),
            "should not have box 1 as selected");
        // box 2
        assert.strictEqual($('.o_invoice_extract_box[data-id=2]').length,
            1, "should have box with ID 2");
        assert.strictEqual($('.o_invoice_extract_box[data-id=2]').data('field-name'),
            'VAT_Number', "should have correct field name for box with ID 2");
        assert.ok($('.o_invoice_extract_box[data-id=2]').hasClass('o_hidden'),
            "should hide box with ID 2 by default");
        assert.ok($('.o_invoice_extract_box[data-id=2]').hasClass('ocr_chosen'),
            "should have box 2 as ocr chosen");
        assert.notOk($('.o_invoice_extract_box[data-id=2]').hasClass('selected'),
            "should not have box 2 as selected");
        // box 3
        assert.strictEqual($('.o_invoice_extract_box[data-id=3]').length,
            1, "should have box with ID 3");
        assert.strictEqual($('.o_invoice_extract_box[data-id=3]').data('field-name'),
            'VAT_Number', "should have correct field name for box with ID 3");
        assert.ok($('.o_invoice_extract_box[data-id=3]').hasClass('o_hidden'),
            "should hide box with ID 3 by default");
        assert.notOk($('.o_invoice_extract_box[data-id=3]').hasClass('ocr_chosen'),
            "should not have box 3 as ocr chosen");
        assert.ok($('.o_invoice_extract_box[data-id=3]').hasClass('selected'),
            "should have box 3 as selected");
        // box 4
        assert.strictEqual($('.o_invoice_extract_box[data-id=4]').length,
            1, "should have box with ID 4");
        assert.strictEqual($('.o_invoice_extract_box[data-id=4]').data('field-name'),
            'total', "should have correct field name for box with ID 4");
        assert.ok($('.o_invoice_extract_box[data-id=4]').hasClass('o_hidden'),
            "should hide box with ID 4 by default");
        assert.notOk($('.o_invoice_extract_box[data-id=4]').hasClass('ocr_chosen'),
            "should not have box 4 as ocr chosen");
        assert.notOk($('.o_invoice_extract_box[data-id=4]').hasClass('selected'),
            "should not have box 4 as selected");
        // box 5
        assert.strictEqual($('.o_invoice_extract_box[data-id=5]').length,
            1, "should have box with ID 5");
        assert.strictEqual($('.o_invoice_extract_box[data-id=5]').data('field-name'),
            'total', "should have correct field name for box with ID 5");
        assert.ok($('.o_invoice_extract_box[data-id=5]').hasClass('o_hidden'),
            "should hide box with ID 5 by default");
        assert.ok($('.o_invoice_extract_box[data-id=5]').hasClass('ocr_chosen'),
            "should have box 5 as ocr chosen");
        // Not selected because there is no synchronization with fields in this
        // test suite.
        assert.notOk($('.o_invoice_extract_box[data-id=5]').hasClass('selected'),
            "should have box 5 as selected");

        parent.destroy();
    });

    QUnit.test('display boxes', function (assert) {
        assert.expect(20);
        var res = invoiceExtractTestUtils.createBoxLayer();
        var boxLayer = res.boxLayer;
        var parent = res.parent;

        assert.strictEqual($('.o_invoice_extract_box[data-id=1]').data('field-name'),
            'VAT_Number', "should have correct field name for box with ID 1");
        assert.strictEqual($('.o_invoice_extract_box[data-id=2]').data('field-name'),
            'VAT_Number', "should have correct field name for box with ID 2");
        assert.strictEqual($('.o_invoice_extract_box[data-id=3]').data('field-name'),
            'VAT_Number', "should have correct field name for box with ID 3");
        assert.strictEqual($('.o_invoice_extract_box[data-id=4]').data('field-name'),
            'total', "should have correct field name for box with ID 4");
        assert.strictEqual($('.o_invoice_extract_box[data-id=5]').data('field-name'),
            'total', "should have correct field name for box with ID 5");

        assert.ok($('.o_invoice_extract_box[data-id=1]').hasClass('o_hidden'),
            "should hide box with ID 1 by default");
        assert.ok($('.o_invoice_extract_box[data-id=2]').hasClass('o_hidden'),
            "should hide box with ID 2 by default");
        assert.ok($('.o_invoice_extract_box[data-id=3]').hasClass('o_hidden'),
            "should hide box with ID 3 by default");
        assert.ok($('.o_invoice_extract_box[data-id=4]').hasClass('o_hidden'),
            "should hide box with ID 4 by default");
        assert.ok($('.o_invoice_extract_box[data-id=5]').hasClass('o_hidden'),
            "should hide box with ID 5 by default");

        boxLayer.displayBoxes({ fieldName: 'VAT_Number' });

        assert.notOk($('.o_invoice_extract_box[data-id=1]').hasClass('o_hidden'),
            "should show box with ID 1 with field name 'VAT_Number'");
        assert.notOk($('.o_invoice_extract_box[data-id=2]').hasClass('o_hidden'),
            "should show box with ID 2 with field name 'VAT_Number'");
        assert.notOk($('.o_invoice_extract_box[data-id=3]').hasClass('o_hidden'),
            "should show box with ID 3 with field name 'VAT_Number'");
        assert.ok($('.o_invoice_extract_box[data-id=4]').hasClass('o_hidden'),
            "should hide box with ID 4 with field name 'VAT_Number'");
        assert.ok($('.o_invoice_extract_box[data-id=5]').hasClass('o_hidden'),
            "should hide box with ID 5 with field name 'VAT_Number'");

        boxLayer.displayBoxes({ fieldName: 'total' });

        assert.ok($('.o_invoice_extract_box[data-id=1]').hasClass('o_hidden'),
            "should hide box with ID 1 with field name 'total'");
        assert.ok($('.o_invoice_extract_box[data-id=2]').hasClass('o_hidden'),
            "should hide box with ID 2 with field name 'total'");
        assert.ok($('.o_invoice_extract_box[data-id=3]').hasClass('o_hidden'),
            "should hide box with ID 3 with field name 'total'");
        assert.notOk($('.o_invoice_extract_box[data-id=4]').hasClass('o_hidden'),
            "should show box with ID 4 with field name 'total'");
        assert.notOk($('.o_invoice_extract_box[data-id=5]').hasClass('o_hidden'),
            "should show box with ID 5 with field name 'total'");

        parent.destroy();
    });

    QUnit.test('click on box', function (assert) {
        assert.expect(3);
        var res = invoiceExtractTestUtils.createBoxLayer({
            intercepts: {
                /**
                 * Triggered by clicking on box
                 *
                 * @param {OdooEvent} ev
                 * @param {account_invoice_extract.Box} ev.data.box
                 */
                click_invoice_extract_box: function (ev) {
                    ev.stopPropagation();
                    assert.step('click_invoice_extract_box');
                    assert.strictEqual(ev.data.box.getID(), 1,
                        "should have clicked on the box with ID 1");
                },
                /**
                 * Triggered by clicking on box layer, without clicking
                 * on a box.
                 *
                 * @param {OdooEvent} ev
                 */
                click_invoice_extract_box_layer: function (ev) {
                    ev.stopPropagation();
                    throw new Error("should not have triggered odoo event" + ev.data.name);
                },
            }
        });
        var parent = res.parent;

        $('.o_invoice_extract_box[data-id=1]').click();
        assert.verifySteps(['click_invoice_extract_box']);

        parent.destroy();
    });

    QUnit.test('click on box layer (not box)', function (assert) {
        assert.expect(2);
        var res = invoiceExtractTestUtils.createBoxLayer({
            intercepts: {
                /**
                 * Triggered by clicking on box
                 *
                 * @param {OdooEvent} ev
                 * @param {account_invoice_extract.Box} ev.data.box
                 */
                click_invoice_extract_box: function (ev) {
                    ev.stopPropagation();
                    throw new Error ("should not have triggered odoo event" + ev.data.name);
                },
                /**
                 * Triggered by clicking on box layer, without clicking
                 * on a box.
                 *
                 * @param {OdooEvent} ev
                 */
                click_invoice_extract_box_layer: function (ev) {
                    ev.stopPropagation();
                    assert.step('click_box_layer');
                },
            }
        });
        var parent = res.parent;

        $('.boxLayer').click();
        assert.verifySteps(['click_box_layer']);

        parent.destroy();
    });

    QUnit.test('multi-page', function (assert) {
        assert.expect(3);
        var parent = testUtils.createParent({});
        var boxesData = invoiceExtractTestUtils.createBoxesData();
        boxesData = boxesData.concat([
            invoiceExtractTestUtils.createBoxData({
                fieldName: 'VAT_Number',
                id: 6,
                page: 1,
                selected_status: 0,
                user_selected: false,
            }),
            invoiceExtractTestUtils.createBoxData({
                fieldName: 'total',
                id: 7,
                page: 1,
                selected_status: 0,
                user_selected: false,
            })
        ]);
        invoiceExtractTestUtils.createBoxLayer({
            boxesData: boxesData,
            parent: parent,
            pageNum: 0,
        });
        invoiceExtractTestUtils.createBoxLayer({
            boxesData: boxesData,
            parent: parent,
            pageNum: 1,
        });

        assert.strictEqual($('.boxLayer').length, 2,
            "should have two box layers");
        assert.strictEqual($('.boxLayer').eq(0).find('.o_invoice_extract_box').length,
            5, "should have 5 boxes in the 1st box layer");
        assert.strictEqual($('.boxLayer').eq(1).find('.o_invoice_extract_box').length,
            2, "should have 2 boxes in the 2nd box layer");

        parent.destroy();
    });

});
});
});
