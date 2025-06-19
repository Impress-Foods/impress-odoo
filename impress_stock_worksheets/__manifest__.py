{
    "name": "impress_stock_worksheets",
    # Non semantic version to allow to tag the most recent document date
    "version": "17.0.25.01.14",
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
    "auto_install": False,
    "license": "GPL-2",
}
