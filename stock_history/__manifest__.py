{
    "name": "Stock History",
    "version": "17.0.1.0.0",
    "summary": """
    Adds a configurable timeframe report to take snapshots of stock levels
    """,
    "author": "Cédric Paradis",
    "website": "https://github.com/cparadis-impressfoods/impress-odoo",
    "category": "Hidden",
    "depends": ["base", "stock"],
    "data": [
        "data/stock_history_config_cron.xml",
        "data/ir_sequences.xml",
        "security/ir.model.access.csv",
        "views/stock_history_config_views.xml",
        "views/stock_history_group_views.xml",
        "views/stock_history_line_views.xml",
    ],
    "installable": True,
    "license": "GPL-2",
}
