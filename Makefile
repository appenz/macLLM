.PHONY: run test

uv = /opt/homebrew/bin/uv

run:
	$(uv) run -m --env-file .env macllm --debug 

test:
	$(uv) run --env-file .env python -m pytest -rx -v

test-external:
	$(uv) run --env-file .env python -m pytest -v -m external

