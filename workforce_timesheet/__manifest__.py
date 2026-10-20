{
    "name": "Workforce Timesheets",
    "version": "19.0.1.5.0",
    "category": "Human Resources/Workforce",
    "summary": "Lean work-time sessions derived from batch-imported punch data.",
    "author": "Cédric Paradis",
    "website": "https://github.com/Impress-Foods/impress-odoo",
    "license": "LGPL-3",
    "depends": [
        "workforce",
    ],
    "external_dependencies": {
        "python": ["pydantic"],
    },
    "data": [
        "security/workforce_timesheet_security.xml",
        "security/ir.model.access.csv",
        "views/workforce_timesheet_views.xml",
        "views/workforce_punch_views.xml",
        "views/res_company_views.xml",
        "views/workforce_timesheet_menus.xml",
        "views/workforce_timesheet_portal_templates.xml",
    ],
    "application": False,
    "installable": True,
}
