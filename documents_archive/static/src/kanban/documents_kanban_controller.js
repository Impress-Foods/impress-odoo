/** @odoo-module **/
import {_t} from "@web/core/l10n/translation";
import {patch} from "@web/core/utils/patch";
import {DocumentsKanbanController} from "@documents/views/kanban/documents_kanban_controller";

patch(DocumentsKanbanController.prototype, {
    getStaticActionMenuItems() {
        const canArchive = this.targetRecords.some((r) => !r.data.archived);
        const canUnarchive = this.targetRecords.some((r) => r.data.archived);
        const actionItems = {
            ...super.getStaticActionMenuItems(),
            archive: {
                isAvailable: () => canArchive,
                sequence: 52,
                description: _t("Archive"),
                icon: "fa fa-recycle",
                callback: () => this.model.onSoftArchive(),
                groupNumber: 1,
            },
            unarchive: {
                isAvailable: () => canUnarchive,
                sequence: 53,
                description: _t("Unarchive"),
                icon: "fa fa-history",
                callback: () => this.model.onSoftUnarchive(),
                groupNumber: 1,
            },
        };
        return actionItems;
    },
});
