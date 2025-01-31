.PHONY: setup test dist coverage lint typecheck clean run client device server

setup: clean
	python -m venv env
	env/bin/pip install -e .[dev]
	env/bin/pre-commit install
	mkdir ssl
	openssl req -new -x509 -days 365 -nodes -subj "/C=/ST=/L=/O=/CN=" -out ssl/server.cert -keyout ssl/server.key

test:
	env/bin/pre-commit run --all-files

dist:
	rm -rf dist
	env/bin/python -m build --wheel

lint:
	env/bin/pre-commit run --all-files pylint

typecheck:
	env/bin/pre-commit run --all-files mypy

clean:
	rm -rf env build dist *.egg-info ssl htmlcov

####################

client:
	env/bin/python examples/client.py

device:
	env/bin/python examples/device.py

server:
	env/bin/python examples/server.py
