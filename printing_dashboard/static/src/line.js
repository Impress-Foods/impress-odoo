/** @odoo-module **/
import LineComponent from "@stock_barcode/components/line";
import {patch} from "@web/core/utils/patch";

patch(LineComponent.prototype, {
    async openPrintDashboard() {
        return this.env.model.openPrintDashboard("stock.move.line", this.line.id);
    },
});
