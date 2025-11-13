# Rowlytics

Rowlytics is a Flask-powered analytics platform that delivers data-driven insights for rowing programs. The project combines a Python backend, a responsive HTML/CSS/JS landing page, and AWS integrations (coming soon) to help teams run smarter.

## Contributors
- Noah Wisniewski
- Kassie Bankson
- Aidan Mahaffey
- Evan Osborne

## Tech stack
- **Backend:** Python 3.12, Flask, gunicorn, boto3 for AWS integrations
- **Frontend:** Jinja templates, vanilla HTML/CSS/JavaScript
- **Tooling:** flake8, isort, bandit, pytest, pre-commit, GitHub Actions

## Project layout
```
Rowlytics/
├── app.py                   # Flask entry point
├── rowlytics_app/           # Application package
│   ├── __init__.py          # App factory
│   ├── routes.py            # Public blueprint + landing page route
│   ├── templates/index.html # Landing page template
│   └── static/              # CSS/JS assets
├── scripts/dev_server.sh    # Helper to install deps + run the dev server
├── requirements.txt         # Runtime dependencies
├── requirements-dev.txt     # Runtime + lint/test tooling
├── Makefile                 # Common commands (install, lint, run, ...)
├── .github/workflows/ci.yml # CI enforcing flake8 & friends on push/PR
├── .pre-commit-config.yaml  # Local git hook automation
└── tests/                   # Pytest smoke tests
```

## Getting started
1. Ensure Python 3.12+ and `pip` are installed.
2. (Optional) Create and activate a virtual environment.
3. Install dependencies and register pre-commit hooks:
   ```bash
   make dev-install
   ```
4. Run the development server with hot reload:
   ```bash
   make run
   # or use the helper script which also bootstraps a .venv
   ./scripts/dev_server.sh
   ```
5. Open http://127.0.0.1:5000 to see the landing page.

## Quality gates
- `make lint` runs flake8, isort, and bandit.
- `make test` runs pytest.
- `make check` runs both lint + tests.
- `.pre-commit-config.yaml` mirrors the CI checks locally. Enable it with `pre-commit install` (already done via `make dev-install`).

GitHub Actions (`.github/workflows/ci.yml`) runs on every push and pull request to `main`. A push will fail unless flake8 and the rest of the tooling succeed, ensuring code going to GitHub stays compliant.

## Environment variables
| Name | Description | Default |
| --- | --- | --- |
| `ROWLYTICS_SECRET_KEY` | Flask secret key | `dev-secret-key` |
| `ROWLYTICS_ENV` | Custom flag for runtime environment | `development` |
| `PORT` | Port for the dev server | `5000` |
| `FLASK_DEBUG` | Enable debug mode when running via `python app.py` | `0` |

## Next steps
- Flesh out the Flask backend (APIs, persistence, AWS services).
- Replace the landing page form action with a real backend endpoint.
- Add integration/unit tests as features are implemented.
