# -*- coding: utf-8 -*-
# pylint: disable=no-member,access-member-before-definition
# Copyright (c) 2018, 	9t9it and contributors
# For license information, please see license.txt

from __future__ import unicode_literals
import json
import frappe
from frappe.utils import get_datetime, flt, cint
from frappe.model.document import Document
from toolz import merge, compose, pluck, excepts, first, unique, concatv, reduceby
from functools import partial
from pos_bahrain.utils import pick, sum_by


class POSClosingVoucher(Document):
    def validate(self):
        clauses = concatv(
            [
                "docstatus = 1",
                "name != %(name)s",
                "company = %(company)s",
                "pos_profile = %(pos_profile)s",
                "period_from <= %(period_to)s",
                "period_to >= %(period_from)s",
            ],
            ["user = %(user)s"] if self.user else [],
        )
        existing = frappe.db.sql(
            """
                SELECT 1 FROM `tabPOS Closing Voucher` WHERE {clauses}
            """.format(
                clauses=" AND ".join(clauses)
            ),
            values={
                "name": self.name,
                "company": self.company,
                "pos_profile": self.pos_profile,
                "user": self.user,
                "period_from": get_datetime(self.period_from),
                "period_to": get_datetime(self.period_to),
            },
        )
        if existing:
            frappe.throw(
                "Another POS Closing Voucher already exists during this time frame."
            )

        existing_opens = frappe.db.sql(
            """
                SELECT 1 FROM `tabPOS Closing Voucher` 
                WHERE docstatus = 0
                AND name != %(name)s
                AND user = %(user)s
            """,
            values={"name": self.name, "user": self.user},
        )
        if existing_opens:
            frappe.throw(
                "There are open closing voucher(s) on user {}. Please submit/delete them.".format(
                    self.user
                )
            )

    def before_insert(self):
        if not self.period_from:
            self.period_from = get_datetime()

    def before_submit(self):
        if not self.period_to:
            self.period_to = get_datetime()
        self.set_report_details()
        get_default_collected = compose(
            lambda x: x.collected_amount if x else 0,
            excepts(StopIteration, first, lambda x: None),
            partial(filter, lambda x: cint(x.is_default) == 1),
        )
        self.closing_amount = self.opening_amount + get_default_collected(self.payments)

    def set_report_details(self):
        args = merge(
            pick(["user", "pos_profile", "company"], self.as_dict()),
            {
                "period_from": get_datetime(self.period_from),
                "period_to": get_datetime(self.period_to),
            },
        )

        sales, returns = _get_invoices(args)
        actual_payments, collection_payments = _get_payments(args)
        taxes = _get_taxes(args)

        jsonString_col = json.dumps(sales, indent=4, sort_keys=True, default=str)
        f3= open("/home/demo9t9it/frappe-bench/apps/pos_bahrain/pos_bahrain/pcv/sales_get_invoices.txt","w+")
        f3.write(jsonString_col)

        jsonString_col = json.dumps(returns, indent=4, sort_keys=True, default=str)
        f3= open("/home/demo9t9it/frappe-bench/apps/pos_bahrain/pos_bahrain/pcv/returns_get_inovoices.txt","w+")
        f3.write(jsonString_col)
        taxes = _get_taxes(args)

        jsonString_col = json.dumps(actual_payments, indent=4, sort_keys=True, default=str) #this value is correct - 187.0
        f3= open("/home/demo9t9it/frappe-bench/apps/pos_bahrain/pos_bahrain/pcv/actual_payments_get_payments.txt","w+")
        f3.write(jsonString_col)

        jsonString_col = json.dumps(collection_payments, indent=4, sort_keys=True, default=str) #this value is correct - 19.8
        f3= open("/home/demo9t9it/frappe-bench/apps/pos_bahrain/pos_bahrain/pcv/collection_payments_get_payments.txt","w+")
        f3.write(jsonString_col)

        jsonString_col = json.dumps(taxes, indent=4, sort_keys=True, default=str)
        f3= open("/home/demo9t9it/frappe-bench/apps/pos_bahrain/pos_bahrain/pcv/taxes.txt","w+")
        f3.write(jsonString_col)

        def make_invoice(invoice):
            return merge(
                pick(["grand_total", "paid_amount", "change_amount"], invoice),
                {
                    "invoice": invoice.name,
                    "total_quantity": invoice.pos_total_qty,
                    "sales_employee": invoice.pb_sales_employee,
                },
            )

        def make_payment(payment):

            jsonString_col = json.dumps(payment, indent=4, sort_keys=True, default=str) #this value is correct
            f3= open("/home/demo9t9it/frappe-bench/apps/pos_bahrain/pos_bahrain/pcv/payment_arg_in_make_payment.txt","a+")
            f3.write(jsonString_col)


            mop_conversion_rate = (
                payment.amount / payment.mop_amount if payment.mop_amount else 1
            )
            expected_amount = (
                payment.amount - sum_by("change_amount", sales)
                if payment.is_default and not payment.pe_entry
                else (payment.mop_amount or payment.amount)
            )

            change_amount_make_payment = sum_by("change_amount", sales) #this value is correct - 1.9
            jsonString_col = json.dumps(change_amount_make_payment, indent=4, sort_keys=True, default=str)
            f3= open("/home/demo9t9it/frappe-bench/apps/pos_bahrain/pos_bahrain/pcv/change_amount_make_payment.txt","a+")
            f3.write(jsonString_col)
            f3.write(" --- ")

            jsonString_col = json.dumps(payment.amount, indent=4, sort_keys=True, default=str) #this value is correct - 187
            f3= open("/home/demo9t9it/frappe-bench/apps/pos_bahrain/pos_bahrain/pcv/payment_amount_make_payment.txt","a+")
            f3.write(jsonString_col)
            f3.write(" --- ")

            jsonString_col = json.dumps(expected_amount, indent=4, sort_keys=True, default=str) #this value is correct - 185.1
            f3= open("/home/demo9t9it/frappe-bench/apps/pos_bahrain/pos_bahrain/pcv/expected_amount_make_payment.txt","a+")
            f3.write(jsonString_col)
            f3.write(" --- ")

            return merge(
                pick(["is_default", "mode_of_payment", "type"], payment),
                {
                    "mop_conversion_rate": mop_conversion_rate,
                    "collected_amount": expected_amount,
                    "expected_amount": expected_amount,
                    "difference_amount": 0,
                    "mop_currency": payment.mop_currency
                    or frappe.defaults.get_global_default("currency"),
                    "base_collected_amount": expected_amount * flt(mop_conversion_rate),
                },
            )

        make_tax = partial(pick, ["rate", "tax_amount"])
        get_employees = partial(
            pick, ["pb_sales_employee", "pb_sales_employee_name", "grand_total"]
        )

        self.returns_total = sum_by("grand_total", returns)
        self.returns_net_total = sum_by("net_total", returns)
        self.grand_total = sum_by("grand_total", sales + returns)
        self.net_total = sum_by("net_total", sales + returns)
        self.outstanding_total = sum_by("outstanding_amount", sales)
        self.total_invoices = len(sales + returns)
        self.average_sales = sum_by("net_total", sales) / len(sales) if sales else 0
        self.total_quantity = sum_by("pos_total_qty", sales)
        self.returns_quantity = -sum_by("pos_total_qty", returns)
        self.tax_total = sum_by("tax_amount", taxes)
        self.discount_total = sum_by("discount_amount", sales)
        self.change_total = sum_by("change_amount", sales)
        self.total_collected = ( #319.9
            sum_by("amount", actual_payments) #302.0 // cash + benifit // benifit = 115, cash 187 // 
            + sum_by("amount", collection_payments) #19.8
            - self.change_total #1.9
        )

        total_collected = ( sum_by("amount", actual_payments) + sum_by("amount", collection_payments) - self.change_total )

        jsonString_col = json.dumps(total_collected, indent=4, sort_keys=True, default=str)
        f3= open("/home/demo9t9it/frappe-bench/apps/pos_bahrain/pos_bahrain/pcv/total_collected.txt","a+")
        f3.write(jsonString_col)

        total_actual_payment = sum_by("amount", actual_payments)
        total_collection_payment = sum_by("amount", collection_payments)
        total_change = self.change_total

        jsonString_col = json.dumps(total_actual_payment, indent=4, sort_keys=True, default=str)
        f3= open("/home/demo9t9it/frappe-bench/apps/pos_bahrain/pos_bahrain/pcv/total_actual_payment.txt","a+")
        f3.write(jsonString_col)
        jsonString_col = json.dumps(total_collection_payment, indent=4, sort_keys=True, default=str)
        f3= open("/home/demo9t9it/frappe-bench/apps/pos_bahrain/pos_bahrain/pcv/total_collection_payment.txt","a+")
        f3.write(jsonString_col)
        jsonString_col = json.dumps(total_change, indent=4, sort_keys=True, default=str)
        f3= open("/home/demo9t9it/frappe-bench/apps/pos_bahrain/pos_bahrain/pcv/total_change.txt","a+")
        f3.write(jsonString_col)

        self.invoices = []
        for invoice in sales:
            self.append("invoices", make_invoice(invoice))
            
            inv_data = make_invoice(invoice) #this value is correct
            jsonString_col = json.dumps(inv_data, indent=4, sort_keys=True, default=str)
            f3= open("/home/demo9t9it/frappe-bench/apps/pos_bahrain/pos_bahrain/pcv/inv_data_invoices.txt","a+")
            f3.write(jsonString_col)

        taxes = _get_taxes(args)

        jsonString_col = json.dumps(taxes, indent=4, sort_keys=True, default=str)
        f3= open("/home/demo9t9it/frappe-bench/apps/pos_bahrain/pos_bahrain/pcv/taxes.txt","a+")
        f3.write(jsonString_col)
        
        self.returns = []
        for invoice in returns:
            self.append("returns", make_invoice(invoice))

            return_inv_data = make_invoice(invoice)
            jsonString_col = json.dumps(return_inv_data, indent=4, sort_keys=True, default=str)
            f3= open("/home/demo9t9it/frappe-bench/apps/pos_bahrain/pos_bahrain/pcv/return_inv_data_invoices.txt","a+")
            f3.write(jsonString_col)

        existing_payments = self.payments

        def get_form_collected(mop):
            existing = compose(
                excepts(StopIteration, first, lambda x: None),
                partial(filter, lambda x: x.mode_of_payment == mop),
            )(existing_payments)
            if not existing or existing.collected_amount == existing.expected_amount:
                return {}
            return {"collected_amount": existing.collected_amount}

        self.payments = []
        for payment in actual_payments:
            self.append(
                "payments",
                merge(
                    make_payment(payment), get_form_collected(payment.mode_of_payment)
                ),
            )

            jsonString_col = json.dumps(actual_payments, indent=4, sort_keys=True, default=str) #this value is correct 187.1
            f3= open("/home/demo9t9it/frappe-bench/apps/pos_bahrain/pos_bahrain/pcv/actual_payment_arg.txt","a+")
            f3.write(jsonString_col)

            actual_payment_data_218 = make_payment(payment) #this value is correct - 185.1
            jsonString_col = json.dumps(actual_payment_data_218, indent=4, sort_keys=True, default=str)
            f3= open("/home/demo9t9it/frappe-bench/apps/pos_bahrain/pos_bahrain/pcv/actual_payment_data_218.txt","a+")
            f3.write(jsonString_col)

            payment_data = merge(make_payment(payment), get_form_collected(payment.mode_of_payment)) #this value is correct - 185.1
            jsonString_col = json.dumps(payment_data, indent=4, sort_keys=True, default=str)
            f3= open("/home/demo9t9it/frappe-bench/apps/pos_bahrain/pos_bahrain/pcv/payment_data.txt","a+")
            f3.write(jsonString_col)

        for payment in collection_payments:
            payment.update({"pe_entry":1})

            jsonString_col = json.dumps(collection_payments, indent=4, sort_keys=True, default=str) #this value is correct - 19.8
            f3= open("/home/demo9t9it/frappe-bench/apps/pos_bahrain/pos_bahrain/pcv/collection_payments_220.txt","a+")
            f3.write(jsonString_col)
            

            make_payment_data = make_payment(payment)
            jsonString_col = json.dumps(make_payment_data, indent=4, sort_keys=True, default=str)
            f3= open("/home/demo9t9it/frappe-bench/apps/pos_bahrain/pos_bahrain/pcv/make_payment_data.txt","a+")
            f3.write(jsonString_col)


            get_form_collected_data = get_form_collected(payment.mode_of_payment) #this value is correct - 19.8
            jsonString_col = json.dumps(get_form_collected_data, indent=4, sort_keys=True, default=str)
            f3= open("/home/demo9t9it/frappe-bench/apps/pos_bahrain/pos_bahrain/pcv/get_form_collected_data.txt","a+")
            f3.write(jsonString_col)


            collected_payment = merge(
                make_payment(payment), get_form_collected(payment.mode_of_payment)
            )

            collection_payment_data = merge( make_payment(payment), get_form_collected(payment.mode_of_payment)) #this value is correct - 19.8
            jsonString_col = json.dumps(collection_payment_data, indent=4, sort_keys=True, default=str)
            f3= open("/home/demo9t9it/frappe-bench/apps/pos_bahrain/pos_bahrain/pcv/collection_payment_data.txt","a+")
            f3.write(jsonString_col)

            existing_payment = list(
                filter(
                    lambda x: x.mode_of_payment == collected_payment["mode_of_payment"],
                    self.payments,
                )
            )[0]


            jsonString_col = json.dumps(existing_payment, indent=4, sort_keys=True, default=str)
            f3= open("/home/demo9t9it/frappe-bench/apps/pos_bahrain/pos_bahrain/pcv/existing_payment_data.txt","a+")
            f3.write(jsonString_col)

            if existing_payment:
                for field in [
                    "expected_amount",
                    "collected_amount",
                    "difference_amount",
                    "base_collected_amount",
                ]:
                    existing_payment.set(
                        field,
                        sum(
                            [
                                existing_payment.get(field),
                                collected_payment.get(field, 0),
                            ]
                        ),
                    )
            else:
                self.append("payments", collected_payment)

        self.taxes = []
        for tax in taxes:
            self.append("taxes", make_tax(tax))

        self.employees = []
        employee_with_sales = compose(list, partial(map, get_employees))(sales)
        employees = compose(
            list, unique, partial(map, lambda x: x["pb_sales_employee"])
        )(employee_with_sales)
        for employee in employees:
            sales_employee_name = compose(
                first, partial(filter, lambda x: x["pb_sales_employee"] == employee)
            )(employee_with_sales)["pb_sales_employee_name"]
            sales = compose(
                list,
                partial(map, lambda x: x["grand_total"]),
                partial(filter, lambda x: x["pb_sales_employee"] == employee),
            )(employee_with_sales)
            self.append(
                "employees",
                {
                    "sales_employee": employee,
                    "sales_employee_name": sales_employee_name,
                    "invoices_count": len(sales),
                    "sales_total": sum(sales),
                },
            )

        self.item_groups = []
        for row in _get_item_groups(args):
            self.append("item_groups", row)


