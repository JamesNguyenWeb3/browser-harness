# Google Flow — generation settings

Field-tested against `flow.google.com/project/<id>` on 2026-10-31 with a local Chrome attached.
The primitive lives in `agent_helpers.py` as `generate_setting_trigger()`.

## Quick summary

- Flow's prompt-box settings are a button with `aria-label="Settings trigger"`. Clicking it reveals a panel of `[role=radio]` toggles; the panel closes on an outside click.
- **Never hardcode the `mat-button-toggle-N` ids.** They are reassigned on every render: in one session Frames was `-74`, in the next `-7`. The helper finds options by their flattened visible text and never uses ids.
- The trigger's own label is the read-back: image mode shows `🍌 <model> crop_<ratio> x<n>`, video shows `Video · <res> · <dur>s crop_<ratio> x<n>`. `generate_setting_trigger()` asserts against it.
- Changing mode or model rebuilds the option groups, so the helper re-opens the panel before each group and retries a radio that a re-render ate.

## Calling it

```python
generate_setting_trigger(generate_type="Image", aspect_ratio="9:16", model="nano banana 2.1", output_count=2)
# -> {'ok': True, 'trigger': '🍌 Nano Banana 2.1 crop_9_16 x2', 'applied': {...}, 'warnings': []}
```

Arguments:

| arg | values | default |
| --- | --- | --- |
| `generate_type` | `"image"` / `"video"` (case-insensitive; `img`/`vid` accepted) | `"video"` |
| `aspect_ratio` | image `16:9 4:3 1:1 3:4 9:16`; video `16:9 9:16` only | `16:9` |
| `model` | image `nano banana 2.1`, `nano banana pro`, `nano banana 2 lite`; video `omni 1.1`, `veo 3.1 lite`, `veo 3.1 fast`, `veo 3.1 quality` | image `nano banana 2.1`; video `omni 1.1` |
| `output_count` | 1–4 | image 2; video 1 |
| `video_type` | `ingredients` / `frames` | `ingredients` |
| `video_resolution` | 360 / 720, **omni only** | 720 |
| `video_duration` | 4 / 6 / 8 / 10, **omni only** | 10 |

## Deciding what to call from a prompt

The prompt names the media type, and often the aspect ratio and the deliverable:

- *"Generate for me image of the character A with … for my short video"* → the deliverable is a video, so 9:16; the request is an image.
  `generate_setting_trigger(generate_type="Image", aspect_ratio="9:16", model="nano banana 2.1", output_count=2)`
- *"make 3 vertical 8-second clips"* → `generate_type="video", aspect_ratio="9:16", output_count=3, video_duration=8`
- *"a 1:1 thumbnail"* → `generate_type="image", aspect_ratio="1:1"`
- Nothing stated → call with no arguments beyond the type and let the defaults apply; do not invent values.

## Model-dependent controls (the main trap)

`video_resolution` and `video_duration` exist **only when the Omni family is selected**. Pick a Veo model and those toggles disappear — the panel shows just Frames/Ingredients, aspect ratio and output count — and the trigger shows the model's own resolution and duration.

So pass resolution/duration with Omni. If you pass them with a Veo model the helper drops them and says so:

```python
{'ok': True, 'trigger': 'Video · 720p · 8s crop_16_9 x1',
 'warnings': ['veo 3.1 lite exposes no resolution/duration controls; its defaults apply']}
```

Order matters inside the helper: mode → video_type → aspect ratio → model → count → resolution → duration. Selecting the model first would drop the duration controls before they could be set.

## Errors

`ValueError` is raised **before any page interaction** for an unsupported combination:

- `generate_type` not image/video
- `aspect_ratio` not offered for that type (video has only 16:9 and 9:16)
- unknown `model`
- `output_count` outside 1–4
- `video_*` arguments passed with `generate_type="image"`
- `video_resolution`/`video_duration` outside their sets on Omni

