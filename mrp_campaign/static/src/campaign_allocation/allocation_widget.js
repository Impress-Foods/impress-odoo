/** @odoo-module **/
import {registry} from "@web/core/registry";
import {standardFieldProps} from "@web/views/fields/standard_field_props";
import {Component, useState, onWillStart} from "@odoo/owl";
import {useService} from "@web/core/utils/hooks";

export class CampaignAllocationWidget extends Component {
    static template = "mrp_campaign.AllocationWidget";
    static props = {...standardFieldProps};

    setup() {
        this.orm = useService("orm");
        this.data = JSON.parse(this.props.record.data[this.props.name]);

        this.state = useState({
            demands: this.data.demands || [],
            allocatedBulk: this.data.allocated_bulk || 0,
            availableBulk: this.data.available_bulk || 0,
        });
    }

    onQtyChange(demandId, moveId, newQty) {
        const move = this.findMove(demandId, moveId);
        move.allocated_qty = parseFloat(newQty);
        this.calculateTotals();
        this.updateValue();
    }

    calculateTotals() {
        this.state.demands.forEach((demand) => {
            demand.total_allocated = demand.moves.reduce(
                (acc, i) => acc + i.allocated_qty,
                0
            );
        });

        this.state.allocatedBulk = this.state.demands.reduce(
            (acc, i) => acc + i.total_allocated,
            0
        );
    }

    findMove(demandId, moveId) {
        const demands = this.state.demands;
        const demand = demands.find((item) => item.id == demandId);
        const move = demand.moves.find((item) => item.id == moveId);
        return move;
    }

    updateValue() {
        const value = JSON.stringify(this.state);
        this.props.record.update({[this.props.name]: value});
    }
}

registry.category("fields").add("campaign_allocation", {
    component: CampaignAllocationWidget,
});