def _get_clauses(args):

    clauses = concatv(
        [
            "si.docstatus = 1",
            "si.is_pos = 1",
            "si.pos_profile = %(pos_profile)s",
            "si.company = %(company)s",
            "TIMESTAMP(si.posting_date, si.posting_time) BETWEEN %(period_from)s AND %(period_to)s",  # noqa
        ],
        ["si.owner = %(user)s"] if args.get("user") else [],
    )

    jsonString_col = json.dumps(clauses, indent=4, sort_keys=True, default=str)
    f3= open("/home/demo9t9it/frappe-bench/apps/pos_bahrain/pos_bahrain/pcv/clauses.txt","w+")
    f3.write(jsonString_col)

    return " AND ".join(clauses)
    

def _get_invoices(args):
    sales = frappe.db.sql(
        """
            SELECT
                si.name AS name,
                si.pos_total_qty AS pos_total_qty,
                si.base_grand_total AS grand_total,
                si.base_net_total AS net_total,
                si.base_discount_amount AS discount_amount,
                si.outstanding_amount AS outstanding_amount,
                si.paid_amount AS paid_amount,
                si.change_amount AS change_amount,
                si.pb_sales_employee,
                si.pb_sales_employee_name
            FROM `tabSales Invoice` AS si
            WHERE {clauses} AND is_return != 1
        """.format(
            clauses=_get_clauses(args)
        ),
        values=args,
        as_dict=1,
    )
    returns = frappe.db.sql(
        """
            SELECT
                si.name AS name,
                si.pos_total_qty AS pos_total_qty,
                si.base_grand_total AS grand_total,
                si.base_net_total AS net_total,
                si.base_discount_amount AS discount_amount,
                si.paid_amount AS paid_amount,
                si.change_amount AS change_amount,
                si.pb_sales_employee,
                si.pb_sales_employee_name
            FROM `tabSales Invoice` As si
            WHERE {clauses} AND is_return = 1
        """.format(
            clauses=_get_clauses(args)
        ),
        values=args,
        as_dict=1,
    )
    return sales, returns


