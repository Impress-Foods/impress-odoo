/** @odoo-module **/

import publicWidget from "@web/legacy/js/public/public_widget";
import DynamicSnippet from "@website/snippets/s_dynamic_snippet/000";

const aplusDynamicSnippetProducts = DynamicSnippet.extend({
    selector: ".aplus_product_carousel",

    /**
     * @override
     */
    init: function () {
        this._super.apply(this, arguments);
        this.template_key = "theme_aplus.aplus_product";
        this.product_data = [];
    },

    async _fetchData() {
        this._super.apply(this, arguments);

        if (this._isConfigComplete()) {
            const nodeData = this.el.dataset;
            //console.log(nodeData);
            const response = await this.rpc(
                "/theme_aplus/get_products",
                Object.assign({
                    filter_id: parseInt(nodeData.filterId),
                }),
                this._getRpcParameters()
            );
            this.product_data = response;
        } else {
            this.product_data = [];
        }
    },

    /**
     * @override
     */
    _getQWebRenderOptions() {
        const result = this._super(...arguments);
        result["product_data"] = this.product_data;
        return result;
    },
});

publicWidget.registry.dynamic_snippet_aplus_carousel = aplusDynamicSnippetProducts;
export default aplusDynamicSnippetProducts;
