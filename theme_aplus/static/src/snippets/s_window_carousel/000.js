/** @odoo-module **/

//import publicWidget from "@web/legacy/js/public/public_widget";
// import DynamicSnippetProductTemplates from "@theme_aplus/snippets/s_dynamic_snippet_product_templates/000";

// const WindowCarousel = DynamicSnippetProductTemplates.extend({
//     selector: ".s_window_carousel",

//     /**
//      * @override
//      */
//     init() {
//         this._super.apply(this, arguments);
//         this.template_key = "theme_aplus.window_carousel";
//         this.current_index = 0;
//         this.next_index = 1;
//         this.bg = document.getElementsByClassName("hero-background")[0];
//         this.sticker = document.getElementsByClassName("hero-sticker")[0];
//         this.buttonHover = false;
//     },

//     /**
//      * Gets the tag search domain
//      * @override
//      * @private
//      */
//     _getTagSearchDomain() {
//         const searchDomain = [];
//         let productTagIds = this.$el.get(0).dataset.productTagIds;
//         productTagIds = productTagIds ? JSON.parse(productTagIds) : [];
//         if (productTagIds.length) {
//             searchDomain.push([
//                 "product_tag_ids",
//                 "in",
//                 productTagIds.map((productTag) => productTag.id),
//             ]);
//         }
//         return searchDomain;
//     },
//     /**
//      * @override
//      * @private
//      */
//     async _fetchData() {
//         if (this._isConfigComplete()) {
//             const nodeData = this.el.dataset;
//             const filter_id = parseInt(nodeData.filterId);
//             const response = await this.rpc(
//                 "/theme_aplus/get_products",
//                 Object.assign({
//                     filter_id: filter_id,
//                     search_domain: this._getSearchDomain(),
//                 }),
//                 this._getRpcParameters()
//             );

//             this.data = response;
//             if (this.wave) {
//                 this.preloadImages();
//             }
//         } else {
//             this.data = [];
//         }
//     },

//     _onSlide(event) {
//         this.current_index = event.to;
//         this.next_index = (this.current_index + 1) % Object.keys(this.data).length;
//         this.changeColors(this.data[this.current_index]);
//     },

//     changeColors(product, first = false) {
//         if (this.buttonHover) {
//             this.setHoverShopButton(this.shop_button, product);
//         } else {
//             this.setNormalShopButton(this.shop_button, product);
//         }

//         Array.from(this.hero_texts).forEach((element) => {
//             element.style.setProperty("color", product.hero_text_color);
//         });
//         this.bg.style.setProperty("background-color", product.hero_background_color);
//         if (!first) {
//             this.sticker.style.setProperty("opacity", 0);
//         }
//         setTimeout(this.swapImage.bind(this), 250);
//     },

//     swapImage: function () {
//         this.sticker.src = this.data[this.current_index].hero_sticker;
//         this.sticker.style.setProperty("opacity", 1);
//     },

//     setNormalShopButton: function (element, product) {
//         element.style.setProperty("background-color", product.hero_text_color);
//         element.style.setProperty("border-color", product.hero_text_color);
//         element.style.setProperty("color", product.hero_background_color);
//     },
//     setHoverShopButton: function (element, product) {
//         element.style.setProperty("background-color", product.hero_background_color);
//         element.style.setProperty("border-color", product.hero_text_color);
//         element.style.setProperty("color", product.hero_text_color);
//     },

//     shopButtonMouseOver: function (event) {
//         this.buttonHover = true;
//         const product = this.data[this.current_index];
//         const button = event.target;
//         this.setHoverShopButton(button, product);
//     },
//     shopButtonMouseOut: function (event) {
//         const product = this.data[this.current_index];
//         const button = event.target;
//         this.setNormalShopButton(button, product);
//         this.buttonHover = false;
//     },
//     /**
//      * @override
//      * @private
//      */
//     _render() {
//         this._super.apply(this, arguments);
//         this.$el.removeClass("o_dynamic_empty");
//         this._prepareContent();
//         this._renderContent();
//         this.trigger_up("widgets_start_request", {
//             $target: this.$el.children("dynamic_snippet_template"),
//             options: {parent: this},
//             editableMode: this.editableMode,
//         });
//         this.carousel_element = document.getElementsByClassName("aplus_carousel")[0];
//         this.carousel_element.addEventListener(
//             "slide.bs.carousel",
//             this._onSlide.bind(this)
//         );
//         this.hero_texts = this.el.querySelectorAll(".hero-text");
//         this.shop_button = document.getElementsByClassName("shop-now-button")[0];
//         this.shop_button.addEventListener(
//             "mouseover",
//             this.shopButtonMouseOver.bind(this)
//         );
//         this.shop_button.addEventListener(
//             "mouseleave",
//             this.shopButtonMouseOut.bind(this)
//         );
//         this.sticker.style.setProperty("background-color", "#ffffff00");
//         this.sticker.src = this.data[0].hero_sticker;
//         this.changeColors(this.data[0], true);
//     },
// });

// publicWidget.registry.s_window_carousel = WindowCarousel;
// export default WindowCarousel;
