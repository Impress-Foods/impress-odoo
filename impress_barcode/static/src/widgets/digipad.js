/** @odoo-module **/
import {patch} from "@web/core/utils/patch";
import {Digipad} from "@stock_barcode/widgets/digipad";

patch(Digipad.prototype, {
    async _increment(interval = 1) {
        this._checkInputValue();

        const current_fraction = this.value.split(".")[1] || "";
        const interval_fraction = String(interval).split(".")[1] || "";
        const fraction =
            current_fraction?.length >= interval_fraction?.length
                ? current_fraction?.length
                : interval_fraction?.length;

        const numberValue = Number(this.value || 0);
        const previousValue = this.value;

        this.value = (numberValue + interval).toFixed(fraction);

        if (this.value < 0 && previousValue > 0) {
            this.value = (0).toFixed(0);
        }
        await this.props.record.update(this.changes);
    },
});
