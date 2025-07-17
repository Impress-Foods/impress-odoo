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

    /**
     * @override
     * @private
     */
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
     * @private
     * @override
     */

    _render: function () {
        if (this.data.length >= 0 || this.editableMode) {
            this.$el.removeClass("o_dynamic_empty");
            this._prepareContent();
        } else {
            this.$el.addClass("o_dynamic_empty");
            this.renderedContent = "";
        }
        this._renderContent();
        this.trigger_up("widgets_start_request", {
            $target: this.$el.children(),
            options: {parent: this},
            editableMode: this.editableMode,
        });
        this.carousel_element = document.getElementsByClassName("aplus_carousel")[0];
        this.carousel_element.addEventListener(
            "slide.bs.carousel",
            this._onSlide.bind(this)
        );
        this.shop_button = document.getElementsByClassName("shop-now-button")[0];
        this.changeColors(this.product_data[0]);
    },

    _onSlide(event) {
        this.changeColors(this.product_data[event.to]);
    },

    changeColors(product) {
        this.shop_button.style.setProperty("background-color", product.primary_color);
        this.shop_button.style.setProperty("color", product.text_color);
    },

    /**
     * @override
     */
    _getQWebRenderOptions() {
        const result = this._super(...arguments);
        result["product_data"] = this.product_data;
        result["interval"] = parseInt(this.el.dataset.carouselInterval);
        return result;
    },
});

publicWidget.registry.dynamic_snippet_aplus_carousel = aplusDynamicSnippetProducts;
export default aplusDynamicSnippetProducts;
