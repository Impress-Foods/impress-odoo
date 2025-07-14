{
    "name": "maintenance_consume_stock",
    "version": "17.0.0.0.2",
    "summary": """ Module to allow stock usage in maintenance requests """,
    "author": "Cédric Paradis",
    "website": "https://github.com/Impress-Foods/impress-odoo",
    "category": "Hidden",
    "depends": ["base", "maintenance", "base_maintenance", "stock"],
    "data": [
        "data/locations.xml",
        "views/maintenance_request_views.xml",
        "views/stock_scrap_views.xml",
    ],
    "installable": True,
    "auto_install": False,
    "license": "GPL-2",
}