`RuntimeError` means the settings trigger was not found — wrong tab, wrong page, or the project has not rendered. Check `page_info()` first.

Treat `ok: False` or a non-empty `warnings` as "the panel is not what you asked for", and read `trigger` to see what it actually is. Do not assume the click worked.

## Limits

- Applies to the prompt-box settings only. It does not type the prompt or start generation (`Start generation`, `aria-label="Start generation"`).
- Do not click Settings, Home, or project-level buttons as part of this.
- The panel is transient: if another action happens between calls it may be closed. The helper re-opens it itself.

---

# Prompt and reference ingredients

Field-tested against `flow.google.com/project/344ca08e-cbf4-4588-9029-be9eab5b6dbb` on 2026-11-01.
Primitives: `flow_compose_prompt()`, `flow_set_prompt()`, `flow_attach_ingredients()`, `flow_clear_ingredients()`.

## Quick summary

- The prompt box is `<flow-rich-text-editor>` wrapping a ProseMirror `contenteditable` (`flow-rich-text-editor .ProseMirror`).
- **ProseMirror ignores JS edits.** Setting `textContent`, `innerHTML`, or a Range + `Selection` does not change the prompt. Text must go in through real key events — `type_text()` works, and clearing needs the keyboard Select-All then Backspace.
- References are **not** inside the editor. Each becomes a `<flow-ingredient-chip>` beside it, with an `<img class="chip-image">`.
- **Flow accepts at most 4 ingredients.** The picker silently stops adding past four; the helpers warn instead of failing.
- The upload input is `input[type=file]` with `accept=".png,.jpg,.jpeg,.webp,.gif,.heif,.heic,.mp4,.m4v,.mov,.3gp,.avi"` and `multiple`. It exists only while the picker is open, and a fresh node is created each time — resolve it per upload or CDP answers `Could not find node with given id`.

## The one-call case

```python
flow_compose_prompt(
    "Character A stands in a rain-soaked alley, neon signs on wet asphalt.",
    refs=["/path/to/characterA.png"],
    clear_refs=True,
)
# -> {'ok': True, 'prompt': '...', 'ingredients': 1, 'errors': [], 'warnings': []}
```

`clear_refs=True` drops existing chips first, so `refs` is exactly the attached set. Use it whenever the reference list matters — otherwise chips from a previous task stay attached.

Reading a request like *"generate for me image of character A (ref A is in /path/to/characterA.png) doing …"*:

1. `generate_setting_trigger(generate_type="Image", ...)` for the mode and format.
2. `flow_compose_prompt(prompt, refs=["/path/to/characterA.png"], clear_refs=True)` to type the prompt and attach the reference.
3. Only then start generation. The primitives never click **Start generation**.

## How attaching works, and why it surprised me

Per file: open picker → **Upload media** → set the file input → wait for the item to leave "Uploading" → **select that item** → **Add to prompt** → wait for the picker to close.

Two traps, both of which produced silent no-ops before they were fixed:

- **The picker does not auto-select a new upload.** Whatever was selected before stays selected, so adding without selecting attaches the *previous* asset. Flow dedupes it against the chip already in the prompt and the count does not move.
- **"Uploading" can persist for many seconds**, and the recents list can already contain earlier uploads with the same filename. Selection therefore waits for the first match that is not uploading, then clicks it by name.

The helpers treat "Add to prompt clicked but chip count did not rise" as an error, so a dedupe no longer reports success.

## Removing references

`flow_clear_ingredients()` clicks each chip's remove control and returns how many it removed. There is no per-file removal by name; clear and re-attach.

## Limits

- Does not type into or start generation; does not edit the video itself.
- Requires the project page to render: a missing project redirects to `/404?reason=project` with "Project not found", and every primitive raises rather than guessing.
- Uploading large videos is slow; the settle wait is 25 s per file before it reports an error.

---

# @-mentions (inline references)

