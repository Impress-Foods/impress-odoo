{
    "name": "Impress Barcode Tweaks",
    "summary": """
        Customizations to barcode app
    """,
    "author": "Cédric Paradis",
    "website": "https://github.com/Impress-Foods/impress-odoo",
    "category": "Hidden",
    "version": "19.0.1.0.1",
    "license": "GPL-2",
    "depends": [
        "base",
        "stock",
        "sale_management",
        "stock_barcode",
        "stock_barcode_mrp",
    ],
    "data": [
        "views/stock_picking_views.xml",
    ],
    "assets": {
        "web.assets_backend": [
            "impress_barcode/static/src/**/*.js",
            "impress_barcode/static/src/**/*.xml",
            "impress_barcode/static/src/**/*.scss",
        ],
    },
}
