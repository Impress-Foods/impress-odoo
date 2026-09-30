/** @odoo-module **/
import BarcodePickingModel from "@stock_barcode/models/barcode_picking_model";
import {patch} from "@web/core/utils/patch";

patch(BarcodePickingModel.prototype, {
    async openPrintDashboard(resModel, resId) {
        await this.save();
        const action = await this.orm.call(resModel, "action_open_print_dashboard", [
            [resId],
        ]);
        await this.action.doAction(action);
    },
});
