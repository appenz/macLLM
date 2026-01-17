.PHONY: run test screenshot

uv = /opt/homebrew/bin/uv
env_vars = KMP_DUPLICATE_LIB_OK=TRUE

run:
	$(env_vars) $(uv) run -m --env-file .env macllm --debug 

test:
	$(env_vars) $(uv) run --env-file .env python -m pytest -rx -v

test-external:
	$(env_vars) $(uv) run --env-file .env python -m pytest -v -m external

screenshot:
	$(env_vars) $(uv) run -m --env-file .env macllm --show-window &
	sleep 3
	screencapture -R 2219,55,682,1330 ./macllm_test_screenshot.png
	pkill -f "macllm --show-window" || true
