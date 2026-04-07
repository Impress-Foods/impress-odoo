{
    "name": "Add QC Note to shop floor",
    "version": "19.0.1.0.1",
    "summary": """ Allows users in the shop floor app to add notes to quality checks""",
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
