# pragma: no coverage
{
    "name": "Manufacturing Campaigns - Direct (Stock Move)",
    "version": "17.0.1.0.0",
    "summary": "Bridge module: create campaign demands from stock moves",
    "author": "Cédric Paradis",
    "website": "https://github.com/Impress-Foods/impress-odoo",
    "category": "Hidden",
    "depends": ["mrp_campaign"],
    "data": [
        "security/ir.model.access.csv",
        "wizards/mrp_campaign_creator_views.xml",
        "wizards/mrp_campaign_add_demand_views.xml",
        "wizards/mrp_campaign_partition_views.xml",
        "views/mrp_campaign_views.xml",
    ],
    "installable": True,
    "license": "GPL-2",
}
