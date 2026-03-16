# pragma: no coverage
{
    "name": "Manufacturing Campaigns - Sales",
    "version": "17.0.1.0.0",
    "summary": """ Bridge module between MRP Campaigns and Sales """,
    "author": "Cédric Paradis",
    "website": "https://github.com/Impress-Foods/impress-odoo",
    "category": "Hidden",
    "depends": ["mrp_campaign", "sale_stock"],
    "data": [
        "views/mrp_campaign_views.xml",
        "views/sale_order_views.xml",
        "views/mrp_campaign_creator_views.xml",
    ],
    "assets": {
        "web.assets_backend": ["mrp_campaign_sale/static/src/**/*"],
    },
    "installable": True,
    "auto_install": ["mrp_campaign", "sale_stock"],
    "license": "GPL-2",
}