def _get_payments(args):
    sales_payments = frappe.db.sql(
        """
            SELECT
                sip.mode_of_payment AS mode_of_payment,
                sip.type AS type,
                SUM(sip.base_amount) AS amount,
                sip.mop_currency AS mop_currency,
                SUM(sip.mop_amount) AS mop_amount
            FROM `tabSales Invoice Payment` AS sip
            LEFT JOIN `tabSales Invoice` AS si ON
                sip.parent = si.name
            WHERE sip.parenttype = 'Sales Invoice' AND {clauses}
            GROUP BY sip.mode_of_payment
        """.format(
            clauses=_get_clauses(args)
        ),
        values=args,
        as_dict=1,
    )
    default_mop = compose(
        excepts(StopIteration, first, lambda __: None),
        partial(pluck, "mode_of_payment"),
        frappe.get_all,
    )(
        "Sales Invoice Payment",
        fields=["mode_of_payment"],
        filters={
            "parenttype": "POS Profile",
            "parent": args.get("pos_profile"),
            "default": 1,
        },
    )
    collection_payments = frappe.db.sql(
        """
            SELECT
                mode_of_payment,
                SUM(paid_amount) AS amount
            FROM `tabPayment Entry`
            WHERE docstatus = 1
            AND company = %(company)s
            AND owner = %(user)s
            AND payment_type = "Receive"
            AND TIMESTAMP(posting_date, pb_posting_time) BETWEEN %(period_from)s AND %(period_to)s
            GROUP BY mode_of_payment
        """,
        values=args,
        as_dict=1,
    )

    d1 = _correct_mop_amounts(sales_payments, default_mop)
    d2 =  _correct_mop_amounts(collection_payments, default_mop)

    jsonString_col = json.dumps(d1, indent=4, sort_keys=True, default=str) # this values are correct
    f3= open("/home/demo9t9it/frappe-bench/apps/pos_bahrain/pos_bahrain/pcv/sales_payments.txt","w+")
    f3.write(jsonString_col)

    jsonString_col = json.dumps(d2, indent=4, sort_keys=True, default=str) # this values are correct
    f3= open("/home/demo9t9it/frappe-bench/apps/pos_bahrain/pos_bahrain/pcv/collection_payments.txt","w+")
    f3.write(jsonString_col)

    return (
        _correct_mop_amounts(sales_payments, default_mop), #// this values are correct
        _correct_mop_amounts(collection_payments, default_mop),  #// this values are correct
    )


