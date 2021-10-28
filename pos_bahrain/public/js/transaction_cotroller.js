// erpnext.TransactionController = erpnext.taxes_and_totals.extend({
//     apply_price_list: function(item, reset_plc_conversion) {
// 		console.logconsole.log("level 1 - custom doc")
// 		if(this.frm.doctype == "Sales Invoice" && this.frm.doc.items.length > 0){
// 			console.log( " level 2 - custom doc")
// 			if(this.frm.doc.items[0].pb_quotation){
// 				console.log(" level 3 - custom doc")
// 				return 0
// 			}
// 		}
		
// 		// We need to reset plc_conversion_rate sometimes because the call to
// 		// `erpnext.stock.get_item_details.apply_price_list` is sensitive to its value
// 		if (!reset_plc_conversion) {
// 			this.frm.set_value("plc_conversion_rate", "");
// 		}

// 		var me = this;
// 		var args = this._get_args(item);
// 		if (!((args.items && args.items.length) || args.price_list)) {
// 			return;
// 		}

// 		if (me.in_apply_price_list == true) return;

// 		me.in_apply_price_list = true;
// 		return this.frm.call({
// 			method: "erpnext.stock.get_item_details.apply_price_list",
// 			args: {	args: args },
// 			callback: function(r) {
// 				if (!r.exc) {
// 					frappe.run_serially([
// 						() => me.frm.set_value("price_list_currency", r.message.parent.price_list_currency),
// 						() => me.frm.set_value("plc_conversion_rate", r.message.parent.plc_conversion_rate),
// 						() => {
// 							if(args.items.length) {
// 								me._set_values_for_item_list(r.message.children);
// 							}
// 						},
// 						() => { me.in_apply_price_list = false; }
// 					]);

// 				} else {
// 					me.in_apply_price_list = false;
// 				}
// 			}
// 		}).always(() => {
// 			me.in_apply_price_list = false;
// 		});
// 	}
// })