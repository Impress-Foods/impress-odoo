from odoo import api, models
from odoo.exceptions import UserError
from odoo.tools import file_path

from ..x12.engine import Outcome, validate_document


class EdiExchangeType(models.Model):
    _inherit = "edi.exchange.type"

    def x12_map_path(self) -> str:
        """Absolute path of the pyx12 map folder named by ``x12.map_set``."""
        return file_path(self._x12_setting("map_set"))

    def x12_mapping(self) -> models.AbstractModel:
        """The mapping model named by ``x12.mapping``."""
        return self.env[self._x12_setting("mapping")]

    @api.model
    def x12_validate(self, text: str, map_path: str) -> Outcome:
        """Validate ``text`` against the maps in ``map_path``; refuse it if rejected."""
        outcome = validate_document(text, map_path)
        if not outcome.ok:
            raise UserError(
                self.env._("Invalid X12 document: %(issues)s", issues=outcome.summary)
            )
        return outcome

    def x12_file_name(self, control_number: int) -> str:
        """Name of an outgoing file from the optional ``x12.filename`` pattern.

        The pattern can use ``{control}``, the interchange control number, which
        is unique across everything we send. Empty when the type sets none, so
        the framework's own naming applies.
        """
        self.ensure_one()
        pattern = (self.get_settings().get("x12") or {}).get("filename")
        if not pattern:
            return ""
        name = pattern.format(control=control_number)
        return f"{name}.{self.exchange_file_ext}" if self.exchange_file_ext else name

    def _x12_setting(self, key: str) -> str:
        self.ensure_one()
        value = (self.get_settings().get("x12") or {}).get(key)
        if not value:
            raise UserError(
                self.env._(
                    "Exchange type %(type)s needs %(key)s under x12 in its "
                    "advanced settings.",
                    type=self.name,
                    key=key,
                )
            )
        return value
