import {WebsiteSaleStickyObject} from "@website_sale/interactions/sticky_object";
import {patch} from "@web/core/utils/patch";

patch(WebsiteSaleStickyObject, {
    get selector() {
        return ".o_wsale_sticky_object:not(.o_wsale_product_images)";
    },
});
