{
    "name": "Delivery Status Multi Step",
    "version": "17.0.1.0.0",
    "summary": """ Adds usefull delivery statuses for multi-step delivery flows """,
    "author": "Cédric Paradis",
    "website": "",
    "category": "Hidden",
    "depends": ["base", "sale_stock"],
    "data": [
        "views/sale_order_views.xml"
    ],
    "installable": True,
    "auto_install": ["sale_stock"],
    "license": "GPL-2",
}
