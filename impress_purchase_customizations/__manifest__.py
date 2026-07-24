{
    "name": "Impress Purchase Customizations",
    "version": "19.0.1.1.0",
    "summary": """ Impress Foods specific purchase customizations """,
    "author": "Cédric Paradis",
    "website": "https://github.com/Impress-Foods/impress-odoo",
    "category": "Hidden",
    "depends": ["base", "purchase"],
    "data": [
        "report/purchase_order_report.xml",
        "security/groups.xml",
        "views/purchase_order_views.xml",
    ],
    "application": False,
    "installable": True,
    "auto_install": False,
    "license": "GPL-2",
}
