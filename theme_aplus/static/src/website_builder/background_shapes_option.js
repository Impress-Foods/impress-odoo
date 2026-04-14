import {Plugin} from "@html_editor/plugin";
import {_t} from "@web/core/l10n/translation";
import {registry} from "@web/core/registry";

export class AplusBackgroundShapesOptionPlugin extends Plugin {
    static id = "aplusBackgroundShapesOption";
    resources = {
        background_shape_groups_providers: () => ({
            aplus: {
                label: _t("A+"),
                subgroups: {
                    aplus: {
                        label: _t("A+"),
                        shapes: {
                            "theme_aplus/aplus/01": {
                                selectLabel: _t("Wave 1"),
                                animated: true,
                            },
                            "theme_aplus/aplus/02": {
                                selectLabel: _t("Wave 2"),
                                animated: true,
                            },
                            "theme_aplus/aplus/03": {
                                selectLabel: _t("Wave 3"),
                                animated: true,
                            },
                        },
                    },
                },
            },
        }),
    };
}

registry
    .category("website-plugins")
    .add(AplusBackgroundShapesOptionPlugin.id, AplusBackgroundShapesOptionPlugin);
