/** @odoo-module **/

import publicWidget from "@web/legacy/js/public/public_widget";

const TickerBlock = publicWidget.Widget.extend({
    selector: ".s_scrolling_text_banner",
    events: {
        "attribute-changed": "_onAttributeChanged",
    },

    /**
     * @override
     */
    start() {
        this._setupTicker();
        return this._super(...arguments);
    },

    /**
     * @override
     */
    destroy() {
        this._cleanupTicker();
        this._super(...arguments);
    },

    //--------------------------------------------------------------------------
    // Private
    //--------------------------------------------------------------------------

    /**
     * Sets up the ticker content and animation.
     * @private
     */
    _setupTicker() {
        // Clear any existing content
        this._cleanupTicker();
        // Get the text from the editable element
        const $sourceText = this.$el.find(".ticker-text");
        const $textElements = $sourceText.children().first();
        const bulletStyle = $textElements.children("font").attr("style");

        const tickerText = $sourceText.length
            ? $sourceText.text().trim()
            : "Infinite Ticker";
        const tickerSpeed = parseInt(this.el.dataset.speed) || 50;

        // Get the speed multiplier from CSS variables (set by the class) - higher values = faster animation
        const computedStyle = window.getComputedStyle(this.el);
        const speedMultiplier =
            parseFloat(computedStyle.getPropertyValue("--ticker-speed-multiplier")) ||
            1.0;

        // Find the ticker stripe that will contain all items
        this.$tickerStripe = this.$el.find(".ticker-stripe");

        // Calculate how many items we need to fill at least one screen width
        const viewportWidth = window.innerWidth;
        const itemWidth = this._estimateItemWidth(tickerText);
        const itemsPerScreen = Math.ceil(viewportWidth / itemWidth) + 1;

        // We'll need at least 2x the number of items to ensure smooth scrolling
        const itemsNeeded = itemsPerScreen * 2;

        const elementToAdd = $textElements
            .clone()
            .addClass("ticker-item")
            .attr("style", bulletStyle);

        // Create ticker items with proper spacing
        for (let i = 0; i < itemsNeeded; i++) {
            //this.$tickerStripe.append(`<div class="ticker-item">${tickerText}</div>`);
            this.$tickerStripe.append(elementToAdd.clone());
        }

        // Get the actual stripe width after items are added
        const stripeWidth = this.$tickerStripe.width();

        // Calculate animation duration based on speed setting
        // Lower speed value = slower animation (longer duration)
        const speedFactor = 101 - Math.min(Math.max(parseInt(tickerSpeed), 10), 100);

        // Calculate the baseline duration
        const baselineDuration = (stripeWidth / 70) * (speedFactor / 5);

        // Apply the speed multiplier - higher values = faster animation (shorter duration)
        // The duration is inversely proportional to the speed
        const duration = Math.max(20, baselineDuration / speedMultiplier);

        // For ultra-smooth animation, use requestAnimationFrame instead of CSS animation
        // But first apply basic styles
        this.$tickerStripe.css({
            "will-change": "transform", // Performance optimization
            "backface-visibility": "hidden", // Prevent flickering
            transform: "translate3d(0,0,0)", // Initial position
            "transition-property": "none", // No transitions for smoother animation
        });

        // Set up animation using requestAnimationFrame for smoother movement
        if (this._animationFrameId) {
            cancelAnimationFrame(this._animationFrameId);
        }

        // Store animation properties
        this._animProps = {
            startTime: performance.now(),
            duration: duration * 1000, // Convert to milliseconds
            stripeWidth: stripeWidth,
        };

        // Start the animation
        this._animateFrame();

        // Handle resize events
        this._onWindowResizeHandler = this._onWindowResize.bind(this);
        window.addEventListener("resize", this._onWindowResizeHandler);
    },

    /**
     * Estimates the width of a ticker item with the given text.
     * @private
     * @param {string} text - The text content
     * @returns {number} - Estimated width in pixels
     */
    _estimateItemWidth(text) {
        // Create a temporary element to measure text width
        const $temp = $(
            `<div class="ticker-item" style="position: absolute; visibility: hidden;">${text}</div>`
        );
        $("body").append($temp);
        const width =
            $temp.width() +
            parseInt($temp.css("padding-left")) +
            parseInt($temp.css("padding-right")) +
            30; // Add some buffer for the bullet
        $temp.remove();
        return width;
    },

    /**
     * Cleans up the ticker animation and elements.
     * @private
     */
    _cleanupTicker() {
        // Clean up resize handler
        if (this._onWindowResizeHandler) {
            window.removeEventListener("resize", this._onWindowResizeHandler);
            this._onWindowResizeHandler = null;
        }

        // Cancel any ongoing animation frame or timer
        if (this._animationFrameId) {
            // Clear both setTimeout and requestAnimationFrame since we use both for Firefox
            cancelAnimationFrame(this._animationFrameId);
            clearTimeout(this._animationFrameId);
            this._animationFrameId = null;
        }

        // Reset animation properties
        this._animProps = null;

        // Clear the ticker container
        this.$el.find(".ticker-stripe").empty();
    },

    /**
     * Handles window resize events by recalculating and re-rendering the ticker.
     * @private
     */
    _onWindowResize() {
        this._setupTicker();
    },

    /**
     * Animates a single frame of the ticker animation.
     * @private
     */
    _animateFrame() {
        // Cancel if props aren't set
        if (!this._animProps) return;

        const now = performance.now();
        const elapsed = now - this._animProps.startTime;
        const duration = this._animProps.duration;

        // Calculate position based on elapsed time with higher precision
        let position = (elapsed % duration) / duration;
        position = position * -50; // Move from 0% to -50%

        // Round to 5 decimal places for Firefox optimization
        // This prevents micro-jitter caused by Firefox's rendering engine
        position = Math.round(position * 100000) / 100000;

        // Apply the transform with specific Firefox optimizations
        // Using matrix3d for Firefox which can provide smoother animation in some cases
        const isFirefox = navigator.userAgent.toLowerCase().indexOf("firefox") > -1;

        if (isFirefox) {
            // Create a matrix3d transform that's equivalent to translateX but tends to perform better in Firefox
            // The format is: matrix3d(1, 0, 0, 0, 0, 1, 0, 0, 0, 0, 1, 0, x, 0, 0, 1)
            // Where x is the horizontal translation value
            const translateValue = (position / 100) * this._animProps.stripeWidth;
            this.$tickerStripe.css(
                "transform",
                `matrix3d(1, 0, 0, 0, 0, 1, 0, 0, 0, 0, 1, 0, ${translateValue}, 0, 0, 1)`
            );
        } else {
            // For other browsers, use translate3d which works well
            this.$tickerStripe.css("transform", `translate3d(${position}%, 0, 0)`);
        }

        // Continue animation loop - use setTimeout with 0 delay for Firefox
        // This helps Firefox to schedule frames more consistently
        if (isFirefox) {
            cancelAnimationFrame(this._animationFrameId);
            this._animationFrameId = setTimeout(() => {
                this._animationFrameId = requestAnimationFrame(() =>
                    this._animateFrame()
                );
            }, 0);
        } else {
            this._animationFrameId = requestAnimationFrame(() => this._animateFrame());
        }
    },

    /**
     * Handles changes to the ticker's data attributes.
     * @private
     */
    _onAttributeChanged() {
        this._setupTicker();
    },
});

publicWidget.registry.snippetTickerBlock = TickerBlock;
export default TickerBlock;
