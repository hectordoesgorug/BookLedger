# Test report

Date: 2026-10-17

## Automated tests
- Command: `.venv\Scripts\python.exe -m pytest` (with `TEMP` and `TMP` redirected to a writable task temp directory)
- Syntax check: `.venv\Scripts\python.exe -m py_compile src/bookledger/app.py src/bookledger/ui/forms.py src/bookledger/services/catalog.py` — passed.
- Diff check: `git diff --check` — passed; Git reported only its configured LF-to-CRLF conversion notices.
- Platform: Windows, Python 3.14.6, pytest 9.1.1
- Result: **35 passed, 2 skipped**
- Coverage includes destroyed/stale Treeview callback handling and Copy ID matching, catalog validation and duplicate rules, distinct-record versus copy counts, copy-level filters, finite monetary values, backup creation/verification/restoration, Add/Edit layout, service-side validation, simulated connection and scan retry, ISBN not-found versus technical lookup failures, per-provider timeouts, stale-result protection, and Clear/Cancel behavior.
- Two Tk UI tests were skipped. This Python installation has incomplete Tcl/Tk files (`tk.tcl`, `ttk.tcl`, and `init.tcl` are missing), so Tk windows cannot be initialized reliably in this environment. The UI tests that initialized Tk passed.
- Metadata provider tests use mocked responses; no live provider request was made.

## GUI verification
- A prior virtual-display smoke test created the initial seven screens and intake form before the current layout reconciliation.
- The revised Add Book layout and Catalog grid have not been visually reviewed on native Windows. This Python installation's incomplete Tcl/Tk files prevent reliable Tk initialization.

## Not yet verified
- Native Windows visual review of the revised Add Book layout, Catalog grid, and Inventory table; executable packaging.
- Large-catalog performance with a production-sized data set.
- Live metadata-provider behavior and network failures against external services.
- Restore failure injection / power-loss recovery.
- Full CSV/Excel import-export, richer reports, and BookLedger Mobile integration.

This is an early development build, not a release candidate. Keep independent backups of any important data while testing.
