"""flow_compose_scene success logic, without a browser.

The primitive's own `ok` is what agents are told to trust, so it is worth pinning:
it must go False when a reference silently failed to attach or to mention, and True
when the page ended up holding exactly the scene that was asked for.
"""
import importlib.util
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
AGENT_HELPERS = ROOT / "agent-workspace" / "agent_helpers.py"


@pytest.fixture()
def flow(tmp_path):
    """The real agent_helpers module, with the page-touching calls stubbed."""
    spec = importlib.util.spec_from_file_location("flow_agent_helpers_under_test", AGENT_HELPERS)
    mod = importlib.util.module_from_spec(spec)
    # Names the module body calls unqualified (helpers injects these at load time).
    mod.__dict__.update({
        "js": lambda *a, **k: None,
        "cdp": lambda *a, **k: {},
        "click_at_xy": lambda *a, **k: None,
        "type_text": lambda *a, **k: None,
        "press_key": lambda *a, **k: None,
        "drain_events": lambda *a, **k: [],
    })
    spec.loader.exec_module(mod)

    state = {"chips": 0, "mentions": 0, "text": ""}
    mod._flow_mention_state = lambda: {"text": state["text"],
                                       "mentions": state["mentions"], "overlay": False}
    mod._flow_chips = lambda: state["chips"]
    mod._flow_editor_text = lambda: state["text"]
    mod.flow_clear_ingredients = lambda: 0
    mod.flow_attach_ingredients = lambda paths: {"ok": True, "attached": len(paths),
                                                 "chips": state["chips"], "errors": [], "warnings": []}
    mod.flow_generate = lambda **kw: {"ok": True, "assets": [{"id": "x"}]}
    def compose_mentions(parts, typing_delay=0.02):
        """Mirror the real composer: mentions that cannot resolve become errors."""
        errs = []
        for part in parts:
            if not isinstance(part, tuple):
                continue
            if part[1].startswith("missing"):
                errs.append(f"flow_mention: no asset matched {part[1]!r}")
            else:
                state["mentions"] += 1
        return {"ok": not errs, "text": state["text"], "errors": errs}

    mod.flow_set_prompt_with_mentions = compose_mentions

    def mention(name):
        if name.startswith("missing"):
            raise RuntimeError(f"flow_mention: no asset matched {name!r}")
        state["mentions"] += 1
        return name

    mod.flow_mention = mention
    mod._state = state

    ref = tmp_path / "refA.png"
    ref.write_bytes(b"x")
    mod._ref = str(ref)
    return mod


def test_ok_when_every_reference_landed(flow):
    flow._state.update(chips=2, mentions=1, text="a scene with Stone")
    r = flow.flow_compose_scene("a scene with {Stone}", references=[flow._ref, "Stone"])
    assert r["ok"] is True
    assert r["expected_chips"] == 2
    assert r["chips"] == 2


def test_not_ok_when_a_chip_did_not_attach(flow):
    """The page ended up with fewer chips than references — the scene is incomplete."""
    flow._state.update(chips=1, mentions=1, text="a scene with Stone")
    r = flow.flow_compose_scene("a scene with {Stone}", references=[flow._ref, "Stone"])
    assert r["ok"] is False
    assert r["expected_chips"] == 2
    assert any("expected" in e and "attached" in e for e in r["errors"])


def test_not_ok_when_a_mention_failed(flow):
    # Chips are complete; the failure is the mention itself.
    flow._state.update(chips=2, mentions=0, text="a scene with")
    r = flow.flow_compose_scene("a scene with {missing_asset}",
                                references=[flow._ref, "missing_asset"])
    assert r["ok"] is False
    assert any("no asset matched" in e for e in r["errors"])


def test_duplicate_references_count_once(flow):
    """The same file given twice dedupes to one chip, and that is still complete."""
    flow._state.update(chips=1, mentions=0, text="scene")
    r = flow.flow_compose_scene("scene", references=[flow._ref, flow._ref])
    assert r["expected_chips"] == 1
    assert r["ok"] is True


def test_many_references_are_not_capped(flow):
    """Seven references is allowed; the old four-reference cap was wrong."""
    flow._state.update(chips=7, mentions=0, text="scene")
    refs = [f"/tmp/ref{i}.png" for i in range(7)]
    for r in refs:
        Path(r).write_bytes(b"x")
    try:
        out = flow.flow_compose_scene("scene", references=refs)
    finally:
        for r in refs:
            Path(r).unlink(missing_ok=True)
    assert out["expected_chips"] == 7
    assert out["ok"] is True
