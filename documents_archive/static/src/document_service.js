/** @odoo-module **/
import {patch} from "@web/core/utils/patch";
import {DocumentService} from "@documents/core/document_service";

patch(DocumentService.prototype, {
    async archive(documentIds) {
        await this.orm.call("documents.document", "action_soft_archive", [documentIds]);
        return true;
    },
    async unarchive(documentIds) {
        await this.orm.call("documents.document", "action_soft_unarchive", [
            documentIds,
        ]);
        return true;
    },
});
