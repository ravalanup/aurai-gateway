# Contributing to aurai-gateway

## Principles
- **Aliases and policy as code.** Model changes and team changes go through pull requests.
- **No secrets in the repository.** Keys come from the environment or a secrets manager.
- **Synthetic data only.** Tests and examples use invented names and numbers.
- **Governance stays testable.** A rule that matters (tier coverage, fallback safety) has a test.

## Before opening a pull request
1. `pytest` and `ruff check .` pass.
2. `aurai-teamctl validate teams/teams.yaml` passes.
3. If you changed models or fallbacks, you updated both `config/model-catalog.yaml` and `charts/aurai-gateway/values.yaml`.
4. If you changed `pii.yaml`, you added or updated tests, and higher tiers still cover everything lower tiers do.
5. Documentation reflects the change.

## Conventions
- Python 3.11+, formatted with `ruff format`.
- Commit messages: imperative mood with a prefix (`feat:`, `fix:`, `docs:`, `test:`, `ci:`, `chore:`).
- Chart values documented in `values.yaml`.

## Reviews
Changes to the PII policy, model catalog, team budgets or network policy need a second reviewer.
