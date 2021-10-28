# Copyright (c) 2013, 	9t9it and contributors
# For license information, please see license.txt

from __future__ import unicode_literals
import frappe, erpnext
from frappe import _
from frappe.utils import flt, cint, getdate, now, date_diff
from erpnext.stock.utils import add_additional_uom_columns
from erpnext.stock.report.stock_ledger.stock_ledger import get_item_group_condition
from erpnext.stock.report.stock_ageing.stock_ageing import get_fifo_queue, get_average_age
from six import iteritems

def execute(filters=None):
	if not filters: filters = {}

	if filters.get("company"):
		company_currency = erpnext.get_company_currency(filters.get("company"))
	else:
		company_currency = frappe.db.get_single_value("Global Defaults", "default_currency")

	include_uom = filters.get("include_uom")
	columns = get_columns(filters)
	items = get_items(filters)
	sle = get_stock_ledger_entries(filters, items)

	if not sle:
		return columns, []

	iwb_map = get_item_warehouse_map(filters, sle)
	item_map = get_item_details(items, sle, filters)

	data = []
	conversion_factors = {}

	for (company, item, warehouse, whc) in sorted(iwb_map):
		if item_map.get(item):
			qty_dict = iwb_map[(company, item, warehouse, whc)]

			report_data = {
				'currency': company_currency,
				'item_code': item,
				'warehouse': warehouse,
				'warehouse_code':whc,
				
			}

			report_data.update(item_map[item])
			report_data.update(qty_dict)

			data.append(report_data)

			if report_data['bal_qty'] > 0:
				report_data.update({"stock_status":1})
			elif report_data['bal_qty'] <= 0:
				report_data.update({"stock_status":0})

	add_additional_uom_columns(columns, data, include_uom, conversion_factors)
	return columns, data

def get_columns(filters):
	"""return columns"""
	columns = [
		{"label": _("Site no"), "fieldname": "warehouse_code", "fieldtype": "Data", "width": 100},
		{"label": _("International barcode"), "fieldname": "intl_barcode", "fieldtype": "Data", "width": 100},
		{"label": _("Product description"), "fieldname": "item_code", "fieldtype": "Link", "options": "Item", "width": 100},
		{"label": _("RSP"), "fieldname": "price_list_rate", "fieldtype": "Float", "precision":3, "width": 100},
		{"label": _("Original price (if there is a discount)"), "fieldname": "price_list_rate", "fieldtype": "Float", "precision":3, "width": 100},
		{"label": _("Stock indicator"), "fieldname": "stock_status", "fieldtype": "Data", "width": 100}
	]
	return columns

def get_conditions(filters):
	conditions = ""

	if filters.get("to_date"):
		conditions += " and sle.posting_date <= %s" % frappe.db.escape(filters.get("to_date"))
	else:
		frappe.throw(_("'To Date' is required"))

	if filters.get("company"):
		conditions += " and sle.company = %s" % frappe.db.escape(filters.get("company"))

	if filters.get("warehouse"):
		warehouse_details = frappe.db.get_value("Warehouse",
			filters.get("warehouse"), ["lft", "rgt"], as_dict=1)
		if warehouse_details:
			conditions += " and exists (select name from `tabWarehouse` wh \
				where wh.lft >= %s and wh.rgt <= %s and sle.warehouse = wh.name)"%(warehouse_details.lft,
				warehouse_details.rgt)

	return conditions

def get_stock_ledger_entries(filters, items):
	item_conditions_sql = ''
	if items:
		item_conditions_sql = ' and sle.item_code in ({})'\
			.format(', '.join([frappe.db.escape(i, percent=False) for i in items]))

	conditions = get_conditions(filters)

	return frappe.db.sql("""
		select
			sle.item_code, warehouse, wh.pb_instashop_code AS whc, sle.posting_date, sle.actual_qty, sle.valuation_rate,
			sle.company, sle.voucher_type, sle.qty_after_transaction, sle.stock_value_difference,
			sle.item_code as name, sle.voucher_no, sle.stock_value
		from
			`tabStock Ledger Entry` sle force index (posting_sort_index)
		RIGHT JOIN
			`tabWarehouse` AS wh ON wh.name = sle.warehouse AND wh.pb_instashop = 1
		where sle.docstatus < 2 %s %s
		order by sle.posting_date, sle.posting_time, sle.creation, sle.actual_qty""" % #nosec
		(item_conditions_sql, conditions), as_dict=1)

