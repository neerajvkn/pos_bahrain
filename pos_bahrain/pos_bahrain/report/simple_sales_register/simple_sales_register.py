# Copyright (c) 2013, 	9t9it and contributors
# For license information, please see license.txt

from __future__ import unicode_literals
import frappe
from frappe import _
from functools import partial
from toolz import compose, pluck, keyfilter, concatv


def execute(filters=None):
    columns = _get_columns()

    # if filters.get('warehouse'):
    #     columns.append({
    #         "label": 'Warehouse',
    #         "fieldname": 'warehouse',
    #         "fieldtype": 'Data',
    #         "width": 200,
    #     })
            
    keys = _get_keys()

    data = _get_data(_get_clauses(filters), filters, keys, filters)
    return columns, data


def _get_columns():
    def make_column(key, label, type="Currency", options=None, width=120):
        return {
            "label": _(label),
            "fieldname": key,
            "fieldtype": type,
            "options": options,
            "width": width,
        }

    columns = [
        make_column("posting_date", "Date", type="Date", width=90),
        make_column("invoice", "Invoice No", type="Link", options="Sales Invoice"),
        make_column("customer", "Customer", type="Link", options="Customer"),
        make_column("customer_name", "Customer Name", type="Data", width=150),
        make_column("total", "Total"),
        make_column("discount", "Discount"),
        make_column("net_total", "Net Total"),
        make_column("tax", "Tax"),
        make_column("grand_total", "Grand Total"),
    ]
    

    return columns


def _get_keys():
    return compose(list, partial(pluck, "fieldname"), _get_columns)()


def _get_clauses(filters):
    if not filters.get("company"):
        frappe.throw(_("Company is required to generate report"))
    invoice_type = {"Sales": 0, "Returns": 1}
    clauses = concatv(
        [
            "si.docstatus = 1",
            "si.company = %(company)s",
            "si.posting_date BETWEEN %(from_date)s AND %(to_date)s",
        ],
        ["si.customer = %(customer)s"] if filters.get("customer") else [],
        ["si.pos_profile = %(pos_profile)s"] if filters.get("pos_profile") else [],
        ["si.is_return = {}".format(invoice_type[filters.get("invoice_type")])]
        if filters.get("invoice_type") in invoice_type else [],
    )
    return " AND ".join(clauses)


def _get_data(clauses, args, keys, filters):
    join_item_table =  ("""RIGHT JOIN
                `tabSales Invoice Item` AS it
                ON it.warehouse = '%(warehouse)s'
                AND it.name = ( SELECT name FROM `tabSales Invoice Item` WHERE parent = si.name LIMIT 1)
                        """%{'warehouse':filters.get('warehouse')}) if filters.get('warehouse') else ""
    items = frappe.db.sql(
        """
            SELECT
                si.posting_date,
                si.name AS invoice,
                si.customer,
                si.customer_name,
                si.base_total AS total,
                si.base_discount_amount AS discount,
                si.base_net_total AS net_total,
                si.base_total_taxes_and_charges AS tax,
                si.base_grand_total AS grand_total
            FROM `tabSales Invoice` AS si
            {join_item_table}
            WHERE {clauses}
        """.format(
            join_item_table = join_item_table,
            clauses=clauses
        ),
        values=args,
        as_dict=1,
    )
    make_row = partial(keyfilter, lambda k: k in keys)
    return [make_row(x) for x in items]
