{
    "name": "Impress Accounting",
    "version": "19.0.1.1.0",
    "summary": """ Accounting specific changes for Impress Foods """,
    "author": "Cédric Paradis",
    "website": "https://github.com/Impress-Foods/impress-odoo",
    "category": "Hidden",
    "depends": ["base", "account", "account_reports", "l10n_ca_check_printing"],
    "data": [],
    "assets": {
        "web.assets_backend": [
            "impress_accounting/static/src/account_report.xml",
        ],
        "web.report_assets_common": [
            "impress_accounting/static/src/report_check_top.scss",
        ],
    },
    "application": False,
    "installable": True,
    "auto_install": False,
    "license": "LGPL-3",
}
