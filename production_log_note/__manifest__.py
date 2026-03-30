{
    "name": "production_log_note",
    "version": "19.0.1.0.2",
    "summary": """Makes note on shop floor read-only""",
    "author": "Cédric Paradis",
    "website": "https://github.com/Impress-Foods/impress-odoo",
    "category": "Hidden",
    "depends": ["base", "web", "mrp_workorder"],
    "data": [],
    "assets": {
        "web.assets_backend": ["production_log_note/static/src/**/*"],
    },
    "installable": True,
    "license": "GPL-2",
}
