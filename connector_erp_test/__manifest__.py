{
    "name": "ERP Connector - Test Support",
    "summary": "Test models and components for the ERP connector framework",
    "version": "19.0.0.1.0",
    "author": "Cédric Paradis",
    "website": "https://github.com/Impress-Foods/impress-odoo",
    "category": "Hidden",
    "depends": ["connector_erp", "connector_erp_stock"],
    "data": ["security/ir.model.access.csv", "data/queue_job_data.xml"],
    "installable": True,
    "application": False,
    "license": "LGPL-3",
}
