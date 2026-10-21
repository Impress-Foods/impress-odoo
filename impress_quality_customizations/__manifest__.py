{
    "name": "impress Quality Customizations",
    "version": "19.0.1.3.0",
    "depends": [
        "base",
        "quality_control",
        "quality_mrp",
        "quality_mrp_workorder",
        "purchase_stock",
        "sale_stock",
    ],
    "author": "Cédric Paradis",
    "website": "https://github.com/Impress-Foods/impress-odoo",
    "category": "Quality",
    "summary": """
    Customizations for the quality module developped in-house by Impress Foods SEC
    """,
    "license": "GPL-2",
    "data": [
        "views/quality_check_views.xml",
        "views/quality_point_views.xml",
        "views/stock_lot_views.xml",
        "views/quality_alert_views.xml",
        "views/purchase_order_views.xml",
        "views/sale_order_views.xml",
        "views/menus.xml",
    ],
    "external_dependencies": {
        "python": ["odoo_upgrade @ git+https://github.com/odoo/upgrade-util@master"]
    },
}
