function print_activity(frm) {
    frappe.ui.get_print_settings(
        false,
        (print_settings) =>
            _print_activity(
                {
                    patient: frm.doc.company,
                    data: frm.doc.items,
                },
                print_settings
            ),
        null
    );
}

function _print_activity(data, print_settings) {
    const base_url = frappe.urllib.get_base_url();
    const print_css = frappe.boot.print_css;
    const landscape = print_settings.orientation == "Landscape";
    const content = frappe.render_template("patient_activity", {
        patient: data.patient,
        data: data.data,
    });
    const html = frappe.render_template("print_template", {
        title: "Clinical History",
        columns: [],
        content,
        base_url,
        print_css,
        print_settings,
        landscape,
    });
    render_pdf_v2(html, print_settings);
}

function render_pdf_v2(html, opts = {}) {
	//Create a form to place the HTML content
	var formData = new FormData();

	//Push the HTML content into an element
	formData.append("html", html);
	// if (opts.orientation) {
	// 	formData.append("orientation", opts.orientation);
	// }

    formData.append("orientation", 'Landscape');
    formData.append("page-size", 'A10');


	var blob = new Blob([], { type: "text/xml"});
	formData.append("blob", blob);

	var xhr = new XMLHttpRequest();
	xhr.open("POST", '/api/method/frappe.utils.print_format.report_to_pdf');````
	xhr.setRequestHeader("X-Frappe-CSRF-Token", frappe.csrf_token);
	xhr.responseType = "arraybuffer";

	xhr.onload = function(success) {
		if (this.status === 200) {
			var blob = new Blob([success.currentTarget.response], {type: "application/pdf"});
			var objectUrl = URL.createObjectURL(blob);

			//Open report in a new window
			window.open(objectUrl);
		}
	};
	xhr.send(formData);
};