def _correct_mop_amounts(payments, default_mop):
    """
    Correct conversion_rate for MOPs using base currency.
    Required because conversion_rate is calculated as
        base_amount / mop_amount
    for MOPs using alternate currencies.
    """
    base_mops = compose(list, partial(pluck, "name"), frappe.get_all)(
        "Mode of Payment", filters={"in_alt_currency": 0}
    )
    base_currency = frappe.defaults.get_global_default("currency")

    def correct(payment):
        return frappe._dict(
            merge(
                payment,
                {"is_default": 1 if payment.mode_of_payment == default_mop else 0},
                {"mop_amount": payment.base_amount, "mop_currency": base_currency}
                if payment.mode_of_payment in base_mops
                else {},
            )
        )

    return [correct(x) for x in payments]


def _get_taxes(args):
    taxes = frappe.db.sql(
        """
            SELECT
                stc.rate AS rate,
                SUM(stc.base_tax_amount_after_discount_amount) AS tax_amount
            FROM `tabSales Taxes and Charges` AS stc
            LEFT JOIN `tabSales Invoice` AS si ON
                stc.parent = si.name
            WHERE stc.parenttype = 'Sales Invoice' AND {clauses}
            GROUP BY stc.rate
        """.format(
            clauses=_get_clauses(args)
        ),
        values=args,
        as_dict=1,
    )
    return taxes


