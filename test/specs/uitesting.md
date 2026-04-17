# UI Testing

## Overview

The UI test infrastructure lets you drive the real macLLM window with synthetic keyboard input, read back Cocoa state, and capture screenshots for visual regression checks. Tests run in-process alongside the UI -- no accessibility permissions or external tools needed.

The core module is `UITestDriver` in `macllm/utils/uitest.py`. The pytest harness lives in `macllm/utils/uitest_harness.py`. Tests go in `test/ui/`.

## How It Works

The driver runs inside the same Python process as the macLLM UI. The harness boots the app with `MacLLMUI.start(dont_run_app=True)`, which initializes NSApp and the full Cocoa view hierarchy but does not enter `app.run()`. The test controls the run loop manually via `NSRunLoop.runUntilDate_()`, interleaving actions and UI updates.

Keyboard input uses two mechanisms:

- **Direct delegate calls** for named keys (Return, Escape, Tab, arrows). The driver calls `InputFieldDelegate.textView_doCommandBySelector_` with the appropriate selector. This is reliable because it skips the Cocoa event dispatch chain entirely.
- **Synthetic NSEvents** for modifier-key shortcuts (Cmd-C, Cmd-N, Shift-Return). The delegate inspects `NSApp().currentEvent()` for modifier flags, so a real event must be in the queue. The driver creates an `NSEvent` with the correct `modifierFlags` and `keyCode`, then posts it via `NSApp.postEvent_atStart_()`.

State reads go directly through the Cocoa object graph: `NSTextView.string()` for text content, `NSPasteboard` for clipboard, `MacLLMUI.quick_window` for window visibility.

Screenshot capture uses the existing Quartz-based tool in `macllm/utils/screenshot/`.

## Test Markers

Two pytest markers, both excluded from the default `make test` run:

- `uitest` -- functional UI tests. Open the window, drive keyboard input, assert on Cocoa state. Fast, free, deterministic.
- `uitest_external` -- visual regression tests. Same as uitest, plus capture screenshots and send them to a vision-capable LLM. Requires API keys.

## Running Tests

```
make test-ui            # functional UI tests
make test-ui-external   # visual regression tests (requires API keys)
```

## The `ui` Fixture

Every test in `test/ui/` can declare a `ui` parameter to get a `UITestDriver` instance. The fixture:

1. Boots the app once per session (session-scoped `_macllm_app` fixture)
2. Resets conversation history and clears the input field before each test
3. Reopens the window if a previous test closed it
4. Provides `ui.tmp_path` for screenshot output (pytest cleans it up automatically)

## UITestDriver API

### Actions

- `type_text(str)` -- insert text into the input field
- `press_key(name)` -- press a named key: return, escape, tab, up, down, left, right, delete
- `press_cmd(key)` -- press Cmd+key (e.g. "c", "v", "n", "1")
- `press_shift_key(name)` -- press Shift+key (e.g. Shift-Return for literal newline)
- `select_text(view, start, length)` -- set the selection range on an NSTextView

### State Reads

- `input_text()` -- current input field text
- `conversation_text()` -- current conversation area text
- `clipboard()` -- current pasteboard string
- `window_open()` -- whether the panel is visible
- `autocomplete_visible()` -- whether the autocomplete popup is showing
- `status_title()` -- menu bar status string

### Visual

- `screenshot(path)` -- capture the window to a PNG file
- `check_screenshot(path, assertion)` -- send screenshot to a vision LLM, returns True if the assertion holds

### Flow Control

- `spin(seconds)` -- run the event loop for a duration
- `wait_for(predicate, timeout)` -- spin until predicate returns True or timeout

## Writing Tests

Functional tests assert on Cocoa state:

```python
@pytest.mark.uitest
def test_type_and_escape(ui):
    ui.type_text("hello")
    assert ui.input_text() == "hello"
    ui.press_key("escape")
    ui.spin(0.3)
    assert not ui.window_open()
```

Visual regression tests capture a screenshot and ask a vision LLM:

```python
@pytest.mark.uitest_external
def test_layout_not_broken(ui, tmp_path):
    ui.type_text("test query")
    ui.press_key("return")
    ui.wait_for(lambda: not ui._ui.macllm.is_agent_running(), timeout=30)
    ui.spin(1.0)
    path = str(tmp_path / "layout.png")
    ui.screenshot(path)
    assert ui.check_screenshot(path, "The status bar text is on a single line")
```
