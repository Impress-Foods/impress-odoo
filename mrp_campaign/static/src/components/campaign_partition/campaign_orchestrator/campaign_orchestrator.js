/** @odoo-module **/
import {Component, useState, onWillStart} from "@odoo/owl";
import {CampaignNode} from "../campaign_node/campaign_node";
import {DemandSidebar} from "../demand_sidebar/demand_sidebar";
import {standardFieldProps} from "@web/views/fields/standard_field_props";

export class CampaignOrchestrator extends Component {
    static components = {CampaignNode, DemandSidebar};
    static template = "mrp_campaign.CampaignOrchestrator";
    static props = {...standardFieldProps};

    setup() {
        this.state = useState({
            data: null,
            loading: true,
        });

        onWillStart(async () => {
            const field_value = this.props.record.data[this.props.name];
            if (field_value) {
                try {
                    this.state.data = JSON.parse(field_value);
                } catch (e) {
                    console.error("Failed to parse partition data:", e);
                }
            }
            this.state.loading = false;
        });
    }

    updateMoveQty(targetId, newQty) {
        const data = this.state.data;

        const move = data.demand_moves.find((m) => m.target_id === targetId);
        if (!move) return;

        move.promised_qty = Math.max(0, newQty);

        const totalForProduct = data.demand_moves
            .filter((m) => m.campaign_line_id === move.campaign_line_id)
            .reduce((sum, m) => sum + m.promised_qty, 0);

        const leaf = this._findLeafByCampaignLineId(data.tree, move.campaign_line_id);
        if (leaf) {
            leaf.quantities.planned = totalForProduct;
            this._recalculateDownstream(data.tree);
        }
        this.props.record.update(
            {[this.props.name]: JSON.stringify(this.state.data)},
            {save: true}
        );
        this.state.data = {...data};
    }

    _findLeafByCampaignLineId(node, campaignLineId) {
        if (node.line_id === campaignLineId) {
            return node;
        }
        if (node.upstream_branches) {
            for (const branch of node.upstream_branches) {
                const found = this._findLeafByCampaignLineId(branch, campaignLineId);
                if (found) return found;
            }
        }
        return null;
    }

    _getFloorForProduct(node, productId) {
        if (
            node.product_id === productId &&
            (!node.upstream_branches || node.upstream_branches.length === 0)
        ) {
            return node.quantities.floor || 0;
        }
        let total = 0;
        if (node.upstream_branches) {
            for (const branch of node.upstream_branches) {
                total += this._getFloorForProduct(branch, productId);
            }
        }
        return total;
    }

    /**
     * Updates a node's 'planned' quantity based on the needs of its children.
     * @param {Object} node - The current node in the tree (starting from Bulk).
     */
    _recalculateDownstream(node) {
        if (!node.upstream_branches || node.upstream_branches.length === 0) return;

        let theoreticalNeed = 0;
        for (const branch of node.upstream_branches) {
            this._recalculateDownstream(branch);
            theoreticalNeed += branch.quantities.planned * branch.ratio;
        }

        const roundedNeed = Math.round(theoreticalNeed * 100) / 100;

        node.quantities.planned = roundedNeed;
    }

    getMinimumQtys() {
        const product_ids = [
            ...new Set(this.state.data.demand_moves.map((d) => d.product_id)),
        ];
        return Object.fromEntries(
            product_ids.map((id) => {
                const floorQty = this._getFloorForProduct(this.state.data.tree, id);
                return [id, floorQty];
            })
        );
    }
}
