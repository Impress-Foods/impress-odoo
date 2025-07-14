/** @odoo-module **/
import MainComponent from "@stock_barcode/components/main";
import {patch} from "@web/core/utils/patch";

patch(MainComponent.prototype, {
    async labelWizard() {
        await this.env.model.save();
        const action = await this.orm.call(this.resModel, "action_open_label_wizard", [
            [this.resId],
        ]);
        /**
        const onClose = (res) => {
            if (res && res.cancelled) {
                this.env.model._cancelNotification();
                this.env.config.historyBack();
            }
        };
        this.action.doAction(action, {
            onClose: onClose.bind(this),
        });
         */
        this.action.doAction(action);
    },
});
