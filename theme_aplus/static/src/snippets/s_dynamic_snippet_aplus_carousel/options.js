/** @odoo-module **/
import options from "@web_editor/js/editor/snippets.options";
import dynamicSnippetProductsOptions from "@website_sale/snippets/s_dynamic_snippet_products/options";

const aplusDynamicSnippetProductOptions = dynamicSnippetProductsOptions.extend({});

options.registry.aplus_product_carousel = aplusDynamicSnippetProductOptions;
export default aplusDynamicSnippetProductOptions;
