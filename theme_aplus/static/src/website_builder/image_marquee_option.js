import {Plugin} from "@html_editor/plugin";
import {registry} from "@web/core/registry";
import {BuilderAction} from "@html_builder/core/builder_action";
import {BaseOptionComponent, useDomState} from "@html_builder/core/utils";
import {withSequence} from "@html_editor/utils/resource";
import {SNIPPET_SPECIFIC} from "@html_builder/utils/option_sequence";
import {loadImageInfo} from "@html_editor/utils/image_processing";

export class ImageMarqueeImagesOption extends BaseOptionComponent {
    static template = "theme_aplus.ImageMarqueeImagesOption";
    static selector = ".s_image_marquee";
    static applyTo = ".marquee";
}

export class ImageMarqueeItemOption extends BaseOptionComponent {
    static template = "theme_aplus.ImageMarqueeItemOption";
    static selector = ".s_image_marquee .marquee-inner img";
    setup() {
        this.state = useDomState((editingElement) => {
            const containerEl = editingElement.closest(".marquee-inner");
            const imageEls = [...containerEl.querySelectorAll(":scope > img")];
            return {
                hasMultiItems: imageEls.length > 1,
                isFirstItem: editingElement === imageEls[0],
                isLastItem: editingElement === imageEls[imageEls.length - 1],
            };
        });
    }
}

export class ImageMarqueeOptionPlugin extends Plugin {
    static id = "imageMarqueeOption";
    static dependencies = ["media", "imagePostProcess", "builderOptions"];
    static shared = ["processImages", "setImages"];

    /** @type {import("plugins").WebsiteResources} */
    resources = {
        builder_options: [
            withSequence(SNIPPET_SPECIFIC, ImageMarqueeImagesOption),
            withSequence(SNIPPET_SPECIFIC, ImageMarqueeItemOption),
        ],
        builder_actions: {
            AddImageAction,
            RemoveAllImagesAction,
            SetMarqueeSpeedAction,
            SetMarqueeImagePositionAction,
        },
        on_snippet_dropped_handlers: ({snippetEl}) => {
            if (snippetEl.matches(".s_image_marquee")) {
                this.cleanupMarquee(snippetEl);
            }
        },
        on_cloned_handlers: ({cloneEl}) => {
            if (cloneEl.matches(".s_image_marquee")) {
                this.cleanupMarquee(cloneEl);
            }
        },
        on_will_remove_handlers: this.onWillRemove.bind(this),
        on_removed_handlers: this.onRemoved.bind(this),
        is_unremovable_selector:
            ".s_image_marquee .marquee-inner img[data-oe-placeholder]",
    };

    cleanupMarquee(snippetEl) {
        const innerEl = snippetEl.querySelector(".marquee-inner");
        if (innerEl) {
            innerEl.querySelectorAll(".marquee-clone").forEach((el) => el.remove());
        }
    }

    createPlaceholder() {
        const placeholder = this.document.createElement("img");
        placeholder.classList.add("marquee-image");
        placeholder.dataset.oePlaceholder = "true";
        placeholder.src = "/web/image/placeholder.png";
        return placeholder;
    }

    onWillRemove(toRemoveEl) {
        if (toRemoveEl.matches(".s_image_marquee .marquee-inner img")) {
            const snippetEl = toRemoveEl.closest(".s_image_marquee");
            const innerEl = snippetEl.querySelector(".marquee-inner");
            const images = this.getImages(innerEl);
            if (images.length <= 1) {
                innerEl.appendChild(this.createPlaceholder());
                this.imageRemovedMarqueeEl = snippetEl;
            }
        }
    }

    onRemoved() {
        if (this.imageRemovedMarqueeEl) {
            this.dependencies.builderOptions.setNextTarget(
                this.imageRemovedMarqueeEl.querySelector(".marquee")
            );
            this.imageRemovedMarqueeEl = undefined;
        }
    }

    getImages(containerEl) {
        return [...containerEl.querySelectorAll(":scope > img")];
    }

    setImages(containerEl, images) {
        const existingEls = containerEl.querySelectorAll(
            ":scope > img, .marquee-clone"
        );
        existingEls.forEach((el) => el.remove());
        if (images.length === 0) {
            containerEl.appendChild(this.createPlaceholder());
        } else {
            for (const image of images) {
                containerEl.appendChild(image);
            }
        }
    }

