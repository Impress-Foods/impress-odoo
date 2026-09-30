{
    "name": "Printing Label Format",
    "summary": "Declare whether a printer renders ZPL or PDF",
    "version": "19.0.1.0.0",
    "category": "Generic Modules/Base",
    "author": "Cédric Paradis",
    "website": "https://github.com/Impress-Foods/impress-odoo",
    "license": "GPL-2",
    "depends": [
        "base_report_to_printer",
    ],
    "data": [
        "security/ir.model.access.csv",
        "data/printing_label_size_data.xml",
        "views/printing_printer_views.xml",
        "views/ir_actions_report.xml",
        "views/printing_label_size_views.xml",
    ],
    "application": False,
    "auto_install": False,
    "installable": True,
}
