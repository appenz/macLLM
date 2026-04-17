.PHONY: run test screenshot test-llm test-calendar test-things test-ui test-ui-external debug-render

uv = /opt/homebrew/bin/uv

run:
	$(uv) run -m macllm --debug

run-debug:
	$(uv) run -m macllm --debug --debuglitellm

QUERY ?= What is the URL of Google 

test-llm:
	QUERY="$(QUERY)" $(uv) run python -m pytest -v -s test/manual_tests/llm_check.py

test:
	$(uv) run python -m pytest -rx -v

test-external:
	$(uv) run python -m pytest -v -m external

test-calendar:
	$(uv) run python -m pytest -v -m calendar

test-things:
	$(uv) run python -m pytest -v -m things

test-ui:
	$(uv) run python -m pytest -v -m uitest

test-ui-external:
	$(uv) run python -m pytest -v -m uitest_external

screenshot:
	$(uv) run -m macllm --show-window &
	sleep 3
	$(uv) run -m macllm.utils.screenshot --output ./macllm_test_screenshot.png
	pkill -f "macllm --show-window" || true

debug-render:
	rm -f ./debug_screenshot.png
	$(uv) run -m macllm --query "$(QUERY)" --screenshot ./debug_screenshot.png
