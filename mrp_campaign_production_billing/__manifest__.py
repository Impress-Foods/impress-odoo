# pragma: no coverage
{
    "name": "Manufacturing Campaigns - Production Billing",
    "version": "19.0.1.0.0",
    "summary": "Bridge module: create campaign demands from production billing",
    "author": "Cédric Paradis",
    "website": "https://github.com/Impress-Foods/impress-odoo",
    "category": "Hidden",
    "depends": ["mrp_campaign", "impress_production_billing"],
    "data": [
        "wizards/mrp_campaign_wizard_views.xml",
    ],
    "installable": True,
    "auto_install": False,
    "license": "GPL-2",
}
