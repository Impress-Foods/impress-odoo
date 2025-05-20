/** @odoo-module **/

import publicWidget from "@web/legacy/js/public/public_widget";
import DynamicSnippetProducts from "@website_sale/snippets/s_dynamic_snippet_products/000";

const aplusDynamicSnippetProducts = DynamicSnippetProducts.extend({
    selector: ".s_dynamic_snippet_aplus_carousel",
});

publicWidget.registry.dynamic_snippet_aplus_carousel = aplusDynamicSnippetProducts;
export default aplusDynamicSnippetProducts;
