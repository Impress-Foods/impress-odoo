{
    "name": "Delivery - Clickship",
    "version": "17.0.1.0.0",
    "summary": """ Clickship delivery provider """,
    "author": "Cédric Paradis",
    "website": "https://github.com/Impress-Foods/impress-odoo",
    "category": "Inventory/Delivery",
    "depends": ["delivery_common", "hr", "stock_barcode"],
    "data": [
        "security/ir.model.access.csv",
        "views/clickship_payment_method_views.xml",
        "views/delivery_carrier_views.xml",
        "views/rate_views.xml",
        "views/stock_picking_views.xml",
        "wizards/wizard_clickship_rates.xml",
    ],
    "assets": {
        "web.assets_backend": [
            "/delivery_clickship/static/src/**/*.js",
            "/delivery_clickship/static/src/**/*.xml",
        ]
    },
    "application": True,
    "installable": True,
    "auto_install": False,
    "license": "LGPL-3",
}
