# Copyright (c) 2013, 	9t9it and contributors
# For license information, please see license.txt

from __future__ import unicode_literals
import frappe
from frappe import _, scrub
import json
import numpy
from datetime import date


def execute(filters=None):
	filters = frappe._dict(filters or {})
	# if not filters: filters = frappe._dict()

	columns = [
		{
			'fieldname': 'invoice_date',
			'label': _('Tax Invoice Date'),
			'fieldtype': 'Data',
			"width": 120
		},
		{
			'fieldname': 'sales_man',
			'label': _('Sales Man'),
			'fieldtype': 'Data',
			"width": 150
		},
		{
			'fieldname': 'customer',
			'label': _('Customer Name'),
			'fieldtype': 'Data',
			"width": 160
		},
		{
			'fieldname': 'invoice_no',
			'label': _('Description'),
			'fieldtype': 'Link',
			"options": "Sales Invoice",
			"width": 100
		},
		{
			'fieldname': 'amount_before_discount',
			'label': _('Amount Before Discount'),
			'fieldtype': 'Float',
			"width": 100,
			'precision': 3
		},
		{
			'fieldname': 'discount',
			'label': _('Discount'),
			'fieldtype': 'Float',
			"width": 80,
			'precision': 3
		},
		{
			'fieldname': 'amount_after_discount',
			'label': _("Amount After Discount"),
			'fieldtype': 'Float',
			"width": 100,
			'precision': 3
		},
		{
			'fieldname': 'vat',
			'label': _('VAT'),
			'fieldtype': 'Float',
			"width": 60,
			'precision': 3
		},
		{
			'fieldname': 'valuation_rate',
			'label': _('Cost of Sales'),
			'fieldtype': 'Float',
			"width": 100,
			'precision': 3
		},
		{
			'fieldname': 'total_sales',
			'label': _('Total Sales'),
			'fieldtype': 'Float',
			"width": 80,
			'precision': 3
		},
		{
			'fieldname': 'payment',
			'label': _('Payment'),
			'fieldtype': 'Float',
			"width": 80,
			'precision': 3
		},
		{
			'fieldname': 'outstanding',
			'label': _('Outstanding'),
			'fieldtype': 'Float',
			"width": 100,
			'precision': 3
		},
		{
			'fieldname': 'mop',
			'label': _('Payment Method'),
			'fieldtype': 'Data',
			"width": 100
		},
		{
			'fieldname': 'disc_percent',
			'label': _('Discount %'),
			'fieldtype': 'Data',
			"width": 100
		}
	]

	data = get_data(filters['from_date'], filters['to_date'])
	return columns, data


def get_data(from_date, to_date):

	inv_data = frappe.db.sql(""" (SELECT
								si.posting_date AS invoice_date,
								si.pb_sales_employee_name AS sales_man,
								si.customer_name AS customer,
								si.name AS invoice_no,
								SUM(inv_item.price_list_rate * inv_item.qty ) AS amount_before_discount,
								SUM(inv_item.discount_amount  * inv_item.qty ) AS discount,
								SUM(inv_item.amount) AS amount_after_discount,
								si.total_taxes_and_charges AS vat,
								si.rounded_total AS total_sales,
								(si.rounded_total - si.outstanding_amount) AS payment,
								si.outstanding_amount AS outstanding, 
								ip.mode_of_payment AS mop,
								si.pb_discount_percentage as disc_percent,
								si.docstatus as docstatus,
								si.is_return	
							FROM
								`tabSales Invoice` si
							LEFT JOIN
								`tabSales Invoice Item` inv_item ON inv_item.parent = si.name
							LEFT JOIN
								`tabSales Invoice Payment` ip ON ip.parent = si.name
							GROUP BY
								si.name
							HAVING
								si.docstatus = 1 AND si.is_return = 0 AND 
								si.posting_date BETWEEN '%(from_date)s' AND '%(to_date)s')
								"""%{"from_date":from_date, "to_date":to_date}, as_dict=1)
	for invoice in inv_data:
		items = frappe.db.sql(""" SELECT item_code, qty FROM `tabSales Invoice Item` where parent='%(si)s'"""%{"si":invoice.invoice_no}, as_dict = 1)
		valuation_rate = 0
		for item in items:
			val_rate = frappe.db.sql(""" SELECT valuation_rate FROM `tabStock Ledger Entry` where item_code='%(item)s'
										ORDER BY posting_date DESC, posting_time DESC LIMIT 1"""%{"item":item.item_code})
			if val_rate:
				valuation_rate += (val_rate[0][0] * item.qty)

		invoice.update({"valuation_rate":valuation_rate})
		
	return inv_data
	