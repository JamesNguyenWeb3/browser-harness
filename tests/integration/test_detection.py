"""Live detection regression: needs a running browser.

Run with:

    BH_LIVE_DETECTION=1 uv run --with pytest python -m pytest tests/integration/test_detection.py -q

These assert the page-side facts hardened in docs/cdp-detection-hardening-research.md.
They drive the real `./browser-harness` entry point through a subprocess, because
that launcher sets the dev runtime dir the daemon listens on; a bare in-process
import would resolve a different socket. Opt-in because CI has no browser.
"""
import json
import os
import pathlib
import subprocess

import pytest

ROOT = pathlib.Path(__file__).resolve().parents[2]
LAUNCHER = ROOT / "browser-harness"

pytestmark = pytest.mark.skipif(
    os.environ.get("BH_LIVE_DETECTION") != "1",
    reason="live browser required; set BH_LIVE_DETECTION=1",
)

# FPScanner's hasCDP signal (src/signals/cdp.ts): replace Error.prepareStackTrace
# and log an Error. With Runtime.enable on, Chrome serializes the console
# argument, runs the stack formatter, and the flag flips.
CDP_PROBE = """(() => {
  let accessed = false;
  const prev = Error.prepareStackTrace;
  Error.prepareStackTrace = function () {
    accessed = true;
    return prev ? prev.apply(this, arguments) : undefined;
  };
  console.log(new Error('probe'));
  Error.prepareStackTrace = prev;
  return accessed;
})()"""

_SCRIPT = "\n".join([
    "import json",
    'tid = new_tab("about:blank")',
    "try:",
    "    print('RESULT ' + json.dumps({",
    f"        'cdp': bool(js({json.dumps(CDP_PROBE)})),",
    "        'title': js('document.title'),",
    "        'visibility': js('document.visibilityState'),",
    "    }))",
    "finally:",
    "    close_tab(tid)",
])


def _probe():
    # The assertions below describe the default configuration, so the child
    # must not inherit an ambient opt-out (or an opt-in marker).
    env = {k: v for k, v in os.environ.items()
           if k not in ("BH_FOCUS_EMULATION", "BH_TAB_MARKER")}
    r = subprocess.run(
        [str(LAUNCHER)], input=_SCRIPT, capture_output=True, text=True, timeout=180,
        env=env,
    )
    assert r.returncode == 0, f"harness failed:\n{r.stderr[-2000:]}"
    line = next((ln for ln in r.stdout.splitlines() if ln.startswith("RESULT ")), None)
    assert line, f"no RESULT line in output:\n{r.stdout[-2000:]}"
    return json.loads(line[len("RESULT "):])


def test_attached_page_shows_no_cdp_and_no_automation_marker():
    result = _probe()
    assert result["cdp"] is False, (
        "Runtime.enable is being sent: console arguments are serialized and run "
        "page getters. Remove it from _enable_default_domains."
    )
    assert result["title"] == "", (
        "The tab-title marker is page-readable; it must stay opt-in (BH_TAB_MARKER=1)."
    )
    assert result["visibility"] == "visible", (
        "Focus emulation is off, so trusted input arrives on a page that reports "
        "itself hidden — a contradiction no human click can produce."
    )
