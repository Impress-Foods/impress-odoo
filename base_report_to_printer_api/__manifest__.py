{
    "name": "Report to Printer API",
    "summary": "Send structured Odoo print data to HTTP APIs",
    "version": "19.0.1.0.0",
    "category": "Generic Modules/Base",
    "author": "Cédric Paradis",
    "website": "https://github.com/Impress-Foods/impress-odoo",
    "license": "GPL-2",
    "depends": ["base_report_to_printer"],
    "data": [
        "security/ir.model.access.csv",
        "views/printing_api_server.xml",
        "views/printing_printer.xml",
        "views/print_report.xml",
        "views/print_field.xml",
        "views/ir_actions_report.xml",
    ],
    "assets": {
        "web.assets_backend": [
            "base_report_to_printer_api/static/src/qweb_action_manager.esm.js",
        ],
    },
    "installable": True,
    "application": False,
    "auto_install": False,
}
