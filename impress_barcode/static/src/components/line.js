/** @odoo-module **/

import {patch} from "@web/core/utils/patch";
import LineComponent from "@stock_barcode/components/line";

patch(LineComponent.prototype, {
    get totalDemand() {
        if (this.line.ids) {
            const move_ids = this.line.lines
                .map((x) => x.move_id)
                .filter((e, i, self) => i === self.indexOf(e));
            const quantities = move_ids
                .map((x) => this.env.model.cache.getRecord("stock.move", x))
                .map((y) => y.product_uom_qty);
            const total_quantity = quantities.reduce(
                (acc, currentVal) => acc + currentVal,
                0
            );

            return total_quantity;
        } else {
            return this.env.model.getTotalDemand(this.line.move_id);
        }
    },

    get totalSupply() {
        const product = this.line.product_id.id;
        const total = this.env.model.totalSupply(product);
        return total;
    },

    // Reservation data for display
    get reservationData() {
        return this.env.model._getReservationData(this.line);
    },

    get plannedQty() {
        return this.reservationData.planned;
    },

    get reservedQty() {
        return this.reservationData.reserved;
    },

    get doneQty() {
        return this.reservationData.done;
    },

    get availableQty() {
        return this.reservationData.available;
    },

    get reservationStatus() {
        return this.reservationData.status;
    },

    get hasGap() {
        return this.availableQty > 0 || this.reservationStatus === "unreserved";
    },

    // For unreserved lines, hide lot and quantity info
    get isUnreservedLine() {
        return this.line.isUnreservedLine === true;
    },
});
