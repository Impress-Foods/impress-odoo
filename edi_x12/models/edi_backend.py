from odoo import fields, models
from odoo.exceptions import UserError

from ..x12.outbound import DEFAULT_QUALIFIER, Envelope
from ..x12.reading import isa_receiver, isa_sender

INTERCHANGE_VERSION = "00401"  # ISA12 and GS08: the release the shipped maps cover
FUNCTIONAL_VERSION = "004010"


class EdiBackend(models.Model):
    _inherit = "edi.backend"

    x12_production = fields.Boolean(
        help="Production backend: inbound files must carry ISA15 'P'. "
        "Test backends take 'T'."
    )
    x12_partner_scheme = fields.Char(
        help="Partner ID scheme (res.partner.id_category code) that holds the X12 "
        "interchange sender ID of a trading partner."
    )
    x12_sender_qualifier = fields.Char(
        string="X12 sender qualifier",
        default=DEFAULT_QUALIFIER,
        help="ISA05 of the interchanges we send.",
    )
    x12_sender_id = fields.Char(
        string="X12 sender ID",
        help="Our interchange ID (ISA06, GS02) on the interchanges we send.",
    )

    def x12_reply_envelope(self, received: str, functional_id: str) -> Envelope:
        """The envelope of an interchange answering ``received``.

        It goes to whoever sent the file, from the identity the file was addressed
        to: a trading partner can give us a different ID in each relationship, and a
        reply swaps the roles. The backend's own ID is the fallback.
        """
        qualifier, sender_id = isa_sender(received)
        own_qualifier, own_id = isa_receiver(received)
        if not own_id:  # keep the pair together: fall back to the backend's identity
            own_qualifier = None
        return self.x12_envelope(
            qualifier,
            sender_id,
            functional_id,
            sender_qualifier=own_qualifier,
            sender_id=own_id,
        )

    def x12_envelope(
        self,
        receiver_qualifier: str,
        receiver_id: str,
        functional_id: str,
        interchange_version: str = INTERCHANGE_VERSION,
        functional_version: str = FUNCTIONAL_VERSION,
        sender_qualifier: str | None = None,
        sender_id: str | None = None,
    ) -> Envelope:
        """The envelope of the next interchange we send, with a fresh control number.

        We send as the backend's identity unless ``sender_id`` gives the one to use
        with this partner.
        """
        self.ensure_one()
        sender_id = sender_id or self.x12_sender_id
        if not sender_id:
            raise UserError(
                self.env._(
                    "Set the X12 sender ID on the backend %(name)s: it is our "
                    "interchange ID on every file we send.",
                    name=self.name,
                )
            )
        control = self.env["ir.sequence"].next_by_code("edi.x12.interchange_control")
        return Envelope(
            sender_id=sender_id,
            receiver_id=receiver_id,
            control_number=int(control),
            production=self.x12_production,
            sent_at=fields.Datetime.now(),
            interchange_version=interchange_version,
            functional_version=functional_version,
            functional_id=functional_id,
            sender_qualifier=(
                sender_qualifier or self.x12_sender_qualifier or DEFAULT_QUALIFIER
            ),
            receiver_qualifier=receiver_qualifier,
        )
