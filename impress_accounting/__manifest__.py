{
    "name": "Impress Accounting",
    "version": "19.0.1.0.2",
    "summary": """ Accounting specific changes for Impress Foods """,
    "author": "Cédric Paradis",
    "website": "https://github.com/Impress-Foods/impress-odoo",
    "category": "Hidden",
    "depends": ["base", "account", "account_reports"],
    "data": ["views/res_partner_views.xml"],
    "assets": {
        "web.assets_backend": [
            "impress_accounting/static/src/account_report.xml",
        ],
    },
    "application": False,
    "installable": True,
    "auto_install": False,
    "license": "LGPL-3",
}
