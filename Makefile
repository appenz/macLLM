.PHONY: run test screenshot test-llm

uv = /opt/homebrew/bin/uv
env_vars = KMP_DUPLICATE_LIB_OK=TRUE

run:
	$(env_vars) $(uv) run -m --env-file .env macllm --debug 

run-debug:
	$(env_vars) $(uv) run -m --env-file .env macllm --debug --debuglitellm

QUERY ?= What is 2 + 2? Answer with just the number.

test-llm:
	$(env_vars) QUERY="$(QUERY)" $(uv) run --env-file .env python -m pytest -v -s test/manual_tests/llm_check.py

test:
	$(env_vars) $(uv) run --env-file .env python -m pytest -rx -v

test-external:
	$(env_vars) $(uv) run --env-file .env python -m pytest -v -m external

test-windowlist:
	$(env_vars) $(uv) run test/manual_tests/screenshot.py

screenshot:
	$(env_vars) $(uv) run -m --env-file .env macllm --show-window &
	sleep 3
	screencapture -R 2219,55,682,1330 ./macllm_test_screenshot.png
	pkill -f "macllm --show-window" || true
