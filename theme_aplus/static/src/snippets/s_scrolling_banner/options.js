/** @odoo-module **/
import options from "@web_editor/js/editor/snippets.options";

const TickerBlock = options.Class.extend({
    selector: ".s_scrolling_text_banner",

    /**
     * @override
     */
    start() {
        this._super(...arguments);
        return this._reloadEditorUI();
    },

    /**
     * @override
     */
    onBuilt() {
        this._super(...arguments);
        this._reloadEditorUI();
    },

    //--------------------------------------------------------------------------
    // Options
    //--------------------------------------------------------------------------

    /**
     * Changes the speed of the ticker.
     *
     * @param {boolean} previewMode
     * @param {string} widgetValue
     * @param {Object} params
     */
    setSpeed(previewMode, widgetValue, params) {
        this.$target[0].dataset.speed = widgetValue;
        this._triggerReload();
    },

    destroy() {},
    //--------------------------------------------------------------------------
    // Private
    //--------------------------------------------------------------------------

    /**
     * Triggers a reload of the editor UI and the ticker.
     * @private
     */
    _reloadEditorUI() {
        this._triggerReload();
        return Promise.resolve();
    },

    /**
     * Triggers a reload of the ticker.
     * @private
     */
    _triggerReload() {
        this.$target.trigger("attribute-changed");
    },
});

options.registry.TickerBlock = TickerBlock;
export default TickerBlock;
