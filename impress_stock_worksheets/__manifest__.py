{
    "name": "impress_stock_worksheets",
    # Non semantic version to allow to tag the most recent document date
    "version": "19.0.1.0.0",
    "summary": """ Impress_stock_worksheets Summary """,
    "author": "Cédric Paradis",
    "website": "https://github.com/Impress-Foods/impress-odoo",
    "category": "Hidden",
    "depends": ["base", "quality_control_worksheet"],
    "data": [
        # Fichiers en date du 2025-01-14
        "reports/receipt/ReceiptWorksheet_20250114.xml",
        "data/receipt/ReceiptWorksheet_20250114.xml",
        "views/receipt/ReceiptWorksheet_20250114.xml",
        "data/delivery/DeliveryWorksheet_20250114.xml",
        "views/delivery/DeliveryWorksheet_20250114.xml",
    ],
    "installable": True,
    "application": False,
    "auto_install": False,
    "license": "GPL-2",
}
