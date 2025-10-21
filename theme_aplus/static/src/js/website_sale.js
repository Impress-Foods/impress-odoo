/** @odoo-module **/
import WebsiteSale from "@website_sale/js/website_sale";
import {patch} from "@web/core/utils/patch";
import {SIZES, utils as uiUtils} from "@web/core/ui/ui_service";

const WebsiteSaleCarouselProduct = WebsiteSale.WebsiteSaleCarouselProduct;

patch(WebsiteSaleCarouselProduct.prototype, {
    /**
     * @private
     */
    _updateJustifyContent: function () {
        const $indicatorsDiv = this.$el.find(".carousel-indicators");
        $indicatorsDiv.css("justify-content", "center");
        if (uiUtils.getSize() <= SIZES.MD) {
            if (
                $indicatorsDiv.children().last().position().left +
                    this.$el.find("li").outerWidth() <
                $indicatorsDiv.outerWidth()
            ) {
                $indicatorsDiv.css("justify-content", "center");
            }
        }
    },
});
