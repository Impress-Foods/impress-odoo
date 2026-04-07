/** @odoo-module **/
import {EventBus} from "@odoo/owl";
import {useBus} from "@web/core/utils/hooks";
import MainComponent from "@stock_barcode/components/main";
import {patch} from "@web/core/utils/patch";
import MoveComponent from "./move";
import {Chatter} from "@mail/core/web/chatter";
import {View} from "@web/views/view";
import GroupedLineComponent from "@stock_barcode/components/grouped_line";
import LineComponent from "@stock_barcode/components/line";
import PackageLineComponent from "@stock_barcode/components/package_line";
import HeaderComponent from "@stock_barcode_mrp/components/header";
const bus = new EventBus();

patch(MainComponent.prototype, {
    get unreservedMoves() {
        if (this.env.model.lineModel != "stock.move.line") {
            return [];
        } else {
            return this.env.model.unreservedMoves;
        }
    },

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

MainComponent.components = {
    Chatter,
    View,
    GroupedLineComponent,
    LineComponent,
    PackageLineComponent,
    MoveComponent,
};
MainComponent.components.Header = HeaderComponent;
