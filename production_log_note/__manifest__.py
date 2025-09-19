{
    "name": "production_log_note",
    "version": "19.0.0.1.2",
    "summary": """ Backport of V18 feature where a note can be
    added to a production order""",
    "author": "Cédric Paradis",
    "website": "https://github.com/impress-foods/impress-odoo",
    "category": "Hidden",
    "depends": ["base", "web", "mrp_workorder"],
    "data": ["views/mrp_production_views.xml"],
    "assets": {
        "web.assets_backend": ["production_log_note/static/src/**/*"],
    },
    "installable": True,
    "license": "GPL-2",
}
