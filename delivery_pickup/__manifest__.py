{
    "name": "Delivery - Pickup",
    "version": "17.0.1.0.0",
    "summary": """ Pickup Delivery Connector """,
    "author": "Cédric Paradis",
    "website": "https://github.com/Impress-Foods/impress-odoo",
    "category": "Inventory/Delivery",
    "depends": ["stock_delivery", "mail", "delivery_common"],
    "data": ["views/delivery_carrier_views.xml", "reports/report_pickup_label.xml"],
    "application": True,
    "installable": True,
    "auto_install": False,
    "license": "GPL-2",
}
