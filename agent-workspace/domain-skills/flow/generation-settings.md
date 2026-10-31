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
