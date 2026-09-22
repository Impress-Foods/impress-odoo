/** @odoo-module **/
import MainComponent from "@stock_barcode/components/main";
import {patch} from "@web/core/utils/patch";

patch(MainComponent.prototype, {
    async labelWizard() {
        await this.env.model.save();
        const action = await this.orm.call(this.resModel, "action_open_label_wizard", [
            [this.resId],
        ]);
        this.action.doAction(action);
    },
});
