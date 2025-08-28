{
    "name": "Deposit_website",
    "version": "17.0.1.0.0",
    "summary": """ Deposit_website Summary """,
    "author": "Cédric Paradis",
    "website": "https://github.com/Impress-Foods/impress-odoo",
    "category": "Hidden",
    "depends": ["website_sale", "impress_deposit"],
    "data": ["views/website_templates.xml"],
    "application": False,
    "installable": True,
    "auto_install": ["impress_deposit", "website_sale"],
    "license": "LGPL-3",
}
