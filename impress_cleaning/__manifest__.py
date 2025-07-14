{
    "name": "impress_cleaning",
    "version": "17.0.0.1.0",
    "summary": "Module to handle cleanings for Impress Foods",
    "author": "Cédric Paradis",
    "website": "https://github.com/Impress-Foods/impress-odoo",
    "license": "GPL-2",
    "category": "maintenance",
    "depends": [
        "maintenance",
        "mrp",
        "mrp_workorder",
        "mrp_maintenance",
        "maintenance_worksheet",
    ],
    "data": [
        "actions/server_actions.xml",
        "data/maintenance_teams.xml",
        "views/maintenance_views.xml",
        "views/mrp_workcenter.xml",
    ],
    "auto_install": False,
    "application": False,
    "assets": {
        "web.assets_backend": [
            "impress_cleaning/static/src/cleaning_request_button.xml",
        ]
    },
}
