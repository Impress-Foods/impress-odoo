import {registry} from "@web/core/registry";
import {printingFeedbackRegistry} from "./printing_feedback";

async function openPrintWizard(env, reportId, activeIds) {
    const action = await env.services.orm.call("print.wizard", "open_wizard", [
        reportId,
        activeIds,
    ]);
    const wizardId = action.res_id;
    return new Promise((resolve) => {
        env.services.action
            .doAction(action, {
                onClose: async () => {
                    const [wizard] = await env.services.orm.read(
                        "print.wizard",
                        [wizardId],
                        [
                            "result_ready",
                            "result_printer_id",
                            "result_printer_name",
                            "result_qty",
                        ]
                    );
                    resolve(wizard?.result_ready ? wizard : null);
                },
            })
            .catch(() => resolve(null));
    });
}

async function printAndNotify(env, action, activeIds, data) {
    const result = await env.services.orm.call("ir.actions.report", "print_api", [
        action.id,
        activeIds,
        data,
    ]);
    const key = action.context?.from_shopfloor ? "shopfloor" : "default";
    printingFeedbackRegistry.get(key)(env, result, action);
    return result;
}

async function apiReportActionHandler(action, options, env) {
    if (action.report_type !== "api") {
        return false;
    }

    const activeIds = action.context?.active_ids || [];
    const data = {...action.data};

    const selectionProvided =
        action.context?.printing_printer_override ||
        action.context?.printing_printing_quantity;
    if (selectionProvided) {
        return printAndNotify(env, action, activeIds, data);
    }

    const selection = await openPrintWizard(env, action.id, activeIds);
    if (!selection) {
        return true;
    }

    data._printer = selection.result_printer_name;
    data._qty = selection.result_qty;
    return printAndNotify(env, action, activeIds, data);
}

registry
    .category("ir.actions.report handlers")
    .add("api_report_action_handler", apiReportActionHandler);
