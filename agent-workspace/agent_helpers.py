"""Agent-editable browser helpers.

Add task-specific browser primitives here. Core helpers from browser_harness.helpers
load this file when BH_AGENT_WORKSPACE points at this directory, or when this
repo's default agent-workspace exists.
"""
import json as _json, os as _os, time as _t

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

# --- Google Flow: prompt + reference ingredients ---
# The prompt box is a ProseMirror contenteditable: JS range edits are ignored, so
# text goes in through real key events. References are not part of the editor DOM;
# each one becomes a <flow-ingredient-chip> beside it.

_FLOW_EDITOR = "flow-rich-text-editor .ProseMirror"
_FLOW_MAX_INGREDIENTS = 4  # the picker stops adding past four

def _flow_editor_text():
    return js(f"""(()=>{{const e=document.querySelector({_FLOW_EDITOR!r});return e?e.innerText:null;}})()""")

def _flow_chips():
    return js("document.querySelectorAll('flow-ingredient-chip').length")

def _flow_click_js(find, wait_s=1.0):
    """Centre-click the element returned by a JS expression, or False if absent."""
    js(f"""(()=>{{const b={find}; if(!b){{window.__bhp=null;return;}}
      const r=b.getBoundingClientRect(); window.__bhp={{x:r.x+r.width/2,y:r.y+r.height/2}};}})()""")
    p = js("window.__bhp")
    if not p: return False
    click_at_xy(p["x"], p["y"]); _t.sleep(wait_s); return True

_OPEN_INGREDIENTS = ("[...document.querySelectorAll('button')]"
                     ".find(x=>x.getAttribute('aria-label')==='Add ingredients to the prompt box')")
_UPLOAD_MEDIA = ("[...document.querySelectorAll('.cdk-overlay-pane button')]"
                 ".find(x=>/Upload media/.test(x.innerText))")
_ADD_TO_PROMPT = ("[...document.querySelectorAll('.cdk-overlay-pane button')]"
                  ".find(x=>/Add to prompt/i.test(x.innerText))")

def _flow_overlay_open():
    return bool(js("!!document.querySelector('.cdk-overlay-pane')"))

def _flow_open_picker(retries=3):
    """Open the ingredients picker. Attaching closes it with a backdrop that eats the
    next click for a few hundred ms, so wait for it to be gone and retry the open."""
    for _ in range(retries):
        if _flow_overlay_open(): return True
        if not _flow_click_js(_OPEN_INGREDIENTS, 0.8): return False
        if _flow_overlay_open(): return True
        _t.sleep(0.5)
    return _flow_overlay_open()

def _flow_wait_closed(timeout=5.0):
    deadline = _t.time() + timeout
    while _t.time() < deadline:
        if not _flow_overlay_open(): return True
        _t.sleep(0.2)
    return False

def _flow_upload(path):
    """Set files on the picker's hidden input. The node is re-created per open, so
    resolve it fresh; a stale nodeId raises 'Could not find node with given id'."""
    doc = cdp("DOM.getDocument", depth=-1)
    nid = cdp("DOM.querySelector", nodeId=doc["root"]["nodeId"], selector="input[type=file]")["nodeId"]
    if not nid: raise RuntimeError("flow: picker file input not found")
    cdp("DOM.setFileInputFiles", files=[path] if isinstance(path, str) else list(path), nodeId=nid)

def _flow_select_upload(name, timeout=25.0):
    """Wait for the freshly uploaded asset to settle, then select it.

    The picker does NOT auto-select a new upload: whatever was selected before stays
    selected. Adding without selecting first attaches the previous asset, which Flow
    dedupes against the chip already in the prompt — a no-op that looks like success.
    The list is newest-first and can hold earlier uploads with the same filename, so
    the first non-uploading match is the right one.
    """
    deadline = _t.time() + timeout
    while _t.time() < deadline:
        state = js(f"""(()=>{{const items=[...document.querySelectorAll('.cdk-overlay-pane .asset-item')];
          const i=items.findIndex(x=>((x.innerText||'').includes({_json.dumps(name)})));
          if(i<0)return 'absent';
          if(/Uploading/i.test(items[i].innerText||''))return 'uploading';
          if(/active/.test(items[i].className))return 'active';
          const r=items[i].getBoundingClientRect();
          window.__bhp={{x:r.x+r.width/2,y:r.y+r.height/2}};return 'ready';}})()""")
        if state == "active": return True
        if state == "ready":
            p = js("window.__bhp")
            if p: click_at_xy(p["x"], p["y"]); _t.sleep(0.6)
            continue
        _t.sleep(0.5)
    return False

def flow_set_prompt(text, clear_first=True, typing_delay=0.02):
    """Type `text` into the Flow prompt box.

    The editor is ProseMirror: assigning textContent or a JS Range selection is
    ignored, so this focuses it and sends real key events. clear_first selects all
    and deletes through the keyboard for the same reason.
    """
    if not js(f"!!document.querySelector({_FLOW_EDITOR!r})"):
        raise RuntimeError("flow_set_prompt: prompt box not found — is the Flow project page loaded?")
    js(f"(()=>{{const e=document.querySelector({_FLOW_EDITOR!r});e.focus();e.click();}})()"); _t.sleep(0.25)
    if clear_first:
        ua = cdp("Browser.getVersion").get("userAgent", "")
        mods = 4 if ("Mac OS X" in ua or "Macintosh" in ua) else 2
        sa = {"key": "a", "code": "KeyA", "modifiers": mods,
              "windowsVirtualKeyCode": 65, "nativeVirtualKeyCode": 65, "commands": ["SelectAll"]}
        cdp("Input.dispatchKeyEvent", type="rawKeyDown", **sa)
        cdp("Input.dispatchKeyEvent", type="keyUp", **{k: v for k, v in sa.items() if k != "commands"})
        _t.sleep(0.2)
        cdp("Input.dispatchKeyEvent", type="rawKeyDown", key="Backspace", code="Backspace",
            windowsVirtualKeyCode=8, nativeVirtualKeyCode=8)
        cdp("Input.dispatchKeyEvent", type="keyUp", key="Backspace", code="Backspace",
            windowsVirtualKeyCode=8, nativeVirtualKeyCode=8)
        _t.sleep(0.2)
    type_text(text, typing_delay=typing_delay)
    _t.sleep(0.3)
    got = _flow_editor_text()
    return {"ok": text in (got or ""), "text": got}

