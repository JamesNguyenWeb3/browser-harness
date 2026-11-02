# Images and videos

The main pipeline: choose the output shape, write the prompt, attach references, run.

## Reading a request

The prompt names the deliverable and often the framing; map that to `generate_type`
and `aspect_ratio` before writing anything.

| Request | Call |
| --- | --- |
| "generate an image of character A … for my short video" | `image`, `9:16` — the deliverable is vertical, the ask is a frame |
| "make 3 vertical 8-second clips" | `video`, `9:16`, `output_count=3`, `video_duration=8` |
| "a 1:1 thumbnail" | `image`, `1:1` |
| nothing stated | `image` or `video` alone; let the defaults stand |

## generate_setting_trigger

```python
generate_setting_trigger(generate_type="image", aspect_ratio="9:16",
                         model="nano banana 2.1", output_count=2)
# {'ok': True, 'trigger': '🍌 Nano Banana 2.1 crop_9_16 x2', 'applied': {...}, 'warnings': [...]}
```

| Argument | Values | Default |
| --- | --- | --- |
| `generate_type` | `image` / `video` | `video` |
| `aspect_ratio` | image `16:9 4:3 1:1 3:4 9:16`; video **`16:9 9:16` only** | `16:9` |
| `model` | image `nano banana 2.1`, `nano banana pro`, `nano banana 2 lite`; video `omni 1.1`, `veo 3.1 lite`, `veo 3.1 fast`, `veo 3.1 quality` | image 2.1; video omni 1.1 |
| `output_count` | 1–4 | image 2; video 1 |
| `video_type` | `ingredients` / `frames` | `ingredients` |
| `video_resolution` | 360 / 720, **Omni only** | 720 |
| `video_duration` | 4 / 6 / 8 / 10, **Omni only** | 10 |

Pass `verify=True` (default) to get the `trigger` label back — that is the read-back:
image mode shows `🍌 <model> crop_<ratio> x<n>`, video shows
`Video · <res> · <dur>s crop_<ratio> x<n>`.

**Resolution and duration belong to Omni.** A Veo model removes those toggles, so the
primitive drops them and says so in `warnings`. Selecting the model before those
controls exist is why the primitive orders mode → video type → ratio → model → count →
resolution → duration; keep that order if you drive the page yourself.

Options are found by their visible text. The `mat-button-toggle-N` ids are reassigned
on every render (the same option was `-7` in one render and `-74` in another), so
selectors built on them break between sessions.

## Writing the prompt

```python
flow_set_prompt("a stone lighthouse on a cliff at dusk")
# {'ok': True, 'text': 'a stone lighthouse on a cliff at dusk'}
```

The prompt box is a ProseMirror editor: assigning `textContent` or a JS Range
selection changes nothing. Text goes in through real key events, which is what the
primitive does. `clear_first=True` (default) selects all and deletes through the
keyboard for the same reason.

## References

```python
flow_compose_prompt("Character A in a rain-soaked alley", refs=["/path/to/a.png"])
# {'ok': True, 'prompt': '…', 'ingredients': 1, 'errors': [], 'warnings': []}
```

`refs` are local files: images `.png .jpg .jpeg .webp .gif .heif .heic`, videos
`.mp4 .m4v .mov .3gp .avi`. References that already live in the project are attached by
name with `flow_attach_assets("name")` instead of being re-uploaded.

For a prompt that needs several references of mixed kinds, read `many-references.md` —
it covers the four-reference ceiling, compression, and the verified workflow.

- **Four references is the ceiling.** Flow stops adding past four; the primitive
  reports the extras in `warnings` rather than attaching them silently.
- **`clear_refs=True`** removes existing chips first, so `refs` is exactly the set.
  Without it, references from an earlier task stay attached and change the output.
- Each attach verifies the chip count rose. A duplicate Flow drops comes back as an
  error, not a success.

## Inline `@` references

Reference an asset *inside* the sentence — `@Lisa holds @RedMud` — instead of as a
chip. Picking one inserts a mention span and adds a chip beside the box.

```python
flow_set_prompt_with_mentions([
    "A studio fashion sequence. Starting with ", ("mention", "Lisa"),
    ", she is holding ", ("mention", "RedMud"), ".",
])
```

Strings are literal text; `("mention", name)` is one `@` pick. The pick leaves the
caret in the editor, so the next literal continues the sentence.

`flow_mention(name)` appends one mention at the caret. It types `@`, filters the popup
by `name`, picks the first match, and raises `RuntimeError` when nothing matches —
after deleting the stray `@` it had typed.

Measured behaviour worth knowing:

- **The query goes in the popup's search box, never the editor.** While the popup is
  open, typing in the editor is mirrored into the search box *and* left in the prompt,
  so `@20c7` ends up in your text. `@` moves focus to the search box; type there.
- **After a pick, the editor's last child is the mention span.** Placing the caret
  there puts the next `@` inside the chip and the popup never opens; the primitive
  collapses to the end of the paragraph instead.
- **A mention adds a chip.** `flow_set_prompt(clear_first=True)` clears the text and
  the mention spans but leaves those chips — call `flow_clear_ingredients()` too when
  resetting.
- Search filters the active picker tab only (All / Images / Videos / Voices /
  Characters / Avatars).

## Running it

```python
flow_generate(prompt=..., refs=[...], generate_type="video", aspect_ratio="9:16", timeout=300)
```

`flow_generate` forwards any extra keyword argument to `generate_setting_trigger`, so
`generate_type=`, `aspect_ratio=`, `model=`, `output_count=` and the video options all
work directly — there is no `settings={...}` wrapper. It adds `refs`, `mentions`,
`frames`, `clear_refs` and `timeout`. It returns:

```python
{'ok': True, 'kind': 'image', 'elapsed': 26.1,
 'assets': [{'id': '…', 'kind': 'image', 'url': '…', 'durable_id': True}],
 'errors': []}
```

- **Start generation is disabled while the prompt box is empty**, so the primitive
  raises instead of clicking a dead button.
- **The percentage is not a completion signal.** It can sit at 99%, and with
  `output_count > 1` pending tiles are sometimes stranded after the assets are usable.
  Completion requires a new asset id *and* no pending tile, with a fallback that
  accepts a result set which stops changing.
- Measured: image ~26 s, 4 s video ~28–34 s, video upscale longer.
