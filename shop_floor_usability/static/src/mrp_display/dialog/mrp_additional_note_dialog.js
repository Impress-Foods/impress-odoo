import {ConfirmationDialog} from "@web/core/confirmation_dialog/confirmation_dialog";
import {TextField} from "@web/views/fields/text/text_field";

export class AdditionalNoteDialog extends ConfirmationDialog {
    static template = "shop_floor_usability.AdditionalNoteDialog";
    static props = {
        ...ConfirmationDialog.props,
        record: Object,
    };
    static components = {
        ...ConfirmationDialog.components,
        TextField,
    };

    async saveAndClose() {
        await this.props.record.save();
        this.props.close();
    }
}
