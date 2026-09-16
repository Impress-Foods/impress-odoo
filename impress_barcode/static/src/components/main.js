/** @odoo-module **/
import MainComponent from "@stock_barcode/components/main";
import {patch} from "@web/core/utils/patch";

patch(MainComponent.prototype, {
    async doReservation() {
        await this.env.model.save();
        await this.orm.call(this.resModel, "action_assign", [[this.resId]]);
        await this._onRefreshState();
    },
    async openBackend() {
        const action = await this.orm.call(
            this.resModel,
            "action_open_picking_backend_form",
            [[this.resId]]
        );
        await this.action.doAction(action);
    },
});
