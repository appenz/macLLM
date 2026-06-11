.PHONY: install uninstall run test screenshot test-llm test-calendar test-things test-ui test-ui-external debug-render test-skill-passnote test-task app app-dev app-clean

uv = /opt/homebrew/bin/uv

install:
	$(uv) run python -m install.model_install install

uninstall:
	$(uv) run python -m install.model_install uninstall

run:
	$(uv) run -m macllm --debug

run-debug:
	$(uv) run -m macllm --debug --debuglitellm

QUERY ?= What is the URL of Google 

test-llm:
	QUERY="$(QUERY)" $(uv) run python -m pytest -v -s test/manual_tests/llm_check.py

test:
	$(uv) run python -m pytest -rx -v

# Verify /passnote-style expansion: fixture skill body must enter the agent prompt.
test-skill-passnote:
	$(uv) run python -m pytest -rx -v test/core/test_skill_passnote_makefile.py

test-task:
	$(uv) run python -m pytest -rx -v test/core/test_task_runner.py

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

app:
	$(uv) run python setup.py py2app --semi-standalone

app-dev:
	$(uv) run python setup.py py2app --alias

app-clean:
	rm -rf build dist .eggs
