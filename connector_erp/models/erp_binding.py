from odoo import fields, models


class ErpBindingMixin(models.AbstractModel):
    """Base for every ERP binding model.

    A binding links an external identity to an Odoo record for one backend.
    Concrete models add ``backend_id`` (a many2one to the ERP backend),
    declare ``_inherits`` on the Odoo model they bind, and enforce
    ``UNIQUE(backend_id, external_id)``.
    """

    _name = "erp.binding.mixin"
    _inherit = ["external.binding"]
    _description = "ERP Binding Mixin"

    external_id = fields.Char(required=True, index=True)
    active = fields.Boolean(default=True)
    state = fields.Selection(
        [
            ("pending", "Pending"),
            ("synced", "Synchronized"),
            ("error", "Error"),
        ],
        required=True,
        default="pending",
        index=True,
    )
    error_message = fields.Text(readonly=True)

    def import_record(self, backend, external_id, force=False, **kwargs):
        """Import one external record as a delayed job.

        This is the model-level entry point used by the batch importer and
        by ``base.exporter`` when it needs to refresh a binding. It runs on
        an (empty) recordset of the binding model.
        """
        with backend.work_on(self._name) as work:
            importer = work.component(usage="record.importer")
            return importer.run(external_id, force=force, **kwargs)
