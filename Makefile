.PHONY: build

install_uv:
	@if ! command -v uv >/dev/null 2>&1; then \
  		curl -LsSf https://astral.sh/uv/install.sh | sh; \
  	fi

setup:
	make install_uv
	uv venv
	uv pip install .[test,publish,dev,capnproto] -U

format:
	./.venv/bin/ruff format .

lint:
	./.venv/bin/ruff check .

test:
	./.venv/bin/pytest -s -v tests/unit

run:
	./.venv/bin/xconn example:app --directory examples/simple

build:
	uv build

publish:
	uv publish

run-docs:
	mkdocs serve

build-docs:
	mkdir -p site/xconn/
	mkdocs build -d site/xconn/python

clean-docs:
	rm -rf site/

install-nxt:
	@if ! command -v nxt >/dev/null 2>&1; then \
  		sudo snap install nxt-router --classic --edge; \
  	fi


integration:
	make install-nxt
	./.venv/bin/pytest -s -v tests/integration/

aat:
	./.venv/bin/pytest -s -v tests/aat/
