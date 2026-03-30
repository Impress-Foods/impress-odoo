/** @odoo-module **/
import {patch} from "@web/core/utils/patch";
import {DocumentsKanbanModel} from "@documents/views/kanban/documents_kanban_model";

patch(DocumentsKanbanModel.prototype, {
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
