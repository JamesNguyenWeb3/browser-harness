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

## Name every reference

A chip carries an **asset name**, and an `@mention` resolves **by name**. Upload a file
as `lisa_ref.png` and the prompt's `{Lisa}` cannot find it: the chip sits attached while
the prompt names something else, so the reference is wasted and the scene is wrong.

The fix is to make the two identities one: **upload, then rename the asset to the
variable the prompt uses.** `flow_compose_scene` does this for you.

```python
flow_compose_scene(
    "A studio sequence. {Lisa} holds {RedMud}, lit from the left.",
    references=[
        {"as": "Lisa",   "path": "/path/to/lisa_ref.png"},   # upload, rename to Lisa
        {"as": "RedMud", "asset": "red clay jar"},           # existing asset, renamed
    ],
)
# {'ok': True, 'text': '… Lisa holds RedMud …', 'chips': 2, 'mentions': 2,
#  'expected_chips': 2, 'variables': ['Lisa', 'RedMud'], 'errors': [], 'warnings': []}
```

Each reference says what it fills (`as`) and where it comes from:

| Reference | Source | Becomes |
| --- | --- | --- |
| `{"as": "Lisa", "path": "/p/Lisa.png"}` | local file | uploaded, renamed to `Lisa` |
| `{"as": "RedMud", "asset": "red clay jar"}` | project asset | renamed to `RedMud` if the name differs |
| `{"as": "Osei", "character": "Osei"}` | character | mentioned under its own name |
| `{"as": "Jar", "generate": "a red clay jar"}` | generated | generated, then renamed to `Jar` |
| `"Stone"` | project asset | used as-is, mentioned as `Stone` |
| `"/p/Stone.png"` | local file | used as-is, mentioned as `Stone.png` |

Every variable in the list gets a mention, so `mentions == chips == len(variables)`.
`flow_rename_asset(old, new)` is the standalone rename when you want it outside a scene.

**Renaming changes the asset in the project.** If the same asset is used by another
scene by its old name, that name is gone — prefer `as` equal to the existing name for
shared assets.

## The workflow

1. **Inventory.** List every reference, and the variable the prompt will call it by.
   Compress until the prompt still reads as one sentence.
   *Done when:* every reference has an `as` name and a source.
2. **Resolve.** Upload, generate, or find each one, then rename it to its variable.
   *Done when:* every variable is an asset name that exists in the project.
3. **Compose.** `{name}` markers become mentions of those variables.
   *Done when:* returned `variables` holds every name, and `mentions` equals its length.
4. **Generate, then download.** `flow_generate`, then `flow_download`.
   *Done when:* `assets` holds at least one entry and `path` names a file.

Check `ok` before generating: it requires the attachments to match `expected_chips` and
no errors, which is what catches a reference whose rename or mention did not land.

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
