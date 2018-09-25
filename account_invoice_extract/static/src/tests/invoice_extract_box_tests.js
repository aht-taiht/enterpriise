odoo.define('account_invoice_extract.BoxTests', function (require) {
"use strict";

var InvoiceExtractBox = require('account_invoice_extract.Box');

var testUtils = require('web.test_utils');

/**
 * @returns {$.Element}
 */
function createBoxLayer() {
    var $boxLayer = $('<div>', { class: 'boxLayer' });
    $boxLayer.css('height', 100);
    $boxLayer.css('width', 200);
    return $boxLayer;
}

/**
 * @param {Object} [params={}]
 * @param {web.Widget} [params.parent]
 * @param {integer} [params.selected_status=0]
 * @param {boolean} [params.user_selected=false]
 * @returns {account_invoice_extract.Box}
 */
function createBox(params) {
    params = params || {};
    if (!params.parent) {
        var parentParams = {};
        if ('debug' in params) {
            parentParams.debug = params.debug;
        }
        if ('intercepts' in params) {
            parentParams.intercepts = params.intercepts;
        }
        params.parent = testUtils.createParent(parentParams);
    }

    var $boxLayer = createBoxLayer();

    var box = new InvoiceExtractBox(params.parent, {
        box_angle: 0, // no angle
        box_height: 0.2, // 20% of the box layer for the height
        box_midX: 0.5, // box in the middle of box layer (horizontally)
        box_midY: 0.5, // box in the middle of box layer (vertically)
        box_width: 0.2, // 20% of the box layer of the width
        feature: 'my_field',
        id: 1,
        selected_status: params.selected_status || 0, // if value != 0, OCR chosen
        user_selected: params.user_selected || false,
        $boxLayer: $boxLayer,
    });

    var $container = params.debug ? $('body') : $('#qunit-fixture');

    $boxLayer.appendTo($container);
    box.appendTo($boxLayer);

    return {
        box: box,
        parent: params.parent,
    };
}

QUnit.module('account_invoice_extract', {}, function () {
QUnit.module('Box', {}, function () {

    QUnit.test('modeling: basic', function (assert) {
        assert.expect(4);
        var res = createBox();
        var box = res.box;
        var parent = res.parent;

        assert.strictEqual(box.getFieldName(), 'my_field');
        assert.strictEqual(box.getID(), 1);
        assert.notOk(box.isOcrChosen(), "should not be OCR chosen");
        assert.notOk(box.isSelected(), "should not be selected");

        parent.destroy();
    });

    QUnit.test('rendering: basic', function (assert) {
        assert.expect(10);
        var res = createBox();
        var parent = res.parent;

        assert.strictEqual($('.boxLayer').length, 1,
            "should display a box layer");
        assert.strictEqual($('.boxLayer').find('.o_invoice_extract_box').length, 1,
            "should display a box inside the box layer");
        assert.notOk($('.o_invoice_extract_box').hasClass('ocr_chosen'),
            "box should not be OCR chosen by default");
        assert.notOk($('.o_invoice_extract_box').hasClass('selected'),
            "box should not be selected by default");
        assert.strictEqual($('.o_invoice_extract_box').data('id'), 1,
            "box should have correct ID");
        assert.strictEqual($('.o_invoice_extract_box').data('field-name'), 'my_field',
            "box should have correct field name");

        var boxLayerRect = $('.boxLayer')[0].getBoundingClientRect();
        var boxRect = $('.o_invoice_extract_box')[0].getBoundingClientRect();

        assert.strictEqual(boxRect.width, 0.2*boxLayerRect.width,
            "box width should be 20% width of box layer");
        assert.strictEqual(boxRect.height, 0.2*boxLayerRect.height,
            "box height should be 20% height of box layer");

        var boxMidX = boxRect.x + (boxRect.width/2);
        var boxMidY = boxRect.y + (boxRect.height/2);
        var boxLayerMidX = boxLayerRect.x + (boxLayerRect.width/2);
        var boxLayerMidY = boxLayerRect.y + (boxLayerRect.height/2);

        assert.strictEqual(boxMidX, boxLayerMidX,
            "box should be horizontally in the middle of the box layer");
        assert.strictEqual(boxMidY, boxLayerMidY,
            "box should be vertically in the middle of the box layer");

        parent.destroy();
    });

    QUnit.test('initially OCR chosen', function (assert) {
        // Note that this box is not selected, because it needs synchronization
        // with account_invoice_extract.Field: if no box is user selected and
        // there is an OCR chosen box, it becomes selected.
        // Since the synchronization is missing, The box is not selected.
        assert.expect(8);
        var res = createBox({
            intercepts: {
                /**
                 * Triggered by the OCR chosen box, when instantiated
                 *
                 * @param {OdooEvent} ev
                 * @param {account_invoice_extract.Box} ev.data.box
                 */
                choice_ocr_invoice_extract_box: function (ev) {
                    ev.stopPropagation();
                    var box = ev.data.box;
                    assert.step('warn_ocr_chosen');
                    assert.strictEqual(box.getID(), 1,
                        "should let box warn that it is OCR chosen");
                },
            },
            selected_status: 1, // OCR chosen if value !== 0
        });
        var box = res.box;
        var parent = res.parent;

        assert.strictEqual($('.o_invoice_extract_box').length, 1,
            "should display a box");
        assert.ok(box.isOcrChosen(), "should be OCR chosen (modeling)");
        assert.ok($('.o_invoice_extract_box').hasClass('ocr_chosen'),
            "should be OCR chosen (rendering)");
        assert.notOk(box.isSelected(),
            "should not be selected (modeling)");
        assert.notOk($('.o_invoice_extract_box').hasClass('selected'),
            "should not be selected (rendering)");
        assert.verifySteps(['warn_ocr_chosen']);

        parent.destroy();
    });

    QUnit.test('unset OCR chosen', function (assert) {
        assert.expect(5);
        var res = createBox({
            selected_status: 1, // OCR chosen if value !== 0
        });
        var box = res.box;
        var parent = res.parent;

        assert.strictEqual($('.o_invoice_extract_box').length, 1,
            "should display a box");
        assert.ok(box.isOcrChosen(), "should be OCR chosen (modeling)");
        assert.ok($('.o_invoice_extract_box').hasClass('ocr_chosen'),
            "should be OCR chosen (rendering)");

        box.unsetOcrChosen();

        assert.notOk(box.isOcrChosen(), "should no longer be OCR chosen (modeling)");
        assert.notOk($('.o_invoice_extract_box').hasClass('ocr_chosen'),
            "should no longer be OCR chosen (rendering)");

        parent.destroy();
    });

    QUnit.test('initially user selected', function (assert) {
        assert.expect(6);
        var res = createBox({
            intercepts: {
                /**
                 * Triggered by the user selected box, when instantiated
                 *
                 * @param {OdooEvent} ev
                 * @param {account_invoice_extract.Box} ev.data.box
                 */
                select_invoice_extract_box: function (ev) {
                    ev.stopPropagation();
                    var box = ev.data.box;
                    assert.step('warn_selected');
                    assert.strictEqual(box.getID(), 1,
                        "should let box warn that it is selected");
                },
            },
            user_selected: true,
        });
        var box = res.box;
        var parent = res.parent;

        assert.strictEqual($('.o_invoice_extract_box').length, 1,
            "should display a box");
        assert.ok(box.isSelected(),
            "should be selected (modeling)");
        assert.ok($('.o_invoice_extract_box').hasClass('selected'),
            "should be selected (rendering)");
        assert.verifySteps(['warn_selected']);

        parent.destroy();
    });

    QUnit.test('(un)set selected', function (assert) {
        assert.expect(7);
        var res = createBox();
        var box = res.box;
        var parent = res.parent;

        assert.strictEqual($('.o_invoice_extract_box').length, 1,
            "should display a box");
        assert.notOk(box.isSelected(),
            "should not be selected by default (modeling)");
        assert.notOk($('.o_invoice_extract_box').hasClass('selected'),
            "should not be selected by default (rendering)");

        box.setSelected();
        assert.ok(box.isSelected(),
            "should become selected (modeling)");
        assert.ok($('.o_invoice_extract_box').hasClass('selected'),
            "should become selected (rendering)");

        box.unsetSelected();
        assert.notOk(box.isSelected(),
            "should become unselected (modeling)");
        assert.notOk($('.o_invoice_extract_box').hasClass('selected'),
            "should become unselected (rendering)");

        parent.destroy();
    });

    QUnit.test('click', function (assert) {
        assert.expect(4);
        var res = createBox({
            intercepts: {
                /**
                 * Triggered by clicked box
                 *
                 * @param {OdooEvent} ev
                 * @param {account_invoice_extract.Box} ev.data.box
                 */
                click_invoice_extract_box: function (ev) {
                    ev.stopPropagation();
                    var box = ev.data.box;
                    assert.step('warn_box_clicked');
                    assert.strictEqual(box.getID(), 1,
                        "should let the box warn that it has been clicked");
                },
            }
        });
        var parent = res.parent;

        assert.strictEqual($('.o_invoice_extract_box').length, 1,
            "should display a box");

        $('.o_invoice_extract_box').click();
        assert.verifySteps(['warn_box_clicked']);

        parent.destroy();
    });

    QUnit.test('destroy', function (assert) {
        assert.expect(5);
        var boxID;
        var res = createBox({
            intercepts: {
                /**
                 * Triggered by destroyed box
                 *
                 * @param {OdooEvent} ev
                 * @param {account_invoice_extract.Box} ev.data.box
                 */
                destroy_invoice_extract_box: function (ev) {
                    ev.stopPropagation();
                    var box = ev.data.box;
                    assert.step('warn_box_destroyed');
                    assert.strictEqual(box.getID(), boxID,
                        "should let the box warn that it has been clicked");
                },
            }
        });
        var box = res.box;
        var parent = res.parent;
        boxID = box.getID();

        assert.strictEqual($('.o_invoice_extract_box').length, 1,
            "should display a box");

        box.destroy();
        assert.strictEqual($('.o_invoice_extract_box').length, 0,
            "should no longer display a box after destroy");
        assert.verifySteps(['warn_box_destroyed']);

        parent.destroy();
    });

});
});
});