Field-tested against `flow.google.com/project/e23b42bb-8b41-42e2-9eaf-d5f25a224edb` on 2026-11-01.
Primitives: `flow_mention()`, `flow_set_prompt_with_mentions()`, `flow_clear_mentions()`.

## Quick summary

- Typing `@` in the prompt opens the **same asset picker** as the ingredients button. Picking an asset replaces the `@` with an inline `<span class="mention-chip" data-mention-id=… data-reference-type=media>`, and **also adds a chip beside the prompt box**.
- **Never type the query into the editor.** While the popup is open, keystrokes are mirrored into the popup's search box *and* left in the prompt, so `@20c7` would end up in the prompt text. `@` moves focus to the popup's `input.search-input` for you; type there.
- The `@` is consumed only when an asset is picked. A query that matches nothing leaves a stray `@` and removes the Add button — `flow_mention()` deletes the `@` and raises.
- Search filters only the **active tab** (All/Images/Videos/Voices/Characters/Avatars). Searching for a voice while on Images finds nothing; switch tabs first.

## Composing a prompt with mentions

```python
flow_set_prompt_with_mentions([
    "A studio fashion sequence. Starting with ", ("mention", "Lisa"),
    ", she is holding ", ("mention", "RedMud"), ".",
])
# -> {'ok': True, 'text': 'A studio fashion sequence. Starting with Lisa, she is holding RedMud.',
#     'mentions': 2, 'chips': 2, 'errors': []}
```

Each string is literal text; each `("mention", name)` is one `@` pick. Picking leaves the caret back in the editor, so the next literal continues the same sentence.

Single mention, when the text is already in place:

```python
flow_mention("RedMud")   # types @, filters, picks, returns the label
```

`flow_mention` raises `RuntimeError` if nothing matches, after removing the stray `@`.

## Two behaviours that make the naive sequence fail

- **Caret placement.** After a pick, the editor's last child is the mention `<span>`. Collapsing the selection to the editor's last child puts the next `@` *inside* the chip, so it never opens the popup. The helper collapses to the end of the paragraph instead.
- **Picking can take one of two paths.** Clicking the asset may add the mention outright and close the overlay, or only select it and leave **Add to prompt** to commit. The helper accepts either and confirms success by counting new mention spans — never by the click's return value, because the overlay closes underneath the click.

## Clearing

- `flow_set_prompt()` wipes mention spans along with the text.
- **It does not remove the ingredient chips.** Mentions add chips beside the box; clear those with `flow_clear_ingredients()`. A prompt reset therefore leaves references attached unless you clear both.
- `flow_clear_mentions()` removes the inline spans while keeping the surrounding words.

## Limits

- Mention resolution is by first match in the active tab; there is no exact-name matching, so pick names that are unique in that tab's list.
- Requires the asset to already exist in the project (upload it first with `flow_attach_ingredients`).

---

# Characters

Field-tested against `flow.google.com/project/e23b42bb-…` on 2026-11-01.
Primitives: `flow_create_character()`, `flow_set_character_voice()`.

## Quick summary

Characters live on their own sub-page: `/project/<id>/character` is the blank creator,
`/character/<uuid>` is an existing one. The blank page shows style cards, a description
editor and **Start generation**; generating opens the character **editor**, which is the
only place name, voice, personality and portrait actually live.

```python
flow_create_character(
    name="Mara",
    prompt="A woman in her early 30s, copper hair, wool coat, overcast daylight.",
    personality="Reserved, precise, quietly warm.",
    voice_preset="Aoede",
)
```

Returns `{"ok", "name", "url", "voice", "image", "errors", "warnings"}`.

## What is actually reachable

| Want | Works? |
| --- | --- |
| Prompt-only character | Yes |
| Preset voice | Yes |
| Custom voice from a performance description | Yes — Preview → Save new voice → Add to character |
| Image-only character (upload a local portrait) | Yes — see below |
| Prompt + image together | Yes |

