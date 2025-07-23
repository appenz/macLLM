.PHONY: run test

uv = /opt/homebrew/bin/uv

run:
	$(uv) run -m --env-file .env macllm --debug 

test:
	$(uv) run python -m pytest test/ -v

