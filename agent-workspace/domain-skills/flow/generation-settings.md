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
