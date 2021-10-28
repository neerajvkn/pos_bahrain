// Copyright (c) 2019, 	9t9it and contributors
// For license information, please see license.txt

{% include 'pos_bahrain/pos_bahrain/doctype/barcode_print/print.js' %}

frappe.ui.form.on('Barcode Print', pos_bahrain.scripts.barcode_print);
frappe.ui.form.on(
  'Barcode Print Item',
  pos_bahrain.scripts.barcode_print.barcode_print_item
);

frappe.ui.form.on('Barcode Print', {
  refresh: function (frm) {
    console.log("data")
    print_barcode(frm);
  }
});

function print_barcode(frm) {
  frm.add_custom_button(__('Print Barcode'), function () {
    print_activity(frm);
  })
}