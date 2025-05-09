/** @odoo-module **/
import options from "@web_editor/js/editor/snippets.options";

const TickerBlock = options.Class.extend({
    selector: ".s_scrolling_text_banner",

    /**
     * @override
     */
    start() {
        this.showTextButton = this.el.querySelector('we-button.edit-text-button');

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



    /**
     * @override
     */
    cleanForSave() {
        const $tickerText = this.$target.find('.ticker-text');
        $tickerText.removeClass('ticker-text-editing').addClass('d-none');
    },

    //--------------------------------------------------------------------------
    // Options
    //--------------------------------------------------------------------------

    /**
     * Toggles the text editor for the ticker.
     *
     * @param {boolean} previewMode
     * @param {string} widgetValue
     *param {Object} params
     */
    toggleText(previewMode, widgetValue, params) {
        this._makeTickerTextEditable();
    },

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





    //--------------------------------------------------------------------------
    // Private
    //--------------------------------------------------------------------------

    /**
     * Handles click on the edit text button.
     * 
     * @private
     */
    _onEditTextClick(ev) {
        ev.preventDefault();
        this._makeTickerTextEditable();
    },

    /**
     * Makes the ticker text element directly editable.
     * @private
     */
    _makeTickerTextEditable() {
        const $textElement = this.$target.find(".ticker-text");
        $textElement.removeClass("d-none").addClass("ticker-text-editing");

        // Focus the element for immediate editing
        $textElement.focus();

        // When editing is done, hide the element again and refresh the ticker
        $textElement.one("blur", () => {
            $textElement.removeClass("ticker-text-editing").addClass("d-none");
            this._triggerReload();
        });
    },

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
