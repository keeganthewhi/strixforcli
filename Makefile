.PHONY: help install dev-install format lint type-check test test-cov clean pre-commit setup-dev

help:
	@echo "Available commands:"
	@echo "  setup-dev     - Install all development dependencies and setup pre-commit"
	@echo "  install       - Install production dependencies"
	@echo "  dev-install   - Install development dependencies"
	@echo ""
	@echo "Code Quality:"
	@echo "  format        - Format code with ruff"
	@echo "  lint          - Lint code with ruff and pylint"
	@echo "  type-check    - Run type checking with mypy and pyright"
	@echo "  security      - Run security checks with bandit"
	@echo "  check-all     - Run all code quality checks"
	@echo ""
	@echo "Testing:"
	@echo "  test          - Run tests with pytest"
	@echo "  test-cov      - Run tests with coverage reporting"
	@echo ""
	@echo "Development:"
	@echo "  pre-commit    - Run pre-commit hooks on all files"
	@echo "  clean         - Clean up cache files and artifacts"

install:
	uv sync --no-dev

dev-install:
	uv sync

setup-dev: dev-install
	uv run pre-commit install
	@echo "✅ Development environment setup complete!"
	@echo "Run 'make check-all' to verify everything works correctly."

format:
	@echo "🎨 Formatting code with ruff..."
	uv run ruff format .
	@echo "✅ Code formatting complete!"

lint:
	@echo "🔍 Linting code with ruff..."
	uv run ruff check . --fix
	@echo "📝 Running additional linting with pylint..."
	uv run pylint strix/ --score=no --reports=no
	@echo "✅ Linting complete!"

type-check:
	@echo "🔍 Type checking with mypy..."
	uv run mypy strix/
	@echo "🔍 Type checking with pyright..."
	uv run pyright strix/
	@echo "✅ Type checking complete!"

security:
	@echo "🔒 Running security checks with bandit..."
	uv run bandit -r strix/ -c pyproject.toml
	@echo "✅ Security checks complete!"

check-all: format lint type-check security
	@echo "✅ All code quality checks passed!"

test:
	@echo "🧪 Running tests..."
	uv run pytest -v
	@echo "✅ Tests complete!"

test-cov:
	@echo "🧪 Running tests with coverage..."
	uv run pytest -v --cov=strix --cov-report=term-missing --cov-report=html
	@echo "✅ Tests with coverage complete!"
	@echo "📊 Coverage report generated in htmlcov/"

pre-commit:
	@echo "🔧 Running pre-commit hooks..."
	uv run pre-commit run --all-files
	@echo "✅ Pre-commit hooks complete!"

clean:
	@echo "🧹 Cleaning up cache files..."
	find . -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name ".pytest_cache" -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name ".mypy_cache" -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name ".ruff_cache" -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name "htmlcov" -exec rm -rf {} + 2>/dev/null || true
	find . -name "*.pyc" -delete 2>/dev/null || true
	find . -name ".coverage" -delete 2>/dev/null || true
	@echo "✅ Cleanup complete!"

dev: format lint type-check test
	@echo "✅ Development cycle complete!"

# ---------------------------------------------------------------
# strixnoapi convenience targets
# ---------------------------------------------------------------

.PHONY: verify test-strixnoapi test-upstream quickstart fresh-clone-test

verify:
	@echo "🔍 strixnoapi verification (ruff + tests)"
	uv run ruff check strixnoapi/
	uv run pytest tests/strixnoapi/ --no-cov

test-strixnoapi:
	uv run pytest tests/strixnoapi/ --no-cov -v

test-upstream:
	uv run pytest tests/ --ignore=tests/strixnoapi --ignore=tests/runtime --no-cov

quickstart:
	@echo "🚀 strixnoapi quickstart"
	uv sync
	uv run strix setup --auto
	uv run strix doctor

fresh-clone-test:
	@echo "🧪 Simulating fresh-user install in /tmp/strix-noapi-freshtest"
	rm -rf /tmp/strix-noapi-freshtest
	git clone https://github.com/keeganthewhi/strix-noapi.git /tmp/strix-noapi-freshtest
	cd /tmp/strix-noapi-freshtest && uv sync && uv run pytest tests/strixnoapi/ --no-cov -q
	cd /tmp/strix-noapi-freshtest && uv run strix version
	cd /tmp/strix-noapi-freshtest && uv run strix doctor || echo "(doctor reports issues; expected on CI without auth'd CLI)"
