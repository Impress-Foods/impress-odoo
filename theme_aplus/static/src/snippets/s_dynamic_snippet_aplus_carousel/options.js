/** @odoo-module **/
import options from "@web_editor/js/editor/snippets.options";
import dynamicSnippetProductsOptions from "@website_sale/snippets/s_dynamic_snippet_products/options";

const aplusDynamicSnippetProductOptions = dynamicSnippetProductsOptions.extend({
    /**
     * @override
     */
    async willStart() {
        const _super = this._super.bind(this);
        const result = _super(...arguments);
        console.log(this.dynamicFilterTemplates);
        return result;
    },

    /**
     * @private
     * @override
     */
    async _fetchDynamicFilterTemplates() {
        const filter =
            this.dynamicFilters[this.$target.get(0).dataset["filterId"]] ||
            this.dynamicFilters[this._defaultFilterId];
        this.dynamicFilterTemplates = {};
        if (!filter) {
            return [];
        }
        const dynamicFilterTemplates = await this.rpc(
            "/website/snippet/filter_templates",
            {
                filter_name: filter.model_name.replaceAll(".", "_"),
            }
        );
        console.log(dynamicFilterTemplates);
        for (let index in dynamicFilterTemplates) {
            this.dynamicFilterTemplates[dynamicFilterTemplates[index].key] =
                dynamicFilterTemplates[index];
        }
        this._defaultTemplateKey = dynamicFilterTemplates[0].key;
    },
});

options.registry.dynamic_snippet_aplus_carousel = aplusDynamicSnippetProductOptions;
export default aplusDynamicSnippetProductOptions;
