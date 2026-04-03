/** @odoo-module **/

import {WebsiteSale} from "@website_sale/interactions/website_sale";
import {patch} from "@web/core/utils/patch";

patch(WebsiteSale.prototype, {
    _onChangeCombination(ev, parent, combination) {
        super._onChangeCombination(ev, parent, combination);
        if (combination.tvn) {
            document
                .querySelector(".tvn-holder")
                ?.replaceChildren(
                    document.createRange().createContextualFragment(combination.tvn)
                );
        } else {
            document.querySelector(".tvn-holder")?.replaceChildren();
        }
    },
});
