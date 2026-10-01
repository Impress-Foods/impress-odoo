{
    "name": "Label Printing Wizard - MRP",
    "version": "19.0.0.1.0",
    "summary": """
    Label Printing Wizard - MRP bridge
    """,
    "author": "Cédric Paradis",
    "website": "https://github.com/Impress-Foods/impress-odoo",
    "category": "Hidden",
    "depends": [
        "label_printing_wizard",
        "mrp_workorder",
    ],
    "data": [],
    "assets": {
        "web.assets_backend": [
            "label_printing_wizard_mrp/static/src/**/*.js",
            "label_printing_wizard_mrp/static/src/**/*.xml",
        ]
    },
    "application": False,
    "installable": True,
    "auto_install": True,
    "license": "LGPL-3",
}
