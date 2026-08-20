{
    "name": "Printing Connector",
    "summary": "Generic printing connector for label-type prints",
    "version": "19.0.1.0.0",
    "category": "hidden",
    "author": "Cédric Paradis",
    "website": "https://github.com/Impress-Foods/impress-odoo",
    "depends": ["base"],
    "data": [
        "security/ir.model.access.csv",
        "views/print_field_views.xml",
        "views/print_report_views.xml",
        "views/ir_report_views.xml",
        "views/menus.xml",
    ],
    "assets": {
        "web.assets_backend": [
            "printing_connector/static/src/**/*.js",
        ]
    },
    "application": True,
    "auto_install": False,
    "license": "GPL-2",
}
