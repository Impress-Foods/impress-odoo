/** @odoo-module **/
import MainComponent from "@stock_barcode/components/main";
import {patch} from "@web/core/utils/patch";
import HeaderComponent from "@stock_barcode_mrp/components/header";

patch(MainComponent.prototype, {
    async doReservation() {
        await this.env.model.save();
        await this.orm.call(this.resModel, "action_assign", [[this.resId]]);
        const {route, params} = this.env.model.getActionRefresh(this.resId);
        const result = await this.rpc(route, params);
        await this.env.model.refreshCache(result.data.records);
        this.env.model._createState();
        this.render();
    },
});

MainComponent.components.Header = HeaderComponent;
