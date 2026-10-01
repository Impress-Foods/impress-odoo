/** @odoo-module **/

import {patch} from "@web/core/utils/patch";
import BarcodePickingModel from "@stock_barcode/models/barcode_picking_model";

patch(BarcodePickingModel.prototype, {
    async labelWizard(resModel, resId) {
        await this.save();
        const action = await this.orm.call(resModel, "action_open_label_wizard", [
            [resId],
        ]);
        this.action.doAction(action);
    },
});
