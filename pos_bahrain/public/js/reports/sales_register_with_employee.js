export function load_filters_on_load(report_name) {
  return async function (report) {
    if (!frappe.query_reports[report_name]) {
      const base = new frappe.views.QueryReport();
      base.report_name = report_name;
      await base.get_report_doc();
      await base.get_report_settings();
    }
    const filters = frappe.query_reports[report_name].filters;

    report.report_settings.filters = [
      ...filters,
      {
        fieldname: 'sales_employee',
        label: __('Sales Employee'),
        fieldtype: 'Link',
        options: 'Employee',
      },
    ];
    report.setup_filters();
  };
}

export default function () {
  return {
    onload: load_filters_on_load('Sales Register'),
    filters: [],
  };
}