def flow_attach_ingredients(paths):
    """Upload local files and add them to the prompt box as reference ingredients.

    `paths`: one path or a list. Images (.png/.jpg/.jpeg/.webp/.gif/.heif/.heic) and
    videos (.mp4/.m4v/.mov/.3gp/.avi) are accepted. The picker selects one asset at a
    time, so each path is uploaded and attached separately. At most four ingredients
    can be attached.

    Returns {"ok", "attached", "chips", "errors", "warnings"}.
    """
    paths = [paths] if isinstance(paths, str) else [str(p) for p in paths]
    errors, warnings = [], []
    missing = [p for p in paths if not _os.path.exists(p)]
    if missing: raise ValueError(f"flow_attach_ingredients: file not found: {missing}")
    while _flow_chips() + len(paths) > _FLOW_MAX_INGREDIENTS:
        dropped = paths.pop()
        warnings.append(f"{dropped}: Flow accepts at most {_FLOW_MAX_INGREDIENTS} ingredients; not attached")
    before = _flow_chips()
    for p in paths:
        try:
            if not _flow_open_picker():
                errors.append(f"{p}: ingredients picker did not open"); break
            if not _flow_click_js(_UPLOAD_MEDIA, 1.0):
                errors.append(f"{p}: Upload media button not found"); break
            _flow_upload(p)
            if not _flow_select_upload(_os.path.basename(p)):
                errors.append(f"{p}: upload did not settle in the picker"); continue
            n_before = _flow_chips()
            if not _flow_click_js(_ADD_TO_PROMPT, 1.6):
                errors.append(f"{p}: Add to prompt not found"); continue
            _flow_wait_closed()
            if _flow_chips() <= n_before:
                errors.append(f"{p}: not added (Flow may treat it as a duplicate)")
        except Exception as e:
            errors.append(f"{p}: {type(e).__name__}: {e}")
            # Leave the picker closed so the next attempt starts clean.
            try: js("document.body.click()"); _t.sleep(0.4)
            except Exception: pass
    return {"ok": not errors, "attached": _flow_chips() - before,
            "chips": _flow_chips(), "errors": errors, "warnings": warnings}

def flow_clear_ingredients():
    """Remove every ingredient chip from the prompt box. Returns chips removed."""
    n = 0
    while _flow_chips():
        if not _flow_click_js("document.querySelector('flow-ingredient-chip button.chip-container')", 0.7):
            break
        n += 1
        if n > 10: break
    return n

def flow_compose_prompt(prompt, refs=None, clear_refs=False):
    """Set the prompt text and attach reference files in one call.

    `prompt`: the text to generate from.
    `refs`:   local image/video paths to attach as ingredients (max 4 total).
    `clear_refs`: drop existing ingredient chips first, so `refs` is exactly the set.

    Returns {"ok", "prompt", "ingredients", "errors", "warnings"}.
    """
    if clear_refs: flow_clear_ingredients()
    text = flow_set_prompt(prompt)
    ing = flow_attach_ingredients(refs) if refs else {"ok": True, "attached": 0, "chips": _flow_chips(),
                                                      "errors": [], "warnings": []}
    return {"ok": bool(text["ok"] and ing["ok"]), "prompt": text["text"],
            "ingredients": ing["chips"], "errors": ing["errors"], "warnings": ing["warnings"]}

# --- Google Flow: @-mentions in the prompt ---
# Typing "@" in the prompt opens the same asset picker as the ingredients button.
# Picking an asset replaces the "@" with an inline <span class="mention-chip"
# data-mention-id=... data-reference-type=...> and also adds a chip beside the box.
# Two behaviours make the naive sequence unsafe:
#   * text typed while the popup is open is mirrored into the popup's search box
#     AND left in the prompt, so "@20c7" ends up in the prompt text;
#   * the "@" is only consumed when an asset is picked. A query that matches
#     nothing leaves a stray "@" behind and the Add button disappears.
# So the query goes to the popup's own search box (which takes focus when "@" is
# typed), never to the editor.

_FLOW_SEARCH = ".cdk-overlay-pane input.search-input"

def _flow_search_box():
    return js(f"""(()=>{{const i=document.querySelector({_FLOW_SEARCH!r});
      if(!i)return null;const r=i.getBoundingClientRect();return {{x:r.x+r.width/2,y:r.y+r.height/2}};}})()""")

def _flow_cursor_to_end():
    """Put the caret at the end of the prompt, after any mention chips.

    Collapsing to the editor's last child is not enough: once a mention is picked
    the last child is the mention <span>, and typing there lands inside the chip
    instead of after it. Collapse to the end of the deepest last node instead,
    falling back to the end of the <p> and then the editor itself.
    """
    js("""(()=>{const e=document.querySelector('flow-rich-text-editor .ProseMirror');
      if(!e)return;e.focus();
      const p=e.querySelector('p')||e;
      const range=document.createRange();range.selectNodeContents(p);range.collapse(false);
      const s=getSelection();s.removeAllRanges();s.addRange(range);})()""")

def _flow_mention_state():
    return js("""(()=>{const e=document.querySelector('flow-rich-text-editor .ProseMirror');
      return {text:e?e.innerText:null,
              mentions:document.querySelectorAll('span.mention-chip').length,
              overlay:!!document.querySelector('.cdk-overlay-pane')};})()""")

def _flow_pick_from_popup(query=None, timeout=8.0):
    """Filter the open @-popup by `query` and add the first match.

    The query is typed into the popup's search input, not the editor: typing in the
    editor is mirrored to both places and leaks the query into the prompt.
    Returns the picked mentions, or None when nothing matched.
    """
    if query:
        # "@" moves focus into the popup's search input, and each popup opens with an
        # empty filter. Typing straight into it works; clicking or clearing the field
        # first drops focus and the keystrokes go nowhere.
        if not _flow_search_box(): return None
        type_text(query, typing_delay=0.02)
        _t.sleep(0.9)
    mentions_before = _flow_mention_state()["mentions"]

    def added(item_name, wait=4.0):
        """Success is a new mention span; the clicks themselves report nothing useful
        because adding closes the overlay underneath them."""
        end = _t.time() + wait
        while _t.time() < end:
            if _flow_mention_state()["mentions"] > mentions_before: return item_name
            _t.sleep(0.25)
        return None

    deadline = _t.time() + timeout
    while _t.time() < deadline:
        item = js("""(()=>{const it=document.querySelector('.cdk-overlay-pane .asset-item');
          if(!it)return null;const r=it.getBoundingClientRect();
          return {x:r.x+r.width/2,y:r.y+r.height/2,name:it.innerText.trim().replace(/\\n/g,' ')};})()""")
        if not item: return None
        click_at_xy(item["x"], item["y"])
        # Two paths exist here and which one runs depends on the asset kind: picking
        # the item can add the mention outright (overlay closes), or only select it,
        # leaving "Add to prompt" to commit. Handle both.
        hit = added(item["name"], wait=1.5)
        if hit: return hit
        add = js("""(()=>{const b=[...document.querySelectorAll('.cdk-overlay-pane button')]
          .find(x=>/Add to prompt/i.test(x.innerText));
          if(!b)return null;const r=b.getBoundingClientRect();
          return {x:r.x+r.width/2,y:r.y+r.height/2};})()""")
        if not add: return None
        click_at_xy(add["x"], add["y"])
        hit = added(item["name"], wait=4.0)
        if hit: return hit
        return None
    return None

def flow_mention(name, clear_text="@", timeout=8.0):
    """Append an @-mention of `name` to the prompt, replacing the "@" it was typed with.

    Call this with the cursor at the end of the prompt. It types "@", filters the
    popup by `name`, picks the first match and returns the mention's label.

    `clear_text`: on no match, the stray "@" is removed by deleting that many
    characters. Pass None to leave the prompt untouched.

    Raises RuntimeError when nothing matches, after removing the stray "@".
    """
    _flow_cursor_to_end()
    _t.sleep(0.2)
    type_text("@"); _t.sleep(1.2)
    if not _flow_mention_state()["overlay"]:
        raise RuntimeError("flow_mention: the @ popup did not open")
    chips_before = _flow_chip_count()
    picked = _flow_pick_from_popup(name, timeout=timeout)
    if picked is None:
        # A pick can add the reference chip without inserting the mention span,
        # leaving a phantom reference that the prompt text never mentions. Undo it.
        added = _flow_chip_count() - chips_before
        for _ in range(max(0, added)):
            _flow_remove_last_chip()
        # Nothing matched: the popup is gone and the "@" is still in the prompt.
        # Focus is left in the closed popup's search box, so Backspace there would
        # do nothing — put the caret back in the editor first.
        if clear_text:
            _t.sleep(0.3)
            _flow_cursor_to_end()
            _t.sleep(0.2)
            for _ in range(len(clear_text) if isinstance(clear_text, str) else 1):
                press_key("Backspace")
            _t.sleep(0.3)
        raise RuntimeError(f"flow_mention: no asset matched {name!r}")
    return picked

