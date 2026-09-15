import {registry} from "@web/core/registry";

export const printingFeedbackRegistry = registry.category("printing label feedback");

const DEFAULT_TRANSLATIONS = {
    printing_success: "Label sent to the printer",
    printing_error: "Label could not be sent to the printer",
};

export function showPrintingFeedback(env, result, _action) {
    const {success, message} = result || {};
    if (success) {
        env.services.notification.add(DEFAULT_TRANSLATIONS.printing_success, {
            type: "success",
        });
    } else {
        const msg = message || DEFAULT_TRANSLATIONS.printing_error;
        env.services.notification.add(
            `${DEFAULT_TRANSLATIONS.printing_error}: ${msg}`,
            {
                type: "danger",
            }
        );
    }
}

printingFeedbackRegistry.add("default", showPrintingFeedback);
