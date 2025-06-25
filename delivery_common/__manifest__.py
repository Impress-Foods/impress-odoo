{
    "name": "Delivery Common",
    "version": "17.0.1.0.0",
    "summary": """ Base module for Impress Delivery Connectors """,
    "author": "Cédric Paradis",
    "website": "https://github.com/cparadis-impressfoods/impress-odoo",
    "category": "Hidden",
    "depends": ["stock_delivery", "mail"],
    "data": [
        "security/ir.model.access.csv",
        "views/stock_picking_views.xml",
        "reports/shipping_label_report.xml",
    ],
    "application": False,
    "installable": True,
    "auto_install": False,
    "license": "GPL-2",
}
