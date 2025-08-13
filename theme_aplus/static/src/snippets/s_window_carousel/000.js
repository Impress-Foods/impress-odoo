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
        this.next_index = 1;
        this.bgs = document.getElementsByClassName("hero-background");

        for (const bg of this.bgs) {
            bg.addEventListener("transitionend", (event) => {
                if (event.target.classList.contains("inactive")) {
                    event.target.src = `/web/image/product.template/${
                        this.data[this.next_index].id
                    }/hero_background`;
                }
            });
        }
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
        this.changeColors(this.data[this.current_index]);
        this.changeBackgrounds();
    },

    changeColors(product) {
        this.shop_button.style.setProperty("background-color", product.primary_color);
        this.shop_button.style.setProperty("color", product.text_color);

        Array.from(this.hero_texts).forEach((element) => {
            element.style.setProperty("color", product.primary_color);
        });
    },
    changeBackgrounds() {
        if (this.next_index !== this.current_index) {
            for (const bg of this.bgs) {
                if (bg.classList.contains("inactive")) {
                    bg.src = `/web/image/product.template/${
                        this.data[this.current_index].id
                    }/hero_background`;
                }
            }
        }

        Array.from(this.bgs).forEach((element) => {
            element.classList.toggle("active");
            element.classList.toggle("inactive");
        });
        this.next_index = (this.current_index + 1) % Object.keys(this.data).length;
        console.log(this.next_index);
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
        this.hero_texts = this.$el.find(".hero-text");
        this.shop_button = document.getElementsByClassName("shop-now-button")[0];

        for (const bg of this.bgs) {
            console.log(bg);
            if (bg.classList.contains("active")) {
                bg.src = `/web/image/product.template/${this.data[0].id}/hero_background`;
            } else {
                bg.src = `/web/image/product.template/${this.data[1].id}/hero_background`;
            }
        }
        this.changeColors(this.data[0]);
    },
});

publicWidget.registry.s_window_carousel = WindowCarousel;
export default WindowCarousel;