def flow_set_prompt_with_mentions(parts, typing_delay=0.02):
    """Type a prompt interleaved with @-mentions.

    `parts` is a list of strings (literal text) and 1-tuples ("mention", name):
        ["A studio fashion sequence. Starting with ", ("mention", "Lisa"),
         ", she is holding ", ("mention", "RedMud"), "."]

    Picking a mention leaves the cursor in the editor, so the next literal part
    continues the same sentence. Returns {"ok", "text", "mentions", "chips", "errors"}.

    Note: an ingredient chip is ADDED for each mention and clearing the prompt text
    does not remove those chips — use flow_clear_ingredients() to reset them.
    """
    errors = []
    # Start from an empty editor; every literal part is appended in order, including
    # the first one, so no part may be typed twice.
    flow_set_prompt("", clear_first=True)
    for part in parts:
        if isinstance(part, str):
            type_text(part, typing_delay=typing_delay)
        else:
            try:
                flow_mention(part[1])
            except RuntimeError as e:
                errors.append(str(e))
    _t.sleep(0.4)
    state = _flow_mention_state()
    return {"ok": not errors, "text": state["text"], "mentions": state["mentions"],
            "chips": _flow_chips(), "errors": errors}

def flow_clear_mentions():
    """Remove inline mention spans from the prompt without wiping the rest of the text.

    Clearing the prompt with flow_set_prompt() already drops mention spans; this is for
    removing them while keeping the surrounding words. Returns spans removed.
    """
    n = 0
    while js("document.querySelectorAll('span.mention-chip').length"):
        ok = js("""(()=>{const m=document.querySelector('span.mention-chip');
          if(!m)return false;m.remove();return true;})()""")
        if not ok: break
        n += 1
        if n > 30: break
    _flow_cursor_to_end()
    return n

# --- Google Flow: character creation ---
# Characters are created on a sub-page: /project/<id>/character (blank) or
# /character/<uuid> (existing). The blank page shows style presets, a description
# editor, Upload / Add from project, and Start generation. Generating opens the
# character editor with name, voice, personality and portrait slots.

_FLOW_CHAR_NAME = "input.name-input"
_FLOW_CHAR_PERSONALITY = "textarea.personality-textarea"
_FLOW_CHAR_VOICE_BTN = ("[...document.querySelectorAll('button')]"
                        ".find(x=>/voice_selection/.test(x.innerText))")
_FLOW_CHAR_URL = "/character"

def _flow_upload_via_chooser(click_js, path, timeout=15.0, quiet_after=1.5):
    """Upload a local file through a button that opens the OS file dialog.

    Buttons like the character page's "Upload" create no input[type=file] — they
    call into the browser's file chooser directly, so DOM.setFileInputFiles has no
    node to target. Intercepting the dialog gives the chooser's backend node, which
    DOM.setFileInputFiles accepts. Returns True when the file was set.

    Interception is enabled only for the click and disabled afterwards, because it
    suppresses every other file dialog on the page while active.
    """
    drain_events()
    cdp("Page.setInterceptFileChooserDialog", enabled=True)
    try:
        if not _flow_click_js(click_js, 0.6): return False
        deadline = _t.time() + timeout
        node = None
        while _t.time() < deadline:
            for ev in drain_events():
                p = ev.get("params") or {}
                if ev.get("method") == "Page.fileChooserOpened" and p.get("backendNodeId"):
                    node = p["backendNodeId"]; break
            if node: break
            _t.sleep(0.4)
        if not node: return False
        cdp("DOM.setFileInputFiles", files=[path], backendNodeId=node)
        _t.sleep(quiet_after)
        return True
    finally:
        try: cdp("Page.setInterceptFileChooserDialog", enabled=False)
        except Exception: pass

def _flow_char_open_new():
    """Open the blank New character page from a project. Returns the URL."""
    if js(f"location.pathname.includes({_FLOW_CHAR_URL!r})"): return js("location.href")
    if not _flow_click_js("[...document.querySelectorAll('button')].find(x=>/Characters/.test(x.innerText))", 1.4):
        return None
    _flow_click_js("[...document.querySelectorAll('button')].find(x=>/New character/.test(x.innerText))", 1.8)
    _t.sleep(0.8)
    return js("location.href")

def _flow_char_set_input(selector, value):
    """Replace a plain input/textarea value with real keystrokes.

    Clearing through the prototype setter empties the field, but clicking afterwards
    puts the caret inside the placeholder text and typing inserts into it
    ("Untitled chTest Namearacter"). Select the whole field with the keyboard and
    type over it instead, which is also what a person does.
    """
    ok = js(f"""(()=>{{const i=document.querySelector({selector!r});if(!i)return false;
      const r=i.getBoundingClientRect();window.__bhp={{x:r.x+r.width/2,y:r.y+r.height/2}};return true;}})()""")
    if not ok: return False
    p = js("window.__bhp")
    click_at_xy(p["x"], p["y"]); _t.sleep(0.25)
    ua = cdp("Browser.getVersion").get("userAgent", "")
    mods = 4 if ("Mac OS X" in ua or "Macintosh" in ua) else 2
    sa = {"key": "a", "code": "KeyA", "modifiers": mods,
          "windowsVirtualKeyCode": 65, "nativeVirtualKeyCode": 65, "commands": ["SelectAll"]}
    cdp("Input.dispatchKeyEvent", type="rawKeyDown", **sa)
    cdp("Input.dispatchKeyEvent", type="keyUp", **{k: v for k, v in sa.items() if k != "commands"})
    _t.sleep(0.2)
    cdp("Input.dispatchKeyEvent", type="rawKeyDown", key="Backspace", code="Backspace",
        windowsVirtualKeyCode=8, nativeVirtualKeyCode=8)
    cdp("Input.dispatchKeyEvent", type="keyUp", key="Backspace", code="Backspace",
        windowsVirtualKeyCode=8, nativeVirtualKeyCode=8)
    _t.sleep(0.2)
    type_text(value, typing_delay=0.02); _t.sleep(0.4)
    got = js(f"document.querySelector({selector!r}).value")
    if got == value:
        # Commit: these fields save on blur/change, not on each keystroke.
        js(f"""(()=>{{const i=document.querySelector({selector!r});
          i.dispatchEvent(new Event('change',{{bubbles:true}}));i.blur();}})()""")
        _t.sleep(0.3)
    return got == value

def _flow_char_wait_idle(timeout=180.0):
    """Wait until no generation-percentage indicator is on the page."""
    deadline = _t.time() + timeout
    _t.sleep(2.0)
    while _t.time() < deadline:
        pct = js("(()=>{const m=document.body.innerText.match(/(\\d+)\\s*%/);return m?parseInt(m[1]):null;})()")
        if pct is None: return True
        _t.sleep(2.5)
    return False

