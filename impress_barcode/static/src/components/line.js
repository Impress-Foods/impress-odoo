/** @odoo-module **/

import {patch} from "@web/core/utils/patch";
import LineComponent from "@stock_barcode/components/line";

patch(LineComponent.prototype, {
    get plannedQty() {
        return this.env.model._getPlannedQty(this.line);
    },

    // For unreserved lines, hide lot and quantity info
    get isUnreservedLine() {
        return this.line.isUnreservedLine === true;
    },

    get style() {
        if (this.line.color) {
            return "border-left: 4px solid " + this.line.color + " !important;";
        }
        return "";
    },
});
