/** @odoo-module **/
import {patch} from "@web/core/utils/patch";
import {DocumentsListModel} from "@documents/views/list/documents_list_model";

patch(DocumentsListModel.prototype, {
    async onSoftArchive() {
        const records = this.targetRecords.filter((r) => !r.data.lock_uid);
        const recordIds = this.isDomainSelected
            ? await this.getResIds([["lock_uid", "=", false]])
            : records.map((rec) => rec.data.id);
        await this.documentService.archive(recordIds);
        await this._notifyChange();
    },
    async onSoftUnarchive() {
        const records = this.targetRecords.filter((r) => !r.data.lock_uid);
        const recordIds = this.isDomainSelected
            ? await this.getResIds([["lock_uid", "=", false]])
            : records.map((rec) => rec.data.id);
        await this.documentService.unarchive(recordIds);
        await this._notifyChange();
    },
});