def flow_set_character_voice(preset=None, performance=None, name=None, sample=None, timeout=180.0):
    """Attach a voice to the character currently open.

    preset:      a built-in voice name (Achernar, Achird, ...). Searched in the panel.
    performance: instead of a preset, describe a voice in Customize performance.
    name:        name for the generated voice (required with `performance`).
    sample:      optional sample dialogue text (max 120 chars).

    With `preset`, the built-in is added directly. With `performance`, the panel's
    "Customize performance" field is filled, then Preview generates the voice and
    only then does "Add to character" appear — Save is never enabled directly.

    Returns {"ok", "voice", "errors"}.
    """
    if preset is None and performance is None:
        raise ValueError("flow_set_character_voice: pass preset or performance")
    if performance and not name:
        raise ValueError("flow_set_character_voice: `name` is required with `performance`")
    errors = []
    # A closing overlay's backdrop swallows the next click, so retry the open until
    # the panel is actually up.
    opened = False
    for _ in range(3):
        if js("!!document.querySelector('.cdk-overlay-pane textarea.performance-input, .cdk-overlay-pane input.search-input')"):
            opened = True; break
        if _flow_click_js(_FLOW_CHAR_VOICE_BTN, 1.4):
            if js("!!document.querySelector('.cdk-overlay-pane')"):
                opened = True; break
        _t.sleep(0.6)
    if not opened:
        return {"ok": False, "voice": None, "errors": ["voice selector not found"]}

    if preset:
        # The panel lists built-ins with a search box; narrow it, then pick the row.
        if not _flow_search_box():
            errors.append("voice search box not found")
        else:
            type_text(preset, typing_delay=0.02)
        # The panel renders a transitional row while the query is being applied: its
        # label is the query itself, lowercased. Picking it stored a voice literally
        # named "aoede"/"gacrux". Require a row whose name equals the preset exactly
        # (case-insensitive) and that stays put across several polls before clicking.
        want = preset.strip().lower()
        item, stable, deadline = None, 0, _t.time() + 15.0
        while _t.time() < deadline:
            found = js(f"""(()=>{{const want={want!r};
              const it=[...document.querySelectorAll('.cdk-overlay-pane button')].find(b=>{{
                const parts=(b.innerText||'').trim().split('\\n').map(x=>x.trim());
                return parts[1] && parts[1].toLowerCase()===want;}});
              if(!it)return null;const r=it.getBoundingClientRect();
              return {{x:r.x+r.width/2,y:r.y+r.height/2,name:(it.innerText||'').trim().split('\\n')[1]}};}})()""")
            if found:
                stable += 1
                item = found
                if stable >= 3: break
            else:
                stable, item = 0, None
            _t.sleep(0.5)
        if not item:
            errors.append(f"preset {preset!r} not found in the voice list")
        else:
            click_at_xy(item["x"], item["y"]); _t.sleep(0.9)
            add = js("""(()=>{const b=[...document.querySelectorAll('.cdk-overlay-pane button')]
              .find(x=>/Add to character/i.test(x.innerText));
              if(!b)return null;const r=b.getBoundingClientRect();
              return {x:r.x+r.width/2,y:r.y+r.height/2};})()""")
            if add: click_at_xy(add["x"], add["y"]); _t.sleep(1.4)
    else:
        # Custom performance: fill the style, optionally the sample dialogue. The
        # panel pre-fills the sample with placeholder text, so always set it.
        _flow_char_set_input(".cdk-overlay-pane textarea.sample-dialogue-input",
                             (sample or "Hi there.")[:120])
        _flow_char_set_input(".cdk-overlay-pane textarea.performance-input", performance)
        # Typing into the performance field is what switches the panel into
        # customize mode; the Voice name input does not exist before that.
        deadline = _t.time() + 6.0
        while _t.time() < deadline and not js("!!document.querySelector('.cdk-overlay-pane input.voice-name-input')"):
            _t.sleep(0.3)
        if not _flow_char_set_input(".cdk-overlay-pane input.voice-name-input", name):
            errors.append("voice name field not found")
        _t.sleep(0.4)
        # Panel state machine for a custom voice (measured):
        #   edit performance/sample -> "Save new voice" (disabled while Preview runs)
        #   Preview                  -> hourglass, then "Save new voice" enabled
        #   Save new voice           -> registers the voice, button becomes "Add to character"
        #   Add to character         -> attaches it to the character
        # Skipping Save leaves the voice unnamed and never attaches.
        def centre(js_find):
            js(f"""(()=>{{const b={js_find};if(!b||b.disabled){{window.__bhp=null;return;}}
              b.scrollIntoView({{block:'center'}});const r=b.getBoundingClientRect();
              window.__bhp={{x:r.x+r.width/2,y:r.y+r.height/2}};}})()""")
            return js("window.__bhp")

        def wait_enabled(pattern, timeout_s=120.0):
            end = _t.time() + timeout_s
            while _t.time() < end:
                c = centre(f"[...document.querySelectorAll('.cdk-overlay-pane button')].find(x=>/{pattern}/i.test(x.innerText))")
                if c: return c
                _t.sleep(1.5)
            return None

        preview = centre("[...document.querySelectorAll('.cdk-overlay-pane button')].find(x=>/Preview/i.test(x.innerText))")
        if preview: click_at_xy(preview["x"], preview["y"])
        else: errors.append("Preview button not found")

        save_btn = wait_enabled("Save new voice")
        if save_btn:
            click_at_xy(save_btn["x"], save_btn["y"]); _t.sleep(1.5)
            # After saving, the panel offers Add to character.
            add = wait_enabled("Add to character", timeout_s=30.0)
            if add:
                click_at_xy(add["x"], add["y"]); _t.sleep(1.4)
            else:
                errors.append("Add to character did not appear after saving the voice")
        else:
            # An already-saved performance may offer Add directly.
            add = wait_enabled("Add to character", timeout_s=10.0)
            if add: click_at_xy(add["x"], add["y"]); _t.sleep(1.4)
            else: errors.append("custom voice never became saveable")

    _t.sleep(1.0)
    if js("!!document.querySelector('.cdk-overlay-pane')"):
        _flow_click_js("[...document.querySelectorAll('.cdk-overlay-pane button')].find(x=>/^close$|Close/i.test((x.innerText||'')+x.getAttribute('aria-label')))", 0.8)
    voice = js("""(()=>{const b=[...document.querySelectorAll('button')].find(x=>/voice_selection/.test(x.innerText));
      return b?b.innerText.trim().replace(/\\n/g,' '):null;})()""")
    ok = bool(voice) and "Select a voice" not in voice and not errors
    return {"ok": ok, "voice": voice, "errors": errors}

