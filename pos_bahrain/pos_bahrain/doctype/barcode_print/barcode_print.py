# -*- coding: utf-8 -*-
# Copyright (c) 2019, 	9t9it and contributors
# For license information, please see license.txt

from __future__ import unicode_literals
import frappe
from frappe.model.document import Document
from toolz import merge

from pos_bahrain.api.item import get_actual_qty
from pos_bahrain.utils import pick

import json


class BarcodePrint(Document):
    def validate(self):
        pass

    # def validate_doc(self):
    #     mismatched_batches = []
    #     for item in self.items:
    #         if item.batch and item.item_code != frappe.db.get_value(
    #             "Batch", item.batch, "item"
    #         ):
    #             mismatched_batches.append(item)
    #     if mismatched_batches:
    #         frappe.throw(
    #             "Batches mismatched in rows: {}".format(
    #                 ", ".join(
    #                     [
    #                         "<strong>{}</strong>".format(x.idx)
    #                         for x in mismatched_batches
    #                     ]
    #                 )
    #             )
    #         )
    #         return 1
    #     else:
    #         return 0

    def set_items_from_reference(self):
        ref_doc = frappe.get_doc(self.print_dt, self.print_dn)

        if self.print_dt == "Stock Entry":
            self.set_warehouse = (
                ref_doc.from_warehouse
                if self.use_warehouse == "Source"
                else ref_doc.to_warehouse
            )
        else:
            self.set_warehouse = ref_doc.set_warehouse
            self.use_warehouse = None  # Target, Source

        self.items = []
        for ref_item in ref_doc.items:
            items = merge(
                pick(
                    ["item_code", "item_name", "qty", "uom", "rate", "warehouse"],
                    ref_item.as_dict(),
                ),
                {
                    "batch": ref_item.batch_no,
                    "expiry_date": _get_expiry_date(ref_item),
                    "actual_qty": _get_actual_qty(ref_item, self.set_warehouse),
                },
            )
            self.append("items", items)


def _get_expiry_date(item):
    if (
        item.batch_no
        and not item.pb_expiry_date
        and frappe.get_cached_value("Item", item.item_code, "has_expiry_date")
    ):
        return frappe.db.get_value("Batch", item.batch_no, "expiry_date")
    return item.pb_expiry_date


def _get_actual_qty(item, warehouse):
    if warehouse:
        return get_actual_qty(item.item_code, warehouse, item.batch_no)
    return 0

@frappe.whitelist()
def validate_doc(item_table):
    item_table_j = json.loads(item_table)

    # jsonString_col = json.dumps(item_table_j, indent=4, sort_keys=True, default=str) #this value is correct - 19.8
    # f3= open("/home/demo9t9it/frappe-bench/apps/pos_bahrain/pos_bahrain/pos_bahrain/doctype/barcode_print/item_table.txt","a+")
    # f3.write(jsonString_col)

    mismatched_batches = []
    for item in item_table_j:
        if 'batch' in item.keys():
            if item['batch'] and item['item_code'] != frappe.db.get_value(
                "Batch", item['batch'], "item"
            ):
                mismatched_batches.append(item)
        else:
            mismatched_batches.append(item)
    if mismatched_batches:
        # frappe.msgprint("mismatched batches")
        frappe.msgprint(
            "Batches mismatched in rows: {}".format(
                ", ".join(
                    [
                        "<strong>{}</strong>".format(x['idx'])
                        for x in mismatched_batches
                    ]
                )
            )
        )
        frappe.msgprint("return 1")
        return 1
    elif not mismatched_batches:
        # frappe.msgprint("return 0 ")
        return 0