/** @odoo-module **/

import DynamicSnippetProducts from "@website_sale/snippets/s_dynamic_snippet_products/000";
import publicWidget from "@web/legacy/js/public/public_widget";

const DynamicSnippetProductTemplates = DynamicSnippetProducts.extend({
    selector: ".s_dynamic_snippet_product_templates",

    init: function () {
        this._super.apply(this, arguments);
        this.template_key = "theme_aplus.s_dynamic_snippet.carousel";
    },
    _getTagSearchDomain: function () {
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
});

publicWidget.registry.dynamic_snippet_product_templates =
    DynamicSnippetProductTemplates;
export default DynamicSnippetProductTemplates;