def flow_create_character(name, prompt=None, image=None, personality=None,
                          voice_preset=None, voice_performance=None, voice_name=None,
                          voice_sample=None, style=None, timeout=180.0, finalize=True):
    """Create a Flow character from a prompt, an image, or both, and give it a voice.

    name:        character name (required).
    prompt:      description used to generate the portrait.
    image:       local image path used as the portrait reference instead of generating.
    personality: optional free text for "Character info".
    voice_preset:      built-in voice name, e.g. "Achernar".
    voice_performance: describe a voice; generates one (needs voice_name).
    style:       optional preset card: Eccentric, Professional, Wildcard, Familiar,
                 Wicked, Fantastical — seeds the prompt from a template.
    finalize:    click Done when the character is complete.

    At least one of `prompt` / `image` must be given; both together is allowed.
    Returns {"ok", "name", "url", "voice", "image", "errors", "warnings"}.
    """
    if not prompt and not image:
        raise ValueError("flow_create_character: pass prompt and/or image")
    errors, warnings = [], []
    url = _flow_char_open_new()
    if not url or _FLOW_CHAR_URL not in url:
        raise RuntimeError("flow_create_character: could not open the New character page")

    if style:
        if not _flow_click_js(f"[...document.querySelectorAll('button')].find(x=>/^{style}\\|/i.test(x.innerText.replace(/\\n/g,'|')))", 1.2):
            warnings.append(f"style card {style!r} not found; continuing without it")

    if prompt:
        if not js("!!document.querySelector('.ProseMirror')"):
            errors.append("character description box not found")
        else:
            js("(()=>{const e=document.querySelector('.ProseMirror');e.focus();e.click();})()"); _t.sleep(0.3)
            type_text(prompt, typing_delay=0.02); _t.sleep(0.5)

    # Image-only (no prompt) means uploading a portrait; with a prompt the image is
    # a starting point that the prompt edits. Both need a generated/committed slot
    # before the character editor exists, so the blank page only opens the editor
    # via Start generation — which requires description text.
    if image:
        # Upload the local file straight through the OS file dialog. The "Upload"
        # button creates no input[type=file], so the chooser is intercepted and the
        # dialog's own node receives the file — this is what makes image-only
        # characters possible without touching the project page.
        if not _flow_upload_via_chooser(
                "[...document.querySelectorAll('button')].find(x=>/^upload/.test((x.innerText||'').trim()))",
                image):
            errors.append(f"could not upload {image} through the file chooser")
        else:
            # Uploading opens the character editor directly. Do NOT wait for the
            # portrait tile's percentage to clear: it can sit at 99% indefinitely
            # while the name field, voice and Done are all already usable. Wait for
            # the editor instead.
            deadline = _t.time() + timeout
            while _t.time() < deadline and not js(f"!!document.querySelector({_FLOW_CHAR_NAME!r})"):
                _t.sleep(1.0)

    if prompt:
        # "Create portrait" only selects the mode; Start generation runs it. With an
        # image the upload itself opened the editor, so the prompt edits that image.
        _flow_click_js("[...document.querySelectorAll('button')].find(x=>/Create portrait|Portrait/.test(x.innerText))", 1.0)
        started = js("""(()=>{const b=[...document.querySelectorAll('button')].find(x=>x.getAttribute('aria-label')==='Start generation');
          return !!(b && !b.disabled);})()""")
        if not started:
            errors.append("Start generation is disabled")
        else:
            _flow_click_js("[...document.querySelectorAll('button')].find(x=>x.getAttribute('aria-label')==='Start generation')", 2.0)
            if not _flow_char_wait_idle(timeout=timeout):
                warnings.append("portrait generation did not finish within the timeout")
    portraits = js("document.querySelectorAll('img[src*=flow-content]').length")

    # Name and personality live on the character editor that generation opens.
    if not js(f"!!document.querySelector({_FLOW_CHAR_NAME!r})"):
        _t.sleep(2.0)
    if js(f"!!document.querySelector({_FLOW_CHAR_NAME!r})"):
        if not _flow_char_set_input(_FLOW_CHAR_NAME, name):
            errors.append("character name field did not accept the value")
        if personality and not _flow_char_set_input(_FLOW_CHAR_PERSONALITY, personality):
            warnings.append("personality field not found")
    else:
        errors.append("character editor (name field) not found")

    voice = None
    if voice_preset or voice_performance:
        v = flow_set_character_voice(preset=voice_preset, performance=voice_performance,
                                     name=voice_name, sample=voice_sample, timeout=timeout)
        voice = v["voice"]
        errors.extend(v["errors"])

    final_url = js("location.href")
    if finalize:
        _flow_click_js("[...document.querySelectorAll('button')].find(x=>/^Done$/.test(x.innerText.trim()))", 2.0)
        final_url = js("location.href")
    return {"ok": not errors, "name": name, "url": final_url, "voice": voice,
            "image": bool(portraits), "errors": errors, "warnings": warnings}

# --- Google Flow: video "Frames" first/last frame slots ---
# In video + Frames mode two slots appear under the prompt: a "Start" button and an
# "End" button, each opening a "Select a frame image" picker. A chosen image fills the
# slot and replaces the label with chip controls, so only the empty slot is findable
# by text — the filled ones are counted via `.chip-image`.

_FLOW_FRAME_TITLE = "Select a frame image"

def _flow_frames_available():
    """True when the prompt box shows Start/End frame slots (video + Frames mode)."""
    return js("""(()=>{const t=[...document.querySelectorAll('button')].map(b=>(b.textContent||'').trim());
      return t.includes('Start') || t.includes('End');})()""")

def _flow_frame_count():
    return js("document.querySelectorAll('button.chip-container .chip-image').length")

def _flow_frame_pick(kind, query=None, timeout=20.0):
    """Click a frame slot, pick an asset from its "Select a frame image" picker.

    kind:  "start" | "end" — the slot label to click. Only an empty slot carries the
           label; a filled one shows chip controls instead.
    query: optional asset-name filter, typed into the picker's search box.

    Returns {"ok", "asset"} — ok is False when the slot label is gone (already
    filled) or the picker never produced an asset.
    """
    k = str(kind).strip().lower()
    if k not in ("start", "end"): raise ValueError(f"frame kind must be start|end, got {kind!r}")
    label = "Start" if k == "start" else "End"

    # A frame picker left open from an earlier attempt swallows the slot click with
    # its backdrop and body clicks do not dismiss it. Close it with its own button.
    if js("!!document.querySelector('.cdk-overlay-pane')"):
        _flow_click_js("""[...document.querySelectorAll('.cdk-overlay-pane button')]
          .find(x=>x.getAttribute('aria-label')==='Close'||(x.textContent||'').trim()==='close')""", 1.0)
        _flow_wait_closed(4.0)

    before = _flow_frame_count()
    if not _flow_click_js(f"[...document.querySelectorAll('button')].find(x=>(x.textContent||'').trim()==={label!r})", 1.8):
        return {"ok": False, "asset": None, "error": f"{label} slot not found (already filled, or not in Frames mode)"}
    # The picker animates in; poll for its title rather than reading once.
    opened = False
    end_open = _t.time() + 6.0
    while _t.time() < end_open:
        pane = js("(()=>{const p=document.querySelector('.cdk-overlay-pane');return p?p.innerText:'';})()")
        if _FLOW_FRAME_TITLE in (pane or "") and js("!!document.querySelector('.cdk-overlay-pane .asset-item')"):
            opened = True; break
        _t.sleep(0.4)
    if not opened:
        return {"ok": False, "asset": None, "error": "frame picker did not open"}

    if query:
        if not _flow_search_box(): return {"ok": False, "asset": None, "error": "frame picker search box not found"}
        type_text(query, typing_delay=0.02); _t.sleep(1.0)

    deadline = _t.time() + timeout
    while _t.time() < deadline:
        item = js("""(()=>{const it=document.querySelector('.cdk-overlay-pane .asset-item');
          if(!it)return null;const r=it.getBoundingClientRect();
          return {x:r.x+r.width/2,y:r.y+r.height/2,name:it.innerText.trim().split(String.fromCharCode(10))[0]};})()""")
        if not item:
            # Leave no picker open on failure; its backdrop swallows the next click.
            _flow_click_js("""[...document.querySelectorAll('.cdk-overlay-pane button')]
              .find(x=>x.getAttribute('aria-label')==='Close'||(x.textContent||'').trim()==='close')""", 0.8)
            _flow_wait_closed(3.0)
            return {"ok": False, "asset": None, "error": "no asset matched in the frame picker"}
        click_at_xy(item["x"], item["y"])
        # Choosing the asset fills the slot and closes the picker. Some assets instead
        # leave an "Add to prompt" button to commit; handle both and verify by count.
        end = _t.time() + 5.0
        while _t.time() < end:
            if _flow_frame_count() > before:
                if js("!!document.querySelector('.cdk-overlay-pane')"): _flow_wait_closed()
                return {"ok": True, "asset": item["name"], "error": None}
            add = js("""(()=>{const b=[...document.querySelectorAll('.cdk-overlay-pane button')]
              .find(x=>/Add to prompt/i.test(x.textContent));
              if(!b||b.disabled)return null;const r=b.getBoundingClientRect();
              return {x:r.x+r.width/2,y:r.y+r.height/2};})()""")
            if add: click_at_xy(add["x"], add["y"])
            _t.sleep(0.4)
        return {"ok": False, "asset": item["name"], "error": "slot did not fill after selecting the asset"}
    return {"ok": False, "asset": None, "error": "timed out"}

