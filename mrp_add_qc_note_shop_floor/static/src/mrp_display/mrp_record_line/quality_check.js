/** @odoo-module **/
import {patch} from "@web/core/utils/patch";
import {QualityCheck} from "@mrp_workorder/mrp_display/mrp_record_line/quality_check";
import {AdditionalNoteDialog} from "../dialog/mrp_additional_note_dialog";

patch(QualityCheck.prototype, {
    async _onClickAdditionalNote() {
        const {dialog} = this;
        const props = {
            title: "Additional Note",
            record: this.props.record,
        };
        await dialog.add(AdditionalNoteDialog, props);
    },
});
