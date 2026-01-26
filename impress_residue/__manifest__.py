{
    "name": "Impress Residue",
    "version": "17.0.0.0.1",
    "summary": """ Module to handle paid residue pickup """,
    "author": "Cédric Paradis",
    "website": "https://github.com/Impress-Foods/impress-odoo",
    "category": "Hidden",
    "depends": ["purchase_stock"],
    "data": [
        "data/stock_data.xml",
        "views/product_views.xml",
    ],
    "application": False,
    "installable": True,
    "auto_install": False,
    "license": "GPL-2",
}
