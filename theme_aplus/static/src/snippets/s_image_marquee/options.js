// /** @odoo-module **/

// import {MediaDialog} from "@web_editor/components/media_dialog/media_dialog";
// import options from "@web_editor/js/editor/snippets.options";
// import {
//     loadImageInfo,
//     applyModifications,
// } from "@web_editor/js/editor/image_processing";
// import {_t} from "@web/core/l10n/translation";

// options.registry.marquee = options.registry.GalleryHandler.extend({
//     /**
//      * @override
//      */
//     start() {
//         const _super = this._super.bind(this);
//         this.$target.find(".marquee-clone").remove();
//         return _super.apply(this, arguments);
//     },
//     /**
//      * Empties the container, adds the given content and returns the container.
//      *
//      * @private
//      * @param {jQuery} $content
//      * @returns {jQuery} the main container of the snippet
//      */
//     _replaceContent: function ($content) {
//         const $container = this.$(".marquee-inner");
//         $container.empty().append($content);
//         return $container;
//     },
// });

// options.registry.MarqueeImageList = options.registry.marquee.extend({
//     /**
//      * @override
//      */
//     init: function () {
//         this.rpc = this.bindService("rpc");
//         return this._super.apply(this, arguments);
//     },

//     /**
//      * @override
//      */
//     _getItemsGallery() {
//         const imgs = this.$("img").get();
//         imgs.sort((a, b) => this._getIndex(a) - this._getIndex(b));
//         return imgs;
//     },

//     /**
//      * Returns the index associated to a given image.
//      *
//      * @private
//      * @param {DOMElement} img
//      * @returns {integer}
//      */
//     _getIndex: function (img) {
//         return img.dataset.index || 0;
//     },

//     /**
//      * Allows to select images to add as part of the snippet.
//      *
//      * @see this.selectClass for parameters
//      */
//     addImages: function (previewMode) {
//         const $images = this.$("img");
//         const $container = this.$(".marquee-inner");
//         const lastImage = this._getItemsGallery().at(-1);
//         let index = lastImage ? this._getIndex(lastImage) : -1;
//         return new Promise((resolve) => {
//             let savedPromise = Promise.resolve();
//             const props = {
//                 multiImages: true,
//                 onlyImages: true,
//                 save: (images) => {
//                     const imagePromises = [];
//                     for (const image of images) {
//                         const $img = $("<img/>", {
//                             class:
//                                 $images.length > 0
//                                     ? $images[0].className
//                                     : "img img-fluid d-block ",
//                             src: image.src,
//                             "data-index": ++index,
//                             alt: image.alt || "",
//                             "data-name": _t("Image"),
//                             style: $images.length > 0 ? $images[0].style.cssText : "",
//                         }).appendTo($container);
//                         const imgEl = $img[0];
//                         imagePromises.push(
//                             new Promise((resolve) => {
//                                 loadImageInfo(imgEl, this.rpc).then(() => {
//                                     if (
//                                         imgEl.dataset.mimetype &&
//                                         ![
//                                             "image/gif",
//                                             "image/svg+xml",
//                                             "image/webp",
//                                         ].includes(imgEl.dataset.mimetype)
//                                     ) {
//                                         // Convert to webp but keep original width.
//                                         imgEl.dataset.mimetype = "image/webp";
//                                         applyModifications(imgEl, {
//                                             mimetype: "image/webp",
//                                         }).then((src) => {
//                                             imgEl.src = src;
//                                             imgEl.classList.add(
//                                                 "o_modified_image_to_save"
//                                             );
//                                             resolve();
//                                         });
//                                     } else {
//                                         resolve();
//                                     }
//                                 });
//                             })
//                         );
//                     }
//                     savedPromise = Promise.all(imagePromises);
//                 },
//             };
//             this.call("dialog", "add", MediaDialog, props, {
//                 onClose: () => {
//                     savedPromise.then(resolve);
//                 },
//             });
//         });
//     },
//     /**
//      * Allows to remove all images. Restores the snippet to the way it was when
//      * it was added in the page.
//      *
//      * @see this.selectClass for parameters
//      */
//     removeAllImages(previewMode) {
//         const $addImg = $("<div>", {
//             class: "alert alert-info css_non_editable_mode_hidden text-center",
//         });
//         const $text = $("<span>", {
//             class: "o_add_images",
//             style: "cursor: pointer;",
//             text: _t(" Add Images"),
//         });
//         const $icon = $("<i>", {
//             class: " fa fa-plus-circle",
//         });
//         this._replaceContent($addImg.append($icon).append($text));
//     },

//     _relayout: async function () {
//         const content = this._getItemsGallery();
//         this._replaceContent(content);
//         this.trigger_up("cover_update");
//         await this._refreshPublicWidgets();
//     },

//     /**
//      * @override
//      */
//     _reorderItems(itemsEls, newItemPosition) {
//         console.log("Reordering!");
//         itemsEls.forEach((img, index) => {
//             img.dataset.index = index;
//         });
//         this.trigger_up("snippet_edition_request", {
//             exec: async () => {
//                 await this._relayout();

//                 const imageEl = this.$target[0].querySelector(
//                     `[data-index='${newItemPosition}']`
//                 );
//                 this.trigger_up("activate_snippet", {
//                     $snippet: $(imageEl),
//                     ifInactiveOptions: true,
//                 });
//             },
//         });
//     },
// });

// options.registry.MarqueeImage = options.registry.GalleryElement.extend({
//     /**
//      * Rebuilds the whole gallery when one image is removed.
//      *
//      * @override
//      */
//     onRemove: function () {
//         this.trigger_up("option_update", {
//             optionName: "MarqueeImageList",
//             name: "image_removed",
//             data: {
//                 $image: this.$target,
//             },
//         });
//     },

//     position: function (previewMode, widgetValue, params) {
//         const itemEl = this.$target[0];
//         const optionName = "MarqueeImageList";
//         this.trigger_up("option_update", {
//             optionName: optionName,
//             name: "reorder_items",
//             data: {
//                 itemEl: itemEl,
//                 position: widgetValue,
//             },
//         });
//     },
// });
