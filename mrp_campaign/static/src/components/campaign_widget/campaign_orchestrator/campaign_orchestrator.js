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
                this.state.data = JSON.parse(field_value);
                this.state.loading = false;
            }
        });
    }

    updateMoveQty(moveId, newQty) {
        const data = this.state.data;

        const move = data.demand_moves.find((m) => m.move_id === moveId);
        if (!move) return;

        move.fulfilled_qty = Math.max(0, newQty);

        const totalForProduct = data.demand_moves
            .filter((m) => m.product_id === move.product_id)
            .reduce((sum, m) => sum + m.fulfilled_qty, 0);

        const leaf = this._findLeafByProductId(data.tree, move.product_id);
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

    _syncTreeWithDemand(productId) {
        const data = this.state.data;

        const totalForProduct = (data.demand_moves || [])
            .filter((m) => m.product_id === productId)
            .reduce((sum, m) => sum + (m.fulfilled_qty || 0), 0);

        const leaf = this._findLeafByProductId(data.tree, productId);
        if (leaf) {
            leaf.quantities.planned = totalForProduct;
            this._recalculateDownstream(data.tree);
        }
    }

    _findLeafByProductId(node, productId) {
        if (
            node.product_id === productId &&
            (!node.upstream_branches || node.upstream_branches.length === 0)
        ) {
            return node;
        }
        if (node.upstream_branches) {
            for (const branch of node.upstream_branches) {
                const found = this._findLeafByProductId(branch, productId);
                if (found) return found;
            }
        }
        return null;
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
                const leaf = this._findLeafByProductId(this.state.data.tree, id);
                // Ensure we handle cases where a leaf might not be found or floor is missing
                const floorQty = leaf?.quantities?.floor || 0;
                return [id, floorQty];
            })
        );
    }
}
