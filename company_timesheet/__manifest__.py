{
    "name": "Company Timesheets",
    "version": "19.0.1.2.0",
    "category": "Human Resources/Employees",
    "summary": "Lean work-time sessions derived from batch-imported punch data.",
    "author": "Cédric Paradis",
    "website": "https://github.com/Impress-Foods/impress-odoo",
    "license": "LGPL-3",
    "depends": [
        "company_employee",
    ],
    "external_dependencies": {
        "python": ["pydantic"],
    },
    "data": [
        "security/company_timesheet_security.xml",
        "security/ir.model.access.csv",
        "data/company_timesheet_cron.xml",
        "views/company_timesheet_views.xml",
        "views/company_punch_views.xml",
        "views/res_company_views.xml",
        "views/company_timesheet_menus.xml",
        "views/company_timesheet_portal_templates.xml",
    ],
    "application": False,
    "installable": True,
}
