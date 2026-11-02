# First and last frame video

Frames mode animates from a start image to an optional end image. Enter it first:

```python
generate_setting_trigger(generate_type="video", video_type="frames")
flow_set_frames(start="20c7")                      # end is optional
flow_set_frames(start="20c7", end="another-image") # both
flow_generate(prompt="the bowl slowly tilts", ...)
```

## flow_set_frames

```python
flow_set_frames(start=None, end=None, swap=False)
# {'ok': True, 'start': '20c7…jpg', 'end': None, 'frames': 1, 'errors': []}
```

- `start` / `end` are **asset names or name fragments**, resolved through the slot's
  own "Select a frame image" picker. Upload the image to the project first when it is
  a local file.
- The end frame is genuinely optional: a video from a start frame alone is valid.
- `swap=True` exchanges first and last after both are set.
- **Raises when the slots are absent** — that means you are not in Frames mode, and a
  silent no-op would generate the wrong thing.

`flow_clear_frames()` empties both slots and reports how many it cleared.

## Two slots, one visible label

The prompt box shows `[Start] ⇄ [End]`. Choosing an image fills the slot and replaces
its label with chip controls, so **a filled slot has no text to find it by**. Count
`button.chip-container .chip-image` instead — that count is the `frames` field.

Clear a slot before setting it again; a filled slot cannot be targeted by name.

## Measured traps

- **An open picker swallows the next click.** Its backdrop eats the slot click and
  `body.click()` does not dismiss it — only the pane's own `Close` does. A leftover
  picker shows up as a misleading "frame picker did not open" while the click landed
  fine. The primitive closes any open picker before starting and after a no-match.
- **The picker animates in**, so wait for its title *and* an asset row before typing a
  search.
- **Success is a rising chip count**, not a click return value: the pane closes
  underneath the click. Some assets also need an "Add to prompt" commit; both paths
  are handled.

## Frames and models

Resolution and duration controls belong to the Omni family and are absent for Veo, the
same rule as Ingredients mode — see `images-and-videos.md`. Video ratios are `16:9` and
`9:16` only.

## Reusing a generated image as a frame

A generated image has a durable UUID, so it can be picked by name once it appears in
the picker:

```python
r = flow_generate(prompt="a stone lighthouse at dusk", generate_type="image")
flow_generate(frames={"start": "<name of that image>"}, generate_type="video",
              video_type="frames")
```
