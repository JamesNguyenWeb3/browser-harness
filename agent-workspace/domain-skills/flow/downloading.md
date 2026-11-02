# Downloading results

The last step of the pipeline, and the one that decides what quality the next process
receives.

## flow_download

```python
flow_download(kind="video")                            # best allowed tier
flow_download(asset_id="50aa573c-…", folder="/path/to/out")
flow_download(kind="image", quality="1K")              # explicit tier
# {'ok': True, 'path': '/path/to/out/Stone_lighthouse_on_cliff_a5319152_2K.jpg',
#  'quality': '2K', 'available': ['1K', '2K'], 'requested': 'best', 'errors': []}
```

| Argument | Meaning |
| --- | --- |
| `asset_id` | id from `flow_generate` / `flow_list_results`; omit to take the first tile of `kind` |
| `kind` | `image` / `video`, narrows the tile and the tier set |
| `quality` | `best` (default), `original`, or an explicit `1K` `2K` `720p` `1080p` `4K` |
| `folder` | destination, created if missing; default `~/Downloads/flow` |

## Tiers, and what the plan allows

The Download menu opens a quality submenu. Measured on a Google Pro plan:

| Asset | Tiers offered |
| --- | --- |
| Image | `1K Original size` · `2K Upscaled` · `4K Upscaled` *(locked)* · `Upgrade` |
| Video (720p source) | `720p Original size` · `1080p Upscaled` · `4K Upscaled` *(locked)* · `Upgrade` |

**Locked tiers carry `tabindex="-1"`.** There is no `aria-disabled`; the tabindex is the
availability signal. `Upgrade` is a call to action, never a quality.

`quality="best"` takes the highest **enabled** tier and skips locked ones, so a plan
that disallows 4K receives 2K (image) or 1080p (video) — the best it is entitled to,
not a failure. An explicitly requested but locked tier raises:

```
flow_download(quality="4K")
→ RuntimeError: 4K is locked on this plan; available ['720p', '1080p']
```

The ladder grows with the source: a 1K image offers `1K`, a 1K-plus source also offers
`2K`. Read `available` when the choice matters.

## Upscaled tiers are asynchronous

- Image 2K: *"Upscaling your image, download will start automatically."*, file in ~5–10 s.
- Video 1080p: *"Upscaling your video. This may take several minutes."*, file at ~36 s.

`Original size` downloads immediately. The primitive waits for a **new, size-stable
file** in the folder instead of treating the click as completion, so raise `timeout`
for video upscales rather than retrying blindly.

## Driving the menu

- **Click the tier element directly.** These are Angular Material menu buttons, and a
  synthetic pointer click is unreliable: the submenu animates in, and a click aimed at
  a mid-animation rect lands on empty space and closes the menu with no download. The
  primitive calls `.click()` on the row, with a pointer click as fallback.
- **A menu left open breaks the next call** — its backdrop swallows the following
  tile's More-options click, surfacing as "Download menu item not found". Menus are
  dismissed with **Escape** on entry and in a `finally`; `body.click()` does not close
  them.

## Filenames

`<Prompt_slug>_<hash>[_<TIER>].<ext>` — for example
`Stone_lighthouse_on_cliff_a5319152_2K.jpg`, and
`Waves_breaking_against_stone_lig…_49e9cd2f_1080p.mp4` (Flow truncates long names with
a literal `…`). Use the returned `path`; do not reconstruct the name.

## Asset identity

| Kind | Id | Reusable in later calls |
| --- | --- | --- |
| Image | real UUID (`data-media-id`) | yes — `durable_id: True` |
| Video | `thumb:<segment>` from the signed thumbnail | no — `durable_id: False`, `url: None` |

Video tiles expose no `data-media-id` and no `flow-content` URL, only a signed
`flow.google.com/asb` thumbnail. So a downloaded video is reused as a **file**, while a
downloaded image can also be re-referenced inside Flow.

## Listing what exists

```python
flow_list_results(kind="image", limit=20)
# {'ok': True, 'assets': [...], 'count': 7}
```

Newest first. Use it before generating: an asset already in the project only needs
downloading.
