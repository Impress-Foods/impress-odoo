{
    "name": "Domino_printing",
    "version": "17.0.0.0.1",
    "summary": """ Domino_printing Summary """,
    "author": "Cédric Paradis",
    "website": "https://github.com/Impress-Foods/impress-odoo",
    "category": "Hidden",
    "depends": ["base", "mrp_workorder"],
    "data": ["views/product_product_views.xml", "views/res_config_settings_views.xml"],
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
