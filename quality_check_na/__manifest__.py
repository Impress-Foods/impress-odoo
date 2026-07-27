{
    "name": "Quality Check Not Applicable",
    "summary": "Add Not Applicable option to quality checks",
    "version": "19.0.1.0.0",
    "category": "Quality",
    "author": "Cédric Paradis",
    "website": "https://github.com/Impress-Foods/impress-odoo",
    "depends": ["quality", "quality_control", "mrp_workorder", "shop_floor_usability"],
    "data": [
        "views/quality_check_views.xml",
        "views/quality_point_views.xml",
        "wizards/quality_check_wizard_views.xml",
    ],
    "assets": {
        "web.assets_backend": ["quality_check_na/static/src/**/*"],
    },
    "application": False,
    "auto_install": False,
    "license": "GPL-2",
}
