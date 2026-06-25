# pragma: no coverage
{
    "name": "Manufacturing Campaigns",
    "version": "19.0.1.0.0",
    "summary": """ Base module for manufacturing campaigns """,
    "author": "Cédric Paradis",
    "website": "https://github.com/Impress-Foods/impress-odoo",
    "category": "Hidden",
    "depends": ["mrp_workorder", "sale_management", "sale_stock"],
    "data": [
        "data/mrp_campaign_sequence.xml",
        "security/ir.model.access.csv",
        "security/mrp_campaign_rules.xml",
        "views/mrp_campaign_views.xml",
        "views/mrp_campaign_demand_views.xml",
        "views/mrp_campaign_line_views.xml",
        "views/mrp_production_views.xml",
        "views/product_views.xml",
        "reports/mrp_campaign_report.xml",
        "wizards/mrp_campaign_creator_views.xml",
        "wizards/mrp_campaign_partition_views.xml",
    ],
    "assets": {
        "web.assets_backend": ["mrp_campaign/static/src/**/*"],
    },
    "installable": True,
    "license": "GPL-2",
}
