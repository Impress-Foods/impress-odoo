/** @odoo-module **/
import MainComponent from "@stock_barcode/components/main";
import {patch} from "@web/core/utils/patch";
import HeaderComponent from "@stock_barcode_mrp/components/header";

patch(MainComponent.prototype, {
    async printOnlineLabel() {
        const action = await this.orm.call(this.resModel, "action_print_online_label", [
            [this.resId],
        ]);
        await this.action.doAction(action);
    },
});

MainComponent.components.Header = HeaderComponent;
