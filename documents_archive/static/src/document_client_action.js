/** @odoo-module */
import {browser} from "@web/core/browser/browser";
import {registry} from "@web/core/registry";

/**
 * This module overrides the buggy documentActionPreference client action from
 * the documents module. The bug causes the action's context (including
 * search_default_* keys) to be lost when loading the documents action.
 *
 * Bug: The original code overwrites the loaded action's context with
 * action.context (which is empty), losing all search defaults.
 */
async function documentActionPreference(env, action, options) {
    const viewType = browser.localStorage.getItem("documentsDefaultViewType");

    const nextAction = await env.services.action.loadAction(
        "documents.document_action"
    );

    return env.services.action.doAction(
        {
            ...nextAction,
            domain: action.domain,
        },
        {...options, viewType}
    );
}

// Remove the buggy entry first, then add our fixed version
registry.category("actions").remove("document_action_preference");
registry
    .category("actions")
    .add("document_action_preference", documentActionPreference);
