install_uv:
	@if ! command -v uv >/dev/null 2>&1; then \
  		curl -LsSf https://astral.sh/uv/install.sh | sh; \
  	fi

setup:
	make install_uv
	uv venv
	uv pip install .[test,publish]

lint:
	./.venv/bin/ruff format .

check-lint:
	./.venv/bin/ruff check .

test:
	./.venv/bin/pytest -s -v

run:
	./.venv/bin/xconn example:app --directory examples/simple

publish-build:
	rm -rf ./dist ./build
	.venv/bin/python -m build --sdist
	.venv/bin/twine check dist/*
	@echo ========================================================
	@echo
	@echo now run .venv/bin/twine upload dist/newly_created.tar.gz


run-docs:
	mkdocs serve

build-docs:
	mkdir -p site/xconn/
	mkdocs build -d site/xconn/python

clean-docs:
	rm -rf site/
