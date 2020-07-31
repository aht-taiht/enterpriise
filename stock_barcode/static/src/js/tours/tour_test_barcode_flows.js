odoo.define('test_barcode_flows.tour', function(require) {
'use strict';

var helper = require('stock_barcode.tourHelper');
var tour = require('web_tour.tour');

tour.register('test_internal_picking_from_scratch_1', {test: true}, [
    {
        trigger: '.o_barcode_client_action',
        run: function() {
            helper.assertPageSummary('From WH/Stock To WH/Stock');
            helper.assertPreviousVisible(true);
            helper.assertPreviousEnabled(false);
            helper.assertNextVisible(false);
            helper.assertNextEnabled(false);
            helper.assertNextIsHighlighted(false);
            helper.assertLinesCount(0);
            helper.assertScanMessage('scan_src');
            helper.assertLocationHighlight(false);
            helper.assertDestinationLocationHighlight(false);
            helper.assertPager('1/1');
            helper.assertValidateVisible(true);
            helper.assertValidateIsHighlighted(false);
            helper.assertValidateEnabled(false);
        }
    },

    //Check show information.
    {
        trigger: '.o_show_information',
    },

    {
        trigger: '.o_form_label:contains("Status")',
    },

    {
        trigger: '.o_close',
    },

    {
        trigger: '.o_barcode_summary_location_dest:contains("Stock")',
    },

    /* We'll create a movement for 2 product1 from shelf1 to shelf2. The flow for this to happen is
     * to scan shelf1, product1, shelf2.
     */
    {
        trigger: '.o_barcode_client_action',
        run: 'scan LOC-01-01-00'
    },

    {
        trigger: '.o_barcode_client_action',
        run: function () {
            helper.assertPageSummary('From WH/Stock/Section 1 To WH/Stock');
            helper.assertPreviousVisible(true);
            helper.assertPreviousEnabled(false);
            helper.assertNextVisible(false);
            helper.assertNextEnabled(false);
            helper.assertNextIsHighlighted(false);
            helper.assertLinesCount(0);
            helper.assertScanMessage('scan_products');
            helper.assertLocationHighlight(true);
            helper.assertDestinationLocationHighlight(false);
            helper.assertPager('1/1');
            helper.assertValidateVisible(true);
            helper.assertValidateIsHighlighted(false);
            helper.assertValidateEnabled(false);
        }
    },

    {
        trigger: '.o_barcode_client_action',
        run: 'scan product1'
    },

    {
        trigger: '.o_barcode_client_action',
        run: function() {
            helper.assertPageSummary('From WH/Stock/Section 1 To WH/Stock');
            helper.assertPreviousVisible(true);
            helper.assertPreviousEnabled(false);
            helper.assertNextVisible(false);
            helper.assertNextEnabled(false);
            helper.assertNextIsHighlighted(false);
            helper.assertLinesCount(1);
            helper.assertScanMessage('scan_more_dest');
            helper.assertLocationHighlight(true);
            helper.assertDestinationLocationHighlight(false);
            helper.assertPager('1/1');
            helper.assertValidateVisible(true);
            helper.assertValidateIsHighlighted(true);
            helper.assertValidateEnabled(true);
            var $line = helper.getLine({barcode: 'product1'});
            helper.assertLineIsHighlighted($line, true);
        }
    },

    {
        trigger: '.o_barcode_client_action',
        run: 'scan product1'
    },

    {
        trigger: '.o_barcode_client_action',
        run: function() {
            helper.assertPageSummary('From WH/Stock/Section 1 To WH/Stock');
            helper.assertPreviousVisible(true);
            helper.assertPreviousEnabled(false);
            helper.assertNextVisible(false);
            helper.assertNextEnabled(false);
            helper.assertNextIsHighlighted(false);
            helper.assertLinesCount(1);
            helper.assertScanMessage('scan_more_dest');
            helper.assertLocationHighlight(true);
            helper.assertDestinationLocationHighlight(false);
            helper.assertPager('1/1');
            helper.assertValidateVisible(true);
            helper.assertValidateIsHighlighted(true);
            helper.assertValidateEnabled(true);
            var $line = helper.getLine({barcode: 'product1'});
            helper.assertLineIsHighlighted($line, true);
            helper.assertLineQty($line, "2");
        }
    },

    {
        trigger: '.o_barcode_client_action',
        run: 'scan LOC-01-02-00'
    },

    {
        trigger: '.o_current_dest_location:contains("WH/Stock/Section 2")',
        run: function() {
            helper.assertPageSummary('From WH/Stock/Section 1 To WH/Stock/Section 2');
            helper.assertPreviousVisible(true);
            helper.assertPreviousEnabled(false);
            helper.assertNextVisible(false);
            helper.assertNextEnabled(false);
            helper.assertNextIsHighlighted(false);
            helper.assertLinesCount(1);
            helper.assertScanMessage('scan_src');
            helper.assertLocationHighlight(true);
            helper.assertDestinationLocationHighlight(true);
            helper.assertPager('1/1');
            helper.assertValidateVisible(true);
            helper.assertValidateIsHighlighted(true);
            helper.assertValidateEnabled(true);
            var $line = helper.getLine({barcode: 'product1'});
            helper.assertLineIsHighlighted($line, false);
        }
    },

    /* We'll create a movement for product2 from shelf1 to shelf3. The flow for this to happen is
     * to scan shelf1, product2, shelf3.
     */
    {
        trigger: '.o_barcode_client_action',
        run: 'scan LOC-01-01-00'
    },

    {
        trigger: '.o_barcode_client_action',
        run: function() {
            helper.assertPageSummary('From WH/Stock/Section 1 To WH/Stock/Section 2');
            helper.assertPreviousVisible(true);
            helper.assertPreviousEnabled(false);
            helper.assertNextVisible(false);
            helper.assertNextEnabled(false);
            helper.assertNextIsHighlighted(false);
            helper.assertLinesCount(1);
            helper.assertScanMessage('scan_products');
            helper.assertLocationHighlight(true);
            helper.assertDestinationLocationHighlight(false);
            helper.assertPager('1/1');
            helper.assertValidateVisible(true);
            helper.assertValidateIsHighlighted(true);
            helper.assertValidateEnabled(true);
            var $line = helper.getLine({barcode: 'product1'});
            helper.assertLineIsHighlighted($line, false);
        }
    },

    {
        trigger: '.o_barcode_client_action',
        run: 'scan product2'
    },

    {
        trigger: '.o_barcode_client_action',
        run: function() {
            helper.assertPageSummary('From WH/Stock/Section 1 To WH/Stock/Section 2');
            helper.assertPreviousVisible(true);
            helper.assertPreviousEnabled(false);
            helper.assertNextVisible(false);
            helper.assertNextEnabled(false);
            helper.assertNextIsHighlighted(false);
            helper.assertLinesCount(2);
            helper.assertScanMessage('scan_more_dest');
            helper.assertLocationHighlight(true);
            helper.assertDestinationLocationHighlight(false);
            helper.assertPager('1/1');
            helper.assertValidateVisible(true);
            helper.assertValidateIsHighlighted(true);
            helper.assertValidateEnabled(true);
            var $lineproduct1 = helper.getLine({barcode: 'product1'});
            helper.assertLineIsHighlighted($lineproduct1, false);
            var $lineproduct2 = helper.getLine({barcode: 'product2'});
            helper.assertLineIsHighlighted($lineproduct2, true);
        }
    },

    {
        trigger: '.o_barcode_client_action',
        run: 'scan shelf3'
    },

    {
        trigger: '.o_current_dest_location:contains("WH/Stock/Section 3")',
        run: function() {
            helper.assertPageSummary('From WH/Stock/Section 1 To WH/Stock/Section 3');
            helper.assertPreviousVisible(true);
            helper.assertPreviousEnabled(true);
            helper.assertNextVisible(false);
            helper.assertNextEnabled(false);
            helper.assertNextIsHighlighted(false);
            helper.assertLinesCount(1);
            helper.assertScanMessage('scan_src');
            helper.assertLocationHighlight(true);
            helper.assertDestinationLocationHighlight(true);
            helper.assertPager('2/2');
            helper.assertValidateVisible(true);
            helper.assertValidateIsHighlighted(true);
            helper.assertValidateEnabled(true);
            var $lineproduct2 = helper.getLine({barcode: 'product2'});
            helper.assertLineIsHighlighted($lineproduct2, false);
        }
    },

    /* We'll now move a product2 from shelf1 to shelf2. As we're still on the shel1 to shelf3 page
     * where a product2 was processed, we make sure the newly scanned product will be added in a
     * new move line that will change page at the time we scan shelf2.
     */
    {
        trigger: '.o_barcode_client_action',
        run: 'scan LOC-01-01-00'
    },

    {
        trigger: '.o_barcode_client_action',
        run: function() {
            helper.assertPageSummary('From WH/Stock/Section 1 To WH/Stock/Section 3');
            helper.assertPreviousVisible(true);
            helper.assertPreviousEnabled(true);
            helper.assertNextVisible(false);
            helper.assertNextEnabled(false);
            helper.assertNextIsHighlighted(false);
            helper.assertLinesCount(1);
            helper.assertScanMessage('scan_products');
            helper.assertLocationHighlight(true);
            helper.assertDestinationLocationHighlight(false);
            helper.assertPager('2/2');
            helper.assertValidateVisible(true);
            helper.assertValidateIsHighlighted(true);
            helper.assertValidateEnabled(true);
            var $lineproduct2 = helper.getLine({barcode: 'product2'});
            helper.assertLineIsHighlighted($lineproduct2, false);
        }
    },

    {
        trigger: '.o_barcode_client_action',
        run: 'scan product2'
    },

    {
        trigger: '.o_barcode_client_action',
        run: function() {
            helper.assertPageSummary('From WH/Stock/Section 1 To WH/Stock/Section 3');
            helper.assertPreviousVisible(true);
            helper.assertPreviousEnabled(true);
            helper.assertNextVisible(false);
            helper.assertNextEnabled(false);
            helper.assertNextIsHighlighted(false);
            helper.assertLinesCount(2);
            helper.assertScanMessage('scan_more_dest');
            helper.assertLocationHighlight(true);
            helper.assertDestinationLocationHighlight(false);
            helper.assertPager('2/2');
            helper.assertValidateVisible(true);
            helper.assertValidateIsHighlighted(true);
            helper.assertValidateEnabled(true);
            var $lines = helper.getLine({barcode: 'product2'});
            if ($lines.filter('.o_highlight').length !== 1) {
                helper.fail('one of the two lins of product2 should be highlighted.');
            }
        }
    },

    {
        trigger: '.o_barcode_client_action',
        run: 'scan LOC-01-02-00'
    },

    {
        trigger: '.o_current_dest_location:contains("WH/Stock/Section 2")',
        run: function() {
            helper.assertPageSummary('From WH/Stock/Section 1 To WH/Stock/Section 2');
            helper.assertPreviousVisible(true);
            helper.assertPreviousEnabled(true);
            helper.assertNextVisible(true);
            helper.assertNextEnabled(true);
            helper.assertNextIsHighlighted(true);
            helper.assertLinesCount(2);
            helper.assertScanMessage('scan_src');
            helper.assertLocationHighlight(true);
            helper.assertDestinationLocationHighlight(true);
            helper.assertPager('1/2');
            helper.assertValidateVisible(false);
            helper.assertValidateIsHighlighted(false);
            helper.assertValidateEnabled(false);
            var $line = helper.getLine({barcode: 'product1'});
            helper.assertLineIsHighlighted($line, false);
        }
    },
]);

tour.register('test_internal_picking_from_scratch_2', {test: true}, [
    /* Move 2 product1 from WH/Stock/Section 1 to WH/Stock/Section 2.
     */
    {
        trigger: '.o_add_line',
    },

    {
        extra_trigger: '.o_field_widget[name="product_id"]',
        trigger: "input.o_field_widget[name=qty_done]",
        run: 'text 2',
    },

    {
        trigger: ".o_field_widget[name=product_id] input",
        run: 'text product1',
    },

    {
        trigger: ".ui-menu-item > a:contains('product1')",
    },

    {
        trigger: ".o_field_widget[name=location_id] input",
        run: 'text Section 1',
    },

    {
        trigger: ".ui-menu-item > a:contains('Section 1')",
    },

    {
        trigger: ".o_field_widget[name=location_dest_id] input",
        run: 'text Section 2',
    },

    {
        trigger: ".ui-menu-item > a:contains('Section 2')",
    },

    {
        trigger: '.o_save',
    },

    {
        trigger: '.o_barcode_summary_location_src:contains("Section 1"),.o_current_dest_location:contains("Section 2")',
        run: function() {
            helper.assertLinesCount(1);
        },
    },

    /* Move 1 product2 from WH/Stock/Section 1 to WH/Stock/Section 3.
     */
    {
        trigger: '.o_add_line',
    },

    {
        extra_trigger: '.o_field_widget[name="product_id"]',
        trigger: ".o_field_widget[name=product_id] input",
        run: 'text product2',
    },

    {
        trigger: ".ui-menu-item > a:contains('product2')",
    },

    {
        trigger: ".o_field_widget[name=location_id] input",
        run: 'text Section 1',
    },

    {
        trigger: ".ui-menu-item > a:contains('Section 1')",
    },

    {
        trigger: ".o_field_widget[name=location_dest_id] input",
        run: 'text WH/Stock/Section 3',
    },

    {
        trigger: ".ui-menu-item > a:contains('Section 3')",
    },

    {
        trigger: '.o_save',
    },

    {
        trigger: '.o_barcode_summary_location_src:contains("Section 1"),.o_current_dest_location:contains("Section 3")',
        run: function() {
            helper.assertLinesCount(1);
        },
    },
    /*
    * Go back to the previous page and edit the first line. We check the transaction
    * doesn't crash and the form view is correctly filled.
    */

    {
        trigger: '.o_previous_page',
    },

    {
        trigger: '.o_barcode_summary_location_src:contains("Section 1"),.o_barcode_summary_location_dest:contains("Section 2")',
        run: function() {
            helper.assertPager('1/2');
            helper.assertPageSummary('From WH/Stock/Section 1 To WH/Stock/Section 2');
            helper.assertLinesCount(1);
            helper.assertPreviousVisible(true);
            helper.assertPreviousEnabled(true);
            helper.assertNextVisible(true);
            helper.assertNextEnabled(true);
            helper.assertNextIsHighlighted(true);
            var $line = helper.getLine({barcode: 'product1'});
            helper.assertLineIsHighlighted($line, false);
        },
    },

    {
        trigger: '.o_edit',
    },

    {
        trigger: '.o_field_widget[name="product_id"]',
        run: function() {
            helper.assertFormLocationSrc("WH/Stock/Section 1");
            helper.assertFormLocationDest("WH/Stock/Section 2");
            helper.assertFormQuantity("2");
        },
    },

    {
        trigger: '.o_save',
    },

    /* Move 1 product2 from WH/Stock/Section 1 to WH/Stock/Section 2.
     */
    {
        trigger: '.o_add_line',
    },

    {
        extra_trigger: '.o_field_widget[name="product_id"]',
        trigger: ".o_field_widget[name=product_id] input",
        run: 'text product2',
    },

    {
        trigger: ".ui-menu-item > a:contains('product2')",
    },

    {
        trigger: ".o_field_widget[name=location_id] input",
        run: 'text Section 1',
    },

    {
        trigger: ".ui-menu-item > a:contains('Section 1')",
    },

    {
        trigger: ".o_field_widget[name=location_dest_id] input",
        run: 'text Section 2',
    },

    {
        trigger: ".ui-menu-item > a:contains('Section 2')",
    },

    {
        trigger: '.o_save',
    },

    {
        trigger: '.o_barcode_summary_location_src:contains("Section 1"),.o_barcode_summary_location_dest:contains("Section 2")',
        run: function() {
            helper.assertLinesCount(2);
        },
    },
    /* on this page, scan a product and then edit it through with the form view without explicitly saving it first.
    */
    {
        trigger: '.o_next_page',
    },

    {
        trigger: '.o_barcode_client_action',
        run: 'scan LOC-01-01-00'
    },

    {
        trigger: '.o_barcode_client_action',
        run: 'scan product1'
    },

    {
        trigger: '.o_edit',
    },

    {
        trigger: '.o_field_widget[name="product_id"]',
    },

    {
        trigger :'.o_save',
    },

    {
        trigger: '.o_validate_page',
    }
]);

tour.register('test_internal_picking_reserved_1', {test: true}, [
    {
        trigger: '.o_barcode_client_action',
        run: function() {
            helper.assertPageSummary('From WH/Stock/Section 1 To WH/Stock/Section 2');
            helper.assertPreviousVisible(true);
            helper.assertPreviousEnabled(true);
            helper.assertNextVisible(true);
            helper.assertNextEnabled(true);
            helper.assertNextIsHighlighted(false);
            helper.assertLinesCount(2);
            helper.assertScanMessage('scan_src');
            helper.assertLocationHighlight(false);
            helper.assertDestinationLocationHighlight(false);
            helper.assertPager('1/2');
            helper.assertValidateVisible(false);
            helper.assertValidateIsHighlighted(false);
            helper.assertValidateEnabled(false);
            var $lineproduct1 = helper.getLine({barcode: 'product1'});
            helper.assertLineIsHighlighted($lineproduct1, false);
            var $lineproduct2 = helper.getLine({barcode: 'product2'});
            helper.assertLineIsHighlighted($lineproduct2, false);
        }
    },

    /* We first move a product1 fro shef3 to shelf2.
     */
    {
        trigger: '.o_barcode_client_action',
        run: 'scan shelf3'
    },

    {
        trigger: '.o_barcode_client_action',
        run: function() {
            helper.assertPageSummary('From WH/Stock/Section 3 To WH/Stock');
            helper.assertPreviousVisible(true);
            helper.assertPreviousEnabled(true);
            helper.assertNextVisible(false);
            helper.assertNextEnabled(false);
            helper.assertNextIsHighlighted(false);
            helper.assertLinesCount(0);
            helper.assertScanMessage('scan_products');
            helper.assertLocationHighlight(true);
            helper.assertDestinationLocationHighlight(false);
            helper.assertPager('3/3');
            helper.assertValidateVisible(true);
            helper.assertValidateIsHighlighted(false);
            helper.assertValidateEnabled(false);
        }
    },

    {
        trigger: '.o_barcode_client_action',
        run: 'scan product1'
    },

    {
        trigger: '.o_barcode_client_action',
        run: function() {
            helper.assertPageSummary('From WH/Stock/Section 3 To WH/Stock');
            helper.assertPreviousVisible(true);
            helper.assertPreviousEnabled(true);
            helper.assertNextVisible(false);
            helper.assertNextEnabled(false);
            helper.assertNextIsHighlighted(false);
            helper.assertLinesCount(1);
            helper.assertScanMessage('scan_more_dest');
            helper.assertLocationHighlight(true);
            helper.assertDestinationLocationHighlight(false);
            helper.assertPager('3/3');
            helper.assertValidateVisible(true);
            helper.assertValidateIsHighlighted(true);
            helper.assertValidateEnabled(true);
            var $lineproduct1 = helper.getLine({barcode: 'product1'});
            helper.assertLineIsHighlighted($lineproduct1, true);
        }
    },

    {
        trigger: '.o_barcode_client_action',
        run: 'scan LOC-01-02-00'
    },

    {
        trigger: '.o_current_dest_location:contains("WH/Stock/Section 2")',
        run: function() {
            helper.assertPageSummary('From WH/Stock/Section 3 To WH/Stock/Section 2');
            helper.assertPreviousVisible(true);
            helper.assertPreviousEnabled(true);
            helper.assertNextVisible(false);
            helper.assertNextEnabled(false);
            helper.assertNextIsHighlighted(false);
            helper.assertLinesCount(1);
            helper.assertScanMessage('scan_src');
            helper.assertLocationHighlight(true);
            helper.assertDestinationLocationHighlight(true);
            helper.assertPager('3/3');
            helper.assertValidateVisible(true);
            helper.assertValidateIsHighlighted(true);
            helper.assertValidateEnabled(true);
            var $lineproduct1 = helper.getLine({barcode: 'product1'});
            helper.assertLineIsHighlighted($lineproduct1, false);
        }
    },

    /* Hit two times previous to get to the shelf1 to fhel2 page.
     */
    {
        'trigger': '.o_previous_page',
    },

    {
        'trigger': '.o_previous_page',
    },

    {
        trigger: '.o_barcode_client_action',
        run: function() {
            helper.assertPageSummary('From WH/Stock/Section 1 To WH/Stock/Section 2');
            helper.assertPreviousVisible(true);
            helper.assertPreviousEnabled(true);
            helper.assertNextVisible(true);
            helper.assertNextEnabled(true);
            helper.assertNextIsHighlighted(false);
            helper.assertLinesCount(2);
            helper.assertScanMessage('scan_src');
            helper.assertLocationHighlight(false);
            helper.assertDestinationLocationHighlight(false);
            helper.assertPager('1/3');
            helper.assertValidateVisible(false);
            helper.assertValidateIsHighlighted(false);
            helper.assertValidateVisible(false);
            var $lineproduct1 = helper.getLine({barcode: 'product1'});
            helper.assertLineIsHighlighted($lineproduct1, false);
            var $lineproduct2 = helper.getLine({barcode: 'product2'});
            helper.assertLineIsHighlighted($lineproduct2, false);
        }
    },

    /* Process the reservation.
     */
    {
        trigger: '.o_barcode_client_action',
        run: 'scan LOC-01-01-00'
    },

    {
        trigger: '.o_barcode_client_action',
        run: function() {
            helper.assertPageSummary('From WH/Stock/Section 1 To WH/Stock/Section 2');
            helper.assertPreviousVisible(true);
            helper.assertPreviousEnabled(true);
            helper.assertNextVisible(true);
            helper.assertNextEnabled(true);
            helper.assertNextIsHighlighted(false);
            helper.assertLinesCount(2);
            helper.assertScanMessage('scan_products');
            helper.assertLocationHighlight(true);
            helper.assertDestinationLocationHighlight(false);
            helper.assertPager('1/3');
            helper.assertValidateVisible(false);
            helper.assertValidateIsHighlighted(false);
            helper.assertValidateEnabled(false);
            var $lineproduct1 = helper.getLine({barcode: 'product1'});
            helper.assertLineIsHighlighted($lineproduct1, false);
            var $lineproduct2 = helper.getLine({barcode: 'product2'});
            helper.assertLineIsHighlighted($lineproduct2, false);
        }
    },

    {
        trigger: '.o_barcode_client_action',
        run: 'scan product1'
    },

    {
        trigger: '.o_barcode_client_action',
        run: function() {
            helper.assertPageSummary('From WH/Stock/Section 1 To WH/Stock/Section 2');
            helper.assertPreviousVisible(true);
            helper.assertPreviousEnabled(true);
            helper.assertNextVisible(true);
            helper.assertNextEnabled(true);
            helper.assertNextIsHighlighted(false);
            helper.assertLinesCount(2);
            helper.assertScanMessage('scan_more_dest');
            helper.assertLocationHighlight(true);
            helper.assertDestinationLocationHighlight(false);
            helper.assertPager('1/3');
            helper.assertValidateVisible(false);
            helper.assertValidateIsHighlighted(false);
            helper.assertValidateEnabled(false);
            var $lineproduct1 = helper.getLine({barcode: 'product1'});
            helper.assertLineIsHighlighted($lineproduct1, true);
            var $lineproduct2 = helper.getLine({barcode: 'product2'});
            helper.assertLineIsHighlighted($lineproduct2, false);
        }
    },

    {
        trigger: '.o_barcode_client_action',
        run: 'scan product2'
    },

    {
        trigger: '.o_barcode_client_action',
        run: function() {
            helper.assertPageSummary('From WH/Stock/Section 1 To WH/Stock/Section 2');
            helper.assertPreviousVisible(true);
            helper.assertPreviousEnabled(true);
            helper.assertNextVisible(true);
            helper.assertNextEnabled(true);
            helper.assertNextIsHighlighted(true);
            helper.assertLinesCount(2);
            helper.assertScanMessage('scan_more_dest');
            helper.assertLocationHighlight(true);
            helper.assertDestinationLocationHighlight(false);
            helper.assertPager('1/3');
            helper.assertValidateVisible(false);
            helper.assertValidateIsHighlighted(false);
            helper.assertValidateEnabled(false);
            var $lineproduct1 = helper.getLine({barcode: 'product1'});
            helper.assertLineIsHighlighted($lineproduct1, false);
            var $lineproduct2 = helper.getLine({barcode: 'product2'});
            helper.assertLineIsHighlighted($lineproduct2, true);
        }
    },

    {
        trigger: '.o_barcode_client_action',
        run: 'scan LOC-01-02-00'
    },

    {
        trigger: '.o_barcode_client_action',
        run: function() {
            helper.assertPageSummary('From WH/Stock/Section 1 To WH/Stock/Section 2');
            helper.assertPreviousVisible(true);
            helper.assertPreviousEnabled(true);
            helper.assertNextVisible(true);
            helper.assertNextEnabled(true);
            helper.assertNextIsHighlighted(true);
            helper.assertLinesCount(2);
            helper.assertScanMessage('scan_src');
            helper.assertLocationHighlight(true);
            helper.assertDestinationLocationHighlight(true);
            helper.assertPager('1/3');
            helper.assertValidateVisible(false);
            helper.assertValidateIsHighlighted(false);
            helper.assertValidateEnabled(false);

            $('.o_barcode_line .fa-cubes').parent().each(function() {
                var qty = $(this).text().trim();
                if (qty !== '1 / 1') {
                    helper.fail();
                }
            });

            var $lineproduct1 = helper.getLine({barcode: 'product1'});
            helper.assertLineIsHighlighted($lineproduct1, false);
            var $lineproduct2 = helper.getLine({barcode: 'product2'});
            helper.assertLineIsHighlighted($lineproduct2, false);
        }
    },

    /* Hit next. The write should happen.
     */
    {
        'trigger': '.o_next_page',
    },

    {
        trigger: '.o_current_dest_location:contains("WH/Stock/Section 4")',
        run: function() {
            helper.assertPageSummary('From WH/Stock/Section 3 To WH/Stock/Section 4');
            helper.assertPreviousVisible(true);
            helper.assertPreviousEnabled(true);
            helper.assertNextVisible(true);
            helper.assertNextEnabled(true);
            helper.assertNextIsHighlighted(false);
            helper.assertLinesCount(1);
            helper.assertScanMessage('scan_src');
            helper.assertLocationHighlight(false);
            helper.assertDestinationLocationHighlight(false);
            helper.assertPager('2/3');
            helper.assertValidateVisible(false);
            helper.assertValidateIsHighlighted(false);
            helper.assertValidateEnabled(false);

            $('.o_barcode_line .fa-cubes').parent().each(function() {
                var qty = $(this).text().trim();
                if (qty !== '0 / 1') {
                    helper.fail();
                }
            });

            var $line = helper.getLine({barcode: 'product2'});
            helper.assertLineIsHighlighted($line, false);
        }
    },
]);

tour.register('test_internal_change_location', {test: true}, [
    {
        trigger: '.o_barcode_client_action',
        run: function () {
            helper.assertPageSummary('From Stock House/Abandonned Ground Floor To Stock House');
            helper.assertPreviousVisible(true);
            helper.assertPreviousEnabled(true);
            helper.assertNextVisible(true);
            helper.assertNextEnabled(true);
            helper.assertNextIsHighlighted(false);
            helper.assertLinesCount(1);
            helper.assertScanMessage('scan_src');
            helper.assertLocationHighlight(false);
            helper.assertDestinationLocationHighlight(false);
            helper.assertPager('1/2');
            helper.assertValidateVisible(false);
            helper.assertValidateIsHighlighted(false);
            helper.assertValidateEnabled(false);
            const $lineproduct1 = helper.getLine({barcode: 'product1'});
            helper.assertLineIsHighlighted($lineproduct1, false);
        }
    },
    // Clicks on the source location and checks the locations list is correclty displayed.
    {
        trigger: '.o_barcode_summary_location_src',
    },
    {
        trigger: '.o_barcode_client_action',
        run: function () {
            const $src_loc_list = $('.o_barcode_list_locations.o_source_locations');
            helper.assert($src_loc_list.css('display'), 'block');
            helper.assert($src_loc_list.find('li').length, 3);
            const $dest_loc_list = $('.o_barcode_list_locations.o_destination_locations');
            helper.assert($dest_loc_list.css('display'), 'none');
        }
    },
    // Clicks on the destination location and checks the locations list is correclty displayed.
    {
        trigger: '.o_barcode_summary_location_dest',
    },
    {
        trigger: '.o_barcode_client_action',
        run: function () {
            const $src_loc_list = $('.o_barcode_list_locations.o_source_locations');
            helper.assert($src_loc_list.css('display'), 'none');
            const $dest_loc_list = $('.o_barcode_list_locations.o_destination_locations');
            helper.assert($dest_loc_list.css('display'), 'block');
            helper.assert($dest_loc_list.find('li').length, 3);
        }
    },
    // Changes the destination location for 'Poorly lit floor'...
    {
        trigger: '.o_destination_locations li:contains("Poorly lit floor")',
    },
    {
        trigger: '.o_current_dest_location:contains("Poorly lit floor")',
        run: function () {
            helper.assertPageSummary('From Stock House/Abandonned Ground Floor To Stock House/Poorly lit floor');
            helper.assertPreviousVisible(true);
            helper.assertPreviousEnabled(true);
            helper.assertNextVisible(true);
            helper.assertNextEnabled(true);
            helper.assertNextIsHighlighted(false);
            helper.assertLinesCount(1);
            helper.assertScanMessage('scan_src');
            helper.assertLocationHighlight(false);
            helper.assertDestinationLocationHighlight(false);
            helper.assertPager('1/2');
            helper.assertValidateVisible(false);
            helper.assertValidateIsHighlighted(false);
            helper.assertValidateEnabled(false);
            const $lineproduct1 = helper.getLine({barcode: 'product1'});
            helper.assertLineIsHighlighted($lineproduct1, false);
        }
    },
    // ... then checks the dest location is really updated on the move line.
    {
        trigger: '.o_edit i',
    },
    {
        trigger: '.o_field_widget[name="location_dest_id"]',
        run: function () {
            helper.assert(
                $('.o_field_widget[name="location_dest_id"] input').val(),
                'Stock House/Poorly lit floor'
            );
        },
    },
    {
        trigger: '.o_save',
    },
    // Scans the product1 then changes the page.
    {
        trigger: '.o_barcode_lines',
        run: 'scan product1',
    },
    {
        trigger: '.o_next_page.btn-primary',
        run: function () {
            const $lineproduct1 = helper.getLine({barcode: 'product1'});
            helper.assertLineIsHighlighted($lineproduct1, true);
            helper.assertLineQty($lineproduct1, "1");
        }
    },
    {
        trigger: '.o_next_page',
    },
    {
        trigger: '.o_barcode_client_action:contains("product2")',
        run: function () {
            helper.assertPageSummary('From Stock House/Poorly lit floor To Stock House');
            helper.assertPreviousVisible(true);
            helper.assertPreviousEnabled(true);
            helper.assertNextVisible(false);
            helper.assertNextEnabled(false);
            helper.assertNextIsHighlighted(false);
            helper.assertLinesCount(1);
            helper.assertScanMessage('scan_src');
            helper.assertLocationHighlight(false);
            helper.assertDestinationLocationHighlight(false);
            helper.assertPager('2/2');
            helper.assertValidateVisible(true);
            helper.assertValidateIsHighlighted(false);
            helper.assertValidateEnabled(true);
            const $lineproduct2 = helper.getLine({barcode: 'product2'});
            helper.assertLineIsHighlighted($lineproduct2, false);
        }
    },
    // Clicks on the destination location and checks the locations list is correclty displayed.
    {
        trigger: '.o_barcode_summary_location_dest',
    },
    {
        trigger: '.o_barcode_client_action',
        run: function () {
            const $src_loc_list = $('.o_barcode_list_locations.o_source_locations');
            helper.assert($src_loc_list.css('display'), 'none');
            const $dest_loc_list = $('.o_barcode_list_locations.o_destination_locations');
            helper.assert($dest_loc_list.css('display'), 'block');
            helper.assert($dest_loc_list.find('li').length, 3);
        }
    },
    // Scans product2 and changes the destination location for 'Poorly lit floor'...
    {
        trigger: '.o_barcode_client_action',
        run: 'scan product2',
    },
    {
        trigger: '.o_destination_locations li:contains("Poorly lit floor")',
    },
    // ... then checks the dest location is really updated on the move line.
    {
        trigger: '.o_edit i',
    },
    {
        trigger: '.o_field_widget[name="location_dest_id"]',
        run: function () {
            helper.assert(
                $('.o_field_widget[name="location_dest_id"] input').val(),
                'Stock House/Poorly lit floor'
            );
        },
    },
    {
        trigger: '.o_save',
    },
    // Now, changes the source location for 'Abandonned Ground Floor'.
    // The purpose of this operation is to get the 2 lines on the same page.
    {
        trigger: '.o_barcode_summary_location_src',
    },
    {
        trigger: '.o_source_locations li:contains("Abandonned Ground Floor")',
    },
    {
        trigger: '.o_current_location:contains("Abandonned Ground Floor")',
        run: function () {
            helper.assertPageSummary('From Stock House/Abandonned Ground Floor To Stock House/Poorly lit floor');
            helper.assertPreviousVisible(true);
            helper.assertPreviousEnabled(false);
            helper.assertNextVisible(false);
            helper.assertNextEnabled(false);
            helper.assertNextIsHighlighted(false);
            helper.assertLinesCount(2);
            helper.assertScanMessage('scan_src');
            helper.assertLocationHighlight(false);
            helper.assertDestinationLocationHighlight(false);
            helper.assertPager('1/1');
            helper.assertValidateVisible(true);
            helper.assertValidateIsHighlighted(true);
            helper.assertValidateEnabled(true);
            const $lineproduct1 = helper.getLine({barcode: 'product1'});
            helper.assertLineIsHighlighted($lineproduct1, false);
            const $lineproduct2 = helper.getLine({barcode: 'product2'});
            helper.assertLineIsHighlighted($lineproduct2, false);
        }
    },
    // Changes the destination location for 'Stock House'...
    {
        trigger: '.o_barcode_summary_location_dest',
    },
    {
        trigger: '.o_destination_locations li:first-child',
    },
    {
        trigger: '.o_current_dest_location:contains("Stock House"):not(:contains("/"))',
        run: function () {
            helper.assertPageSummary('From Stock House/Abandonned Ground Floor To Stock House');
        }
    },
    // ... then checks the dest location is really updated on the two move lines.
    {
        trigger: '.o_barcode_line:first-child .o_edit i',
    },
    {
        trigger: '.o_field_widget[name="location_id"]',
        run: function () {
            helper.assert(
                $('.o_field_widget[name="location_id"] input').val(),
                'Stock House/Abandonned Ground Floor'
            );
            helper.assert(
                $('.o_field_widget[name="location_dest_id"] input').val(),
                'Stock House'
            );
        },
    },
    {
        trigger: '.o_save',
    },
    {
        trigger: '.o_barcode_line:last-child .o_edit i',
    },
    {
        trigger: '.o_field_widget[name="location_id"]',
        run: function () {
            helper.assert(
                $('.o_field_widget[name="location_id"] input').val(),
                'Stock House/Abandonned Ground Floor'
            );
            helper.assert(
                $('.o_field_widget[name="location_dest_id"] input').val(),
                'Stock House'
            );
        },
    },
    {
        trigger: '.o_save',
    },
    // Validate the delivery.
    {
        trigger: '.o_validate_page'
    },
    {
        trigger: '.o_notification.bg-success',
    },
]);

tour.register('test_receipt_reserved_1', {test: true}, [
    {
        trigger: '.o_barcode_client_action',
        run: function() {
            helper.assertPageSummary(' To WH/Stock');
            helper.assertPreviousVisible(true);
            helper.assertPreviousEnabled(false);
            helper.assertNextVisible(false);
            helper.assertNextEnabled(false);
            helper.assertNextIsHighlighted(false);
            helper.assertLinesCount(2);
            helper.assertScanMessage('scan_products');
            helper.assertLocationHighlight(false);
            helper.assertDestinationLocationHighlight(false);
            helper.assertPager('1/1');
            helper.assertValidateVisible(true);
            helper.assertValidateIsHighlighted(false);
            helper.assertValidateEnabled(true);
        }
    },

    {
        trigger: '.o_barcode_client_action',
        run: 'scan product2'
    },

    {
        trigger: '.o_barcode_client_action',
        run: 'scan product2'
    },

    {
        trigger: '.o_barcode_client_action',
        run: 'scan product2'
    },

    {
        trigger: '.o_barcode_client_action',
        run: 'scan product2'
    },

    {
        trigger: '.o_barcode_client_action',
        run: 'scan product1'
    },

    {
        trigger: '.o_barcode_client_action',
        run: 'scan product1'
    },

    {
        trigger: '.o_barcode_client_action',
        run: 'scan product1'
    },

    {
        trigger: '.o_barcode_client_action',
        run: function() {
            helper.assertValidateIsHighlighted(false);
        }
    },

    {
        trigger: '.o_barcode_client_action',
        run: 'scan product1'
    },

    {
        trigger: '.o_barcode_client_action',
        run: function() {
            helper.assertValidateIsHighlighted(true);
        }
    },

    {
        trigger: '.o_barcode_client_action',
        run: 'scan LOC-01-01-00'
    },

    {
        trigger: '.o_current_dest_location:contains("WH/Stock/Section 1")',
        run: function() {
            helper.assertPageSummary(' To WH/Stock/Section 1');
            helper.assertPreviousVisible(true);
            helper.assertPreviousEnabled(false);
            helper.assertNextVisible(false);
            helper.assertNextEnabled(false);
            helper.assertNextIsHighlighted(false);
            helper.assertLinesCount(2);
            helper.assertScanMessage('scan_products');
            // not relevant in receipt mode
            // helper.assertLocationHighlight(false);
            helper.assertDestinationLocationHighlight(true);
            helper.assertPager('1/1');
            helper.assertValidateVisible(true);
            helper.assertValidateIsHighlighted(true);
            helper.assertValidateEnabled(true);

            $('.o_barcode_line .fa-cubes').parent().each(function() {
                var qty = $(this).text().trim();
                if (qty !== '1 / 4') {
                    helper.fail();
                }
            });
        }
    },

    {
        trigger: '.o_add_line',
    },

    {
        trigger: '.o_field_widget[name="product_id"]',
        run: function() {
            helper.assertFormLocationDest('WH/Stock/Section 1');
        },
    },
]);

tour.register('test_delivery_reserved_1', {test: true}, [
    {
        trigger: '.o_barcode_client_action',
        run: function() {
            helper.assertPageSummary('From WH/Stock ');
            helper.assertPreviousVisible(true);
            helper.assertPreviousEnabled(false);
            helper.assertNextVisible(false);
            helper.assertNextEnabled(false);
            helper.assertNextIsHighlighted(false);
            helper.assertLinesCount(2);
            helper.assertScanMessage('scan_src');
            helper.assertLocationHighlight(false);
            // not relevant in delivery mode
            // helper.assertDestinationLocationHighlight(false);
            helper.assertPager('1/1');
            helper.assertValidateVisible(true);
            helper.assertValidateIsHighlighted(false);
            helper.assertValidateEnabled(true);
        }
    },

    {
        trigger: '.o_barcode_client_action',
        run: 'scan LOC-01-00-00'
    },

    {
        trigger: '.o_barcode_client_action',
        run: function() {
            helper.assertPageSummary('From WH/Stock ');
            helper.assertPreviousVisible(true);
            helper.assertPreviousEnabled(false);
            helper.assertNextVisible(false);
            helper.assertNextEnabled(false);
            helper.assertNextIsHighlighted(false);
            helper.assertLinesCount(2);
            helper.assertScanMessage('scan_products');
            helper.assertLocationHighlight(true);
            // not relevant in delivery mode
            // helper.assertDestinationLocationHighlight(false);
            helper.assertPager('1/1');
            helper.assertValidateVisible(true);
            helper.assertValidateIsHighlighted(false);
            helper.assertValidateEnabled(true);
        }
    },

    {
        trigger: '.o_barcode_client_action',
        run: 'scan product1'
    },

    {
        trigger: '.o_barcode_client_action',
        run: 'scan product2'
    },

    {
        trigger: '.o_barcode_client_action',
        run: 'scan LOC-01-01-00'
    },

    {
        trigger: '.o_current_location:contains("WH/Stock/Section 1")',
        run: function() {
            helper.assertPageSummary('From WH/Stock/Section 1 ');
            helper.assertPreviousVisible(true);
            helper.assertPreviousEnabled(true);
            helper.assertNextVisible(false);
            helper.assertNextEnabled(false);
            helper.assertNextIsHighlighted(false);
            helper.assertLinesCount(0);
            helper.assertScanMessage('scan_products');
            helper.assertLocationHighlight(true);
            // not relevant in delivery mode
            // helper.assertDestinationLocationHighlight(false);
            helper.assertPager('2/2');
            helper.assertValidateVisible(true);
            helper.assertValidateIsHighlighted(false);
            helper.assertValidateEnabled(false);
        }
    },
]);

tour.register('test_delivery_reserved_2', {test: true}, [
    {
        trigger: '.o_barcode_client_action',
        run: function() {
            helper.assertPageSummary('');
            helper.assertPreviousVisible(true);
            helper.assertPreviousEnabled(false);
            helper.assertNextVisible(false);
            helper.assertNextEnabled(false);
            helper.assertNextIsHighlighted(false);
            helper.assertLinesCount(2);
            helper.assertScanMessage('scan_products');
            helper.assertLocationHighlight(false);
            // not relevant in delivery mode
            // helper.assertDestinationLocationHighlight(false);
            helper.assertValidateVisible(true);
            helper.assertValidateIsHighlighted(false);
            helper.assertValidateEnabled(true);
        }
    },

    {
        trigger: '.o_barcode_client_action',
        run: 'scan product1'
    },

    {
        trigger: '.o_barcode_client_action',
        run: 'scan product1'
    },

    {
        trigger: '.o_barcode_client_action',
        run: 'scan product2'
    },

    {
        trigger: '.o_barcode_line_title:contains("product2")',
        run: function() {
            helper.assertPageSummary('');
            helper.assertPreviousVisible(true);
            helper.assertPreviousEnabled(true);
            helper.assertNextVisible(false);
            helper.assertNextEnabled(false);
            helper.assertNextIsHighlighted(false);
            helper.assertLinesCount(3);
            helper.assertScanMessage('scan_products');
            // not relevant in delivery mode
            // helper.assertDestinationLocationHighlight(false);
            helper.assertValidateVisible(true);
            helper.assertValidateIsHighlighted(false);
            helper.assertValidateEnabled(true);
        }
    },

    {
        trigger: '.o_barcode_client_action',
        run: 'scan product1'
    },

    {
        trigger: '.o_barcode_client_action',
        run: 'scan product1'
    },

    {
        trigger: '.o_barcode_line_title:contains("product2")',
        run: function() {
            helper.assertPageSummary('');
            helper.assertPreviousVisible(true);
            helper.assertPreviousEnabled(true);
            helper.assertNextVisible(false);
            helper.assertNextEnabled(false);
            helper.assertNextIsHighlighted(false);
            helper.assertLinesCount(3);
            helper.assertScanMessage('scan_products');
            // not relevant in delivery mode
            // helper.assertDestinationLocationHighlight(false);
            helper.assertValidateVisible(true);
            helper.assertValidateIsHighlighted(true);
            helper.assertValidateEnabled(true);
            var $lines = helper.getLine({barcode: 'product1'});
            for (var i = 0; i < $lines.length; i++) {
                helper.assertLineQty($($lines[i]), "2");
            }

        }
    },

    {
        trigger: '.o_barcode_client_action',
        run: 'scan product1'
    },

    {
        trigger: '.o_barcode_client_action',
        run: function () {
            helper.assertPageSummary('');
            helper.assertPreviousVisible(true);
            helper.assertPreviousEnabled(true);
            helper.assertNextVisible(false);
            helper.assertNextEnabled(false);
            helper.assertNextIsHighlighted(false);
            helper.assertLinesCount(4);
            helper.assertScanMessage('scan_products');
            // not relevant in delivery mode
            // helper.assertDestinationLocationHighlight(false);
            helper.assertValidateVisible(true);
            helper.assertValidateIsHighlighted(true);
            helper.assertValidateEnabled(true);
        }
    },
]);


tour.register('test_delivery_reserved_3', {test: true}, [
    {
        trigger: '.o_barcode_client_action',
        run: function() {
            helper.assertPageSummary('');
            helper.assertPreviousVisible(true);
            helper.assertPreviousEnabled(false);
            helper.assertNextVisible(false);
            helper.assertNextEnabled(false);
            helper.assertNextIsHighlighted(false);
            helper.assertLinesCount(1);
            helper.assertScanMessage('scan_products');
            helper.assertLocationHighlight(false);
            // not relevant in delivery mode
            // helper.assertDestinationLocationHighlight(false);
            helper.assertValidateVisible(true);
            helper.assertValidateIsHighlighted(false);
            helper.assertValidateEnabled(true);
        }
    },

    {
        trigger: '.o_barcode_client_action',
        run: 'scan product1'
    },

    {
        trigger: '.o_barcode_client_action',
        run: 'scan this_is_not_a_barcode_dude'
    },

    {
        trigger: '.o_barcode_client_action',
        run: function() {
            helper.assertPageSummary('');
            helper.assertPreviousVisible(true);
            helper.assertPreviousEnabled(true);
            helper.assertNextVisible(false);
            helper.assertNextEnabled(false);
            helper.assertNextIsHighlighted(false);
            helper.assertLinesCount(1);
            helper.assertScanMessage('scan_products');
            // not relevant in delivery mode
            // helper.assertDestinationLocationHighlight(false);
            helper.assertValidateVisible(true);
            helper.assertValidateIsHighlighted(true);
            helper.assertValidateEnabled(true);
            var $line = helper.getLine({barcode: 'product1'});
            helper.assertLineIsHighlighted($line, true);
            helper.assertLineQty($line, "1");
        }
    },
]);

tour.register('test_delivery_using_buttons', {test: true}, [
    {
        trigger: '.o_barcode_client_action',
        run: function() {
            helper.assertPageSummary('');
            helper.assertPreviousVisible(true);
            helper.assertPreviousEnabled(false);
            helper.assertNextVisible(false);
            helper.assertNextEnabled(false);
            helper.assertNextIsHighlighted(false);
            helper.assertLinesCount(3);
            helper.assertScanMessage('scan_products');
            helper.assertLocationHighlight(false);
            helper.assertValidateVisible(true);
            helper.assertValidateIsHighlighted(false);
            helper.assertValidateEnabled(true);
            helper.assert(
                $('.o_line_button').length, 6,
                "6 buttons must be present in the view (2 by line)"
            );
            // slice so we don't include the keyboard shortcut (even if it's hidden)
            helper.assert($('.o_add_reserved').eq(0).text().slice(0,3), '+ 2');
            helper.assert($('.o_add_reserved').eq(1).text().slice(0,3), '+ 3');
            helper.assert($('.o_add_reserved').eq(2).text().slice(0,3), '+ 4');
            helper.assertLineQuantityOnReservedQty(0, '0 / 2');
            helper.assertLineQuantityOnReservedQty(1, '0 / 3');
            helper.assertLineQuantityOnReservedQty(2, '0 / 4');
            helper.assertButtonIsVisible($('.o_barcode_line').eq(0), 'add_unit');
            helper.assertButtonIsVisible($('.o_barcode_line').eq(1), 'add_unit');
            helper.assertButtonIsVisible($('.o_barcode_line').eq(2), 'add_unit');
        }
    },

    // On the first line...
    // Press +1 button.
    {
        trigger: '.o_barcode_line:first-child .o_add_unit'
    },
    {
        trigger: '.o_barcode_client_action',
        run: function() {
            const $line = $('.o_barcode_line:first-child');
            helper.assertButtonIsNotVisible($line, 'add_reserved');
            helper.assertLineQuantityOnReservedQty(0, '1 / 2');
            helper.assertLineIsHighlighted($('.o_barcode_line:first-child'), true);
            helper.assertLineIsHighlighted($('.o_barcode_line:nth-child(2)'), false);
            helper.assertLineIsHighlighted($('.o_barcode_line:last-child'), false);
        }
    },
    // Press +1 button again, now its buttons must be hidden.
    // and it is moved to the end of the list
    {
        trigger: '.o_barcode_line:first-child .o_add_unit'
    },
    {
        trigger: '.o_barcode_client_action',
        run: function() {
            helper.assertLineButtonsAreVisible(2, false);
            helper.assertLineQuantityOnReservedQty(2, '2 / 2');
        }
    },

    // Second line (product2) gets pushed up to 1st line in list
    {
        trigger: '.o_barcode_client_action',
        run: function() {
            helper.assert($('.o_add_reserved').eq(0).text().slice(0,3), '+ 3');
            helper.assertButtonIsVisible($('.o_barcode_line').eq(0), 'add_unit');
            helper.assertLineQuantityOnReservedQty(0, '0 / 3');
        }
    },
    // Press the add remaining quantity button after triggering "shift" button so it is visible, now its buttons must be hidden.
    {
        trigger: '.o_barcode_line:first-child',
        run: function() {
            var event = jQuery.Event("keydown");
            event.key = "Shift";
            $(document).trigger(event);
            $('.o_barcode_line:first-child .o_add_reserved').click();
        }
    },
    // Product2 is now done + last line
    {
        trigger: '.o_barcode_client_action',
        run: function() {
            helper.assertLineButtonsAreVisible(2, false);
            helper.assertLineQuantityOnReservedQty(2, '3 / 3');
            helper.assertLineIsHighlighted($('.o_barcode_line:first-child'), false);
            helper.assertLineIsHighlighted($('.o_barcode_line:nth-child(2)'), false);
            helper.assertLineIsHighlighted($('.o_barcode_line:last-child'), true);
        }
    },

    // Last line at beginning (product3) now at top of list
    {
        trigger: '.o_barcode_client_action',
        run: function() {
            helper.assert($('.o_add_reserved').eq(0).text().slice(0,3), '+ 4');
            helper.assertButtonIsVisible($('.o_barcode_line').eq(0), 'add_unit');
            helper.assertLineQuantityOnReservedQty(0, '0 / 4');
        }
    },
    // Scan product3 one time, then checks the quantities.
    {
        trigger: '.o_barcode_client_action',
        run: 'scan product3',
    },
    {
        trigger: '.o_barcode_client_action',
        run: function() {
            helper.assert($('.o_add_reserved').eq(0).text().slice(0,3), '+ 3');
            helper.assertButtonIsVisible($('.o_barcode_line').eq(0), 'add_unit');
            helper.assertLineQuantityOnReservedQty(0, '1 / 4');
            helper.assertLineIsHighlighted($('.o_barcode_line:first-child'), true);
            helper.assertLineIsHighlighted($('.o_barcode_line:nth-child(2)'), false);
            helper.assertLineIsHighlighted($('.o_barcode_line:last-child'), false);
        }
    },
    // Press +1 button, then checks the quantities.
    {
        trigger: '.o_barcode_line:first-child .o_add_unit'
    },
    {
        trigger: '.o_barcode_client_action',
        run: function() {
            helper.assert($('.o_add_reserved').eq(0).text().slice(0,3), '+ 2');
            helper.assertButtonIsVisible($('.o_barcode_line').eq(0), 'add_unit');
            helper.assertLineQuantityOnReservedQty(0, '2 / 4');
        }
    },
    // Press the add remaining quantity button, now its buttons must be hidden
    {
        trigger: '.o_barcode_line:first-child',
        run: function() {
            var event = jQuery.Event("keydown");
            event.key = "Shift";
            $(document).trigger(event);
            $('.o_barcode_line:first-child .o_add_reserved').click();
        }
    },
    // and it is the last line again
    {
        trigger: '.o_barcode_client_action',
        run: function() {
            helper.assertLineButtonsAreVisible(2, false);
            helper.assertLineQuantityOnReservedQty(2, '4 / 4');
            helper.assertValidateIsHighlighted(true);
        }
    },

    // Now, scan one more time the product3...
    // ... So, a new line must be created and only the +1 button must be visible.
    {
        trigger: '.o_barcode_client_action',
        run: 'scan product3',
    },
    {
        trigger: '.o_barcode_line:nth-child(4)',
        run: function() {
            helper.assertLinesCount(4);
            helper.assertLineIsHighlighted($('.o_barcode_line:first-child'), true);
            helper.assertLineIsHighlighted($('.o_barcode_line:nth-child(2)'), false);
            helper.assertLineIsHighlighted($('.o_barcode_line:nth-child(3)'), false);
            helper.assertLineIsHighlighted($('.o_barcode_line:last-child'), false);
            const $line = $('.o_barcode_line:first-child');
            helper.assertLineQty($line, '1');
            // +1 button must be present on new line.
            helper.assert($line.find('.o_add_unit').length, 1);
            // "Add remaining reserved quantity" button must not be present on new line.
            helper.assert($line.find('.o_add_reserved').length, 0);
        }
    },
    // Press +1 button of the new line.
    {
        trigger: '.o_barcode_line:first-child .o_add_unit'
    },
    {
        trigger: '.o_barcode_client_action',
        run: function() {
            helper.assertLineIsHighlighted($('.o_barcode_line:first-child'), true);
            helper.assertLineIsHighlighted($('.o_barcode_line:nth-child(2)'), false);
            helper.assertLineIsHighlighted($('.o_barcode_line:nth-child(3)'), false);
            helper.assertLineIsHighlighted($('.o_barcode_line:last-child'), false);
            const $line = $('.o_barcode_line:first-child');
            helper.assertLineQty($line, '2');
            // +1 button must still be present.
            helper.assert($line.find('.o_add_unit').length, 1);
            helper.assert($line.find('.o_add_reserved').length, 0);
        }
    },

    // Validate the delivery.
    {
        trigger: '.o_validate_page'
    },
    {
        trigger: '.o_notification.bg-success',
    },
]);


tour.register('test_receipt_from_scratch_with_lots_1', {test: true}, [
    {
        trigger: '.o_barcode_client_action',
        run: function() {
            helper.assertPageSummary(' To WH/Stock');
        }
    },

    {
        trigger: '.o_barcode_client_action',
        run: 'scan lot1',
    },

    {
        trigger: '.o_notification.bg-danger'
    },

    {
        trigger: '.o_barcode_client_action',
        run: function () {
            helper.assertErrorMessage('You are expected to scan one or more products.');
        },
    },

    {
        trigger: '.o_barcode_client_action',
        run: 'scan productserial1'
    },

    {
        trigger: '.o_barcode_client_action',
        run: 'scan lot1',
    },

    {
        trigger: '.o_barcode_client_action',
        run: 'scan LOC-01-00-00'
    },

    {
        trigger: '.o_barcode_client_action',
        run: 'scan productserial1'
    },

    {
        trigger: '.o_barcode_client_action',
        run: 'scan lot2',
    },

    {
        trigger: '.o_barcode_client_action',
        run: 'scan LOC-01-01-00'
    },

    {
        trigger: '.o_current_dest_location:contains("WH/Stock/Section 1")',
        run: function() {
            helper.assertPageSummary(' To WH/Stock/Section 1');
            helper.assertPreviousVisible(true);
        }
    },
]);

tour.register('test_receipt_from_scratch_with_lots_2', {test: true}, [
    {
        trigger: '.o_barcode_client_action',
        run: function() {
            helper.assertPageSummary(' To WH/Stock');
        }
    },

    {
        trigger: '.o_barcode_client_action',
        run: 'scan productlot1'
    },

    {
        trigger: '.o_barcode_client_action',
        run: 'scan lot1',
    },

    {
        trigger: '.o_barcode_client_action',
        run: 'scan lot1',
    },

    {
        trigger: '.o_barcode_client_action',
        run: 'scan lot2',
    },

    {
        trigger: '.o_barcode_client_action',
        run: 'scan lot2',
    },

    {
        trigger: '.o_barcode_client_action',
        run: 'scan LOC-01-01-00'
    },

    {
        trigger: '.o_current_dest_location:contains("WH/Stock/Section 1")',
        run: function() {
            helper.assertPageSummary(' To WH/Stock/Section 1');
            helper.assertPreviousVisible(true);
        }
    },
]);

tour.register('test_receipt_from_scratch_with_lots_3', {test: true}, [
    {
        trigger: '.o_barcode_client_action',
        run: function() {
            helper.assertPageSummary('To WH/Stock');
        }
    },

    {
        trigger: '.o_barcode_client_action',
        run: 'scan product1'
    },

    {
        trigger: '.o_barcode_line',
        run: function() {
            helper.assertLinesCount(1);
            const $line = helper.getLine({barcode: 'product1'});
            helper.assertLineIsHighlighted($line, true);
            helper.assertLineQty($line, "1");
        }
    },

    {
        trigger: '.o_barcode_client_action',
        run: 'scan productlot1'
    },

    {
        trigger: '.o_barcode_line:nth-child(2)',
        run: function() {
            helper.assertLinesCount(2);
            const $line1 = helper.getLine({barcode: 'product1'});
            const $line2 = helper.getLine({barcode: 'productlot1'});
            helper.assertLineIsHighlighted($line1, false);
            helper.assertLineQty($line1, "1");
            helper.assertLineIsHighlighted($line2, true);
            helper.assertLineQty($line2, "0");
        }
    },

    {
        trigger: '.o_barcode_client_action',
        run: 'scan lot1',
    },

    {
        trigger: '.o_barcode_client_action',
        run: 'scan lot1',
    },

    {
        trigger: '.qty-done:contains(2)',
        run: function() {
            helper.assertLinesCount(2);
            const $line1 = helper.getLine({barcode: 'product1'});
            const $line2 = helper.getLine({barcode: 'productlot1'});
            helper.assertLineIsHighlighted($line1, false);
            helper.assertLineQty($line1, "1");
            helper.assertLineIsHighlighted($line2, true);
            helper.assertLineQty($line2, "2");
        }
    },

    {
        trigger: '.o_barcode_client_action',
        run: 'scan O-BTN.validate'
    },
]);

tour.register('test_delivery_from_scratch_with_lots_1', {test: true}, [

    {
        trigger: '.o_barcode_client_action',
        run: 'scan lot1',
    },

    {
        trigger: '.o_barcode_client_action',
        run: 'scan lot1',
    },

    {
        trigger: '.o_barcode_client_action',
        run: 'scan lot2',
    },

    {
        trigger: '.o_barcode_client_action',
        run: 'scan lot2',
    },
    // Open the form view to trigger a save
    {
        trigger: '.o_add_line',
    },

    {
        trigger: '.o_field_widget[name="product_id"]',
    },

]);

tour.register('test_delivery_from_scratch_with_sn_1', {test: true}, [
    /* scan a product tracked by serial number. Then scan 4 a its serial numbers.
    */
    {
        trigger: '.o_barcode_client_action',
        run: 'scan productserial1',
    },

    {
        trigger: '.o_barcode_client_action',
        run: 'scan sn1',
    },

    {
        trigger: '.o_barcode_client_action',
        run: 'scan sn1',
    },

    {
        trigger: '.o_notification.bg-danger'
    },

    {
        trigger: '.o_barcode_client_action',
        run: function () {
            helper.assertErrorMessage('The scanned serial number is already used.');
        },
    },

    {
        trigger: '.o_barcode_client_action',
        run: 'scan sn2',
    },

    {
        trigger: '.o_barcode_client_action',
        run: 'scan sn3',
    },

    {
        trigger: '.o_barcode_client_action',
        run: 'scan sn4',
    },
    // Open the form view to trigger a save
    {
        trigger: '.o_add_line',
    },

    {
        trigger: '.o_field_widget[name="product_id"]',
    },

]);
tour.register('test_delivery_reserved_lots_1', {test: true}, [

    {
        trigger: '.o_barcode_client_action',
        run: 'scan productlot1',
    },

    {
        trigger: '.o_barcode_client_action',
        run: 'scan lot2',
    },

    {
        trigger: '.o_barcode_client_action',
        run: 'scan lot1',
    },

    {
        trigger: '.o_barcode_client_action',
        run: 'scan lot2',
    },
    // Open the form view to trigger a save
    {
        trigger: '.o_add_line',
    },

    {
        trigger: '.o_field_widget[name="product_id"]',
    },

]);

tour.register('test_delivery_reserved_with_sn_1', {test: true}, [
    /* scan a product tracked by serial number. Then scan 4 a its serial numbers.
    */
    {
        trigger: '.o_barcode_client_action',
        run: 'scan productserial1',
    },

    {
        trigger: '.o_barcode_client_action',
        run: 'scan sn3',
    },

    {
        trigger: '.o_barcode_client_action',
        run: 'scan sn3',
    },

    {
        trigger: '.o_notification.bg-danger'
    },

    {
        trigger: '.o_barcode_client_action',
        run: function () {
            helper.assertErrorMessage('The scanned serial number is already used.');
        },
    },

    {
        trigger: '.o_barcode_client_action',
        run: 'scan sn1',
    },

    {
        trigger: '.o_barcode_client_action',
        run: 'scan sn4',
    },

    {
        trigger: '.o_barcode_client_action',
        run: 'scan sn2',
    },
    // Open the form view to trigger a save
    {
        trigger: '.o_add_line',
    },

    {
        trigger: '.o_field_widget[name="product_id"]',
    },

]);

tour.register('test_receipt_reserved_lots_multiloc_1', {test: true}, [
    /* Receipt of a product tracked by lots. Open an existing picking with 4
    * units initial demands. Scan 2 units in lot1 in location WH/Stock. Then scan
    * 2 unit in lot2 in location WH/Stock/Section 2
    */

    {
        trigger: '.o_barcode_client_action',
        run: 'scan productlot1',
    },

    {
        trigger: '.o_barcode_client_action',
        run: 'scan lot1',
    },

    {
        trigger: '.o_barcode_client_action',
        run: 'scan lot1',
    },

    {
        trigger: '.o_barcode_client_action',
        run: 'scan LOC-01-02-00',
    },

    {
        trigger: '.o_barcode_client_action',
        run: 'scan productlot1',
    },

    {
        trigger: '.o_barcode_client_action',
        run: 'scan lot2',
    },

    {
        trigger: '.o_barcode_client_action',
        run: 'scan lot2',
    },

    {
        trigger: '.o_barcode_client_action',
        run: 'scan LOC-01-01-00',
    },
    // Open the form view to trigger a save
    {
        trigger: '.o_add_line',
    },

    {
        trigger: '.o_field_widget[name="product_id"]',
    },

]);

tour.register('test_receipt_duplicate_serial_number', {test: true}, [
    /* Create a receipt. Try to scan twice the same serial in different
    * locations.
    */
    {
        trigger: '.o_stock_barcode_main_menu:contains("Barcode Scanning")',
    },
    // reception
    {
        trigger: '.o_stock_barcode_main_menu',
        run: 'scan WH-RECEIPTS',
    },

    {
        trigger: '.o_barcode_client_action',
        run: 'scan productserial1',
    },

    {
        trigger: '.o_barcode_client_action',
        run: 'scan sn1',
    },

    {
        trigger: '.o_barcode_client_action',
        run: 'scan LOC-01-01-00',
    },

    {
        trigger: '.o_barcode_client_action',
        run: 'scan productserial1',
    },

    {
        trigger: '.o_barcode_client_action',
        run: 'scan sn1',
    },

    {
        trigger: '.o_notification.bg-danger'
    },

    {
        trigger: '.o_barcode_client_action',
        run: function () {
            helper.assertErrorMessage('The scanned serial number is already used.');
        },
    },

    {
        trigger: '.o_barcode_client_action',
        run: 'scan sn2',
    },

    {
        trigger: '.o_barcode_client_action',
        run: 'scan LOC-01-02-00',
    },

    {
        trigger: '.o_barcode_client_action',
        run: 'scan O-BTN.validate',
    },

    {
        trigger: '.o_notification.bg-success'
    },

    {
        trigger: '.o_stock_barcode_main_menu',
        run: function () {
            helper.assertErrorMessage('The transfer has been validated');
        },
    },
]);

tour.register('test_delivery_duplicate_serial_number', {test: true}, [
    /* Create a delivery. Try to scan twice the same serial in different
    * locations.
    */
    {
        trigger: '.o_stock_barcode_main_menu',
        run: 'scan WH-DELIVERY',
    },

    {
        trigger: '.o_barcode_client_action',
        run: 'scan LOC-01-01-00',
    },

    {
        trigger: '.o_barcode_client_action',
        run: 'scan productserial1',
    },

    {
        trigger: '.o_barcode_client_action',
        run: 'scan sn1',
    },

    {
        trigger: '.o_barcode_client_action',
        run: 'scan LOC-01-01-00',
    },

    {
        trigger: '.o_barcode_client_action',
        run: 'scan productserial1',
    },

    {
        trigger: '.o_barcode_client_action',
        run: 'scan sn1',
    },

    {
        trigger: '.o_notification.bg-danger'
    },

    {
        trigger: '.o_barcode_client_action',
        run: function () {
            helper.assertErrorMessage('The scanned serial number is already used.');
        },
    },

    {
        trigger: '.o_barcode_client_action',
        run: 'scan sn2',
    },

    {
        trigger: '.o_barcode_client_action',
        run: 'scan O-BTN.validate',
    },

    {
        trigger: '.o_notification.bg-success'
    },

    {
        trigger: '.o_stock_barcode_main_menu',
        run: function () {
            helper.assertErrorMessage('The transfer has been validated');
        },
    },
]);

tour.register('test_bypass_source_scan', {test: true}, [
    /* Scan directly a serial number, a package or a lot in delivery order.
    * It should implicitely trigger the same action than a source location
    * scan with the state location.
    */
    {
        trigger: '.o_barcode_client_action',
        run: function () {
            helper.assertPageSummary('From WH/Stock/Section 1');
            helper.assertPreviousVisible(true);
            helper.assertPreviousEnabled(true);
            helper.assertNextVisible(true);
            helper.assertNextEnabled(true);
            helper.assertNextIsHighlighted(false);
            helper.assertLinesCount(1);
            helper.assertScanMessage('scan_src');
            helper.assertLocationHighlight(false);
            helper.assertDestinationLocationHighlight(false);
            helper.assertPager('1/2');
            helper.assertValidateVisible(false);
            helper.assertValidateIsHighlighted(false);
            helper.assertValidateEnabled(false);
        }
    },

    {
        trigger: '.o_barcode_client_action',
        run: 'scan THEPACK',
    },

    {
        trigger: '.o_notification.bg-danger'
    },

    {
        trigger: '.o_barcode_client_action',
        run: function () {
            helper.assertErrorMessage("You are expected to scan one or more products or a package available at the picking's location");
        },
    },

    {
        trigger: '.o_barcode_client_action',
        run: 'scan serial1',
    },

    {
        trigger: '.o_edit'
    },

    {
        trigger: '.o_field_many2one[name=lot_id]',
        extra_trigger: '.o_field_widget[name="qty_done"]',
        position: "bottom",
        run: function (actions) {
            actions.text("", this.$anchor.find("input"));
        },
    },

    {
        trigger: 'input.o_field_widget[name=qty_done]',
        run: 'text 0',
    },

    {
        trigger: '.o_save'
    },

    {
        trigger: '.o_barcode_client_action',
        extra_trigger: '.o_barcode_line',
        run: 'scan lot1',
    },

    {
        trigger: '.o_barcode_client_action',
        run: 'scan lot1',
    },

    {
        trigger: '.o_barcode_client_action',
        run: 'scan LOC-01-02-00',
    },

    {
        trigger: '.o_barcode_client_action',
        run: 'scan THEPACK',
    },

    {
        trigger: '.o_barcode_client_action',
        run: 'scan productserial1',
    },

    {
        trigger: '.o_barcode_client_action',
        run: 'scan serial1',
    },

    {
        trigger: '.o_barcode_client_action',
        run: 'scan O-BTN.validate',
    },

    {
        trigger: '.o_notification.bg-success'
    },
]);

tour.register('test_inventory_adjustment', {test: true}, [

    {
        trigger: '.button_inventory',
    },

    {
        trigger: '.o-kanban-button-new',
    },
    //Check show information.
    {
        trigger: '.o_show_information',
    },

    {
        trigger: '.o_form_label:contains("Status")',
    },

    {
        trigger: '.o_close',
    },

    {
        trigger: '.o_barcode_message:contains("Scan products")',
    },

    {
        trigger: '.o_barcode_client_action',
        run: 'scan product1',
    },

    {
        trigger: '.o_barcode_client_action',
        run: 'scan product1',
    },

    {
        trigger: '.o_edit',
    },

    {
        trigger: '.o_field_widget[name="product_qty"]',
        run: function () {
            helper.assertInventoryFormQuantity('2');
        }
    },

    {
        trigger :'.o_save',
    },

    {
        trigger: '.o_add_line',
    },

    {
        trigger: ".o_field_widget[name=product_id] input",
        run: 'text product2',
    },

    {
        trigger: ".ui-menu-item > a:contains('product2')",
    },

    {
        trigger: "input.o_field_widget[name=product_qty]",
        run: 'text 2',
    },

    {
        trigger: '.o_save',
    },

    {
        extra_trigger: '.o_barcode_message:contains("Scan products")',
        trigger: '.o_barcode_client_action',
        run: 'scan O-BTN.validate',
    },

    {
        trigger: '.o_stock_barcode_kanban',
    },

    {
        trigger: '.o_notification.bg-success',
        run: function () {
            helper.assertErrorMessage('The inventory adjustment has been validated');
        },
    },

    {
        trigger: '.breadcrumb-item:contains("Barcode")',
    },

    {
        trigger: '.o_stock_barcode_main_menu',
    },
]);

tour.register('test_inventory_adjustment_mutli_location', {test: true}, [

    {
        trigger: '.button_inventory',
    },

    {
        trigger: '.o-kanban-button-new',
    },

    {
        trigger: '.o_barcode_client_action',
        run: 'scan LOC-01-00-00'
    },

    {
        trigger: '.o_barcode_summary_location_src:contains("WH/Stock")',
    },

    {
        trigger: '.o_barcode_client_action',
        run: 'scan product1',
    },

    {
        trigger: '.o_barcode_client_action',
        run: 'scan product1',
    },

    {
        trigger: '.o_barcode_client_action',
        run: 'scan product2',
    },

    {
        trigger: '.o_barcode_client_action',
        run: 'scan LOC-01-01-00'
    },

    {
        trigger: '.o_barcode_summary_location_src:contains("WH/Stock/Section 1")',
    },

    {
        trigger: '.o_barcode_client_action',
        run: 'scan product2',
    },

    {
        trigger: '.o_barcode_client_action',
        run: 'scan LOC-01-02-00'
    },

    {
        trigger: '.o_barcode_summary_location_src:contains("WH/Stock/Section 2")',
    },

    {
        trigger: '.o_barcode_client_action',
        run: 'scan product1',
    },

    {
        trigger: '.o_add_line',
    },

    {
        trigger: '.o_field_widget[name="product_id"]',
    },

]);

tour.register('test_inventory_adjustment_tracked_product', {test: true}, [

    {
        trigger: '.button_inventory',
    },

    {
        trigger: '.o-kanban-button-new',
    },

    {
        trigger: '.o_barcode_client_action',
        run: 'scan productlot1',
    },

    {
        trigger: '.o_barcode_client_action',
        run: 'scan lot1',
    },

    {
        trigger: '.o_barcode_client_action',
        run: 'scan lot1',
    },

    {
        trigger: '.o_barcode_client_action',
        run: 'scan productserial1',
    },

    {
        trigger: '.o_barcode_client_action',
        run: 'scan serial1',
    },

    {
        trigger: '.o_barcode_client_action',
        run: 'scan serial1',
    },

    {
        trigger: '.o_notification.bg-danger'
    },

    {
        trigger: '.o_barcode_client_action',
        run: function () {
            helper.assertErrorMessage('The scanned serial number is already used.');
        },
    },

    {
        trigger: '.o_barcode_client_action',
        run: 'scan serial2',
    },

    {
        trigger: '.o_barcode_client_action',
        run: 'scan productlot1',
    },

    {
        trigger: '.o_barcode_client_action',
        run: 'scan lot1',
    },

    {
        trigger: '.o_barcode_client_action',
        run: 'scan productserial1',
    },

    {
        trigger: '.o_barcode_client_action',
        run: 'scan serial3',
    },

    // Edit a line to trigger a save.
    {
        trigger: '.o_add_line',
    },

    {
        trigger: '.o_field_widget[name="product_id"]',
    },
    {
        trigger: '.o_discard',
    },

    // Scan tracked by lots product, then scan new lots.
    {
        extra_trigger: '.o_barcode_message',
        trigger: '.o_barcode_client_action',
        run: 'scan productlot1',
    },
    {
        trigger: '.o_barcode_client_action',
        run: 'scan lot2',
    },
    {
        trigger: '.o_barcode_client_action',
        run: 'scan lot3',
    },

    // Must have 6 lines (lot1, serial1, serial2, serial3, lot2, lot3).
    {
        trigger: '.o_barcode_line:nth-child(6)',
        run: function () {
            helper.assertLinesCount(6);
        }
    },
]);

tour.register('test_inventory_nomenclature', {test: true}, [

    {
        trigger: '.button_inventory',
    },

    {
        trigger: '.o-kanban-button-new',
    },

    {
        trigger: '.o_barcode_client_action',
        run: function() {
            helper.assertScanMessage('scan_products');
        },
    },

    {
        trigger: '.o_barcode_client_action',
        run: 'scan 2145631123457', // 12.345 kg
    },

    {
        trigger: '.product-label:contains("product_weight")'
    },

    {
        trigger: '.o_barcode_client_action',
        run: 'scan O-BTN.validate',
    },

    {
        trigger: '.o_notification.bg-success'
    },
    {
        trigger: '.breadcrumb-item:contains("Barcode")',
    },
    {
        trigger: '.o_stock_barcode_main_menu',
        run: function () {
            helper.assertErrorMessage('The inventory adjustment has been validated');
        },
    },
]);

tour.register('test_inventory_package', {test: true}, [

    {
        trigger: '.button_inventory',
    },
    {
        trigger: '.o-kanban-button-new',
    },

    {
        trigger: '.o_barcode_client_action',
        run: 'scan PACK001',
    },

    {
        trigger: '.o_barcode_line:contains("product2") .o_edit',
    },

    {
        trigger: '[name="product_qty"]',
        run: 'text 21'
    },

    {
        trigger: '.o_save',
    },

    {
        trigger: '.o_validate_page',
    },

    {
        trigger: '.o_stock_barcode_kanban',
    },

    {
        trigger: '.o_notification.bg-success',
        run: function () {
            helper.assertErrorMessage('The inventory adjustment has been validated');
        },
    },

    {
        trigger: '.breadcrumb-item:contains("Barcode")',
    },

    {
        trigger: '.o_stock_barcode_main_menu',
    },
]);

tour.register('test_pack_multiple_scan', {test: true}, [

    {
        trigger: '.o_stock_barcode_main_menu:contains("Barcode Scanning")',
    },
// reception
    {
        trigger: '.o_stock_barcode_main_menu',
        run: 'scan WH-RECEIPTS',
    },

    {
        trigger: '.o_barcode_client_action',
        run: 'scan product1',
    },

    {
        trigger: '.o_barcode_client_action',
        run: 'scan product2',
    },

    {
        trigger: '.o_barcode_client_action',
        run: 'scan O-BTN.pack',
    },

    {
        trigger: '.o_barcode_client_action',
        run: 'scan O-BTN.validate',
    },

    {
        trigger: '.o_notification.bg-success'
    },

    {
        trigger: '.o_stock_barcode_main_menu',
        run: function () {
            helper.assertErrorMessage('The transfer has been validated');
        },
    },
// Delivery transfer to check the error message
    {
        trigger: '.o_stock_barcode_main_menu',
        run: 'scan WH-DELIVERY',
    },

    {
        trigger: '.o_barcode_client_action',
        run: 'scan PACK0001000',
    },

    {
        trigger: '.o_barcode_client_action',
        run: 'scan PACK0001000',
    },

    {
        trigger: '.o_notification.bg-danger'
    },

    {
        trigger: '.o_barcode_client_action',
        run: function () {
            helper.assertErrorMessage('This package is already scanned.');
            var $line = helper.getLine({barcode: 'product1'});
            helper.assertLineIsHighlighted($line, true);
            var $line = helper.getLine({barcode: 'product2'});
            helper.assertLineIsHighlighted($line, true);
        },
    },

    {
        trigger: '.o_barcode_client_action',
        run: 'scan O-BTN.validate',
    },

    {
        trigger: '.o_notification.bg-success'
    },

    {
        trigger: '.o_stock_barcode_main_menu',
        run: function () {
            helper.assertErrorMessage('The transfer has been validated');
        },
    },
]);

tour.register('test_pack_common_content_scan', {test: true}, [
    /* Scan 2 packages PACK1 and PACK2 that contains both product1 and
     * product 2. It also scan a single product1 before scanning both pacakges.
     * the purpose is to check that lines with a same product are not merged
     * together. For product 1, we should have 3 lines. One with PACK 1, one
     * with PACK2 and the last without package.
     */
    {
        trigger: '.o_stock_barcode_main_menu:contains("Barcode Scanning")',
    },

    {
        trigger: '.o_stock_barcode_main_menu',
        run: 'scan WH-DELIVERY',
    },

    {
        trigger: '.o_barcode_client_action',
        run: 'scan product1',
    },

    {
        trigger: '.o_barcode_client_action',
        run: 'scan PACK1',
    },

    {
        trigger: '.o_barcode_client_action',
        run: 'scan PACK2',
    },

    {
        trigger: '.o_barcode_client_action:contains("PACK2")',
        run: function () {
            helper.assertLinesCount(5);
        },
    },

    {
        trigger: '.o_barcode_client_action',
        run: 'scan O-BTN.validate',
    },

    {
        trigger: '.o_notification.bg-success'
    },

    {
        trigger: '.o_stock_barcode_main_menu',
        run: function () {
            helper.assertErrorMessage('The transfer has been validated');
        },
    },
]);


tour.register('test_pack_multiple_location', {test: true}, [

    {
        trigger: '.o_stock_barcode_main_menu:contains("Barcode Scanning")',
    },

    {
        trigger: '.o_stock_barcode_main_menu',
        run: 'scan WH-INTERNAL',
    },

    {
        trigger: '.o_barcode_client_action',
        run: 'scan LOC-01-01-00'
    },

    {
        trigger: '.o_current_location:contains("WH/Stock/Section 1")',
        run: 'scan PACK0000666',
    },

    {
        trigger: '.o_package_content',
    },

    {
        trigger: '.o_kanban_view:contains("product1")',
        run: function () {
            helper.assertQuantsCount(2);
        },
    },

    {
        trigger: '.o_close',
    },

    {
        trigger: '.o_barcode_client_action',
        run: 'scan LOC-01-02-00',
    },

    {
        trigger: '.o_current_dest_location:contains("WH/Stock/Section 2")',
        run: 'scan O-BTN.validate',
    },

    {
        trigger: '.o_notification.bg-success'
    },

    {
        trigger: '.o_stock_barcode_main_menu',
        run: function () {
            helper.assertErrorMessage('The transfer has been validated');
        },
    },
]);

tour.register('test_put_in_pack_from_multiple_pages', {test: true}, [
    {
        trigger: '.o_barcode_client_action',
        run: function () {
            helper.assertPageSummary('From WH/Stock/Section 1 To WH/Stock');
            helper.assertPreviousVisible(true);
            helper.assertPreviousEnabled(true);
            helper.assertNextVisible(true);
            helper.assertNextEnabled(true);
            helper.assertNextIsHighlighted(false);
            helper.assertLinesCount(2);
            helper.assertScanMessage('scan_src');
            helper.assertLocationHighlight(false);
            helper.assertDestinationLocationHighlight(false);
            helper.assertPager('1/2');
            helper.assertValidateVisible(false);
            helper.assertValidateIsHighlighted(false);
            helper.assertValidateEnabled(false);
        },
    },

    {
        trigger: '.o_barcode_client_action',
        run: 'scan LOC-01-01-00'
    },

    {
        trigger: '.o_barcode_client_action',
        run: function () {
            helper.assertPageSummary('From WH/Stock/Section 1 To WH/Stock');
            helper.assertPreviousVisible(true);
            helper.assertPreviousEnabled(true);
            helper.assertNextVisible(true);
            helper.assertNextEnabled(true);
            helper.assertNextIsHighlighted(false);
            helper.assertLinesCount(2);
            helper.assertScanMessage('scan_products');
            helper.assertLocationHighlight(true);
            helper.assertDestinationLocationHighlight(false);
            helper.assertPager('1/2');
            helper.assertValidateVisible(false);
            helper.assertValidateIsHighlighted(false);
            helper.assertValidateEnabled(false);
        },
    },

    {
        trigger: '.o_barcode_client_action',
        run: 'scan product1',
    },

    {
        trigger: '.o_barcode_client_action',
        run: 'scan product2',
    },

    {
        trigger: '.o_next_page',
    },

    {
        trigger: '.o_barcode_client_action',
        run: 'scan LOC-01-02-00',
    },

    {
        trigger: '.o_barcode_client_action',
        run: 'scan product1',
    },

    {
        trigger: '.o_barcode_client_action',
        run: 'scan product2',
    },

    {
        trigger: '.o_barcode_client_action',
        run: 'scan O-BTN.pack',
    },

    {
        trigger: '.o_barcode_summary_location_src:contains("WH/Stock/Section 2")',
        run: 'scan O-BTN.validate',
    },

    {
        trigger: '.o_notification.bg-success'
    },

]);

tour.register('test_reload_flow', {test: true}, [
    {
        trigger: '.o_stock_barcode_main_menu',
        run: 'scan WH-RECEIPTS'
    },

    {
        trigger: '.o_barcode_client_action',
        run: 'scan product1'
    },

    {
        trigger: '.o_edit',
    },

    {
        extra_trigger: '.o_field_widget[name="product_id"]',
        trigger: 'input.o_field_widget[name=qty_done]',
        run: 'text 2',
    },

    {
        trigger: '.o_save',
    },

    {
        trigger: '.o_add_line',
    },

    {
        trigger: ".o_field_widget[name=product_id] input",
        run: 'text product2',
    },

    {
        trigger: ".ui-menu-item > a:contains('product2')",
    },

    {
        trigger: '.o_save',
    },

    {
        trigger: '.o_barcode_summary_location_dest:contains("WH/Stock")',
        run: function () {
            helper.assertScanMessage('scan_more_dest');
            helper.assertLocationHighlight(false);
            helper.assertDestinationLocationHighlight(true);
        },
    },

    {
        trigger: '.o_barcode_summary_location_dest:contains("WH/Stock")',
        run: 'scan LOC-01-01-00',
    },

    {
        trigger: '.o_barcode_summary_location_dest:contains("WH/Stock/Section 1")',
    },

    {
        trigger: '.o_barcode_client_action',
        run: 'scan O-BTN.validate',
    },

    {
        trigger: '.o_notification.bg-success',
    },

]);

tour.register('test_highlight_packs', {test: true}, [
    {
        trigger: '.o_barcode_client_action',
        run: function () {
            helper.assertLinesCount(1);
            helper.assertScanMessage('scan_products');
            helper.assertValidateVisible(true);
            helper.assertValidateIsHighlighted(false);
            helper.assertValidateEnabled(true);
            var $line = $('.o_barcode_line');
            helper.assertLineIsHighlighted($line, false);

        },
    },

    {
        trigger: '.o_barcode_client_action',
        run: 'scan PACK002',
    },

    {
        trigger: '.o_barcode_client_action:contains("PACK002")',
    },

    {
        trigger: '.o_barcode_client_action',
        run: function () {
            helper.assertLinesCount(2);
            helper.assertScanMessage('scan_products');
            helper.assertValidateVisible(true);
            helper.assertValidateIsHighlighted(false);
            helper.assertValidateEnabled(true);
            var $line = $('.o_barcode_line').eq(0);
            helper.assertLineIsHighlighted($line, true);
        },
    },

]);

tour.register('test_put_in_pack_from_different_location', {test: true}, [
    {
        trigger: '.o_barcode_client_action',
        run: 'scan LOC-01-01-00',
    },

    {
        trigger: '.o_barcode_client_action',
        run: 'scan product1',
    },

    {
        trigger: '.o_next_page',
    },

    {
        trigger: '.o_barcode_client_action',
        run: 'scan shelf3',
    },

    {
        trigger: '.o_barcode_client_action',
        run: 'scan product2',
    },

    {
        trigger: '.o_barcode_client_action',
        run: 'scan O-BTN.pack',
    },

    {
        trigger: '.o_barcode_line:contains("product2")',
        run: function() {
            const $line = helper.getLine({barcode: 'product2'});
            helper.assert($line.find('.fa-archive').length, 1, "Expected a 'fa-archive' icon for assigned pack");
        },
    },

    {
        trigger: '.o_barcode_client_action',
        run: 'scan LOC-01-01-00',
    },

    {
        trigger: '.o_barcode_summary_location_src:contains("WH/Stock/Section 1")',
    },

    {
        trigger: '.o_barcode_client_action',
        run: function () {
            helper.assertPageSummary('From WH/Stock/Section 1 To WH/Stock');
            helper.assertPreviousVisible(true);
            helper.assertPreviousEnabled(true);
            helper.assertNextVisible(false);
            helper.assertNextEnabled(false);
            helper.assertNextIsHighlighted(false);
            helper.assertLinesCount(0);
            helper.assertScanMessage('scan_products');
            helper.assertLocationHighlight(true);
            helper.assertDestinationLocationHighlight(false);
            helper.assertPager('3/3');
            helper.assertValidateVisible(true);
            helper.assertValidateIsHighlighted(false);
            helper.assertValidateEnabled(false);
        },
    },

    {
        trigger: '.o_previous_page',
    },

    {
        trigger: '.o_barcode_client_action',
        run: 'scan O-BTN.validate',
    },

    {
        trigger: '.o_notification.bg-success',
    },
]);

tour.register('test_put_in_pack_before_dest', {test: true}, [
    {
        trigger: '.o_barcode_client_action',
        run: 'scan LOC-01-01-00',
    },

    {
        trigger: '.o_barcode_client_action',
        run: 'scan product1',
    },

    {
        trigger: '.o_next_page',
    },

    {
        trigger: '.o_barcode_client_action',
        run: 'scan shelf3',
    },

    {
        trigger: '.o_barcode_client_action',
        run: 'scan product2',
    },

    {
        trigger: '.o_barcode_client_action',
        run: 'scan shelf4',
    },

    {
        trigger: '.o_barcode_client_action',
        run: 'scan O-BTN.pack'
    },

    {
        trigger: '.modal-title:contains("Choose destination location")',
    },

    {
        trigger: '.btn-primary',
    },

    {
        trigger: '.o_barcode_client_action',
        run: 'scan O-BTN.validate',
    },

    {
        trigger: '.o_notification.bg-success',
    },

]);

tour.register('test_picking_owner_scan_package', {test: true}, [
    {
        trigger: '.o_stock_barcode_main_menu:contains("Barcode Scanning")',
    },
    {
        trigger: '.o_stock_barcode_main_menu',
        run: 'scan WH-DELIVERY',
    },
    {
        trigger: '.o_barcode_client_action',
        run: 'scan P00001',
    },
    {
        trigger: '.o_barcode_client_action:contains("P00001")',
    },
    {
        trigger: '.o_barcode_client_action:contains("Azure Interior")',
    },
    {
        trigger: '.o_barcode_client_action',
        run: 'scan O-BTN.validate',
    },
    {
        trigger: '.o_notification.bg-success',
    },
]);

tour.register('test_inventory_owner_scan_package', {test: true}, [
    {
        trigger: '.button_inventory',
    },
    {
        trigger: '.o-kanban-button-new',
    },
    {
        trigger: '.o_barcode_client_action',
        run: 'scan P00001',
    },
    {
        trigger: '.o_barcode_client_action:contains("P00001")',
    },
    {
        trigger: '.o_barcode_client_action:contains("Azure Interior")',
    },
    {
        trigger: '.o_barcode_client_action',
        run: 'scan O-BTN.validate',
    },
    {
        trigger: '.o_notification.bg-success',
    },
]);

tour.register('test_inventory_using_buttons', {test: true}, [
    {
        trigger: '.button_inventory',
    },
    {
        trigger: '.o-kanban-button-new',
    },

    // Scans product 1: must have 1 quantity and buttons +1/-1 must be visible.
    {
        trigger: '.o_barcode_client_action',
        run: 'scan product1',
    },
    {
        trigger: '.o_barcode_client_action .o_barcode_line',
        run: function () {
            helper.assertLinesCount(1);
            const $line = helper.getLine({barcode: 'product1'});
            helper.assertLineIsHighlighted($line, true);
            helper.assertLineQty($line, '1');
            helper.assertButtonIsVisible($line, 'add_unit');
            helper.assertButtonIsVisible($line, 'remove_unit');
        }
    },
    // Clicks on -1 button: must have 0 quantity, -1 must be hidden now.
    {
        trigger: '.o_remove_unit',
    },
    {
        trigger: '.o_barcode_line:contains("0")',
        run: function () {
            helper.assertLinesCount(1);
            const $line = helper.getLine({barcode: 'product1'});
            helper.assertLineIsHighlighted($line, true);
            helper.assertLineQty($line, '0');
            helper.assertButtonIsVisible($line, 'add_unit');
            helper.assertButtonIsNotVisible($line, 'remove_unit');
        }
    },
    // Clicks on +1 button: must have 1 quantity, -1 must be visible now.
    {
        trigger: '.o_add_unit',
    },
    {
        trigger: '.o_barcode_line:contains("1")',
        run: function () {
            helper.assertLinesCount(1);
            const $line = helper.getLine({barcode: 'product1'});
            helper.assertLineIsHighlighted($line, true);
            helper.assertLineQty($line, '1');
            helper.assertButtonIsVisible($line, 'add_unit');
            helper.assertButtonIsVisible($line, 'remove_unit');
        }
    },

    // Scans productserial1: must have 0 quantity, buttons must be hidden (a
    // line for a tracked product can't have buttons if it has no lot).
    {
        trigger: '.o_barcode_client_action',
        run: 'scan productserial1',
    },
    {
        trigger: '.o_barcode_client_action .o_barcode_line:nth-child(2)',
        run: function () {
            helper.assertLinesCount(2);
            const $line = helper.getLine({barcode: 'productserial1'});
            helper.assertLineIsHighlighted($line, true);
            helper.assertLineQty($line, '0');
            helper.assertButtonIsNotVisible($line, 'add_unit');
            helper.assertButtonIsNotVisible($line, 'remove_unit');
        }
    },
    // Scans a serial number: must have 1 quantity, button -1 must be visible.
    {
        trigger: '.o_barcode_client_action',
        run: 'scan BNG-118',
    },
    {
        trigger: '.o_barcode_line:contains("BNG-118")',
        run: function () {
            helper.assertLinesCount(2);
            const $line = helper.getLine({barcode: 'productserial1'});
            helper.assertLineIsHighlighted($line, true);
            helper.assertLineQty($line, '1');
            helper.assertButtonIsNotVisible($line, 'add_unit');
            helper.assertButtonIsVisible($line, 'remove_unit');
        }
    },
    // Clicks on -1 button: must have 0 quantity, button +1 must be visible.
    {
        trigger: '.o_barcode_line:contains("productserial1") .o_remove_unit'
    },
    {
        trigger: '.o_barcode_line:contains("BNG-118")',
        run: function () {
            helper.assertLinesCount(2);
            const $line = helper.getLine({barcode: 'productserial1'});
            helper.assertLineIsHighlighted($line, true);
            helper.assertLineQty($line, '0');
            helper.assertButtonIsVisible($line, 'add_unit');
            helper.assertButtonIsNotVisible($line, 'remove_unit');
        }
    },

    // Scans productlot1: must have 0 quantity, buttons must be hidden.
    {
        trigger: '.o_barcode_client_action',
        run: 'scan productlot1',
    },
    {
        trigger: '.o_barcode_client_action .o_barcode_line:nth-child(3)',
        run: function () {
            helper.assertLinesCount(3);
            const $line = helper.getLine({barcode: 'productlot1'});
            helper.assertLineIsHighlighted($line, true);
            helper.assertLineQty($line, '0');
            helper.assertButtonIsNotVisible($line, 'add_unit');
            helper.assertButtonIsNotVisible($line, 'remove_unit');
        }
    },
    // Scans a lot number: must have 1 quantity, buttons must be visible.
    {
        trigger: '.o_barcode_client_action',
        run: 'scan toto-42',
    },
    {
        trigger: '.o_barcode_line:contains("toto-42")',
        run: function () {
            helper.assertLinesCount(3);
            const $line = helper.getLine({barcode: 'productlot1'});
            helper.assertLineIsHighlighted($line, true);
            helper.assertLineQty($line, '1');
            helper.assertButtonIsVisible($line, 'add_unit');
            helper.assertButtonIsVisible($line, 'remove_unit');
        }
    },
    // Clicks on -1 button: must have 0 quantity, button +1 must be visible.
    {
        trigger: '.o_barcode_line:contains("productlot1") .o_remove_unit'
    },
    {
        trigger: '.o_barcode_line:contains("toto-42")',
        run: function () {
            helper.assertLinesCount(3);
            const $line = helper.getLine({barcode: 'productlot1'});
            helper.assertLineIsHighlighted($line, true);
            helper.assertLineQty($line, '0');
            helper.assertButtonIsVisible($line, 'add_unit');
            helper.assertButtonIsNotVisible($line, 'remove_unit');
        }
    },
    // Clicks on +1 button: must have 1 quantity, buttons must be visible.
    {
        trigger: '.o_barcode_line:contains("productlot1") .o_add_unit'
    },
    {
        trigger: '.o_barcode_line:contains("toto-42")',
        run: function () {
            helper.assertLinesCount(3);
            const $line = helper.getLine({barcode: 'productlot1'});
            helper.assertLineIsHighlighted($line, true);
            helper.assertLineQty($line, '1');
            helper.assertButtonIsVisible($line, 'add_unit');
            helper.assertButtonIsVisible($line, 'remove_unit');
        }
    },

    // Validates the inventory.
    {
        trigger: '.o_validate_page'
    },
    {
        trigger: '.o_notification.bg-success'
    }
]);

tour.register('test_picking_keyboard_shortcuts', {test: true}, [
    {
        trigger: '.o_barcode_client_action',
        run: function() {
            helper.assertPageSummary('');
            helper.assertPreviousVisible(true);
            helper.assertPreviousEnabled(false);
            helper.assertNextVisible(false);
            helper.assertNextEnabled(false);
            helper.assertNextIsHighlighted(false);
            helper.assertLinesCount(3);
            helper.assertScanMessage('scan_products');
            helper.assertLocationHighlight(false);
            helper.assertValidateVisible(true);
            helper.assertValidateIsHighlighted(false);
            helper.assertValidateEnabled(true);
            helper.assert(
                $('.o_line_button').length, 6,
                "6 buttons must be present in the view (2 by line)"
            );
            // check that keyboard shortcuts are assigned and visible on button
            // since default is QWERTY we expect this order for the buttons.
            // Due to html formatting to make text look pretty, let's assume '+1' and
            // remaining qty values numbers on buttons are validated by other tests
            helper.assert($('.o_add_unit').eq(0).text().slice(-1), 'q');
            helper.assert($('.o_add_unit').eq(1).text().slice(-1), 'w');
            helper.assert($('.o_add_unit').eq(2).text().slice(-1), 'e');
            helper.assert($('.o_add_reserved').eq(0).text().slice(-1), 'Q');
            helper.assert($('.o_add_reserved').eq(1).text().slice(-1), 'W');
            helper.assert($('.o_add_reserved').eq(2).text().slice(-1), 'E');
            // add reserved buttons only visible when "Shift" is pushed
            helper.assertButtonIsNotVisible($('.o_barcode_line:first-child'), 'add_reserved');
            helper.assertButtonIsNotVisible($('.o_barcode_line:nth-child(2)'), 'add_reserved');
            helper.assertButtonIsNotVisible($('.o_barcode_line:last-child'), 'add_reserved');
            helper.assertLineQuantityOnReservedQty(0, '0 / 2');
            helper.assertLineQuantityOnReservedQty(1, '0 / 3');
            helper.assertLineQuantityOnReservedQty(2, '0 / 4');
        }
    },

    // On the first line...
    // Press +1 button using keyboard shortcut
    {
        trigger: '.o_barcode_client_action',
        run: function() {
            helper.triggerKeydown("q");
            helper.assert($('.o_add_reserved').eq(0).text().slice(-1), 'Q');
            const $line = $('.o_barcode_line:first-child');
            helper.assertButtonIsNotVisible($line, 'add_reserved');
            helper.assertLineQuantityOnReservedQty(0, '1 / 2');
            helper.assertLineIsHighlighted($('.o_barcode_line:first-child'), true);
            helper.assertLineIsHighlighted($('.o_barcode_line:nth-child(2)'), false);
            helper.assertLineIsHighlighted($('.o_barcode_line:last-child'), false);
        }
    },
    // Press +1 button again, now its buttons must be hidden and moved to the end of list
    {
        trigger: '.o_barcode_client_action',
        run: function() {
            helper.triggerKeydown("q");
            helper.assertLineButtonsAreVisible(2, false);
            helper.assertLineQuantityOnReservedQty(2, '2 / 2');
            helper.assertLineIsHighlighted($('.o_barcode_line:first-child'), false);
            helper.assertLineIsHighlighted($('.o_barcode_line:nth-child(2)'), false);
            helper.assertLineIsHighlighted($('.o_barcode_line:last-child'), true);
        }
    },

    // Product 2 now at top of list. Press Product2 add remaining quantity button.
    // Now its buttons must be hidden and it is at the bottom fo the list.
    {
        trigger: '.o_barcode_client_action',
        run: function() {
            helper.assertLineQuantityOnReservedQty(0, '0 / 3');
            helper.triggerKeydown("Shift");
            // only add reserved buttons visible when "Shift" is pushed for not done lines
            helper.assertButtonIsNotVisible($('.o_barcode_line:first-child'), 'add_unit');
            helper.assertButtonIsNotVisible($('.o_barcode_line:nth-child(2)'), 'add_unit');
            helper.assertButtonIsVisible($('.o_barcode_line:first-child'), 'add_reserved');
            helper.assertButtonIsVisible($('.o_barcode_line:nth-child(2)'), 'add_reserved');
            helper.assertLineButtonsAreVisible(2, false);
            helper.triggerKeydown("W", true);
            helper.assertLineQuantityOnReservedQty(2, '3 / 3');
            helper.assertLineIsHighlighted($('.o_barcode_line:first-child'), false);
            helper.assertLineIsHighlighted($('.o_barcode_line:nth-child(2)'), false);
            helper.assertLineIsHighlighted($('.o_barcode_line:last-child'), true);
            document.querySelector('.o_barcode_client_action')
                .dispatchEvent(new window.KeyboardEvent('keyup', { bubbles: true, key: "Shift"}));
            // only add unit buttons visible when "Shift" button is released
            helper.assertButtonIsNotVisible($('.o_barcode_line:first-child'), 'add_reserved');
            helper.assertButtonIsVisible($('.o_barcode_line:first-child'), 'add_unit');
            helper.assertLineButtonsAreVisible(1, false);
            helper.assertLineButtonsAreVisible(2, false);
        }
    },

    // change view to see that keyboard shorts get re-assigned (done lines = no keyboard shortcuts)
    {
        trigger: '.o_show_information'
    },

    {
        trigger: '.o_discard'
    },

    //(product3) is at the top of list and has new shortcut key
    {
        trigger: '.o_barcode_lines',
        run: function() {
            helper.assert($('.o_add_unit').eq(0).text().slice(-1), 'q');
            helper.assert($('.o_add_reserved').eq(0).text().slice(-1), 'Q');
            helper.assertButtonIsVisible($('.o_barcode_line:first-child'), 'add_unit');
            helper.assertLineQuantityOnReservedQty(0, '0 / 4');
            helper.assert($('.o_add_unit').eq(1)[0].hasAttribute('shortcutkey'), false);
            helper.assert($('.o_add_reserved').eq(1)[0].hasAttribute('shortcutkey'), false);
            helper.assert($('.o_add_unit').eq(2)[0].hasAttribute('shortcutkey'), false);
            helper.assert($('.o_add_reserved').eq(2)[0].hasAttribute('shortcutkey'), false);
        }
    },
    // Add rest of product3
    {
        trigger: '.o_barcode_client_action',
        run: function() {
            helper.triggerKeydown("Shift");
            helper.triggerKeydown("Q", true);
            helper.assertLineButtonsAreVisible(2, false);
            helper.assertLineQuantityOnReservedQty(2, '4 / 4');
            helper.assertValidateIsHighlighted(true);
        }
    },

    // Validate the delivery.
    {
        trigger: '.o_validate_page'
    },
    {
        trigger: '.o_notification.bg-success',
    },
]);

tour.register('test_inventory_keyboard_shortcuts', {test: true}, [
    {
        trigger: '.o_barcode_client_action .o_barcode_line',
        run: function () {
            helper.assertLinesCount(1);
            const $line = $('.o_barcode_line');
            helper.assertLineQty($line, '1');
            helper.assertButtonIsVisible($line, 'add_unit');
            helper.assertButtonIsVisible($line, 'remove_unit');
            // check that keyboard shortcuts are assigned and visible on button
            // since default is QWERTY we expect this order for the buttons.
            // Due to html formatting to make text look pretty, let's assume '+1' and
            // -1 numbers on buttons are validated by other tests
            helper.assert($('.o_add_unit').text().slice(-1), 'q');
            helper.assert($('.o_remove_unit').text().slice(-1), 'Q');
            // "Q" shouldn't be visible but "q" should
            helper.assert($('.o_remove_unit').children(":first").css('display'), 'none');
            helper.assert($('.o_add_unit').children(":first").css('display'), 'inline');
            helper.triggerKeydown("Shift");
            // "q" shouldn't be visible but "Q" should
            helper.assert($('.o_add_unit').children(":first").css('display'), 'none');
            helper.assert($('.o_remove_unit').children(":first").css('display'), 'inline');
            helper.triggerKeydown("Q", true);
        }
    },
    // -1 button triggered via key shortcut: must have 0 quantity, -1 must be hidden now.
    {
        trigger: '.o_barcode_line:contains("0")',
        run: function () {
            helper.assertLinesCount(1);
            const $line = $('.o_barcode_line');
            helper.assertLineIsHighlighted($line, true);
            helper.assertLineQty($line, '0');
            helper.assertButtonIsVisible($line, 'add_unit');
            helper.assertButtonIsNotVisible($line, 'remove_unit');
            // stop pressing shift = can see "q" again
            document.querySelector('.o_barcode_client_action')
                .dispatchEvent(new window.KeyboardEvent('keyup', { bubbles: true, key: "Shift"}));
            helper.assert($('.o_add_unit').children(":first").css('display'), 'inline');
            helper.triggerKeydown("q");

        }
    },
    // +1 button trigged via key shortcut: must have 1 quantity, -1 must be visible now.
    {
        trigger: '.o_barcode_line:contains("1")',
        run: function () {
            helper.assertLinesCount(1);
            const $line = $('.o_barcode_line');
            helper.assertLineIsHighlighted($line, true);
            helper.assertLineQty($line, '1');
            helper.assertButtonIsVisible($line, 'add_unit');
            helper.assertButtonIsVisible($line, 'remove_unit');
            // "Q" shouldn't be visible but "q" should
            helper.assert($('.o_remove_unit').children(":first").css('display'), 'none');
            helper.assert($('.o_add_unit').children(":first").css('display'), 'inline');
        }
    },

    // Validates the inventory.
    {
        trigger: '.o_validate_page'
    },
    {
        trigger: '.o_notification.bg-success'
    }
]);
});
