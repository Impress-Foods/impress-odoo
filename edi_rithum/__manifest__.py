{
    "name": "EDI Rithum",
    "version": "19.0.1.0.0",
    "summary": """ Files exchanged with retailers through Rithum (HubEDI) """,
    "author": "Cédric Paradis",
    "website": "https://github.com/Impress-Foods/impress-odoo",
    "category": "Hidden",
    "depends": [
        "edi_x12",
        "edi_storage_oca",
        "edi_exchange_deduplicate_oca",
    ],
    "data": [
        "security/ir.model.access.csv",
        "data/edi_backend.xml",
        "data/edi_exchange_type.xml",
        "views/rithum_partner_views.xml",
    ],
    "installable": True,
    "license": "AGPL-3",
}
