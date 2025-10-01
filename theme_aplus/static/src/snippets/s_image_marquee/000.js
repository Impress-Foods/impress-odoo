/** @odoo-module **/

import publicWidget from "@web/legacy/js/public/public_widget";

const ImageMarqueeWidget = publicWidget.Widget.extend({
    selector: ".s_image_marquee",

    /**
     * @override
     */
    start() {
        this._super.apply(this, arguments);
        this.editorActive = $("body").hasClass("editor_enable");
        this.$inner = this.$target.find(".marquee-inner").first();
        this.$holder = this.$target.find(".marquee").first();
        this.animationDuration = this.$holder[0].dataset.speed;
        this.$holder[0].style.setProperty(
            "--marquee-duration",
            `${this.animationDuration}s`
        );
        if (this.$inner && this.$holder && !this.editorActive) {
            this.setupMarquee();
            this._attachResizeListener();
        }
    },

    setupMarquee: function () {
        this._clearClones();
        this._cloneContent();
    },

    _cloneContent: function () {
        // 1. Clear previous clones inside the *single* animated block
        this.$inner.find(".marquee-clone").remove();

        // 2. Identify the content to clone (assuming image wrappers/images are direct children)
        // We clone the *children* of the inner block.
        const $contentToClone = this.$inner.children().not(".marquee-clone");

        if ($contentToClone.length === 0) {
            // If content is missing, we can't clone.
            return;
        }

        // 3. Clone the content set exactly once
        const $clonedContent = $contentToClone.clone(true);

        // 4. Add the identification class to the cloned content
        $clonedContent.addClass("marquee-clone");

        // 5. Append the clone *into* the original inner block
        this.$inner.append($clonedContent);

        // 🛑 CRITICAL ALIGNMENT STEP: Set the initial scroll position of the marquee holder
        // to ensure the scroll starts smoothly, although the CSS animation handles the main movement.
        // This is optional but can sometimes help alignment on initialization.
        this.$holder.scrollLeft(0);
    },
    /**
     * Clears all existing cloned elements before recalculating and cloning again.
     */
    _clearClones() {
        this.$holder.find(".marquee-clone").remove();
    },

    _attachResizeListener() {
        let resizeTimer;

        const handleResize = () => {
            // Re-run setup to adjust the number of clones for the new viewport size
            const editorActive = $("body").hasClass("editor_enable");
            if (!editorActive) {
                this.setupMarquee();
            }
        };

        $(window).on("resize.ImageMarqueeWidget", () => {
            // Added namespace for easier cleanup
            clearTimeout(resizeTimer);
            // Debounce the resize event to prevent performance issues
            resizeTimer = setTimeout(handleResize, 150);
        });
    },
});

publicWidget.registry.marquee = ImageMarqueeWidget;

export default {ImageMarqueeWidget: ImageMarqueeWidget};
