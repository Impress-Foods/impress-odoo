{
    "name": "Domino_printing",
    "version": "19.0.1.0.0",
    "summary": """ Domino_printing for work orders and manufacturing orders """,
    "author": "Cédric Paradis",
    "website": "https://github.com/Impress-Foods/impress-odoo",
    "category": "Hidden",
    "depends": ["base", "mrp_workorder"],
    "data": [
        "security/ir.model.access.csv",
        "views/product_product_views.xml",
        "views/res_config_settings_views.xml",
        "views/domino_label.xml",
        "views/domino_printer.xml",
        "views/domino_print_field.xml",
        "views/domino_print_template.xml",
        "views/quality_points.xml",
        "views/menus.xml",
        "wizards/domino_print_wizard_views.xml",
        "data/cron.xml",
    ],
    "application": False,
    "installable": True,
    "auto_install": False,
    "license": "LGPL-3",
    "external_dependencies": {
        "python": [
            "pydantic>=2.0.0",
        ]
    },
}
