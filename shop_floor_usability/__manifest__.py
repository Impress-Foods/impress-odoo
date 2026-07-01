{
    "name": "Shop Floor Usability",
    "version": "19.0.1.0.0",
    "summary": """General QoL improvements for the shop floor module""",
    "author": "Cédric Paradis",
    "website": "https://github.com/Impress-Foods/impress-odoo",
    "category": "Manufacturing/Shop Floor",
    "depends": ["mrp_workorder", "quality_mrp_workorder", "html_editor"],
    "assets": {
        "web.assets_backend": [
            "shop_floor_usability/static/src/**/*.js",
            "shop_floor_usability/static/src/**/*.xml",
        ],
    },
    "installable": True,
    "license": "GPL-2",
}
