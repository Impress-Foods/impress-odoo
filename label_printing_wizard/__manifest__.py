{
    "name": "Label Printing Wizard",
    "version": "19.0.1.0.0",
    "summary": """
    Adds different wizards to print custom labels for products and lots
    """,
    "author": "Cédric Paradis",
    "website": "https://github.com/Impress-Foods/impress-odoo",
    "category": "Hidden",
    "depends": [
        "product_expiry",
        "stock_barcode",
        "barcodes_gs1_nomenclature",
    ],
    "data": [
        "wizards/label_wizard.xml",
        "reports/common.xml",
        "reports/lot_labels.xml",
        "reports/product_labels.xml",
        "reports/reports.xml",
        "views/product_product.xml",
        "views/stock_lot.xml",
        "views/stock_picking.xml",
        "security/ir.model.access.csv",
    ],
    "assets": {
        "web.assets_backend": [
            "label_printing_wizard/static/src/**/*.js",
            # "label_printing_wizard/static/src/**/*.xml",
        ]
    },
    "application": True,
    "installable": True,
    "auto_install": False,
    "license": "LGPL-3",
}