def flow_set_frames(start=None, end=None, swap=False):
    """Set the first and/or last frame of a Frames-mode video.

    start: asset name (or name fragment) already in the project, picked from the
           Start slot's picker. Omit to leave the Start slot alone.
    end:   same for the End slot. Optional — a single-frame video only needs `start`.
    swap:  click Swap after both are set, exchanging first and last.

    Requires video + Frames mode:
        generate_setting_trigger(generate_type="video", video_type="frames")
    which this does not do for you, because the model, ratio and duration are
    separate choices.

    Returns {"ok", "start", "end", "frames", "errors"}.
    """
    if swap and start is None and end is None:
        return {"ok": _flow_swap_frames(), "start": None, "end": None,
                "frames": _flow_frame_count(), "errors": []}
    if not _flow_frames_available():
        raise RuntimeError("flow_set_frames: Start/End slots not present — call "
                           "generate_setting_trigger(generate_type='video', video_type='frames') first")
    errors, out = [], {}
    if start is not None:
        r = _flow_frame_pick("start", start)
        out["start"] = r["asset"]
        if not r["ok"]: errors.append(f"start frame: {r['error']}")
    if end is not None:
        r = _flow_frame_pick("end", end)
        out["end"] = r["asset"]
        if not r["ok"]: errors.append(f"end frame: {r['error']}")
    if swap and not errors: _flow_swap_frames()
    return {"ok": not errors, "start": out.get("start"), "end": out.get("end"),
            "frames": _flow_frame_count(), "errors": errors}

def _flow_swap_frames():
    return _flow_click_js("[...document.querySelectorAll('button')].find(x=>(x.textContent||'').trim()==='swap_horiz')", 1.4)

def flow_clear_frames():
    """Empty both frame slots. Returns slots cleared."""
    n = 0
    while js("document.querySelectorAll('button.chip-container').length"):
        gone = js("""(()=>{const c=[...document.querySelectorAll('button.chip-container')].pop();
          if(!c)return false;c.click();return true;})()""")
        if not gone: break
        n += 1; _t.sleep(0.6)
        if n > 6: break
    return n

# --- Google Flow: run a generation and read back the result ---
# Results land as tiles in the media grid, not in the prompt-box DOM. Each asset's
# id is the UUID in its flow-content URL (flow-content.google/image/<uuid>), which is
# the same id the picker uses, so a result can be fed back into a later call.

_FLOW_GEN_BTN = ("[...document.querySelectorAll('button')]"
                 ".find(x=>x.getAttribute('aria-label')==='Start generation')")

def _flow_asset_ids():
    """{id: kind} for every asset tile in the media grid.

    Identity, in order of reliability:
      * `data-media-id` on a descendant — the real asset UUID (images have it);
      * the UUID inside a flow-content URL;
      * the thumbnail's last path segment — video tiles carry only a signed
        flow.google.com/asb thumbnail and no data-media-id, so this is a
        session-unique stand-in, not the asset's real id.
    """
    return js("""(()=>{const out={};
      for(const t of document.querySelectorAll('flow-tile-container')){
        const kind=t.querySelector('flow-video-tile')?'video':'image';
        const mid=t.querySelector('[data-media-id]');
        let id=mid?mid.getAttribute('data-media-id'):null;
        if(!id){
          const img=[...t.querySelectorAll('img')].find(i=>(i.src||'').indexOf('flow-content.google')>=0);
          if(img){const parts=(img.src||'').split('/');
            const k=parts.findIndex(x=>x==='image'||x==='video');
            if(k>=0&&parts[k+1]) id=parts[k+1].split('?')[0];}
        }
        if(!id){
          const img=t.querySelector('img');
          if(img&&img.src){const seg=img.src.split('?')[0].split('/').pop();
            if(seg) id='thumb:'+seg.slice(0,40);}
        }
        if(id) out[id]=kind;
      }
      return out;})()""") or {}

def _flow_asset(key, kind):
    """Build an asset record. Only a real UUID gets a resolvable flow-content URL;
    a `thumb:` key is a session-unique stand-in for video tiles, so url is None
    rather than a URL that would 404."""
    if key.startswith("thumb:"):
        return {"id": key, "kind": kind, "url": None, "durable_id": False}
    return {"id": key, "kind": kind,
            "url": f"https://flow-content.google/{kind}/{key}", "durable_id": True}

def _flow_gen_state():
    return js("""(()=>({pending:document.querySelectorAll('flow-pending-tile').length,
      pct:(()=>{const m=document.body.innerText.match(/(\\d+)\\s*%/);return m?parseInt(m[1]):null;})()}))()""")

def _flow_wait_generation(before_ids, timeout=300.0, settle=6.0):
    """Wait until a generation started before this call has produced new assets.

    Success is a new asset id appearing with no pending tile left. But pending tiles
    can be stranded after the assets are already usable (seen at 99% and with
    output_count>1), so a result set that stops changing is also accepted. The
    percentage indicator is never trusted on its own.
    """
    start = _t.time()
    _t.sleep(settle)
    last_ids, stable_since = None, None
    while _t.time() - start < timeout:
        ids = _flow_asset_ids()
        new = {k: v for k, v in ids.items() if k not in before_ids}
        st = _flow_gen_state()
        if new:
            if st["pending"] == 0:
                return {"ok": True, "new": new, "elapsed": round(_t.time() - start, 1)}
            if ids == last_ids:
                if stable_since is None:
                    stable_since = _t.time()
                elif _t.time() - stable_since >= 5.0:
                    # Assets settled even though a pending tile never cleared.
                    return {"ok": True, "new": new, "elapsed": round(_t.time() - start, 1),
                            "stale_pending": st["pending"]}
            else:
                stable_since = None
        elif st["pending"] == 0 and st["pct"] is None and _t.time() - start > settle + 10:
            return {"ok": False, "new": {}, "elapsed": round(_t.time() - start, 1)}
        last_ids = ids
        _t.sleep(2.0)
    return {"ok": False, "new": {}, "elapsed": round(_t.time() - start, 1), "timeout": True}

