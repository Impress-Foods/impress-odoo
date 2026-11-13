{
    "name": "EDI X12",
    "version": "19.0.1.0.0",
    "summary": """ X12 reading, writing and validation through pyx12 """,
    "author": "Cédric Paradis",
    "website": "https://github.com/Impress-Foods/impress-odoo",
    "category": "Hidden",
    "depends": [
        "edi_core_oca",
        "integration_queue_job",
        "partner_identification_import",
    ],
    "data": [
        "data/edi_backend_type.xml",
        "data/partner_id_category.xml",
        "data/ir_sequence.xml",
        "data/queue_job.xml",
        "views/edi_backend_views.xml",
        "views/edi_exchange_record_views.xml",
    ],
    "external_dependencies": {
        "python": ["defusedxml>=0.7", "pyx12==4.0.0"],
    },
    "installable": True,
    "license": "AGPL-3",
}
