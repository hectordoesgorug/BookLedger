# Initial test report

Date: 2026-10-17

## Automated tests
- Result: **12 passed**
- Coverage includes ISBN-10/13 check digits, manual override, required-field/genre/price validation, copy creation and numbering, duplicate lookup behavior, default location, all four statuses, sale-history retention, photo compression, backup verification, and backup restoration with relative photo paths.

## GUI smoke test
- Constructed the main window under a virtual X display.
- Successfully created each of the seven initial screens: Dashboard, Catalog, Inventory, Acquisitions, Sales, Reports, Settings.
- Constructed the intake/edit form and verified default status/location values and inline field highlighting.

## Not yet verified
- Native Windows rendering and executable packaging.
- Large-catalog performance with a production-sized data set.
- All metadata-provider edge cases and network failures.
- Restore failure injection / power-loss recovery.
- Full CSV/Excel import-export, richer reports, and Android companion integration.

This is an early development build, not a release candidate. Keep independent backups of any important data while testing.
