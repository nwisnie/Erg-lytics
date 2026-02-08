PYTHON ?= python3
PIP ?= $(PYTHON) -m pip
APP_MODULE = app.py

.PHONY: install dev-install lint fmt test check run hooks clean

install:
	$(PYTHON) -m pip install --upgrade pip
	$(PIP) install -r requirements.txt

dev-install:
	$(PYTHON) -m pip install --upgrade pip
	$(PIP) install -r requirements-dev.txt
	pre-commit install

lint:
	flake8 rowlytics_app $(APP_MODULE)
	isort --check-only rowlytics_app $(APP_MODULE)

fmt:
	isort rowlytics_app $(APP_MODULE)

hooks:
	pre-commit run --all-files

check: lint test

test:
	$(PYTHON) -m pytest

run:
	FLASK_APP=$(APP_MODULE) flask run --debug

clean:
	rm -rf __pycache__ */__pycache__ .pytest_cache .mypy_cache
