# AGENTS.md — BookLedger Development Guidelines

## 1. Project Overview

BookLedger is a portable, offline-first Windows desktop application for managing a personal book collection, physical copies, inventory, sales, and backups.

- Language: Python
- UI: Tkinter with ttkbootstrap
- Database: SQLite
- Packaging: Python packaging with a future portable Windows distribution
- Architecture: Modular application with a clear separation between UI, services, database access, and configuration.

Read `README.md` and the relevant documentation in `docs/` before making substantial changes.

## 2. Core Development Principles

- Preserve offline-first functionality. Core features must not require an internet connection.
- Prefer simple, maintainable solutions over unnecessary abstractions or dependencies.
- Keep the application modular. Do not introduce a monolithic application module.
- Avoid unrelated refactoring when implementing a focused fix.
- Do not silently change approved product requirements or data-model decisions.
- Do not invent features that have not been approved.
- Preserve existing user data and avoid destructive database changes.
- Treat backups, restoration, photo integrity, and data validation as critical functionality.

## 3. Architecture

- Keep UI code in `src/bookledger/ui/`.
- Keep business logic in `src/bookledger/services/`.
- Keep database implementation and schema management in `src/bookledger/db/`.
- Keep application startup in `src/bookledger/app.py`.
- Keep configuration and path handling in their existing modules.
- Avoid putting business rules directly in UI event handlers.
- Use the existing database and service interfaces where practical.
- Manage SQLite connections and other resources explicitly, including on exceptional execution paths.
- Do not add dependencies without explaining why they are needed.

Inspect the existing implementation before deciding where code belongs.

## 4. Product and Data Rules

- One bibliographic record may have multiple physical copies.
- Each physical copy has a unique, stable Copy ID.
- ISBNs are optional, and different ISBNs must remain separate bibliographic records.
- Each physical copy has its own required photo, format, condition, location, price, and status.
- The approved genre list is fixed unless a product requirement explicitly authorizes a change.
- The selling status and sales history of one copy must not silently affect another copy.
- Sold copies and their sales records must remain available for historical reporting.
- Distinguish personal inventory valuation from actual sales revenue and publisher SRP.
- Missing optional metadata must not cause unnecessary failures or overwrite manually entered information.

Consult the product specification in `docs/` for the complete requirements. If documentation and implementation disagree, report the discrepancy rather than guessing which should change.

## 5. Reliability and Security

- Validate inputs at service and data boundaries, not only in the UI.
- Reject non-finite monetary values such as NaN and positive or negative infinity.
- Do not bypass validation to make a test pass.
- Treat imported archives and their contents as untrusted input.
- Validate backup contents and database integrity before restoration.
- Avoid unsafe archive extraction, path traversal, accidental data loss, and incomplete restores.
- Close database connections, files, and other resources reliably.
- Keep temporary files and generated test data isolated from real user data.
- Never include passwords, API keys, private credentials, or personal data in source control.

## 6. Testing

- Use the project's configured test framework and virtual environment.
- Run the full test suite after meaningful changes:
  `.venv\Scripts\python.exe -m pytest`
- Add regression tests for bug fixes.
- Test normal cases, invalid inputs, boundary conditions, and failure paths where relevant.
- For data-sensitive functionality, test that failures do not corrupt existing data.
- Do not skip or weaken tests merely to obtain a passing result.
- Report the exact commands executed and their actual results.
- Distinguish tests that passed from tests that could not run.
- Consider Windows-specific behavior, especially file locking, path handling, and temporary directories.

## 7. Change Workflow

Before editing:
1. Inspect relevant source files, tests, and documentation.
2. Identify the root cause or requirement.
3. Outline the intended changes and any risks.

While editing:
1. Make the smallest coherent change that solves the problem.
2. Follow existing naming, formatting, and architectural conventions.
3. Update documentation when behavior or setup instructions change.
4. Avoid unrelated modifications.

After editing:
1. Review the complete diff.
2. Run relevant tests, then the full test suite when practical.
3. Report changed files, implementation decisions, test results, and unresolved issues.
4. Do not claim verification that was not performed.
5. Do not commit changes unless explicitly instructed.

## 8. Documentation and Project Status

- Keep `README.md`, product specifications, architecture notes, and testing instructions consistent with the implementation.
- Update `PROGRESS.md` to distinguish implemented, partially implemented, and planned features when appropriate.
- Update `TEST_REPORT.md` when project testing status materially changes.
- Record significant architectural decisions when they affect future development.
- Do not describe planned features as implemented.

## 9. Scope and Approval

- Follow the approved product requirements.
- Ask for clarification before making significant product, schema, migration, or architectural decisions that are not covered by the requirements.
- Explain trade-offs when multiple viable approaches exist.
- Do not commit, push, delete user data, or perform destructive operations without explicit authorization.
- Prefer changes that preserve the project's portability and offline operation.