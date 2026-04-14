import {registry} from "@web/core/registry";
import {Interaction} from "@web/public/interaction";

export class ImageMarquee extends Interaction {
    static selector = ".s_image_marquee";

    dynamicContent = {
        ".marquee-inner": {
            "t-att-style": () => ({
                "--marquee-duration": `${this.animationDuration}s`,
            }),
        },
        _window: {
            "t-on-resize": this.debounced(this.onResize, 150, {
                leading: false,
                trailing: true,
            }),
        },
    };

    setup() {
        this.innerEl = this.el.querySelector(".marquee-inner");
        this.holderEl = this.el.querySelector(".marquee");
        this.animationDuration = parseFloat(this.holderEl?.dataset.speed) || 10;
        this.editorActive = document.body.classList.contains("editor_enable");
    }

    start() {
        if (!this.editorActive && this.innerEl && this.holderEl) {
            this.setupMarquee();
        }
    }

    destroy() {
        this.clearClones();
    }

    onResize() {
        if (!document.body.classList.contains("editor_enable")) {
            this.setupMarquee();
        }
    }

    setupMarquee() {
        this.clearClones();
        this.cloneContent();
    }

    cloneContent() {
        const children = [...this.innerEl.children].filter(
            (el) => !el.classList.contains("marquee-clone") && !el.dataset.oePlaceholder
        );
        if (children.length === 0) {
            return;
        }
        const clonedContent = children.map((el) => {
            const clone = el.cloneNode(true);
            clone.classList.add("marquee-clone");
            return clone;
        });
        this.innerEl.append(...clonedContent);
        this.holderEl.scrollLeft = 0;
    }

    clearClones() {
        if (this.innerEl) {
            this.innerEl
                .querySelectorAll(".marquee-clone")
                .forEach((el) => el.remove());
        }
    }
}

registry.category("public.interactions").add("theme_aplus.image_marquee", ImageMarquee);
