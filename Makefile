.PHONY: run

uv = /opt/homebrew/bin/uv

run:
	$(uv) run -m --env-file .env macllm --debug 