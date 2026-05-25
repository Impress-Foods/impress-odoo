{
    "name": "Impress Worksheets - Stock",
    # Non semantic version to allow to tag the most recent document date
    "version": "19.0.2026.05.22",
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
        "data/delivery_meat/DeliveryMeatWorksheet_2026_05_22.xml",
        "views/delivery_meat/DeliveryMeatWorksheet_2026_05_22.xml",
        "data/receipt_qc_meat/ReceiptQcMeatWorksheet_20260522.xml",
        "views/receipt_qc_meat/ReceiptQcMeatWorksheet_20260522.xml",
    ],
    "installable": True,
    "application": False,
    "auto_install": False,
    "license": "GPL-2",
}
