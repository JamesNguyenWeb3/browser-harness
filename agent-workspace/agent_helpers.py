"""Agent-editable browser helpers.

Add task-specific browser primitives here. Core helpers from browser_harness.helpers
load this file when BH_AGENT_WORKSPACE points at this directory, or when this
repo's default agent-workspace exists.
"""
import json as _json, time as _t

# --- Google Flow: generation settings trigger ---
# The panel's element ids (mat-button-toggle-N) are reassigned on every render,
# so options are found by their visible text and grouped by their label set.

_IMG_MODELS = {"nano banana pro": "🍌 Nano Banana Pro", "nano banana 2 pro": "🍌 Nano Banana Pro",
               "nano banana 2 lite": "🍌 Nano Banana 2 Lite", "nano banana 2.1": "🍌 Nano Banana 2.1"}
_VID_MODELS = {"omni 1.1": "volume_up Omni 1.1 Flash", "omni 1.1 flash": "volume_up Omni 1.1 Flash",
               "veo 3.1 - lite": "volume_up Veo 3.1 - Lite", "veo 3.1 lite": "volume_up Veo 3.1 - Lite",
               "veo 3.1 - fast": "volume_up Veo 3.1 - Fast", "veo 3.1 fast": "volume_up Veo 3.1 - Fast",
               "veo 3.1 - quality": "volume_up Veo 3.1 - Quality", "veo 3.1 quality": "volume_up Veo 3.1 - Quality"}
_IMG_RATIOS = ("16:9", "4:3", "1:1", "3:4", "9:16")
_VID_RATIOS = ("16:9", "9:16")
_OMNI_RES = (360, 720)  # only the Omni family exposes resolution/duration toggles
_VEO_DURATIONS = (4, 6, 8, 10)  # 4/6/8/10 when the model exposes toggles; Veo uses its own default

def _flow_center(jsel):
    """Viewport centre {x,y} of the first button whose newline-flattened text equals jsel, else None."""
    return js(f"""(()=>{{const b=[...document.querySelectorAll('button,[role=menuitem],[role=radio]')]
      .find(x=>(x.innerText||'').trim().replace(/\\n/g,' ')===({jsel}));
      if(!b)return null;const r=b.getBoundingClientRect();
      return {{x:r.x+r.width/2,y:r.y+r.height/2}};}})()""")

def _flow_trigger():
    return js("""(()=>{const b=[...document.querySelectorAll('button')].find(x=>x.getAttribute('aria-label')==='Settings trigger');
      if(!b)return null;const r=b.getBoundingClientRect();return {x:r.x+r.width/2,y:r.y+r.height/2};})()""")

def _flow_panel_open():
    return bool(js("!!document.querySelector('[role=radio]')"))

def _flow_pick(jsel, retries=3):
    """Click an option by its flattened text. Returns True when the click landed."""
    for _ in range(retries):
        c = _flow_center(jsel)
        if not c: return False
        click_at_xy(c["x"], c["y"]); _t.sleep(0.4)
        return True
    return False

def _flow_pick_radio(jsel, retries=3):
    """Click a radio option and confirm it reports checked; retries if a re-render ate the click."""
    for _ in range(retries):
        if _flow_active(jsel): return True
        if not _flow_pick(jsel): return False
        _t.sleep(0.25)
    return _flow_active(jsel)

def _flow_active(jsel):
    return js(f"""(()=>{{const b=[...document.querySelectorAll('[role=radio],[role=menuitem]')]
      .find(x=>(x.innerText||'').trim().replace(/\\n/g,' ')===({jsel}));
      return !!b && (b.getAttribute('aria-checked')==='true' || b.getAttribute('aria-pressed')==='true');}})()""")

def _flow_trigger_label():
    return js("""(()=>{const b=[...document.querySelectorAll('button')].find(x=>x.getAttribute('aria-label')==='Settings trigger');
      return b?b.innerText.trim().replace(/\\n/g,' '):null;})()""")