def _get_item_groups(args):
    def get_tax_rate(item_tax_rate):
        try:
            tax_rates = json.loads(item_tax_rate)
            return sum([v for k, v in tax_rates.items()])
        except TypeError:
            0

    def set_tax_and_total(row):
        tax_amount = (
            get_tax_rate(row.get("item_tax_rate")) * row.get("net_amount") / 100
        )
        return merge(
            row,
            {
                "tax_amount": tax_amount,
                "grand_total": tax_amount + row.get("net_amount"),
            },
        )

    groups = reduceby(
        "item_group",
        lambda a, x: {
            "qty": a.get("qty") + x.get("qty"),
            "net_amount": a.get("net_amount") + x.get("net_amount"),
            "tax_amount": a.get("tax_amount") + x.get("tax_amount"),
            "grand_total": a.get("grand_total") + x.get("grand_total"),
        },
        (
            set_tax_and_total(x)
            for x in frappe.db.sql(
                """
            SELECT
                sii.item_code,
                sii.item_group,
                sii.qty,
                sii.net_amount,
                sii.item_tax_rate
            FROM `tabSales Invoice Item` AS sii
            LEFT JOIN `tabSales Invoice` AS si ON
                si.name = sii.parent
            WHERE {clauses}
        """.format(
                    clauses=_get_clauses(args)
                ),
                values=args,
                as_dict=1,
            )
        ),
        {"qty": 0, "net_amount": 0, "tax_amount": 0, "grand_total": 0},
    )
    return [merge(v, {"item_group": k}) for k, v in groups.items()]


def _validate_existing(doc):
    print(doc)
