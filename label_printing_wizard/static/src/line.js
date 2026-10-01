/** @odoo-module **/
import LineComponent from "@stock_barcode/components/line";
import {patch} from "@web/core/utils/patch";

patch(LineComponent.prototype, {
    async labelWizard() {
        return this.env.model.labelWizard("stock.move.line", this.line.id);
    },
});
