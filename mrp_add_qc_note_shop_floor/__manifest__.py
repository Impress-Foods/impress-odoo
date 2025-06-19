{
    "name": "Add QC Note to shop floor",
    "version": "17.0.0.1.0",
    "summary": """ Mrp_add_qc_note_shop_floor Summary """,
    "author": "Cédric Paradis",
    "website": "https://github.com/Impress-Foods/impress-odoo",
    "category": "Hidden",
    "depends": ["base", "web", "mrp_workorder"],
    "data": [],
    "assets": {
        "web.assets_backend": [
            "mrp_add_qc_note_shop_floor/static/src/**/*.js",
            "mrp_add_qc_note_shop_floor/static/src/**/*.xml",
        ],
    },
    "installable": True,
    "license": "GPL-2",
}
