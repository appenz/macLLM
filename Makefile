.PHONY: run test screenshot

uv = /opt/homebrew/bin/uv

run:
	$(uv) run -m --env-file .env macllm --debug 

test:
	$(uv) run --env-file .env python -m pytest -rx -v

test-external:
	$(uv) run --env-file .env python -m pytest -v -m external

screenshot:
	$(uv) run -m --env-file .env macllm --show-window &
	sleep 3
	screencapture -R 2219,55,682,1330 ./macllm_test_screenshot.png
	pkill -f "macllm --show-window" || true
