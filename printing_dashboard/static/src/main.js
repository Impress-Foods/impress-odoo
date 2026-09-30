/** @odoo-module **/
import MainComponent from "@stock_barcode/components/main";
import {patch} from "@web/core/utils/patch";

patch(MainComponent.prototype, {
    async openPrintDashboard() {
        await this.env.model.save();
        const action = await this.orm.call(
            this.resModel,
            "action_open_print_dashboard",
            [[this.resId]]
        );
        await this.action.doAction(action);
    },
});
