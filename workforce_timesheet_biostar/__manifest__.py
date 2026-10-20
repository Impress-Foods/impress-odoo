{
    "name": "Workforce Timesheets - BioStar 2",
    "version": "19.0.1.4.0",
    "category": "Human Resources/Workforce",
    "summary": "Pull punches from a BioStar 2 into workforce.timesheet sessions.",
    "author": "Cédric Paradis",
    "website": "https://github.com/Impress-Foods/impress-odoo",
    "license": "LGPL-3",
    "depends": [
        "workforce_timesheet",
    ],
    "external_dependencies": {
        "python": ["pydantic", "requests"],
    },
    "data": [
        "security/biostar_backend_security.xml",
        "security/ir.model.access.csv",
        "data/biostar_cron.xml",
        "views/workforce_employee_views.xml",
        "views/biostar_backend_views.xml",
    ],
    "application": False,
    "installable": True,
}
