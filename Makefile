.PHONY: run test screenshot test-llm test-calendar test-things debug-render

uv = /opt/homebrew/bin/uv
env_vars = KMP_DUPLICATE_LIB_OK=TRUE

run:
	$(env_vars) $(uv) run -m --env-file .env macllm --debug 

run-debug:
	$(env_vars) $(uv) run -m --env-file .env macllm --debug --debuglitellm

QUERY ?= What is the URL of Google 

test-llm:
	$(env_vars) QUERY="$(QUERY)" $(uv) run --env-file .env python -m pytest -v -s test/manual_tests/llm_check.py

test:
	$(env_vars) $(uv) run --env-file .env python -m pytest -rx -v

test-external:
	$(env_vars) $(uv) run --env-file .env python -m pytest -v -m external

test-calendar:
	$(env_vars) $(uv) run --env-file .env python -m pytest -v -m calendar

test-things:
	$(env_vars) $(uv) run --env-file .env python -m pytest -v -m things

screenshot:
	$(env_vars) $(uv) run -m --env-file .env macllm --show-window &
	sleep 3
	$(env_vars) $(uv) run -m macllm.utils.screenshot --output ./macllm_test_screenshot.png
	pkill -f "macllm --show-window" || true

debug-render:
	rm -f ./debug_screenshot.png
	$(env_vars) $(uv) run -m --env-file .env macllm --query "$(QUERY)" --screenshot ./debug_screenshot.png
