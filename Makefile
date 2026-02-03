.PHONY: test test-unit test-integration test-cov test-cov-html clean install lint format

install:
	pip install -r requirements.txt
	npm install

test:
	pytest

test-unit:
	pytest tests/unit/ -v

test-integration:
	pytest tests/integration/ -v

test-cov:
	pytest --cov=tools --cov=run_audit --cov-report=term-missing --cov-report=xml

test-cov-html:
	pytest --cov=tools --cov=run_audit --cov-report=html --cov-report=term-missing
	@echo "Coverage report generated in htmlcov/index.html"

test-cov-check:
	pytest --cov=tools --cov=run_audit --cov-report=term-missing
	coverage report --fail-under=70

lint:
	flake8 run_audit.py list_tabs.py get_service_account_email.py validate_setup.py tools/ --count --select=E9,F63,F7,F82 --show-source --statistics
	flake8 run_audit.py list_tabs.py get_service_account_email.py validate_setup.py tools/ --count --exit-zero --max-complexity=10 --max-line-length=127 --statistics

format:
	black run_audit.py list_tabs.py get_service_account_email.py validate_setup.py tools/
	isort run_audit.py list_tabs.py get_service_account_email.py validate_setup.py tools/

clean:
	rm -rf .pytest_cache
	rm -rf .coverage
	rm -rf htmlcov
	rm -rf coverage.xml
	rm -rf coverage.svg
	rm -rf __pycache__
	find . -type d -name "__pycache__" -exec rm -rf {} +
	find . -type f -name "*.pyc" -delete
	find . -type f -name "*.pyo" -delete
	find . -type f -name "*.coverage" -delete

help:
	@echo "Available commands:"
	@echo "  make install          - Install Python and Node.js dependencies"
	@echo "  make test             - Run all tests"
	@echo "  make test-unit        - Run unit tests only"
	@echo "  make test-integration - Run integration tests only"
	@echo "  make test-cov         - Run tests with coverage report"
	@echo "  make test-cov-html    - Run tests with HTML coverage report"
	@echo "  make test-cov-check   - Run tests and check 70% coverage threshold"
	@echo "  make lint             - Run linting checks"
	@echo "  make format           - Format code with black and isort"
	@echo "  make clean            - Clean up test artifacts"
