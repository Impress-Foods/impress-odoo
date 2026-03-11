/** @odoo-module **/

import GroupedLineComponent from "@stock_barcode/components/grouped_line";
import {patch} from "@web/core/utils/patch";

patch(GroupedLineComponent.prototype, {
    async labelWizard() {
        return this.env.model.labelWizard("stock.move", this.line.move_id);
    },
});
