// /** @odoo-module **/

// import publicWidget from "@web/legacy/js/public/public_widget";

// const ImageMarqueeWidget = publicWidget.Widget.extend({
//     selector: ".s_image_marquee",

//     /**
//      * @override
//      */
//     start() {
//         this._super.apply(this, arguments);
//         this.editorActive = $("body").hasClass("editor_enable");
//         this.$inner = this.$target.find(".marquee-inner").first();
//         this.$holder = this.$target.find(".marquee").first();
//         this.animationDuration = this.$holder[0].dataset.speed;
//         this.$holder[0].style.setProperty(
//             "--marquee-duration",
//             `${this.animationDuration}s`
//         );
//         if (this.$inner && this.$holder && !this.editorActive) {
//             this.setupMarquee();
//             this._attachResizeListener();
//         }
//     },

//     setupMarquee: function () {
//         this._clearClones();
//         this._cloneContent();
//     },

//     _cloneContent: function () {
//         this.$inner.find(".marquee-clone").remove();
//         const $contentToClone = this.$inner.children().not(".marquee-clone");

//         if ($contentToClone.length === 0) {
//             return;
//         }
//         const $clonedContent = $contentToClone.clone(true);
//         $clonedContent.addClass("marquee-clone");
//         this.$inner.append($clonedContent);
//         this.$holder.scrollLeft(0);
//     },
//     /**
//      * Clears all existing cloned elements before recalculating and cloning again.
//      */
//     _clearClones() {
//         this.$holder.find(".marquee-clone").remove();
//     },

//     _attachResizeListener() {
//         let resizeTimer;

//         const handleResize = () => {
//             const editorActive = $("body").hasClass("editor_enable");
//             if (!editorActive) {
//                 this.setupMarquee();
//             }
//         };

//         $(window).on("resize.ImageMarqueeWidget", () => {
//             clearTimeout(resizeTimer);
//             resizeTimer = setTimeout(handleResize, 150);
//         });
//     },
// });

// publicWidget.registry.marquee = ImageMarqueeWidget;

// export default {ImageMarqueeWidget: ImageMarqueeWidget};
