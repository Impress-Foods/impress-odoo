{
    "name": "maintenance_consume_stock",
    "version": "19.0.0.0.2",
    "summary": """ Module to allow stock usage in maintenance requests """,
    "author": "Cédric Paradis",
    "website": "https://github.com/impress-foods/impress-odoo",
    "category": "Hidden",
    "depends": ["base_maintenance", "stock", "maintenance_product_list"],
    "data": [
        "data/locations.xml",
        "views/maintenance_request_views.xml",
        "views/stock_scrap_views.xml",
        "views/product_product_views.xml",
    ],
    "installable": True,
    "auto_install": False,
    "license": "GPL-2",
}
