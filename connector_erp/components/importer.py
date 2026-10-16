from odoo.addons.component.core import AbstractComponent


class ErpImporter(AbstractComponent):
    """Generic importer for a single external record.

    It orchestrates the adapter (read), the mapper (translate) and the
    binder (resolve identity), and is idempotent: re-importing an already
    bound record updates it instead of creating a duplicate.

    Concrete importers usually only need ``_apply_on`` and ``_collection``,
    overriding the hooks below when the default flow does not fit.
    """

    _name = "erp.importer"
    _inherit = ["base.importer", "erp.connector"]
    _description = "ERP Record Importer"
    _usage = "record.importer"

    def run(self, external_id, force=False, **kwargs):
        external_id = str(external_id)
        binding = self.binder.to_internal(external_id)
        if binding and not force and not self._should_import(binding):
            return binding

        data = self._get_external_data(external_id, **kwargs)
        values = self._map_data(data)
        values["external_id"] = external_id
        values["backend_id"] = self.backend_record.id

        if binding:
            self._update_binding(binding, values)
        else:
            binding = self._create_binding(values)

        self.binder.bind(external_id, binding)
        self._after_import(binding)
        return binding

    def _should_import(self, binding):
        """Hook: return False to skip an already bound record."""
        return True

    def _get_external_data(self, external_id, **kwargs):
        return self.backend_adapter.read_record(external_id, **kwargs)

    def _map_data(self, data):
        return self.mapper.map_record(data).values()

    def _create_binding(self, values):
        return self.model.create(values)

    def _update_binding(self, binding, values):
        binding.write(values)
        return binding

    def _after_import(self, binding):
        if "state" in binding._fields:
            binding.with_context(connector_no_export=True).write(
                {"state": "synced", "error_message": False}
            )
