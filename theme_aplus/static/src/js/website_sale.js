/** @odoo-module **/
import {WebsiteSale} from "@website_sale/js/website_sale";
import {patch} from "@web/core/utils/patch";

patch(WebsiteSale.prototype, {
    willStart() {
        const res = super.willStart(...arguments);
        console.log(this);
        if (this.el.dataset) {
            if (this.el.dataset.highlightColor) {
                document
                    .querySelector(":root")
                    .style.setProperty(
                        "--product-page-highlight-color",
                        this.el.dataset.highlightColor
                    );
            }
            if (this.el.dataset.highlightSecColor) {
                document
                    .querySelector(":root")
                    .style.setProperty(
                        "--product-page-highlight-sec-color",
                        this.el.dataset.highlightSecColor
                    );
            }
        }

        return res;
    },
});