def flow_generate(prompt=None, refs=None, mentions=None, frames=None, clear_refs=False,
                  finalize=True, timeout=300.0, **settings):
    """Configure (optionally), start a generation, and wait for the result.

    prompt:   prompt text. Omit to use whatever is already in the box.
    refs:     local image/video paths to attach as ingredients.
    mentions: list of asset names to insert as @-mentions, interleaved with `prompt`
              by writing "{{name}}" markers in the prompt text.
    frames:   {"start": name, "end": name} for Frames-mode video.
    settings: forwarded to generate_setting_trigger (generate_type, aspect_ratio,
              model, output_count, video_type, video_resolution, video_duration).

    Returns {"ok", "kind", "assets": [{"id","kind","url"}], "elapsed", "errors"}.

    Raises RuntimeError when Start generation is disabled — that means the prompt box
    is empty, and clicking a disabled button would silently do nothing.
    """
    errors = []
    if settings:
        r = generate_setting_trigger(**settings)
        errors.extend(r["warnings"])
    if frames:
        r = flow_set_frames(start=frames.get("start"), end=frames.get("end"))
        errors.extend(r["errors"])
    if prompt is not None:
        if mentions:
            parts, rest = [], prompt
            for name in mentions:
                marker = "{{" + name + "}}"
                if marker in rest:
                    head, rest = rest.split(marker, 1)
                    parts.extend([head, ("mention", name)])
                else:
                    parts.append(("mention", name))
            if rest: parts.append(rest)
            r = flow_set_prompt_with_mentions(parts)
            errors.extend(r["errors"])
        else:
            r = flow_set_prompt(prompt)
            if not r["ok"]: errors.append("prompt text did not land in the editor")
    if refs:
        r = flow_attach_ingredients(refs) if not clear_refs else (
            flow_clear_ingredients() and flow_attach_ingredients(refs))
        errors.extend(r["errors"]); errors.extend(r["warnings"])

    enabled = js(f"""(()=>{{const b={_FLOW_GEN_BTN};return !!(b && !b.disabled);}})()""")
    if not enabled:
        raise RuntimeError("flow_generate: Start generation is disabled — the prompt box is empty")
    before = _flow_asset_ids()
    _flow_click_js(_FLOW_GEN_BTN, 1.5)
    res = _flow_wait_generation(before, timeout=timeout)
    if res.get("timeout"): errors.append(f"generation did not finish within {timeout:g}s")
    elif not res["ok"] and not errors: errors.append("no new asset appeared after generation")

    assets = [_flow_asset(k, v) for k, v in res["new"].items()]
    if finalize and assets:
        # Close a result preview if one opened, so the next call starts from the grid.
        if js("!!document.querySelector('.cdk-overlay-pane')") and not _flow_overlay_is_picker():
            js("(()=>{const b=[...document.querySelectorAll('.cdk-overlay-pane button')].find(x=>x.getAttribute('aria-label')==='Close');if(b)b.click();})()")
            _t.sleep(0.6)
    kinds = {a["kind"] for a in assets}
    return {"ok": not errors, "kind": (kinds.pop() if len(kinds) == 1 else None),
            "assets": assets, "elapsed": res.get("elapsed"), "errors": errors}

def _flow_overlay_is_picker():
    """The asset pickers all show a search box; a result preview does not."""
    return bool(js("!!document.querySelector('.cdk-overlay-pane input.search-input')"))

def _flow_show_all_media():
    """Make sure the media grid is the active library tab.

    flow_list_results and flow_download read tiles from the media grid. On the
    Characters or Scenes tab those tiles are not rendered (character cards take their
    place), so listing returned 0 for a project that has assets. Click "All media"
    when no media tile is present.
    """
    if js("""(()=>{for(const t of document.querySelectorAll('flow-tile-container')){
      if(t.querySelector('flow-image-tile,flow-video-tile,[data-media-id]'))return true;}
      return false;})()"""): return True
    return _flow_click_js("[...document.querySelectorAll('button')].find(x=>/All media/.test(x.textContent||''))", 2.0)

def _flow_chip_count():
    return js("document.querySelectorAll('flow-ingredient-chip').length")

def _flow_remove_last_chip():
    """Remove the most recently added ingredient chip. Returns True if one went."""
    gone = js("""(()=>{const chips=[...document.querySelectorAll('flow-ingredient-chip')];
      const last=chips[chips.length-1]; if(!last)return false;
      const b=last.querySelector('button.chip-container'); if(!b)return false;
      b.click(); return true;})()""")
    _t.sleep(0.8)
    return bool(gone)

def flow_list_results(kind=None, limit=20):
    """Assets currently rendered in the project's media grid, newest first.

    kind: "image" | "video" | None for both.
    Returns {"ok", "assets": [{"id","kind","url"}], "count"}.
    """
    _flow_show_all_media()
    ids = _flow_asset_ids()
    want = str(kind).strip().lower() if kind else None
    assets = [_flow_asset(k, v) for k, v in ids.items() if want is None or v == want]
    return {"ok": True, "assets": assets[:limit], "count": len(assets)}

# --- Google Flow: download a generated asset at the best allowed quality ---
# Each tile's More options menu has Download, which opens a quality submenu:
#   images  -> "1K Original size", "2K Upscaled", "4K Upscaled", "Upgrade"
#   videos  -> "720p Original size", "4K Upscaled", "Upgrade"
# Options the plan does not allow are rendered with tabindex="-1"; "Upgrade" is a
# call to action, never a quality. Upscaled choices are asynchronous: Flow shows
# "Upscaling your image, download will start automatically." and writes the file
# a few seconds later, so the primitive waits for a new file to appear.

_FLOW_QUALITY_RANK = {"360p": 360, "720p": 720, "1080p": 1080,
                      "1K": 1000, "2K": 2000, "4K": 4000}
_FLOW_DEFAULT_DL = "~/Downloads/flow"

def _flow_quality_options():
    """[(label, rank, enabled)] from the open download submenu."""
    raw = js("""JSON.stringify([...document.querySelectorAll('[role=menuitem]')]
      .map(m=>({t:(m.innerText||'').trim().replace(/\\n/g,' '),tab:m.getAttribute('tabindex')}))
      .filter(o=>/Original size|Upscaled|Upgrade/i.test(o.t)||/^\\d+(p|K)\\b/i.test(o.t)))""")
    out = []
    for o in _json.loads(raw or "[]"):
        text = o["t"]
        if "upgrade" in text.lower(): continue
        head = text.split(" ")[0]
        rank = _FLOW_QUALITY_RANK.get(head.upper()) or _FLOW_QUALITY_RANK.get(head.lower())
        if rank is None:
            # "2K Upscaled" style already covered; anything else is not a quality.
            continue
        out.append((head, rank, o["tab"] != "-1"))
    return out

