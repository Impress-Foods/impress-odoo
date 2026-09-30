{
    "name": "Quality Label Printing",
    "summary": "Print a quality step's label on the printer that step uses",
    "version": "19.0.1.0.0",
    "category": "Manufacturing",
    "author": "Cédric Paradis",
    "website": "https://github.com/Impress-Foods/impress-odoo",
    "license": "GPL-2",
    "depends": [
        "quality_mrp_workorder",
        "printing_dashboard",
    ],
    "data": [
        "security/ir.model.access.csv",
        "views/quality_point_views.xml",
        "wizards/quality_check_printer_picker_views.xml",
    ],
    "application": False,
    "auto_install": False,
    "installable": True,
}
