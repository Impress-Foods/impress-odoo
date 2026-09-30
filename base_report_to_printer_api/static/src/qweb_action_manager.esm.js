/** @odoo-module **/

import {_t} from "@web/core/l10n/translation";
import {registry} from "@web/core/registry";

async function apiReportActionHandler(action, options, env) {
    if (action.report_type !== "api") {
        return false;
    }
    if (!action.report_name || !action.id) {
        return false;
    }

    const orm = env.services.orm;
    const notification = env.services.notification;
    const context = {
        ...env.context,
        ...options?.additionalContext,
        ...action.context,
    };

    const printAction = await orm.call(
        "ir.actions.report",
        "print_action_for_report_name",
        [action.report_name],
        {context}
    );

    if (
        !printAction ||
        printAction.action !== "server" ||
        printAction.backend !== "api"
    ) {
        notification.add(
            _t("Configure this API report to use an API printer and server printing."),
            {type: "warning"}
        );
        return true;
    }

    const result = await orm.call(
        "ir.actions.report",
        "print_document_client_action",
        [action.id, action.context?.active_ids || [], action.data || {}],
        {context}
    );

    if (result) {
        notification.add(_t("Print data sent to the API printer."), {
            type: "success",
        });
    } else {
        notification.add(_t("Could not send the print data to the API printer."), {
            type: "danger",
        });
    }
    return true;
}

registry
    .category("ir.actions.report handlers")
    .add("api_report_action_handler", apiReportActionHandler, {sequence: 0});