def _flow_tile_for(asset_id=None, kind=None):
    """Centre of the More-options button for the tile matching `asset_id`/`kind`.

    asset_id matches a data-media-id UUID or a `thumb:` key; with neither, the first
    tile of `kind` is used (the grid is newest-first).
    """
    want = None
    if asset_id:
        want = asset_id.split(":", 1)[1] if asset_id.startswith("thumb:") else asset_id
    return js(f"""(()=>{{const want={_json.dumps(want)};const kind={_json.dumps(kind)};
      for(const t of document.querySelectorAll('flow-tile-container')){{
        const isVid=!!t.querySelector('flow-video-tile');
        const isImg=!!t.querySelector('flow-image-tile');
        if(kind==='video'&&!isVid)continue;
        if(kind==='image'&&!isImg)continue;
        if(want){{
          const mid=t.querySelector('[data-media-id]');
          const img=t.querySelector('img');
          const seg=img&&img.src?img.src.split('?')[0].split('/').pop():'';
          const hit=(mid&&mid.getAttribute('data-media-id')===want)||(seg&&seg.indexOf(want)>=0)
                   ||(img&&(img.src||'').indexOf(want)>=0);
          if(!hit)continue;
        }}
        const b=t.querySelector('button[aria-label="More options"]');
        if(!b)continue;
        const r=b.getBoundingClientRect();
        return {{x:r.x+r.width/2,y:r.y+r.height/2}};
      }}
      return null;}})()""")

def _flow_wait_new_file(folder, before, timeout=180.0):
    """Wait for a new, complete file in `folder`. Size must be stable across two polls."""
    deadline = _t.time() + timeout
    last = {}
    while _t.time() < deadline:
        try:
            now = {f: _os.path.getsize(_os.path.join(folder, f))
                   for f in _os.listdir(folder) if f not in before and not f.endswith(".crdownload")}
        except FileNotFoundError:
            now = {}
        if now:
            if now == last and all(now[f] > 0 for f in now):
                name = max(now, key=lambda f: _os.path.getmtime(_os.path.join(folder, f)))
                return _os.path.join(folder, name)
            last = now
        _t.sleep(1.5)
    return None

def _flow_close_menus():
    """Dismiss any open mat-menu. body clicks do not close these; Escape does."""
    for _ in range(4):
        if not js("document.querySelectorAll('[role=menu]').length"): return True
        press_key("Escape"); _t.sleep(0.4)
    if js("document.querySelectorAll('[role=menu]').length"):
        js("document.body.click()"); _t.sleep(0.4)
    return not js("document.querySelectorAll('[role=menu]').length")

def flow_download(asset_id=None, kind=None, quality="best", folder=None, timeout=180.0):
    """Download a generated asset at the best quality the plan allows. See _impl."""
    try:
        return _flow_download_impl(asset_id=asset_id, kind=kind, quality=quality,
                                   folder=folder, timeout=timeout)
    finally:
        # Always dismiss the menu: a leftover one swallows the next tile's
        # More-options click, which surfaced as "Download menu item not found".
        try: _flow_close_menus()
        except Exception: pass

def _flow_download_impl(asset_id=None, kind=None, quality="best", folder=None, timeout=180.0):
    """Download a generated asset, choosing the best quality the plan allows.

    asset_id: id from flow_generate()/flow_list_results() (UUID, or `thumb:` key).
              Omit to take the first tile of `kind`.
    kind:     "image" | "video" — narrows the tile search and picked quality.
    quality:  "best" (default) picks the highest enabled tier and quietly skips
              locked ones (e.g. 4K on a plan that does not allow it), so a Pro
              plan downloads 2K/720p instead of failing. Or name one explicitly:
              "original", "1K", "2K", "720p", "1080p", "4K". A locked explicit
              choice raises rather than silently downgrading.
    folder:   destination directory; created if missing. Defaults to
              ~/Downloads/flow.

    Returns {"ok", "path", "quality", "available", "requested", "errors"}.
    """
    dest = _os.path.expanduser(folder or _FLOW_DEFAULT_DL)
    _os.makedirs(dest, exist_ok=True)
    errors = []

    # A menu left open from an earlier call (including one that raised) keeps the
    # next More-options click from opening a fresh one.
    _flow_close_menus()
    # Tiles only exist while the media grid is the active tab.
    _flow_show_all_media()

    tile = _flow_tile_for(asset_id, kind)
    if not tile:
        raise RuntimeError(f"flow_download: no {kind or 'asset'} tile matched {asset_id!r}")

    before = set(_os.listdir(dest))
    cdp("Browser.setDownloadBehavior", behavior="allow", downloadPath=dest, eventsEnabled=True)

    # Open the menus for the resolved tile only.
    click_at_xy(tile["x"], tile["y"]); _t.sleep(1.2)
    if not _flow_click_js("[...document.querySelectorAll('[role=menuitem]')].find(x=>/Download/i.test(x.innerText))", 1.6):
        raise RuntimeError("flow_download: Download menu item not found")

    opts = _flow_quality_options()
    if not opts:
        raise RuntimeError("flow_download: no quality options appeared")
    available = [o[0] for o in opts if o[2]]

    if str(quality).strip().lower() == "best":
        enabled = [o for o in opts if o[2]]
        if not enabled: raise RuntimeError("flow_download: no enabled quality option")
        head, rank, _ = max(enabled, key=lambda o: o[1])
    else:
        want = str(quality).strip()
        match = next((o for o in opts if o[0].lower() == want.lower()), None)
        if match is None and want.lower() == "original":
            match = next((o for o in opts if o[0].lower().endswith("p") or o[0].upper().endswith("K")), None)
        if match is None:
            raise ValueError(f"flow_download: quality {quality!r} not offered; available {available}")
        if not match[2]:
            raise RuntimeError(f"flow_download: {match[0]} is locked on this plan; available {available}")
        head = match[0]

    # Click the chosen tier. Angular Material menu items are buttons, so a direct
    # DOM click is deterministic; a coordinate click has to survive the submenu's
    # open animation and the pointer passing over other rows. Try the DOM click
    # first and fall back to the pointer only if no download starts.
    fired = js(f"""(()=>{{const m=[...document.querySelectorAll('[role=menuitem]')]
      .find(x=>(x.innerText||'').trim().startsWith({_json.dumps(head)}));
      if(!m)return false;m.click();return true;}})()""")
    if not fired:
        raise RuntimeError(f"flow_download: could not click {head}")

    path = _flow_wait_new_file(dest, before, timeout=8.0)
    if not path and fired:
        # Some tiers need a real pointer event; retry through the menu.
        _flow_close_menus()
        click_at_xy(tile["x"], tile["y"]); _t.sleep(1.2)
        _flow_click_js("[...document.querySelectorAll('[role=menuitem]')].find(x=>/Download/i.test(x.innerText))", 1.6)
        target = js(f"""(()=>{{const m=[...document.querySelectorAll('[role=menuitem]')]
          .find(x=>(x.innerText||'').trim().startsWith({_json.dumps(head)}));
          if(!m)return null;const r=m.getBoundingClientRect();
          return {{x:r.x+r.width/2,y:r.y+r.height/2}};}})()""")
        if target: click_at_xy(target["x"], target["y"])
    path = _flow_wait_new_file(dest, before, timeout=timeout)
    if not path:
        errors.append(f"no file appeared in {dest} within {timeout:g}s "
                      f"(upscaled downloads can be slow)")
    return {"ok": bool(path), "path": path, "quality": head, "available": available,
            "requested": quality if quality != "best" else "best", "errors": errors}
