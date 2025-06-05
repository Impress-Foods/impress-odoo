{
    "name": "impress account report customizations",
    "version": "18.0.0.1.0",
    "depends": ["account_accountant", "account_reports"],
    "author": "Cédric Paradis",
    "category": "Accounting",
    "website": "https://github.com/impress-foods/impress-odoo",
    "summary": """
    Module to customize the accounting reports
    """,
    # data files always loaded at installation
    "assets": {
        "web.assets_backend": [
            "impress_account_report/static/src/account_report.xml",
        ],
    },
    "license": "GPL-2",
    "installable": True,
}