def _flow_open_panel():
    if _flow_panel_open(): return True
    t = _flow_trigger()
    if not t: return False
    click_at_xy(t["x"], t["y"]); _t.sleep(0.45)
    if _flow_panel_open(): return True
    # A click on the trigger can land while the panel is still animating shut; retry once.
    _t.sleep(0.4); t = _flow_trigger()
    if not t: return False
    click_at_xy(t["x"], t["y"]); _t.sleep(0.6)
    return _flow_panel_open()

def _flow_close_panel():
    t = _flow_trigger()
    if t and _flow_panel_open(): click_at_xy(t["x"], t["y"]); _t.sleep(0.3)

def _flow_model_button():
    return js("""(()=>{const b=[...document.querySelectorAll('button')].find(x=>x.getAttribute('aria-label')==='Select model family');
      if(!b)return null;const r=b.getBoundingClientRect();return {x:r.x+r.width/2,y:r.y+r.height/2};})()""")

def _flow_menu_items():
    return js("JSON.stringify([...document.querySelectorAll('[role=menuitem]')].map(b=>b.innerText.trim().replace(/\\n/g,' ')))")

def _flow_pick_model(name, generate_type):
    want = (_IMG_MODELS if generate_type == "image" else _VID_MODELS)[str(name).strip().lower()]
    for _ in range(2):
        btn = _flow_model_button()
        if not btn: return False
        # Opening the menu is what proves which family is on screen: the item list
        # itself is the check, not a re-read of the trigger.
        click_at_xy(btn["x"], btn["y"]); _t.sleep(0.6)
        labels = _json.loads(_flow_menu_items() or "[]")
        if not labels: continue
        bare = lambda s: s.replace("🍌 ", "").replace("volume_up ", "").strip().lower()
        match = next((l for l in labels if bare(l) == bare(want)), None)
        if match is None: return False
        target = js(f"""(()=>{{const m=[...document.querySelectorAll('[role=menuitem]')]
          .find(x=>x.innerText.trim().replace(/\\n/g,' ')===({_json.dumps(match)}));
          if(!m)return null;const r=m.getBoundingClientRect();return {{x:r.x+r.width/2,y:r.y+r.height/2}};}})()""")
        if not target: continue
        click_at_xy(target["x"], target["y"]); _t.sleep(0.6)
        if not js("!!document.querySelector('[role=menuitem]')"): return True
    return False

