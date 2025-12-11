{
    "name": "impress_expiration_lot",
    "version": "17.0.0.1.0",
    "depends": ["base", "stock", "product_expiry", "base_automation"],
    "author": "Cédric Paradis",
    "category": "Inventory",
    "website": "https://github.com/Impress-Foods/impress-odoo",
    "summary": """
    Module that allows to automatically calculate to correct dates for a lot's expiry,
    """,
    "license": "GPL-2",
    # data files always loaded at installation
    "data": [
        "actions/server_actions.xml",
        "actions/automation_rules.xml",
        "actions/lot_cron.xml",
        "data/templates.xml",
    ],
    "assets": {},
}
