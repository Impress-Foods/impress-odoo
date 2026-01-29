{
    "name": "Delivery_auto_select_carrier",
    "version": "19.0.1.0.0",
    "summary": """ Delivery_auto_select_carrier Summary """,
    "author": "Cédric Paradis",
    "website": "https://github.com/impress-foods/impress-odoo",
    "category": "Hidden",
    "depends": ["sale_management", "stock_delivery"],
    "data": [
        "views/delivery_carrier_views.xml",
        "views/res_config_settings_views.xml",
        "views/sale_order_views.xml",
    ],
    "application": True,
    "installable": True,
    "auto_install": False,
    "license": "GPL-2",
}
