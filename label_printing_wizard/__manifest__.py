{
    "name": "Label Printing Wizard",
    "version": "17.0.1.0.0",
    "summary": """
    Adds different wizards to print custom labels for products and lots
    """,
    "author": "Cédric Paradis",
    "website": "https://github.com/cparadis-impressfoods/impress-odoo",
    "category": "Hidden",
    "depends": ["base", "product", "stock", "product_expiry", "stock_barcode"],
    "data": [
        "views/product_product.xml",
        "views/stock_lot.xml",
        "views/stock_picking.xml",
        "reports/datamatrix.xml",
        "reports/lot_labels.xml",
        "reports/product_labels.xml",
        "reports/reports.xml",
        "wizards/label_wizard.xml",
        "security/ir.model.access.csv",
    ],
    "assets": {
        "web.assets_backend": [
            "label_printing_wizard/static/src/**/*.js",
            "label_printing_wizard/static/src/**/*.xml",
        ]
    },
    "application": True,
    "installable": True,
    "auto_install": False,
    "license": "LGPL-3",
}
