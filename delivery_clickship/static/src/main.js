/** @odoo-module **/

import MainComponent from "@stock_barcode/components/main";
import {patch} from "@web/core/utils/patch";

patch(MainComponent.prototype, {
    _print_data() {
        console.log(this);
    },

    async openClickshipRateWizard() {
        await this.env.model.openClickshipRateWizard();
    },
});
