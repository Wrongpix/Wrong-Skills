# stack-rig

based on danielwh2/sprite-stacking (MIT)

An agent skill that takes four flat pixel views, carves them into a sprite stack (Daniel White's slicer), and then **rigs named parts** so a lid can hinge open or a wheel can spin — without redrawing a new strip for every frame.

The carve is not ours. The moving parts are.

## What we added

The official skill (and its HTML viewer) already turns a stack and can even bake a 16-direction sheet. What it does not ship is a CLI for **articulated parts on the carved volume**:

- `hinge` — rotate a slice range around a seam (a chest lid, a door, a hatch)
- `spin` — rotate a part around a vertical axis (a wheel, a record, a gear)
- optional **hollow** + treasure/interior, because a solid carve has nothing to reveal when the lid opens

One command: 4-view sheet + `parts.json` → preview, GIF and MP4 of the part moving.

## Requirements

Python 3, Pillow, NumPy. `ffmpeg` only if you want `--mp4`.

This copy is local. It is not published to GitHub and is not on the skills registry. To try it, point your agent at this folder or run the CLI yourself.

## Use

```bash
python3 scripts/stack_rig.py examples/chest/views.png \
  --parts examples/chest/parts.json \
  --slices 24 --order reading --top-nose down \
  --frames 48 --yaw 0:360 --part-motion lid=0:75:0 \
  --scale 8 \
  --preview chest-preview.png --gif chest.gif --mp4 chest.mp4
```

`parts.json` names the moving piece and how it is selected (here: every slice from 14 up is the lid, hinged at the back seam):

```json
{
  "hollow": { "wall": 2, "body_z": [5, 14], "treasure": true },
  "parts": [
    {
      "name": "lid",
      "mode": "hinge",
      "select": { "z_from": 14 },
      "pivot": "back-seam",
      "open_degrees": 75
    }
  ]
}
```

The treasure-chest sheet in `examples/chest/` was drawn for this skill. It is not the author's demo art.

## Upstream carve (unchanged)

The four-view slicer is vendored, unmodified, from [danielwh2/sprite-stacking](https://github.com/danielwh2/sprite-stacking) (MIT, Copyright 2026 Daniel White):

```bash
python3 scripts/views_to_slices.py views.png slices.png \
  --slices 24 --preview check.png
```

Sprite stacking itself is a long-standing indie technique. Daniel's skill added the four-view carve and the agent workflow. We added the part rig.

## Tests

```bash
python3 tests/check_upstream.py   # official slicer self-check, should print ok
python3 tests/test_stack_rig.py   # hinge + hollow + the chest example, should print ok
```

## Licence

MIT. Copyright 2026 Daniel White (slicer) and 2026 Wrong Pixel (stack-rig). See `LICENSE`.
