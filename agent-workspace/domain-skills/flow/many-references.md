# Scenes with several references

A **reference** is anything the generation must look at: a local file, a project asset,
a character, or something you generate first. This page is the workflow for prompts
that need more than one.

## There is no hard ceiling

Flow accepted **seven** reference chips in testing with no refusal, and no limit was
found. Nothing is dropped: `flow_attach_ingredients`, `flow_attach_assets` and
`flow_compose_scene` attach what you give them and warn past **eight** references,
because that is where the model's own reference budget and the prompt budget start to
matter rather than where Flow stops.

Treat four as a *comfort* point, not a rule. Every reference you add dilutes the
prompt, so compress when the scene reads like a list of assets rather than a
description.

## Pick the primitive per reference

| Reference is | Use | Ends up as |
| --- | --- | --- |
| a local file | `flow_attach_ingredients([path])` | chip |
| already an image/video in the project | `flow_attach_assets("name")` | chip |
| a character | mention it: `("mention", "Lisa")` | chip + inline name |
| missing, must be made | `flow_generate` first, then reference it | chip |
| several of the above | `flow_compose_scene(...)` | all of it, verified |

## The workflow

`flow_compose_scene` runs the whole thing. Use it unless you need to inspect a step.

```python
flow_compose_scene(
    "A studio fashion sequence. {Lisa} holds {RedMud}, lit from the left.",
    references=["/path/to/lisa_ref.png", "Lisa", {"generate": "a red clay jar", "as": "clay jar"}],
)
# {'ok': True, 'text': '… Lisa holds …', 'chips': 4, 'mentions': 2,
#  'references': ['lisa_ref.png', 'Lisa', 'clay jar'], 'errors': [], 'warnings': []}
```

1. **Inventory.** List every reference and its type, then compress until the prompt
   still reads as one sentence.
   *Done when:* every reference has a type, and each one earns its place.
2. **Resolve — make each one real.** Local files upload, missing ones generate, existing
   ones are found by name.
   *Done when:* every reference exists either as a local path that uploads or a name
   that appears in the picker.
3. **Compose — write the prompt.** `{name}` markers become mentions; everything else is
   attached.
   *Done when:* returned `chips` equals your reference count and `mentions` equals the
   number of named references.
4. **Generate, then download.** `flow_generate` with the same references already in
   place, then `flow_download`.
   *Done when:* `assets` holds at least one entry and `path` names a file.

## Compress by choosing the unit

A reference can stand for more than a file:

- **A character is one reference.** `flow_create_character` bundles portrait,
  personality and voice, so "Lisa in a red coat, voiced warmly" is `@Lisa` rather than
  a portrait plus a costume image plus a voice.
- **A composite is one reference.** Generate a scene from several references, download
  that image, then run the final generation with the composite as the only reference.
  Two cheap passes beat one crowded one.
- **Mention what you already chip.** Mentioning an attached asset is free — it adds
  wording, not budget. Chips suit description; mentions suit a prompt that names the
  thing.

## Mixing chips and mentions

- **Attach first, then mention.** The prompt setter clears text and mention spans but
  leaves chips, and a mention of an already-attached asset dedupes to the same chip.
- **Uploaded files are mentionable by filename**, so one upload can serve both as a
  chip and as `@name` text.
- **Generated assets are named from their prompt** (`Stone_lighthouse_on_cliff_a5319152`),
  so a mention has to search a term from that prompt. `flow_compose_scene` takes `as`
  for this; pass a distinctive word.
- **Video rows do not insert mentions.** Clicking a video in the `@` popup commits and
  closes it with no mention span. The primitives prefer image-like rows, so mention an
  image or a character, and pass a search term specific enough to skip the video.

## Verify the state, not the call

Every step can return `ok` while the page disagrees, because Flow closes overlays
underneath clicks. Read the counts:

```python
r = flow_compose_scene(...)
if not r["ok"]:                 # chips attached, mentions inserted, nothing dropped
    ...
if r["chips"] < r["expected_chips"]:
    ...
```

`ok` requires all three: no errors, `mentions` at least as many as the named references,
and `chips` at least `expected_chips` — one per distinct reference, so a duplicate that
Flow dedupes still counts as satisfied. A reference that silently failed to attach now
turns `ok` false instead of passing.

A `flow_mention` that adds a chip without inserting its mention span is the failure
this guards against; the primitive now removes that phantom chip, but the count check
is what tells you the scene is sound.

## Why "four" appears in older notes

An early probe concluded four because it re-picked the first result each round, and
Flow dedupes a repeated asset — the count stopped rising at four for that reason, not
because of a limit. Re-measured directly, five, six and seven all attached.