def generate_setting_trigger(generate_type="video", aspect_ratio=None, model=None, output_count=None,
                             video_type=None, video_resolution=None, video_duration=None,
                             verify=True, close=True):
    """Set the Google Flow generation panel to an image/video configuration.

    generate_type:      "image" | "video"
    aspect_ratio:       image 16:9 (default) | 4:3 | 1:1 | 3:4 | 9:16;  video 16:9 (default) | 9:16
    model:              image: nano banana 2.1 (default) | nano banana pro | nano banana 2 lite
                        video: omni 1.1 (default) | veo 3.1 lite | veo 3.1 fast | veo 3.1 quality
    output_count:       image 2 (default) | video 1 (default); range 1-4
    video_type:         video only: ingredients (default) | frames
    video_resolution:   video + omni only: 360 | 720 (default 720)
    video_duration:     video + omni only: 4 | 6 | 8 | 10 (default 10)
                        These three are None by default so image calls need not pass
                        them; the values above are what None resolves to for video.
    verify:             read the trigger label back and report what the panel actually shows
    close:              collapse the panel when done (it closes on an outside click anyway)

    Returns {"ok": bool, "trigger": "<label after>", "applied": {...}, "warnings": [...]}.
    Raises ValueError on an unsupported combination before touching the page. Options
    that the chosen model does not expose (e.g. resolution on Veo) are reported in
    warnings, not applied.
    """
    gt = str(generate_type).strip().lower()
    if gt in ("img", "picture", "photo"): gt = "image"
    if gt in ("vid", "movie", "film"): gt = "video"
    if gt not in ("image", "video"): raise ValueError(f"generate_type must be image|video, got {generate_type!r}")

    warnings = []
    aspect_ratio = str(aspect_ratio or "16:9")
    allowed_ratios = _IMG_RATIOS if gt == "image" else _VID_RATIOS
    if aspect_ratio not in allowed_ratios:
        raise ValueError(f"aspect_ratio {aspect_ratio!r} not available for {gt}; use one of {allowed_ratios}")

    default_model = "nano banana 2.1" if gt == "image" else "omni 1.1"
    model = str(model or default_model).strip().lower()
    if model not in (_IMG_MODELS if gt == "image" else _VID_MODELS):
        raise ValueError(f"model {model!r} not available for {gt}; use one of "
                         f"{sorted(_IMG_MODELS if gt == 'image' else _VID_MODELS)}")

    output_count = int(output_count if output_count is not None else (2 if gt == "image" else 1))
    if not 1 <= output_count <= 4: raise ValueError(f"output_count must be 1-4, got {output_count}")

    vt = str(video_type or "ingredients").strip().lower()
    is_omni = model.startswith("omni")
    if gt == "image" and any(v is not None for v in (video_type, video_resolution, video_duration)):
        raise ValueError("video_type/video_resolution/video_duration only apply to generate_type='video'")
    if gt == "video" and vt not in ("ingredients", "frames"): raise ValueError(f"video_type must be ingredients|frames, got {video_type!r}")
    if gt == "video" and not is_omni and (video_resolution is not None or video_duration is not None):
        warnings.append(f"{model} exposes no resolution/duration controls; its defaults apply")
        video_resolution, video_duration = None, None
    video_resolution = int(video_resolution or 720)
    video_duration = int(video_duration or 10)
    if gt == "video" and is_omni:
        if video_resolution not in _OMNI_RES: raise ValueError(f"video_resolution must be one of {_OMNI_RES}, got {video_resolution}")
        if video_duration not in _VEO_DURATIONS: raise ValueError(f"video_duration must be one of {_VEO_DURATIONS}, got {video_duration}")

    if not _flow_open_panel(): raise RuntimeError("generate_setting_trigger: settings trigger not found — is the Flow project page loaded?")

    applied = {}
    # Order matters: the mode switch can close the panel; switching to video rebuilds
    # the option groups, so re-open before every group and re-assert the mode if it reverted.
    def ensure_open(): return _flow_open_panel()
    if not ensure_open(): raise RuntimeError("generate_setting_trigger: settings panel did not open")

    if not _flow_pick_radio("'image Image'" if gt == "image" else "'videocam Video'"):
        # Mode can reset to video when the panel re-renders; retry once from a clean open.
        _flow_close_panel(); ensure_open()
        if not _flow_pick_radio("'image Image'" if gt == "image" else "'videocam Video'"):
            warnings.append(f"could not select {gt} mode")
    else:
        applied["generate_type"] = gt

    if gt == "video":
        if _flow_pick_radio("'chrome_extension Ingredients'" if vt == "ingredients" else "'crop_free Frames'"):
            applied["video_type"] = vt
        else: warnings.append(f"video_type {vt} not found")

    _flow_open_panel()
    ratio = {"4:3": "crop_landscape", "1:1": "crop_square", "3:4": "crop_portrait", "9:16": "crop_9_16", "16:9": "crop_16_9"}[aspect_ratio]
    if _flow_pick_radio(f"'{ratio} {aspect_ratio}'"): applied["aspect_ratio"] = aspect_ratio
    else: warnings.append(f"aspect_ratio {aspect_ratio} not found")

    _flow_open_panel()
    if _flow_pick_model(model, gt): applied["model"] = model
    else: warnings.append(f"model {model!r}: menu item not found; panel kept its current model")

    _flow_open_panel()
    if _flow_pick_radio(f"'x{output_count}'", retries=2): applied["output_count"] = output_count
    else: warnings.append(f"output_count x{output_count} not found")

    if gt == "video" and is_omni:
        _flow_open_panel()
        if _flow_pick_radio(f"'{video_resolution}p'" if video_resolution != 360 else "'360p info'"):
            applied["video_resolution"] = video_resolution
        else: warnings.append(f"video_resolution {video_resolution}p not found")
        if _flow_pick_radio(f"'{video_duration}s'"): applied["video_duration"] = video_duration
        else: warnings.append(f"video_duration {video_duration}s not found")

    if close: _flow_close_panel()
    label = _flow_trigger_label() if verify else None
    return {"ok": bool(label) and not [w for w in warnings if "not found" in w],
            "trigger": label, "applied": applied, "warnings": warnings}
