/** @odoo-module **/

import {patch} from "@web/core/utils/patch";
import BarcodePickingModel from "@stock_barcode/models/barcode_picking_model";

patch(BarcodePickingModel.prototype, {
    getTotalDemand(move_id) {
        try {
            return this.cache.getRecord("stock.move", move_id)["product_uom_qty"];
        } catch (error) {
            return 0;
        }
    },

    get origin() {
        return this.record.origin;
    },

    _getMoveData(id) {
        const smData = this.cache.getRecord("stock.move", id);
        smData.product_id = this.cache.getRecord("product.product", smData.product_id);
        return smData;
    },

    get unreservedMoves() {
        const move_ids = this.moveIds;
        const lines = this.pageLines;
        for (const line of lines) {
            const move_id = line.move_id;
            const index = move_ids.indexOf(move_id);
            if (index != -1) {
                move_ids.splice(index, 1);
            }
        }
        const moves = move_ids.map((x) => this._getMoveData(x));
        return moves;
    },

    totalSupply(product_id) {
        // We need to check every stock move line
        // to grab the ones with this product
        const move_lines = this.cache.dbIdCache["stock.move.line"];
        let total = 0;

        for (const key in move_lines) {
            const line = move_lines[key];
            if (line.product_id == product_id) {
                total += line.qty_done;
            }
        }

        return total;
    },
});
