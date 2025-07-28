/** @odoo-module **/

import DynamicSnippetProducts from "@website_sale/snippets/s_dynamic_snippet_products/000";
import publicWidget from "@web/legacy/js/public/public_widget";

const DynamicSnippetProductTemplates = DynamicSnippetProducts.extend({
    selector: ".s_dynamic_snippet_product_templates",

    init: function () {
        this._super.apply(this, arguments);
        this.template_key = "theme_aplus.s_dynamic_snippet.carousel";
    },
});

publicWidget.registry.dynamic_snippet_product_templates =
    DynamicSnippetProductTemplates;
export default DynamicSnippetProductTemplates;
