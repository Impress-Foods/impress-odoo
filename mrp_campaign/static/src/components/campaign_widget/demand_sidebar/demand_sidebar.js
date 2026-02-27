/** @odoo-module **/
import {Component, onWillStart} from "@odoo/owl";
import {formatDate, deserializeDate} from "@web/core/l10n/dates";

export class DemandSidebar extends Component {
    static template = "mrp_campaign.DemandSidebar";
    static props = {
        moves: {type: Object},
        onUpdateMove: {type: Function},
        minimumQtys: {type: Object},
    };

    setup() {
        onWillStart(async () => {
            //console.log(this.props);
        });
    }

    _onInputChange(moveId, ev) {
        const val = parseFloat(ev.target.value) || 0;
        const clamped = this.clamp(val, 0, this.getMove(moveId).target_qty);
        this.props.onUpdateMove(moveId, clamped);
    }

    _onBtnClick(moveId, currentQty, delta) {
        const value = currentQty + delta;
        const clamped = this.clamp(value, 0, this.getMove(moveId).target_qty);
        this.props.onUpdateMove(moveId, clamped);
    }
    /**
     * Helper for the template to calculate move progress
     */
    getPercent(move) {
        if (!move.target_qty) return 0;
        return Math.min(100, Math.round((move.fulfilled_qty / move.target_qty) * 100));
    }

    /**
     * Determine badge and progress bar color
     */
    getStatusClass(move) {
        const pct = this.getPercent(move);
        if (pct >= 100) return "bg-success";
        if (pct > 0) return "bg-primary";
        return "bg-secondary";
    }

    getBadgeStatusClass(move) {
        const pct = this.getPercent(move);
        if (pct >= 100) return "bg-success";
        if (pct > 0) return "bg-info";
        return "bg-danger";
    }

    clamp(x, min_value, max_value) {
        return Math.max(min_value, Math.min(x, max_value));
    }

    getMove(moveId) {
        return this.props.moves.find((m) => m.move_id === moveId);
    }

    formatDate(date) {
        return formatDate(deserializeDate(date));
    }

    _setMoveFull(moveId) {
        const move = this.getMove(moveId);
        const value = move.target_qty;
        this.props.onUpdateMove(moveId, value);
    }
    _setMoveEmpty(moveId) {
        this.props.onUpdateMove(moveId, 0);
    }

    getFulfilledQty(productId) {
        const moves = this.props.moves.filter((m) => m.product_id === productId);
        return moves.reduce((sum, m) => sum + m.fulfilled_qty, 0);
    }

    isAboveFloor(productId) {
        const fulfilled = this.getFulfilledQty(productId);
        const floor = this.props.minimumQtys[productId];
        return fulfilled >= floor;
    }

    getProgressBarClass(productId) {
        if (this.isAboveFloor(productId)) {
            return "bg-secondary";
        } else {
            return "bg-danger";
        }
    }

    getPercentFulfilled(productId) {
        const moves = this.props.moves.filter((m) => m.product_id === productId);
        const fulfilled = this.getFulfilledQty(productId);
        const needed = moves.reduce((sum, m) => sum + (m.target_qty || 0), 0);
        if (!needed) return 0;
        return (fulfilled / needed) * 100;
    }
}
