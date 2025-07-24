/** @odoo-module **/
import {WebsiteSale} from "@website_sale/js/website_sale";
import {patch} from "@web/core/utils/patch";

patch(WebsiteSale.prototype, {
    // start() {
    //     const def = super.start();
    //     document
    //         .querySelector(":root")
    //         .style.setProperty(
    //             "--product-page-highlight-color",
    //             this.el.dataset.highlightColor
    //         );
    //     console.log(this);
    //     return def;
    // },

    willStart() {
        const res = super.willStart(...arguments);
        document
            .querySelector(":root")
            .style.setProperty(
                "--product-page-highlight-color",
                this.el.dataset.highlightColor
            );
        document
            .querySelector(":root")
            .style.setProperty(
                "--product-page-highlight-sec-color",
                this.el.dataset.highlightSecColor
            );
        console.log(this);
        return res;
    },
});
