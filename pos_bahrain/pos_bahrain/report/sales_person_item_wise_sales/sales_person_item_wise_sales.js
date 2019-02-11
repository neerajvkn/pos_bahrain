// Copyright (c) 2016, 	9t9it and contributors
// For license information, please see license.txt
/* eslint-disable */

frappe.query_reports['Sales Person Item-wise Sales'] = {
  filters: [
    {
      fieldname: 'from_date',
      label: __('From Date'),
      fieldtype: 'Date',
      default: frappe.datetime.month_start(),
    },
    {
      fieldname: 'to_date',
      label: __('To Date'),
      fieldtype: 'Date',
      default: frappe.datetime.month_end(),
    },
    {
      fieldname: 'salesman',
      label: __('Sales Person'),
      fieldtype: 'Link',
      options: 'User',
    },
  ],
};