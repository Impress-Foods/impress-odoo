from typing import Self

from odoo import api, fields, models
from odoo.exceptions import UserError
from odoo.tools import file_path

from odoo.addons.edi_core_oca.models.edi_backend import EDIBackend
from odoo.addons.edi_x12.x12.outbound import DEFAULT_QUALIFIER, Envelope


class EdiRithumPartner(models.Model):
    """A retailer we trade with through Rithum, told apart by its interchange ID.

    Every retailer's files share one folder. The envelope of each carries the
    retailer's own interchange ID, and the partner found from it decides which
    module reads the file and which maps check it.
    """

    _name = "edi.rithum.partner"
    _description = "Rithum Partner"
    _order = "name"

    name = fields.Char(required=True)
    active = fields.Boolean(default=True)
    backend_id = fields.Many2one(
        "edi.backend",
        string="Backend",
        required=True,
        default=lambda self: self.env.ref(
            "edi_rithum.rithum_backend", raise_if_not_found=False
        ),
    )
    x12_qualifier = fields.Char(
        string="Interchange qualifier",
        default=DEFAULT_QUALIFIER,
        help="ISA05 of the files the retailer sends.",
    )
    x12_id = fields.Char(
        string="Interchange ID",
        help="The retailer's interchange ID (ISA06): the sender of its files. "
        "Files from an ID no partner has are refused.",
    )
    own_qualifier = fields.Char(
        string="Our qualifier",
        help="Only if it differs from the backend's: our ISA qualifier with this "
        "retailer, for files that answer nothing, like the inventory.",
    )
    own_id = fields.Char(
        string="Our ID",
        help="Only if it differs from the backend's: our interchange ID with this "
        "retailer, for files that answer nothing, like the inventory. A reply takes "
        "the ID the retailer's file was addressed to.",
    )
    map_set = fields.Char(
        required=True,
        help="The folder of pyx12 maps for this retailer's documents, for example "
        "edi_rithum_costco/x12_maps.",
    )
    intake_model = fields.Char(
        required=True,
        help="The model that reads this retailer's documents. It inherits "
        "edi.rithum.intake.",
    )

    _x12_id_unique = models.Constraint(
        "UNIQUE(backend_id, x12_id)", "Two partners cannot share an interchange ID."
    )

    def map_path(self) -> str:
        """Absolute path of this retailer's pyx12 map folder."""
        self.ensure_one()
        return file_path(self.map_set)

    def intake(self) -> models.AbstractModel:
        """The model that processes this retailer's documents."""
        self.ensure_one()
        return self.env[self.intake_model]

    def x12_envelope(self, functional_id: str) -> Envelope:
        """The envelope of a file for this retailer that answers none of its files."""
        self.ensure_one()
        if not self.x12_id:
            raise UserError(
                self.env._(
                    "Set the interchange ID of the Rithum partner %(name)s: it is "
                    "the address of every file we send it that answers nothing.",
                    name=self.name,
                )
            )
        backend: EDIBackend = self.backend_id
        return backend.x12_envelope(
            self.x12_qualifier or DEFAULT_QUALIFIER,
            self.x12_id,
            functional_id,
            sender_qualifier=self.own_qualifier or None,
            sender_id=self.own_id or None,
        )

    @api.model
    def from_sender(self, backend: EDIBackend, sender_id: str) -> Self:
        """The partner whose interchange ID is ``sender_id``, or an empty record."""
        return self.search(
            [("backend_id", "=", backend.id), ("x12_id", "=", sender_id)], limit=1
        )