## Uploading a local portrait

The character page's `Upload` button creates **no** `input[type=file]` in the DOM — it
calls straight into the browser's file chooser, so `DOM.setFileInputFiles` has no node
to target by selector. The way in is to intercept the dialog:

```python
cdp("Page.setInterceptFileChooserDialog", enabled=True)   # before the click
# click Upload -> Page.fileChooserOpened carries params.backendNodeId
cdp("DOM.setFileInputFiles", files=[path], backendNodeId=backendNodeId)
cdp("Page.setInterceptFileChooserDialog", enabled=False)  # after
```

`_flow_upload_via_chooser()` wraps this. Interception is armed only for the click,
because while it is on it suppresses every other file dialog on the page.

Uploading an image opens the character editor directly and starts a portrait
generation from it — no description text is needed, so **image-only characters work**:

```python
flow_create_character(name="Nadia", image="/path/to/portrait.png",
                      voice_preset="Erinome")
```

Real workflow order: Upload → choose file → wait for the editor → set name →
voice (optional) → Character info (optional) → Done.

**Do not wait on the portrait tile's percentage.** It can sit at 99% indefinitely
(`flow-pending-tile` -> `.loading-percentage`) while the name field, voice selector
and Done are all already usable. Waiting for it to clear hangs the whole flow. The
primitive waits for `input.name-input` instead.

**The name field must be typed over, not assigned.** Clicking after clearing puts the
caret inside the placeholder and typing inserts into it
("Untitled chTest Namearacter"). Select the field with Cmd/Ctrl+A, backspace, type,
then dispatch `change` and blur so the value commits.

## Custom voice state machine (the fiddly part)

Measured by stepping the panel:

| Step | Button shown |
| --- | --- |
| Panel opens | `Preview` + `Save new voice` (disabled) |
| Editing performance or sample text | `Save new voice` (disabled) |
| Click `Preview` | `hourglass_top` on Preview, everything disabled |
| Preview finishes | `Save new voice` enabled |
| Click `Save new voice` | `Add to character` |
| Click `Add to character` | voice attached, panel closes |

Skipping **Save new voice** leaves the voice unpublished and never offers
`Add to character` — that was the failure that took longest to diagnose. `Preview`
also takes 10–30 s, so the helper waits for the button to leave its disabled state
rather than sleeping a fixed time.

The panel **remembers** the previous custom voice: reopening it can already show
`Add to character` with no Preview. The helper re-runs Preview when you pass a new
`performance`, so the audio matches the description.

## Two behaviours worth knowing

- **Preset lookup must be exact.** Searching narrows the list asynchronously; an
  intermediate row carries the query text as its own label. Matching on substring
  once stored a voice literally named `aoede`. The helper waits for the list to
  settle and matches the row's name exactly.
- **The name field appears only after the performance field is non-empty.** Filling
  `voice-name-input` first fails with "not found".

## Limits

- Voice presets are the built-ins listed in the panel (Achernar, Achird, Aoede, …).
- The portrait generates as several variants (3 observed); the primitive reports
  `image: True` but does not pick among them.
- `finalize=True` clicks **Done**, which returns to the project and saves the
  character. Pass `False` to stay on the editor.

---

# Frames (first / last frame video)

Field-tested against `flow.google.com/project/e23b42bb-…` on 2026-11-01.
Primitives: `flow_set_frames()`, `flow_clear_frames()`.

## Quick summary

In **video + Frames** mode two slots appear under the prompt box:

```
[Start]  (swap_horiz)  [End]
```

Each opens a **"Select a frame image"** picker. Choosing an asset fills the slot and
replaces its label with chip controls (`cancel` + `close`), so a **filled slot has no
text to find it by** — the primitives count `button.chip-container .chip-image`
instead.

```python
generate_setting_trigger(generate_type="video", video_type="frames")  # enter Frames mode
flow_set_frames(start="characterA.png")            # last frame optional
flow_set_frames(start="characterA.png", end="characterB.png")
```

