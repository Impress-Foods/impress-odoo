/** @odoo-module **/

import {BaseOptionComponent} from "@html_builder/core/utils";
import {Plugin} from "@html_editor/plugin";
import {registry} from "@web/core/registry";

export class AplusWaveTransitionOption extends BaseOptionComponent {
    static template = "theme_aplus.WaveTransitionSnippetOption";
    static selector = ".wave-transition-container";
    static applyTo = ".wave-transition";
}

export class AplusWaveTransitionOptionPlugin extends Plugin {
    static id = "aplusWaveTransitionSnippetOption";
    resources = {
        builder_options: [AplusWaveTransitionOption],
    };
}

registry
    .category("website-plugins")
    .add(AplusWaveTransitionOptionPlugin.id, AplusWaveTransitionOptionPlugin);
