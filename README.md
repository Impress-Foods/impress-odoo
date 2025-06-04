
<!-- /!\ Non OCA Context : Set here the badge of your runbot / runboat instance. -->
[![Pre-commit Status](https://github.com/Impress-Foods/impress-odoo/actions/workflows/pre-commit.yml/badge.svg?branch=17.0)](https://github.com/Impress-Foods/impress-odoo/actions/workflows/pre-commit.yml?query=branch%3A17.0)
[![Build Status](https://github.com/Impress-Foods/impress-odoo/actions/workflows/test.yml/badge.svg?branch=17.0)](https://github.com/Impress-Foods/impress-odoo/actions/workflows/test.yml?query=branch%3A17.0)
[![codecov](https://codecov.io/gh/Impress-Foods/impress-odoo/graph/badge.svg?token=INNNC7JQ2E)](https://codecov.io/gh/Impress-Foods/impress-odoo)
<!-- /!\ Non OCA Context : Set here the badge of your translation instance. -->

<!-- /!\ do not modify above this line -->

# Impress Odoo

Odoo modules for Impress Foods

<!-- /!\ do not modify below this line -->

<!-- prettier-ignore-start -->

[//]: # (addons)

Available addons
----------------
addon | version | maintainers | summary
--- | --- | --- | ---
[audit_reports](audit_reports/) | 17.0.0.0.1 |  | Audit_reports Summary
[delivery_status_multi_step](delivery_status_multi_step/) | 17.0.1.0.0 |  | Adds usefull delivery statuses for multi-step delivery flows
[documents_archive](documents_archive/) | 17.0.0.1.0 |  | Module to allow a "soft" archive feature for documents.
[gs1_sequences](gs1_sequences/) | 17.0.1.0.0 |  | Adds GS1 check digit option on sequences
[impress_account_report](impress_account_report/) | 17.0.0.1.0 |  | Module to customize the accounting reports
[impress_accounting](impress_accounting/) | 17.0.0.0.1 |  | Impress_accounting Summary
[impress_barcode](impress_barcode/) | 17.0.1.0.0 |  | Customizations to barcode app
[impress_billback](impress_billback/) | 17.0.0.1.0 |  | Impress_billback Summary
[impress_check_customizations](impress_check_customizations/) | 17.0.0.1.0 |  | Small tweaks to l10n_ca_check to allow better printing on preprinted checks
[impress_cleaning](impress_cleaning/) | 17.0.0.1.0 |  | Module to handle cleanings for Impress Foods
[impress_deposit](impress_deposit/) | 17.0.0.1.1 |  | Module to allow the management of deposits for containers
[impress_expiration_lot](impress_expiration_lot/) | 17.0.0.1.0 |  | Module that allows to automatically calculate to correct dates for a lot's expiry,
[impress_lot_lab](impress_lot_lab/) | 17.0.0.1.2 |  | Impress_lot_lab Summary
[impress_maintenance](impress_maintenance/) | 17.0.0.0.1 |  | Impress_maintenance Summary
[impress_maintenance_quality_mgmt](impress_maintenance_quality_mgmt/) | 17.0.1.0.0 |  | Impress Foods quality management for maintenance
[impress_maintenance_worksheets](impress_maintenance_worksheets/) | 17.0.0.0.1 |  | Impress_maintenance_worksheets Summary
[impress_manufacturing_customizations](impress_manufacturing_customizations/) | 17.0.0.1.1 |  | " Customizations for the manufacturing module
[impress_prevent_workorder_bo](impress_prevent_workorder_bo/) | 17.0.0.1.0 |  | Prevents the creation of BO on workorder validation when producing less than expected.
[impress_production_billing](impress_production_billing/) | 17.0.0.1.2 |  | Module to allow billing of MOs directly through SOs
[impress_project_billing_production](impress_project_billing_production/) | 17.0.0.1.0 |  | Impress Foods customization to allow billing of MOs through projects DEPRECATED
[impress_purchase_customizations](impress_purchase_customizations/) | 17.0.1.0.0 |  | Impress Foods specific purchase customizations
[impress_quality_customizations](impress_quality_customizations/) | 17.0.0.1.0 |  | Customizations for the quality module developped in-house by Impress Foods SEC
[impress_quality_logs](impress_quality_logs/) | 17.0.0.1.2 |  | Implements many quality logs used by ^ Impress Foods for quality control
[impress_quality_worksheets](impress_quality_worksheets/) | 17.0.0.1.1 |  | Worksheets to use in conjunction with Impress Quality Logs
[impress_sales_customizations](impress_sales_customizations/) | 17.0.0.1.0 |  | " Customizations for the sales module
[impress_stock_customizations](impress_stock_customizations/) | 17.0.0.1.1 |  | Customizations for the stock module developped in-house by Impress Foods SEC
[impress_stock_worksheets](impress_stock_worksheets/) | 17.0.25.01.14 |  | Impress_stock_worksheets Summary
[julian_sequence](julian_sequence/) | 17.0.0.1.0 |  | Adds a sequence type to follow a YYDDD format
[label_printing_wizard](label_printing_wizard/) | 17.0.1.0.0 |  | Adds different wizards to print custom labels for products and lots
[maintenance_consume_stock](maintenance_consume_stock/) | 17.0.0.0.2 |  | Module to allow stock usage in maintenance requests
[maintenance_documents](maintenance_documents/) | 17.0.1.0.0 |  | Bridge module between Maintenance and Documents
[maintenance_product_list](maintenance_product_list/) | 17.0.1.0.0 |  | Allows to link products to maintenance equipments
[maintenance_quality](maintenance_quality/) | 17.0.0.0.1 |  | Bridge module between Maintenance and Quality Control
[mrp_add_qc_note_shop_floor](mrp_add_qc_note_shop_floor/) | 17.0.0.1.0 |  | Mrp_add_qc_note_shop_floor Summary
[mrp_fast_allocation](mrp_fast_allocation/) | 17.0.0.0.1 |  | Adds an action to assign all moves in the allocation report for a production order
[production_log_note](production_log_note/) | 17.0.0.1.2 |  | Backport of V18 feature where a note can be added to a production order
[warehouse_billing](warehouse_billing/) | 17.0.0.0.1 |  | This module allows billing customers based on the warehouse space utilized by their products on a daily basis. Features: - Track daily warehouse space usage per client - Configure billing rates - Generate monthly invoices automatically

[//]: # (end addons)

<!-- prettier-ignore-end -->

## Licenses

This repository is licensed under [AGPL-3.0](LICENSE).

However, each module can have a totally different license, as long as they adhere to Cédric Paradis
policy. Consult each module's `__manifest__.py` file, which contains a `license` key
that explains its license.

----
<!-- /!\ Non OCA Context : Set here the full description of your organization. -->
