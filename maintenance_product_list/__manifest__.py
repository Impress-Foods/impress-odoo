{
    "name": "Maintenance Product Bridge",
    "version": "17.0.1.0.0",
    "summary": """ Allows to link products to maintenance equipments """,
    "author": "Cédric Paradis",
    "website": "https://github.com/Impress-Foods/impress-odoo",
    "category": "Hidden",
    "depends": ["base", "stock", "maintenance", "purchase_stock"],
    "data": [
        "views/maintenance_equipment_views.xml",
        "views/product_product_views.xml",
        "views/product_template_views.xml",
        "views/res_partner_views.xml",
        "views/stock_orderpoint_views.xml",
    ],
    "installable": True,
    "auto_install": ["maintenance", "stock"],
    "license": "GPL-2",
}
