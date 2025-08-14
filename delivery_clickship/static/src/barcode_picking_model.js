/** @odoo-module **/

import BarcodePickingModel from "@stock_barcode/models/barcode_picking_model";
import {patch} from "@web/core/utils/patch";

patch(BarcodePickingModel.prototype, {
    async openClickshipRateWizard() {
        const action = await this.orm.call(
            this.resModel,
            "action_get_clickship_rates",
            [[this.resId]]
        );
        if (typeof action === "object") {
            this.trigger("process-action", action);
            this.trigger("refresh");
        } else {
            this.trigger("refresh");
        }
    },

    clickshipRateNeeded() {
        return this.record.clickship_rate_needed;
    },

    get displayValidateButton() {
        const res = super.displayValidateButton;
        const ratesNeeded = this.clickshipRateNeeded();
        return res && !ratesNeeded;
    },
});
