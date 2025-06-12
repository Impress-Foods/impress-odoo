/** @odoo-module **/

import {patch} from "@web/core/utils/patch";
import {DocumentsControlPanel} from "@documents/views/search/documents_control_panel";
import {toggleSoftArchive} from "./hook";

patch(DocumentsControlPanel.prototype, {
    async onSoftArchive() {
        const records = this.targetRecords.filter((r) => r.data.active);
        const recordIds = records.map((r) => r.data.id);
        await toggleSoftArchive(records[0].model, records[0].resModel, recordIds, true);
        await this.notifyChange();
    },

    async onSoftUnarchive() {
        const records = this.targetRecords.filter((r) => r.data.active);
        const recordIds = records.map((r) => r.data.id);
        await toggleSoftArchive(
            records[0].model,
            records[0].resModel,
            recordIds,
            false
        );
        await this.notifyChange();
    },
});
