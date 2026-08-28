import {registry} from "@web/core/registry";

export const printingFeedbackRegistry = registry.category("printing label feedback");

const DEFAULT_TRANSLATIONS = {
    printing_success: "Label sent to the printer",
    printing_error: "Label could not be sent to the printer",
};

export function showPrintingFeedback(env, result, translations = DEFAULT_TRANSLATIONS) {
    const {success, message} = result || {};
    if (success) {
        env.services.notification.add(translations.printing_success, {
            type: "success",
        });
    } else {
        const msg = message || translations.printing_error;
        env.services.notification.add(`${translations.printing_error}: ${msg}`, {
            type: "danger",
        });
    }
}

printingFeedbackRegistry.add("default", showPrintingFeedback);
