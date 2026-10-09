from odoo.addons.component.core import AbstractComponent


class ErpBatchImporter(AbstractComponent):
    """Generic batch importer sweeping a whole external entity.

    It asks the concrete adapter which external ids exist, keeps the ones
    that are not bound yet, and enqueues one ``record.importer`` job per id.
    The queue channel and retry policy come from ``queue.job.function``
    records, not from the code.
    """

    _name = "erp.batch.importer"
    _inherit = ["base.importer", "erp.connector"]
    _description = "ERP Batch Importer"
    _usage = "batch.importer"

    def run(self, force=False, **kwargs):
        external_ids = [str(ext_id) for ext_id in self._iter_external_ids(**kwargs)]
        to_import = external_ids if force else self._filter_new_ids(external_ids)
        for external_id in to_import:
            self._enqueue_record_import(external_id)
        return len(to_import)

    def _iter_external_ids(self, **kwargs):
        """Hook: return the external ids available on the backend."""
        raise NotImplementedError

    def _filter_new_ids(self, external_ids):
        if not external_ids:
            return []
        existing = self.model.with_context(active_test=False).search(
            [
                ("backend_id", "=", self.backend_record.id),
                ("external_id", "in", external_ids),
            ]
        )
        existing_ids = set(existing.mapped("external_id"))
        return [ext_id for ext_id in external_ids if ext_id not in existing_ids]

    def _enqueue_record_import(self, external_id):
        self.model.with_delay().import_record(self.backend_record, external_id)
