---
name: stack-rig
description: Adds moving parts (hinge, spin) to a sprite-stacked pixel object carved from four orthographic views. Use when someone asks to "open the lid on a pixel chest", "spin the wheels on a stacked sprite", "animate a part of a sprite stack", "hinge a hatch", or to rig a carved volume instead of redrawing every frame. Built on danielwh2/sprite-stacking (MIT). The carve is upstream; the rig is ours.
---

# stack-rig

based on danielwh2/sprite-stacking (MIT)

Four views still become a carved slice stack with Daniel White's official slicer (`scripts/views_to_slices.py`, vendored unchanged). This skill adds a second step: **name parts of that volume and move them**.

Use this when the object has a piece that should open, swing or spin. Do not use it as a replacement for the official skill when you only need a rigid turntable — run the upstream CLI for that.

## 1. Get a 4-view sheet

Same rules as the official skill. TOP, SIDE, FRONT, BACK in one row, front of TOP pointing down, front of SIDE pointing left, identical scale, 1 px dark outline, flat fills.

For a hinged lid, draw the lid and the body as clearly different heights in the SIDE / FRONT / BACK views (a seam you can point at). Wall detail in the elevations; lid detail in the TOP view and on the top slices.

The example `examples/chest/views.png` is a wooden treasure chest drawn for this skill, not upstream demo art.

## 2. Describe the parts

Write a `parts.json` next to the sheet:

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

- `select.z_from` / `z_to` — slice range (0 is the ground). For a chest, every slice from the seam up is the lid.
- `mode` — `hinge` (rotate in the YZ plane around a seam) or `spin` (rotate in XY around the part's centroid).
- `pivot` for a hinge — `back-seam` or `front-seam`. Front of the object is +Y (the TOP view's down direction).
- `hollow` — optional. The official carve fills cavities the four silhouettes cannot see. Hollow the body so a lid opens onto an interior; `treasure` plants a small coin heap on the cavity floor.

Look at the official `--preview` contact sheet first, then pick `z_from` by inspecting the slices (ground is on the left of the strip).

## 3. Run the rig

```bash
python3 scripts/stack_rig.py views.png \
  --parts parts.json \
  --slices 24 --order reading --top-nose down \
  --frames 48 --yaw 0:360 --part-motion lid=0:75:0 \
  --scale 8 \
  --preview preview.png --gif out.gif --mp4 out.mp4
```

- `--yaw` and `--part-motion name=k0:k1:k2` are keyframe lists over the sequence (smoothstep between keys). `lid=0:75:0` opens and closes once.
- `--scale` is integer nearest-neighbour only.
- `--rigid-preview` writes the same volume with the official rigid renderer (lid shut) so you can compare.

This repo is local. Do not `npx skills add` it; it is not published. Copy this folder into an agent's skills directory only when the owner has decided to share it.

## 4. Inspect before you ship

Open the preview. Check:

- [ ] Closed pose matches a rigid official render of the same sheet.
- [ ] The moving part rotates around the seam, not the bounding-box centre (a lid should not float).
- [ ] The body does not move.
- [ ] A hollowed interior is actually visible at the open pose, not a solid block.
- [ ] 1 px-thin parts still obey the official warning: they will blink. Draw them 2 px wide.

## Credit

Carve and official preview/renderer: Daniel White, [danielwh2/sprite-stacking](https://github.com/danielwh2/sprite-stacking), MIT. Sprite stacking as a technique predates that repo. The part rig (`scripts/stack_rig.py`) is Wrong Pixel's addition.
