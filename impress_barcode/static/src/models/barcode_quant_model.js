import {patch} from "@web/core/utils/patch";
import BarcodeQuantModel from "@stock_barcode/models/barcode_quant_model";

patch(BarcodeQuantModel.prototype, {
    _getPlannedQty(line) {
        return this.getQtyDemand(line);
    },
});
