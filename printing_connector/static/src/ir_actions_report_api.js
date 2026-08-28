import {registry} from "@web/core/registry";

async function apiReportActionHandler(action, options, env) {
    if (action.report_type !== "api") {
        return false;
    }
    const orm = env.services.orm;
    await orm.call("ir.actions.report", "print_api", [
        action.id,
        action.context.active_ids,
        action.data,
    ]);
    options.onClose?.();
    return true;
}

registry
    .category("ir.actions.report handlers")
    .add("api_report_action_handler", apiReportActionHandler);
