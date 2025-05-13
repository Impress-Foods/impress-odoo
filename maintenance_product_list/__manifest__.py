{
    "name": "Maintenance Product Bridge",
    "version": "17.0.1.0.0",
    "summary": """ Allows to link products to maintenance equipments """,
    "author": "Cédric Paradis",
    "website": "https://github.com/cparadis-impressfoods/impress-odoo",
    "category": "Hideen",
    "depends": ["base", "stock", "maintenance"],
    "data": [
        "views/maintenance_equipment_views.xml",
        "views/product_product_views.xml",
        "views/product_template_views.xml",
    ],
    "installable": True,
    "auto_install": ["maintenance", "stock"],
    "license": "GPL-2",
}
