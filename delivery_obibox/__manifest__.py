{
    "name": "Delivery - Obibox",
    "version": "19.0.1.1.1",
    "summary": """ Obibox Delivery Connector """,
    "author": "Cédric Paradis",
    "website": "https://github.com/Impress-Foods/impress-odoo",
    "category": "Inventory/Delivery",
    "depends": ["stock_delivery", "mail", "delivery_common"],
    "external_dependencies": {
        "python": [
            "pydantic>=2.0.0",
        ]
    },
    "data": [
        "views/delivery_carrier_views.xml",
        "data/delivery_obibox.xml",
        "security/ir.model.access.csv",
    ],
    "application": True,
    "installable": True,
    "auto_install": False,
    "license": "GPL-2",
}
