import {BaseOptionComponent} from "@html_builder/core/utils";
import {SNIPPET_SPECIFIC} from "@html_builder/utils/option_sequence";
import {Plugin} from "@html_editor/plugin";
import {withSequence} from "@html_editor/utils/resource";
import {registry} from "@web/core/registry";

export class WindowCarouselOption extends BaseOptionComponent {
    static template = "theme_aplus.WindowCarouselOption";
    static selector = ".s_window_carousel";
}

class WindowCarouselOptionPlugin extends Plugin {
    static id = "windowCarouselOption";
    resources = {
        builder_options: [withSequence(SNIPPET_SPECIFIC, WindowCarouselOption)],
    };
}

registry
    .category("website-plugins")
    .add(WindowCarouselOptionPlugin.id, WindowCarouselOptionPlugin);