def get_item_warehouse_map(filters, sle):
	iwb_map = {}
	from_date = getdate(filters.get("from_date"))
	to_date = getdate(filters.get("to_date"))

	float_precision = cint(frappe.db.get_default("float_precision")) or 3

	for d in sle:
		key = (d.company, d.item_code, d.warehouse, d.whc)
		if key not in iwb_map:
			iwb_map[key] = frappe._dict({
				"opening_qty": 0.0, "opening_val": 0.0,
				"in_qty": 0.0, "in_val": 0.0,
				"out_qty": 0.0, "out_val": 0.0,
				"bal_qty": 0.0, 
				"bal_val": 0.0,
				"val_rate": 0.0
			})

		qty_dict = iwb_map[(d.company, d.item_code, d.warehouse, d.whc)]

		if d.voucher_type == "Stock Reconciliation":
			qty_diff = flt(d.qty_after_transaction) - flt(qty_dict.bal_qty)
		else:
			qty_diff = flt(d.actual_qty)

		value_diff = flt(d.stock_value_difference)

		if d.posting_date < from_date:
			qty_dict.opening_qty += qty_diff
			qty_dict.opening_val += value_diff

		elif d.posting_date >= from_date and d.posting_date <= to_date:
			if flt(qty_diff, float_precision) >= 0:
				qty_dict.in_qty += qty_diff
				qty_dict.in_val += value_diff
			else:
				qty_dict.out_qty += abs(qty_diff)
				qty_dict.out_val += abs(value_diff)

		qty_dict.val_rate = d.valuation_rate
		qty_dict.bal_qty += qty_diff
		qty_dict.bal_val += value_diff

	iwb_map = filter_items_with_no_transactions(iwb_map, float_precision, filters)
	return iwb_map


def filter_items_with_no_transactions(iwb_map, float_precision, filters):
	for (company, item, warehouse, whc) in sorted(iwb_map):
		
		qty_dict = iwb_map[(company, item, warehouse, whc)]
		no_transactions = True
		pop_out = True

		for key, val in iteritems(qty_dict):
			if filters.get("available_qty"):
				if (filters.get("available_qty") <= val):
					pop_out = False
	
			val = flt(val, float_precision)
			qty_dict[key] = val
			if key != "val_rate" and val:
				no_transactions = False

		if filters.get("available_qty"):
			if no_transactions or pop_out:
				iwb_map.pop((company, item, warehouse, whc))

		if not filters.get("available_qty"):
			if no_transactions:
				iwb_map.pop((company, item, warehouse, whc))

	return iwb_map

def get_items(filters):
	conditions = []
	if filters.get("item_code"): 
		conditions.append("item.name=%(item_code)s")
	else:
		if filters.get("item_group"):
			conditions.append(get_item_group_condition(filters.get("item_group")))

	items = []
	if conditions:
		items = frappe.db.sql_list("""select name from `tabItem` item where item.insta_shop = 1 AND {}"""
			.format(" and ".join(conditions)), filters)
	if not conditions:
		items = frappe.db.sql_list("""select name from `tabItem` item where item.insta_shop = 1 """ )
	return items

def get_item_details(items, sle, filters):
	item_details = {}
	if not items:
		items = list(set([d.item_code for d in sle]))

	if not items:
		return item_details

	res = frappe.db.sql("""
		SELECT
			item.name, item.item_name, item.item_group, ip.price_list_rate
		FROM
			`tabItem` item
		LEFT JOIN
			`tabItem Price` ip ON ip.item_code = item.name AND ip.price_list = 'Standard Selling'
		HAVING
			item.name in (%s) 
	""" % (','.join(['%s'] *len(items))), items, as_dict=1)

	for item in res:
		barcodes = frappe.db.sql("""SELECT GROUP_CONCAT(barcode SEPARATOR ';'	) as barcode
						FROM `tabItem Barcode` bt
						WHERE bt.parenttype = 'Item' AND bt.parent='%(item_code)s'
						"""%{'item_code':item['name']}, as_dict = 1)

		item.update({"intl_barcode":barcodes[0]['barcode']})
		item_details.setdefault(item.name, item)

	return item_details
