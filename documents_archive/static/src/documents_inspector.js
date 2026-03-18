/** @odoo-module **/
import {patch} from "@web/core/utils/patch";
import {DocumentsInspector} from "@documents/views/inspector/documents_inspector";
import {inspectorFields} from "@documents/views/inspector/documents_inspector";

inspectorFields.push("archived");

patch(DocumentsInspector.prototype, {
    async onSoftArchive() {
        const record = this.props.documents[0];
        await this.orm.call("documents.document", "action_soft_archive", [
            [record.data.id],
        ]);
        await record.model.load();
    },

    async onSoftUnarchive() {
        const record = this.props.documents[0];
        await this.orm.call("documents.document", "action_soft_unarchive", [
            [record.data.id],
        ]);
        await record.model.load();
    },
});
