import {Interaction} from "@web/public/interaction";
import {registry} from "@web/core/registry";
import {rpc} from "@web/core/network/rpc";

export class WindowCarousel extends Interaction {
    static selector = ".s_window_carousel";

    dynamicContent = {
        ".carousel": {
            "t-on-slide.bs.carousel": this.onSlide,
        },
    };

    setup() {
        this.products = [];
    }

    async willStart() {
        const params = {
            limit: parseInt(this.el.dataset.numberOfRecords) || 16,
        };
        const tagIds = this.el.dataset.productTagIds;
        if (tagIds) {
            params.tag_ids = tagIds;
        }
        this.products = await rpc("/window_carousel/products", params);
    }

    start() {
        if (!this.products.length) {
            return;
        }
        const target = this.el.querySelector(".dynamic_snippet_template");
        if (!target) {
            return;
        }
        this.renderAt(
            "theme_aplus.window_carousel",
            {
                products: this.products,
                interval: parseInt(this.el.dataset.bsInterval) || 5000,
            },
            target
        );
        this.updateContent();
        this._updateHero();
    }

    onSlide(ev) {
        const items = this.el.querySelectorAll(".carousel-item");
        const targetItem = items[ev.to];
        if (!targetItem) {
            return;
        }
        this._updateHeroFromItem(targetItem);
    }

    _updateHero() {
        const activeItem = this.el.querySelector(".carousel-item.active");
        if (activeItem) {
            this._updateHeroFromItem(activeItem);
        }
    }

    _updateHeroFromItem(itemEl) {
        const bgColor = itemEl.dataset.bgColor || "#f7f9fc";
        const textColor = itemEl.dataset.textColor || "#000000";
        const productUrl = itemEl.dataset.productUrl || "/shop";
        const stickerUrl = itemEl.dataset.stickerUrl || "";

        const bgEl = this.el.closest(".hero-background") || this.el;
        bgEl.style.setProperty("background-color", bgColor);

        for (const textEl of this.el.querySelectorAll(".hero-text")) {
            textEl.style.setProperty("color", textColor);
        }

        const stickerEl = this.el.querySelector(".hero-sticker");
        if (stickerEl && stickerUrl) {
            stickerEl.src = stickerUrl;
            stickerEl.style.removeProperty("opacity");
        } else if (stickerEl) {
            stickerEl.style.setProperty("opacity", "0");
        }

        const shopBtn = this.el.querySelector(".shop-now-button");
        if (shopBtn) {
            shopBtn.href = productUrl;
            shopBtn.dataset.url = productUrl;
            shopBtn.style.setProperty("background-color", textColor);
            shopBtn.style.setProperty("border-color", textColor);
            shopBtn.style.setProperty("color", bgColor);
        }
    }
}

registry
    .category("public.interactions")
    .add("theme_aplus.window_carousel", WindowCarousel);
