/** @odoo-module **/

import options from "@web_editor/js/editor/snippets.options";
import dynamicSnippetCarouselOptions from "@website_sale/snippets/s_dynamic_snippet_products/options";

import wUtils from "@website/js/utils";

const dynamicSnippetProductTemplatesOptions = dynamicSnippetCarouselOptions.extend({
    /**
     *
     * @override
     */
    init: function () {
        this._super.apply(this, arguments);
        this.modelNameFilter = "product.template";
    },
});

options.registry.dynamic_snippet_product_templates =
    dynamicSnippetProductTemplatesOptions;
export default dynamicSnippetProductTemplatesOptions;
