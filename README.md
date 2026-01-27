<!-- /!\ Non OCA Context : Set here the badge of your runbot / runboat instance. -->
[![Pre-commit Status](https://github.com/Impress-Foods/impress-odoo/actions/workflows/pre-commit.yml/badge.svg?branch=19.0)](https://github.com/Impress-Foods/impress-odoo/actions/workflows/pre-commit.yml?query=branch%3A19.0)
[![Build Status](https://github.com/Impress-Foods/impress-odoo/actions/workflows/test.yml/badge.svg?branch=19.0)](https://github.com/Impress-Foods/impress-odoo/actions/workflows/test.yml?query=branch%3A19.0)
[![codecov](https://codecov.io/gh/Impress-Foods/impress-odoo/branch/19.0/graph/badge.svg)](https://codecov.io/gh/Impress-Foods/impress-odoo)
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
[gs1_sequences](gs1_sequences/) | 19.0.1.0.0 |  | Adds GS1 check digit option on sequences
[impress_datetime_widget](impress_datetime_widget/) | 19.0.0.1.0 |  | Module to restore the default DateTime picker widget behavior from Odoo V15 where the default time selected when a widget is opened is the current time without any rounding.
[impress_expiration_lot](impress_expiration_lot/) | 19.0.0.1.0 |  | Module that allows to automatically calculate to correct dates for a lot's expiry,
[impress_lot_lab](impress_lot_lab/) | 19.0.0.1.2 |  | Impress_lot_lab Summary
[impress_production_billing](impress_production_billing/) | 19.0.0.1.2 |  | Module to allow billing of MOs directly through SOs
[impress_quality_logs](impress_quality_logs/) | 19.0.0.1.2 |  | Implements many quality logs used by Impress Foods for quality control
[impress_quality_worksheets](impress_quality_worksheets/) | 19.0.0.1.1 |  | Worksheets to use in conjunction with Impress Quality Logs
[julian_sequence](julian_sequence/) | 19.0.0.1.0 |  | Adds a sequence type to follow a YYDDD format
[package_consume_stock](package_consume_stock/) | 19.0.1.0.0 |  | Automatically consume packaging material when putting in package

[//]: # (end addons)

<!-- prettier-ignore-end -->

## Licenses

This repository is licensed under [AGPL-3.0](LICENSE).

However, each module can have a totally different license, as long as they adhere to
Impress Foods policy. Consult each module's `__manifest__.py` file, which contains a
`license` key that explains its license.

---

<!-- /!\ Non OCA Context : Set here the full description of your organization. -->
