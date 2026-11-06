# Google Flow

Generate images and videos in a `flow.google.com` project, create reusable characters,
and download the results — all through primitives already loaded from
`agent_helpers.py`. No setup step: import nothing, call them directly.

These files are surfaced by `goto_url()` for a `flow.google.com` project when
`BH_DOMAIN_SKILLS=1`; read `README.md` first, then the one branch you need.

## Files in this folder

- `images-and-videos.md` — the pipeline: settings, prompt, references, generate
- `characters.md` — create a character from a prompt and/or a portrait, with a voice
- `video-frames.md` — first/last-frame video: an image per slot
- `downloading.md` — pick the best tier the plan allows, write the file to disk
- `many-references.md` — scenes needing several references: how many are sane,
  compression, and how chips and mentions combine

## The pipeline

Four steps. Each primitive returns its own **read-back**, so the completion criterion
is a field in the result, not a judgement call.

| Step | Call | Done when |
| --- | --- | --- |
| 1 Configure | `generate_setting_trigger(...)` | `trigger` label shows the mode, model and count you asked for |
| 2 Compose | `flow_compose_prompt(prompt, refs=[...])` | `prompt` matches your text and `ingredients` equals the reference count |
| 3 Generate | `flow_generate(...)` | `ok` is true and `assets` holds at least one entry |
| 4 Download | `flow_download(asset_id=...)` | `path` names a file that exists |

A minimal image:

```python
flow_generate(
    prompt="a ceramic bowl of lemons on linen, soft window light",
    generate_type="image", aspect_ratio="1:1", output_count=1,
)
# {'ok': True, 'kind': 'image', 'elapsed': 26.1,
#  'assets': [{'id': '50aa573c-…', 'kind': 'image', 'durable_id': True, ...}]}

flow_download(kind="image", folder="/path/to/out")
```

`flow_generate` runs steps 1–3 in one call: pass the `generate_setting_trigger` options
directly (`generate_type=`, `aspect_ratio=`, …) plus `refs`, `mentions` or `frames`.
Compose by hand when you want to inspect each step.

## Primitive index

| Primitive | Use |
| --- | --- |
| `generate_setting_trigger` | image/video, model, ratio, count, video type, resolution, duration |
| `flow_set_prompt` | put text in the prompt box |
| `flow_compose_prompt` | text + reference files, one call |
| `flow_compose_scene` | several references of mixed kinds, capped and verified |
| `flow_attach_ingredients` / `flow_attach_assets` / `flow_clear_ingredients` | reference files, or project assets by name |
| `flow_rename_asset` | rename an asset so a mention resolves to it |
| `flow_set_prompt_with_mentions` / `flow_mention` / `flow_clear_mentions` | inline `@` references inside the text |
| `flow_set_frames` / `flow_clear_frames` | first/last frame slots for Frames-mode video |
| `flow_create_character` / `flow_set_character_voice` | characters and their voices |
| `flow_generate` | run a generation and wait for the result |
| `flow_list_results` | what is already in the project |
| `flow_download` | best-allowed tier, written to a folder |

## Shared rules

**Read-back over assumption.** Every primitive returns what the page actually shows
after the action. Trust `trigger`, `prompt`, `ingredients`, `frames` and `path`; treat
`ok` as the summary of those. When a field disagrees with what you asked for, the
action did not take — report it rather than generating anyway.

**Assets.** A result is an **asset** in the project grid. Images carry a real UUID
(`durable_id: True`) that later calls accept. Videos carry only a session-scoped
`thumb:` key (`durable_id: False`) — reuse a generated video as a file, not as an id.
Details in `downloading.md`.

**Errors.** `ValueError` means the request was invalid before the page was touched
(unknown model, ratio not offered for that mode, count outside 1–4). `RuntimeError`
means the page is not in the expected state — wrong tab, project not rendered, prompt
box empty. Read the message; it names the remedy.

**Reuse before generating.** `flow_list_results()` shows what already exists. If the
asset you need is there, skip to `flow_download`.

**Empty projects.** A project with no assets has no tiles; `flow_list_results` returns
`count: 0` rather than failing. Generate first.
