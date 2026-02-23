/** @odoo-module **/
import {registry} from "@web/core/registry";
import {standardFieldProps} from "@web/views/fields/standard_field_props";
import {Component, useState, onWillStart} from "@odoo/owl";
import {useService} from "@web/core/utils/hooks";

export class CampaignPartitionAllocationWidget extends Component {
    static template = "mrp_campaign.PartitionAllocationWidget";
    static props = {...standardFieldProps};

    setup() {
        this.orm = useService("orm");
        // Initialize data, parsing from JSON field value
        this.state = useState({
            demands: [],
            // Add other state variables if needed for overall widget logic
        });

        onWillStart(async () => {
            const field_value = this.props.record.data[this.props.name];
            if (field_value) {
                const parsed_data = JSON.parse(field_value);
                this.state.demands = parsed_data.demands || [];
            }
        });

        /**
         * Handles quantity changes for a specific demand line.
         * Updates the allocated_to_a and allocated_to_b values.
         * @param {number} demandId The ID of the mrp.campaign.demand record.
         * @param {string} allocationKey 'allocated_to_a' or 'allocated_to_b'
         * @param {number} newQty The new quantity for the allocationKey.
         */
        this.onAllocationChange = (demandId, allocationKey, newQty) => {
            const demand = this.state.demands.find((item) => item.id === demandId);
            if (demand) {
                demand[allocationKey] = parseFloat(newQty) || 0;
                this.updateValue();
            }
        };
    }

    updateValue() {
        const value = JSON.stringify({demands: this.state.demands});
        this.props.record.update({[this.props.name]: value});
    }

    get isSplitMode() {
        return this.props.record.data.partition_mode === "split";
    }

    get destinationALabel() {
        return this.isSplitMode
            ? this.props.record.data.new_campaign_name_a || "New Campaign 1"
            : "Original Campaign";
    }

    get destinationBLabel() {
        return this.isSplitMode
            ? this.props.record.data.new_campaign_name_b || "New Campaign 2"
            : "Backorder Campaign";
    }
}

registry.category("fields").add("campaign_partition_allocation", {
    component: CampaignPartitionAllocationWidget,
});
