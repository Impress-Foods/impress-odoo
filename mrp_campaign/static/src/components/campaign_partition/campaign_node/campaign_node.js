import {Component} from "@odoo/owl";

export class CampaignNode extends Component {
    static template = "mrp_campaign.CampaignNode";
    static props = {
        node: {type: Object},
        isRoot: {type: Boolean, optional: true},
    };

    formatQty(val) {
        return Math.round(val * 100) / 100;
    }

    get barColor() {
        return this.props.node.quantities.planned >= this.props.node.quantities.floor
            ? "bg-success"
            : "bg-danger";
    }
}
