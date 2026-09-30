{
    "name": "Printing Dashboard",
    "summary": "Open label and print reports from a unified contextual dashboard",
    "version": "19.0.1.0.0",
    "category": "Generic Modules/Base",
    "author": "Cédric Paradis",
    "website": "https://github.com/Impress-Foods/impress-odoo",
    "license": "GPL-2",
    "depends": [
        "web",
        "stock",
        "stock_barcode",
        "mrp_workorder",
        "base_report_to_printer",
        "printing_label_format",
    ],
    "data": [
        "security/ir.model.access.csv",
        "views/ir_actions_report.xml",
        "wizards/printing_dashboard.xml",
        "views/source_buttons.xml",
    ],
    "assets": {
        "web.assets_backend": [
            "printing_dashboard/static/src/**/*.js",
            "printing_dashboard/static/src/**/*.xml",
        ],
    },
    "application": False,
    "auto_install": False,
    "installable": True,
}
