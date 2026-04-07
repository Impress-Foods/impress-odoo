/** @odoo-module **/
import {patch} from "@web/core/utils/patch";
import {MrpQualityCheckConfirmationDialog} from "@mrp_workorder/mrp_display/dialog/mrp_quality_check_confirmation_dialog";
import {TextField} from "@web/views/fields/text/text_field";

patch(MrpQualityCheckConfirmationDialog, {
    components: {
        ...MrpQualityCheckConfirmationDialog.components,
        TextField,
    },
});

patch(MrpQualityCheckConfirmationDialog.prototype, {
    async saveAndClose() {
        await this.props.record.save();
        this.props.close();
    },
});
