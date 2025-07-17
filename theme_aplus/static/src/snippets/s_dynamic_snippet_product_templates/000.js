/** @odoo-module **/

import DynamicSnippetProducts from "@website_sale/snippets/s_dynamic_snippet_products/000";
import publicWidget from "@web/legacy/js/public/public_widget";

const DynamicSnippetProductTemplates = DynamicSnippetProducts.extend({
    selector: ".s_dynamic_snippet_product_templates",
});

publicWidget.registry.dynamic_snippet_product_templates =
    DynamicSnippetProductTemplates;
export default DynamicSnippetProductTemplates;
