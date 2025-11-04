/** @odoo-module **/
import options from "@web_editor/js/editor/snippets.options";
import dynamicSnippetProductsOptions from "@theme_aplus/snippets/s_dynamic_snippet_product_templates/options";

const windowCarouselOptions = dynamicSnippetProductsOptions.extend({});

options.registry.s_window_carousel = windowCarouselOptions;
export default windowCarouselOptions;