The End frame is genuinely optional: `flow_set_frames(start=...)` leaves it empty and
the video generates from the start frame alone.

`flow_set_frames` does **not** switch into Frames mode for you — model, ratio and
duration are separate choices — and raises if the slots are absent.

## Behaviour worth knowing

- **A left-open picker swallows the next click.** Its backdrop eats the slot click and
  `document.body.click()` does not dismiss it; only the pane's own `Close` does. The
  primitive closes any open picker before starting, and on a no-match failure, so a
  retry works. Left unhandled this showed up as a confusing "frame picker did not
  open" even though the click landed.
- **The picker animates in**, so wait for both the title *and* an asset row before
  searching rather than reading the pane once.
- **Search is the picker's own box**, same as the mention picker; it filters within the
  active tab (Images / Uploads).
- **Success is a rising chip count**, not a click return value — the pane closes under
  the click. Some assets also need an "Add to prompt" commit; both paths are handled.
- **Only one asset in this project**, so a two-frame test sets the same image in both
  slots. Distinct frames need distinct assets — upload them with
  `flow_attach_ingredients()` first, or via the picker's **Upload media** (which, unlike
  the character page, does expose a `input[type=file]` here).

## Clearing

`flow_clear_frames()` clicks each filled slot's remove control and returns how many it
emptied; the Start/End labels come back.

---

# Running a generation and reading the result

Field-tested against `flow.google.com/project/e23b42bb-…` on 2026-11-01.
Primitives: `flow_generate()`, `flow_list_results()`.

## Quick summary

```python
flow_generate(
    prompt="a ceramic bowl of lemons on linen, soft window light",
    generate_type="image", aspect_ratio="1:1", model="nano banana 2.1", output_count=1,
)
# -> {'ok': True, 'kind': 'image', 'elapsed': 26.1,
#     'assets': [{'id': '50aa573c-…', 'kind': 'image', 'url': 'https://flow-content.google/image/50aa573c-…'}],
#     'errors': []}
```

`flow_generate` optionally configures settings, sets the prompt / refs / mentions /
frames, clicks **Start generation**, and waits for the result. `flow_list_results()`
returns what is currently in the media grid.

## What the page does

- **Start generation is disabled while the prompt box is empty.** The primitive raises
  rather than clicking a dead button.
- Results are **tiles in the media grid**, not in the prompt-box DOM, so `page_info()`
  never shows them.
- A run goes: button disables -> `flow-pending-tile` appears -> a percentage climbs ->
  the pending tile becomes a result tile. Measured: image ~26 s, 4 s video ~34 s.
- **The percentage is not a completion signal.** It can sit at 99% indefinitely while
  the result is already usable. Completion is judged by a new asset id appearing *and*
  no pending tile remaining.

## Asset identity

| Tile | Identity |
| --- | --- |
| Image | `data-media-id` on a descendant — the real asset UUID |
| Image (fallback) | UUID inside the `flow-content.google/image/<uuid>` URL |
| Video | **no `data-media-id`**; only a signed `flow.google.com/asb/…` thumbnail, so the id is `thumb:<segment>` — session-unique, not the real asset id |

That asymmetry is why `flow_list_results()` reports `kind` per asset: a `thumb:` id is
usable for "did something new appear" but should not be treated as a durable asset
reference.

## Feeding a result into the next call

Image results carry a real UUID, which is the same id the pickers use, so a generated
image can be referenced by name in a later `flow_set_frames` / `flow_attach_ingredients`
call once it is visible in the picker. Video results do not expose a UUID in the grid.

## Limits

- No download/export primitive: results are identified, not saved to disk.
- `flow_generate` waits for the *first* new asset; with `output_count > 1` it returns
  whatever ids appeared by the time the pending tiles cleared.
- A generation that fails server-side leaves no new asset and reports
  `no new asset appeared after generation`.
