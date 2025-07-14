{
    "name": "Impress Deposit",
    "version": "17.0.0.1.1",
    "summary": """ Module to allow the management of deposits for containers """,
    "author": "Cédric Paradis",
    "website": "https://github.com/Impress-Foods/impress-odoo",
    "category": "Stock",
    "depends": ["base", "web", "sale_management", "stock"],
    "data": [
        "views/product_product_views.xml",
        "views/res_config_settings_views.xml",
        "views/res_partner_views.xml",
        "views/sale_order_views.xml",
        "views/stock_picking_views.xml",
    ],
    "assets": {
        # 'web.assets_backend': [
        #    'impress_deposit/static/src/**/*'
        # ],
    },
    "installable": True,
    "license": "GPL-2",
}