    async processImages(newImages) {
        await this.transformImagesToWebp(newImages);
        this.setImageProperties(newImages);
    }

    setImageProperties(images) {
        for (const image of images) {
            image.classList.add("marquee-image");
        }
    }

    async transformImagesToWebp(images) {
        const process = async (img) => {
            const newDataset = await loadImageInfo(img);
            const {mimetypeBeforeConversion} = {...img.dataset, ...newDataset};
            if (
                mimetypeBeforeConversion &&
                !["image/gif", "image/svg+xml", "image/webp"].includes(
                    mimetypeBeforeConversion
                )
            ) {
                const update = await this.dependencies.imagePostProcess.processImage({
                    img,
                    newDataset: {
                        formatMimetype: "image/webp",
                        ...newDataset,
                    },
                });
                update();
            }
        };
        return await Promise.all(images.map(process));
    }
}

export class AddImageAction extends BuilderAction {
    static id = "addMarqueeImage";
    static dependencies = ["media", "imageMarqueeOption"];

    async load({_editingElement}) {
        let selectedImages;
        await new Promise((resolve) => {
            const onClose = this.dependencies.media.openMediaDialog({
                onlyImages: true,
                multiImages: true,
                save: (images) => {
                    selectedImages = images;
                    resolve();
                },
            });
            onClose.then(resolve);
        });
        if (!selectedImages || !selectedImages.length) {
            return;
        }
        await this.dependencies.imageMarqueeOption.processImages(selectedImages);
        return selectedImages;
    }

    apply({editingElement, loadResult: selectedImages}) {
        if (!selectedImages || !selectedImages.length) {
            return;
        }
        const containerEl = editingElement.querySelector(".marquee-inner");
        if (!containerEl) {
            return;
        }
        const currentImages = [...containerEl.querySelectorAll(":scope > img")];
        this.dependencies.imageMarqueeOption.setImages(containerEl, [
            ...currentImages,
            ...selectedImages,
        ]);
    }
}

export class RemoveAllImagesAction extends BuilderAction {
    static id = "removeAllMarqueeImages";
    static dependencies = ["imageMarqueeOption"];

    apply({editingElement}) {
        let containerEl = editingElement.querySelector(".marquee-inner");
        if (!containerEl) {
            containerEl = this.document.createElement("div");
            containerEl.classList.add("marquee-inner");
            const marqueeEl = editingElement.querySelector(".marquee");
            if (marqueeEl) {
                marqueeEl.appendChild(containerEl);
            }
        }
        this.dependencies.imageMarqueeOption.setImages(containerEl, []);
    }
}

export class SetMarqueeSpeedAction extends BuilderAction {
    static id = "setMarqueeSpeed";

    getValue({editingElement}) {
        return editingElement.dataset.speed || "10";
    }

    apply({editingElement, value}) {
        editingElement.dataset.speed = value;
        editingElement.style.setProperty("--marquee-duration", `${value}s`);
    }
}

export class SetMarqueeImagePositionAction extends BuilderAction {
    static id = "setMarqueeImagePosition";
    static dependencies = ["imageMarqueeOption"];

    apply({editingElement: activeItemEl, value: position}) {
        const containerEl = activeItemEl.closest(".marquee-inner");
        const itemEls = [...containerEl.querySelectorAll(":scope > img")];

        const oldPosition = itemEls.indexOf(activeItemEl);
        if (oldPosition === -1) {
            return;
        }

        if (oldPosition === 0 && position === "prev") {
            position = "last";
        } else if (oldPosition === itemEls.length - 1 && position === "next") {
            position = "first";
        }

        itemEls.splice(oldPosition, 1);
        switch (position) {
            case "first":
                itemEls.unshift(activeItemEl);
                break;
            case "prev":
                itemEls.splice(Math.max(oldPosition - 1, 0), 0, activeItemEl);
                break;
            case "next":
                itemEls.splice(oldPosition + 1, 0, activeItemEl);
                break;
            case "last":
                itemEls.push(activeItemEl);
                break;
        }

        this.dependencies.imageMarqueeOption.setImages(containerEl, itemEls);
    }
}

registry
    .category("website-plugins")
    .add(ImageMarqueeOptionPlugin.id, ImageMarqueeOptionPlugin);
