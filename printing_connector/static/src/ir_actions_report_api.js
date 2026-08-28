import {registry} from "@web/core/registry";
import {printingFeedbackRegistry} from "./printing_feedback";

async function apiReportActionHandler(action, options, env) {
    if (action.report_type !== "api") {
        return false;
    }
    const result = await env.services.orm.call("ir.actions.report", "print_api", [
        action.id,
        action.context.active_ids,
        action.data,
    ]);
    options.onClose?.();

    const key = action.context?.from_shopfloor ? "shopfloor" : "default";
    const handler =
        printingFeedbackRegistry.get(action.report_name, null) ??
        printingFeedbackRegistry.get(key);
    handler(env, result, action);

    return result;
}

registry
    .category("ir.actions.report handlers")
    .add("api_report_action_handler", apiReportActionHandler);
