# Characters

A character is a reusable actor in the project: a portrait, a name, a personality and
a voice. Characters live on their own sub-page and then appear in pickers as
ingredients and `@` mentions.

## flow_create_character

```python
flow_create_character(
    name="Mara",
    prompt="A woman in her early 30s, copper hair, wool coat, overcast daylight.",
    personality="Reserved, precise, quietly warm.",
    voice_preset="Aoede",
)
# {'ok': True, 'name': 'Mara', 'url': '…', 'voice': 'voice_selection Aoede …',
#  'image': True, 'errors': [], 'warnings': []}
```

| Argument | Meaning |
| --- | --- |
| `name` | required |
| `prompt` | description used to generate the portrait |
| `image` | local portrait path, used instead of generating one |
| `personality` | free text for "Character info" |
| `voice_preset` / `voice_performance` + `voice_name` | a built-in voice, or a generated one |
| `style` | preset card: `Eccentric`, `Professional`, `Wildcard`, `Familiar`, `Wicked`, `Fantastical` |
| `finalize` | click **Done** when complete (default true) |

Give `prompt`, `image`, or both. Uploading a portrait also opens the editor directly,
so image-only characters work.

## Order of the real workflow

Upload → choose the file → wait for the editor → set the name → voice (optional) →
**Character info** (optional) → **Done**.

The editor is the only place name, voice and personality exist, and it opens after a
portrait is generated or uploaded.

## The portrait

**Upload is driveable** even though the button creates no `input[type=file]` in the
DOM: it calls into the browser's file chooser, so the primitive intercepts the dialog
(`Page.setInterceptFileChooserDialog`), reads the chooser's `backendNodeId` from
`Page.fileChooserOpened`, and sets the file on that node. That is what makes image-only
characters work.

**The portrait tile's percentage can sit at 99% forever** while the name field, voice
selector and Done are all usable. Wait for `input.name-input` to exist — never for the
percentage to clear.

**The name field must be typed over.** Clearing it and clicking puts the caret inside
the placeholder, producing `Untitled chTest Namearacter`. The primitive selects all,
backspaces, types, then dispatches `change` and blurs so the value commits.

## flow_set_character_voice

```python
flow_set_character_voice(preset="Gacrux")
flow_set_character_voice(performance="Deep, slow, gravelly.", name="Gravel warm",
                         sample="Hi there.")
```

With `preset`, the built-in is searched and added. With `performance`, the voice is
generated from your description and needs `name`.

**The custom voice is a three-step state machine.** Measured, in order:

1. Editing the performance text disables *Save new voice*.
2. **Preview** runs 10–30 s, then re-enables *Save new voice*.
3. **Save new voice** registers it, and only then does *Add to character* appear.

Waiting for *Add to character* straight after Preview never succeeds — this was the
failure that took longest to diagnose. The primitive walks Preview → Save → Add.

Two more:

- **Preset matching is exact.** While the list filters it renders a transitional row
  whose label is your lowercased query; picking it stored voices literally named
  `aoede` and `charon`. The primitive requires a row whose name equals the preset and
  stays put across several polls.
- **The Voice name field only exists after the performance field is non-empty**, and
  the sample-dialogue field is pre-filled, so it is always set explicitly.

## Limits

- Presets are the built-ins the panel lists (Achernar, Achird, Aoede, …).
- The portrait generates as several variants; the primitive reports `image: True` and
  does not choose among them.
- Characters save on **Done**; `finalize=False` leaves you on the editor.
