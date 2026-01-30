{
    "name": "Maintenance - Documents",
    "version": "19.0.1.0.0",
    "summary": """ Bridge module between Maintenance and Documents """,
    "author": "Cédric Paradis",
    "website": "https://github.com/impress-foods/impress-odoo",
    "category": "Hidden",
    "depends": [
        "documents",
        "base_maintenance",
    ],
    "data": [
        "views/maintenance_equipment_views.xml",
        "data/document_folder.xml",
    ],
    "installable": True,
    "auto_install": True,
    "license": "GPL-2",
}
