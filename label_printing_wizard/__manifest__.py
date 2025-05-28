{
    "name": "Label Printing Wizard",
    "version": "17.0.1.0.0",
    "summary": """
    Adds different wizards to print custom labels for products and lots
    """,
    "author": "Cédric Paradis",
    "website": "",
    "category": "Hidden",
    "depends": ["base", "stock", "product_expiry", "stock_barcode"],
    "data": [
        "security/ir.model.access.csv",
        "wizards/label_wizard.xml",
        "reports/lot_labels.xml",
        "reports/product_labels.xml",
        "reports/reports.xml",
        "views/stock_lot.xml",
        "views/product_product.xml",
    ],
    "application": True,
    "installable": True,
    "auto_install": False,
    "license": "LGPL-3",
}
