/** @odoo-module **/

import publicWidget from "@web/legacy/js/public/public_widget";
import DynamicSnippetProductTemplates from "@theme_aplus/snippets/s_dynamic_snippet_product_templates/000";

const WindowCarousel = DynamicSnippetProductTemplates.extend({
    selector: ".s_window_carousel",

    /**
     * @override
     */
    init() {
        this._super.apply(this, arguments);
        this.template_key = "theme_aplus.window_carousel";
        this.current_index = 0;
    },

    /**
     * Gets the tag search domain
     * @override
     * @private
     */
    _getTagSearchDomain() {
        const searchDomain = [];
        let productTagIds = this.$el.get(0).dataset.productTagIds;
        productTagIds = productTagIds ? JSON.parse(productTagIds) : [];
        if (productTagIds.length) {
            searchDomain.push([
                "product_tag_ids",
                "in",
                productTagIds.map((productTag) => productTag.id),
            ]);
        }
        return searchDomain;
    },
    /**
     * @override
     * @private
     */
    async _fetchData() {
        if (this._isConfigComplete()) {
            const nodeData = this.el.dataset;
            const filter_id = parseInt(nodeData.filterId);
            console.log(nodeData);
            const response = await this.rpc(
                "/theme_aplus/get_products",
                Object.assign({
                    filter_id: filter_id,
                    search_domain: this._getSearchDomain(),
                }),
                this._getRpcParameters()
            );

            this.data = response;
        } else {
            this.data = [];
        }
    },

    _onSlide(event) {
        this.current_index = event.to;
        this.changeColors(this.data[this.current_index], false);
    },

    changeColors(product, firstRun) {
        this.shop_button.style.setProperty("background-color", product.primary_color);
        this.shop_button.style.setProperty("color", product.text_color);
        const hero_texts = this.$el.find(".hero-text");
        for (const el of hero_texts) {
            el.style.setProperty("color", product.primary_color);
        }

        const hero_bg_active = document.getElementsByClassName(
            "hero-background active"
        )[0];
        const hero_bg_inactive = document.getElementsByClassName(
            "hero-background inactive"
        )[0];

        const next_index = (this.current_index + 1) % Object.keys(this.data).length;
        if (firstRun) {
            hero_bg_active.src = `/web/image/product.template/${
                this.data[this.current_index].id
            }/hero_image`;

            hero_bg_inactive.src = `/web/image/product.template/${this.data[next_index].id}/hero_image`;
        } else {
            hero_bg_inactive.classList.replace("inactive", "active");
            hero_bg_active.classList.replace("active", "inactive");
            hero_bg_active.src = `/web/image/product.template/${this.data[next_index].id}/hero_image`;
        }
    },

    /**
     * @override
     * @private
     */
    _render: function () {
        this._super.apply(this, arguments);
        this.$el.removeClass("o_dynamic_empty");
        this._prepareContent();
        this._renderContent();
        this.trigger_up("widgets_start_request", {
            $target: this.$el.children("dynamic_snippet_template"),
            options: {parent: this},
            editableMode: this.editableMode,
        });
        this.carousel_element = document.getElementsByClassName("aplus_carousel")[0];
        this.carousel_element.addEventListener(
            "slide.bs.carousel",
            this._onSlide.bind(this)
        );
        this.shop_button = document.getElementsByClassName("shop-now-button")[0];
        this.changeColors(this.data[this.current_index], true);
    },
});

publicWidget.registry.s_window_carousel = WindowCarousel;
export default WindowCarousel;
