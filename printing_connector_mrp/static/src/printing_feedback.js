import {ConfirmationDialog} from "@web/core/confirmation_dialog/confirmation_dialog";
import {printingFeedbackRegistry} from "@printing_connector/printing_feedback";

export class PrintOutcomeDialog extends ConfirmationDialog {
    static template = "printing_connector_mrp.PrintOutcomeDialog";
    static defaultProps = {
        ...ConfirmationDialog.defaultProps,
        title: "Printing",
        body: "",
        type: "info",
    };
    static props = {
        ...ConfirmationDialog.props,
        body: {type: String, optional: true},
        type: {type: String, optional: true},
    };
}

function asMessage(result) {
    if (typeof result?.message === "string") {
        return result.message;
    }
    if (result?.message) {
        return JSON.stringify(result.message);
    }
    return "";
}

export function showTabletPrintingFeedback(env, result, _action) {
    const type = result?.success ? "success" : "danger";
    const title = result?.success ? "Label printed" : "Printing failed";
    const body = result?.success
        ? "The label was sent to the printer."
        : asMessage(result) || "Label could not be sent to the printer.";
    env.services.dialog.add(PrintOutcomeDialog, {
        title,
        body,
        type,
    });
}

printingFeedbackRegistry.add("shopfloor", showTabletPrintingFeedback);
