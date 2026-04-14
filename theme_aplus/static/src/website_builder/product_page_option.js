import {BaseOptionComponent} from "@html_builder/core/utils";
import {Plugin} from "@html_editor/plugin";
import {registry} from "@web/core/registry";
import {_t} from "@web/core/l10n/translation";

export class AplusProductPageOption extends BaseOptionComponent {
    static template = "theme_aplus.AplusProductPageOption";
    static selector = "section:has(#product_detail_main)";
    static applyTo = "#product_detail_main";
    static title = _t("A+ Features");
    static groups = ["website.group_website_designer"];
    static editableOnly = false;
}

export class AplusProductPageOptionPlugin extends Plugin {
    static id = "aplusProductPageOptionPlugin";

    resources = {
        builder_options: [AplusProductPageOption],
    };
}

registry
    .category("website-plugins")
    .add(AplusProductPageOptionPlugin.id, AplusProductPageOptionPlugin);
