# Rowlytics

Rowlytics is a web based application that will help rowers to improve their rowing technique on the erg.

## Contributors
- Noah Wisniewski
- Kassie Bankson
- Aidan Mahaffey :)
- Evan Osborne

## Getting started
1. Make sure Python and `pip` are installed.
2. (Optional) Create and activate a virtual environment.
3. Install dependencies and register pre-commit hooks:
   ```bash
   make dev-install
   ```
4. Run the development server with hot reload:
   ```bash
   ./scripts/dev_server.sh
   ```

## Quality gates
- `make lint` runs flake8 and isort.
- `make test` runs pytest.
- `make check` runs both lint + tests.
- `.pre-commit-config.yaml` mirrors the CI checks locally. Enable it with `pre-commit install` (already done via `make dev-install`).

GitHub Actions (`.github/workflows/ci.yml`) runs on every push and pull request to `main`. A push will fail unless all quality gates are passed.
