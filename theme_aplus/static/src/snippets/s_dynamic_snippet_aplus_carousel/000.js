/** @odoo-module **/

import publicWidget from "@web/legacy/js/public/public_widget";
import DynamicSnippetProducts from "@website_sale/snippets/s_dynamic_snippet_products/000";

const aplusDynamicSnippetProducts = DynamicSnippetProducts.extend({
    selector: ".aplus_product_carousel",

    /**
     * @override
     */
    init: function () {
        this._super.apply(this, arguments);
        this.template_key = "theme_aplus.aplus_product";
    },
});

publicWidget.registry.dynamic_snippet_aplus_carousel = aplusDynamicSnippetProducts;
export default aplusDynamicSnippetProducts;
