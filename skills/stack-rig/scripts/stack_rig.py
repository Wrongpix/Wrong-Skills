#!/usr/bin/env python3
"""
stack_rig — Wrong Pixel's addition to danielwh2/sprite-stacking.

Carve is unchanged and comes from the vendored official slicer.
This script adds named moving parts on the carved volume (hinge, spin)
and can hollow a solid carve so a lid opens onto a real interior.

Examples:
  python3 scripts/stack_rig.py examples/chest/views.png \\
      --parts examples/chest/parts.json --slices 24 \\
      --frames 48 --yaw 0:360 --part-motion lid=0:75:0 \\
      --gif out/chest.gif --mp4 out/chest.mp4 --preview out/preview.png
"""
from __future__ import annotations

import argparse
import json
import math
import sys
from pathlib import Path

import numpy as np
from PIL import Image

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))
from views_to_slices import (  # noqa: E402
    compute_normals,
    render_stack_image,
    thin_runs,
    views_to_slices,
)

# ---------------------------------------------------------------------------
# Volume edits
# ---------------------------------------------------------------------------


def _erode(mask: np.ndarray, steps: int) -> np.ndarray:
    m = mask.copy()
    for _ in range(steps):
        p = np.pad(m, 1, mode="constant", constant_values=False)
        m = (
            m
            & p[:-2, 1:-1]
            & p[2:, 1:-1]
            & p[1:-1, :-2]
            & p[1:-1, 2:]
        )
    return m


def hollow_body(
    vol: np.ndarray,
    z_from: int,
    z_to: int,
    wall: int = 2,
    lining=(62, 32, 18, 255),
) -> np.ndarray:
    """Clear the interior of body slices, leaving a `wall`-voxel shell."""
    out = vol.copy()
    lining = np.array(lining, dtype=np.uint8)
    z_from = max(0, z_from)
    z_to = min(out.shape[0], z_to)
    for z in range(z_from, z_to):
        occ = out[z, ..., 3] > 0
        interior = _erode(occ, wall)
        if not interior.any():
            continue
        # dark lining one voxel in from the new cavity wall
        cavity_pad = np.pad(interior, 1, mode="constant", constant_values=False)
        cavity_ring = interior & ~(
            cavity_pad[:-2, 1:-1]
            & cavity_pad[2:, 1:-1]
            & cavity_pad[1:-1, :-2]
            & cavity_pad[1:-1, 2:]
        )
        # keep a lining colour on the inner face, clear the rest
        out[z][interior] = 0
        out[z][cavity_ring] = lining
    return out


def plant_treasure(vol: np.ndarray, z: int, color=(228, 180, 56, 255), hi=(244, 214, 110, 255)) -> np.ndarray:
    """Heap of coins toward the back of the chest, tall enough to read over the front wall."""
    out = vol.copy()
    z = int(np.clip(z, 0, out.shape[0] - 1))
    h, w = out.shape[1], out.shape[2]
    # back half of the plan (front is +y)
    cy, cx = int(h * 0.38), w // 2
    gem = (196, 48, 52, 255)
    gem_hi = (236, 110, 100, 255)
    # radii of the heap per slice above the floor
    radii = [5, 4, 4, 3, 2, 2, 1]
    for dz, radius in enumerate(radii):
        zz = z + dz
        if zz >= out.shape[0]:
            break
        for dy in range(-radius, radius + 1):
            for dx in range(-radius, radius + 1):
                if dy * dy + dx * dx > radius * radius:
                    continue
                y, x = cy + dy, cx + dx
                if not (0 <= y < h and 0 <= x < w):
                    continue
                # stay inside the hollow: neighbouring walls/floor must exist
                if not (out[z, max(0, y - 6): y + 7, max(0, x - 6): x + 7, 3] > 0).any():
                    continue
                # don't fill the front-most cells — leave an aisle so the heap is visible
                c = hi if ((dy + dx + dz) % 2 == 0) else color
                out[zz, y, x] = np.array(c, dtype=np.uint8)
    # red gem on the peak
    peak = z + len(radii) - 1
    if peak < out.shape[0]:
        out[peak, cy, cx] = np.array(gem_hi, dtype=np.uint8)
        if cy + 1 < h:
            out[max(z, peak - 1), cy + 1, cx] = np.array(gem, dtype=np.uint8)
    return out


def paint_cavity_floor(vol: np.ndarray, z: int, color=(48, 24, 40, 255)) -> np.ndarray:
    """Paint a dark velvet floor on the solid slice under the hollow, inside the walls."""
    out = vol.copy()
    z = int(np.clip(z, 0, out.shape[0] - 1))
    occ = out[z, ..., 3] > 0
    interior = _erode(occ, 2)
    if interior.any():
        out[z][interior] = np.array(color, dtype=np.uint8)
    return out


def part_mask(vol: np.ndarray, select: dict) -> np.ndarray:
    n, h, w, _ = vol.shape
    mask = vol[..., 3] > 0
    if "z_from" in select:
        zs = np.zeros(n, dtype=bool)
        zs[int(select["z_from"]) :] = True
        mask &= zs[:, None, None]
    if "z_to" in select:
        zs = np.zeros(n, dtype=bool)
        zs[: int(select["z_to"])] = True
        mask &= zs[:, None, None]
    return mask


def hinge_pivot(mask: np.ndarray, kind: str = "back-seam") -> tuple[float, float]:
    """Return (y_hinge, z_hinge) in volume coordinates."""
    zz, yy, xx = np.nonzero(mask)
    if len(zz) == 0:
        raise SystemExit("hinge part is empty — check z_from / select")
    z_seam = int(zz.min())  # lowest slice of the lid sits on the seam
    if kind == "back-seam":
        # front is +y (top-view front points down). Back is small y.
        # use a robust back edge of the seam slice
        seam = mask[z_seam]
        ys, xs = np.nonzero(seam)
        y_back = float(np.percentile(ys, 5))
        return y_back, float(z_seam)
    if kind == "front-seam":
        seam = mask[z_seam]
        ys, xs = np.nonzero(seam)
        return float(np.percentile(ys, 95)), float(z_seam)
    raise SystemExit(f"unknown pivot: {kind}")


def transform_voxels(
    vol: np.ndarray,
    parts: list[dict],
) -> tuple[np.ndarray, np.ndarray]:
    """Return (positions[N,3] as z,y,x and colors[N,4]) after applying part motions.

    Unmoved voxels keep their integer centres. Hinged / spun voxels are floats.
    """
    n, h, w, _ = vol.shape
    occupied = vol[..., 3] > 0
    claimed = np.zeros_like(occupied)
    chunks_pos = []
    chunks_col = []

    for part in parts:
        mask = part["mask"] & occupied
        claimed |= mask
        zz, yy, xx = np.nonzero(mask)
        if len(zz) == 0:
            continue
        z = zz.astype(np.float64)
        y = yy.astype(np.float64)
        x = xx.astype(np.float64)
        mode = part["mode"]
        angle = math.radians(part["angle"])
        if mode == "hinge":
            y0, z0 = part["pivot"]
            # Open the lid: front (+y) rises toward +z, back stays on the seam.
            y_rel, z_rel = y - y0, z - z0
            ca, sa = math.cos(angle), math.sin(angle)
            y = y0 + y_rel * ca - z_rel * sa
            z = z0 + y_rel * sa + z_rel * ca
        elif mode == "spin":
            # spin around a vertical axis through the part's xy centroid, or a given pivot
            pivot = part.get("spin_pivot")
            if pivot is None:
                x0, y0 = float(x.mean()), float(y.mean())
            else:
                x0, y0 = pivot
            x_rel, y_rel = x - x0, y - y0
            ca, sa = math.cos(angle), math.sin(angle)
            x = x0 + x_rel * ca - y_rel * sa
            y = y0 + x_rel * sa + y_rel * ca
        else:
            raise SystemExit(f"unknown part mode: {mode}")
        pos = np.stack([z, y, x], axis=1)
        col = vol[zz, yy, xx]
        chunks_pos.append(pos)
        chunks_col.append(col)

    rest = occupied & ~claimed
    zz, yy, xx = np.nonzero(rest)
    if len(zz):
        chunks_pos.append(np.stack([zz.astype(np.float64), yy.astype(np.float64), xx.astype(np.float64)], axis=1))
        chunks_col.append(vol[zz, yy, xx])

    if not chunks_pos:
        return np.zeros((0, 3)), np.zeros((0, 4), dtype=np.uint8)
    return np.concatenate(chunks_pos, axis=0), np.concatenate(chunks_col, axis=0)


def render_voxels(
    pos: np.ndarray,
    col: np.ndarray,
    vol_shape: tuple[int, int, int],
    angle_deg: float,
    squash: float = 0.75,
    spacing: float = 1.0,
    shadow: bool = True,
    outline: bool = True,
) -> Image.Image:
    """Forward-project voxels with the official camera (turn, squash, 1px lift)."""
    n, h, w = vol_shape
    rad = math.radians(angle_deg)
    ca, sa = math.cos(rad), math.sin(rad)

    # canvas size: official formula plus headroom for an open lid
    diag = int(math.ceil(math.hypot(w, h))) + 8
    lift_max = int(math.ceil((n + 8) * spacing))  # lid can rise above the roof
    cw = diag + 16
    ch = int(math.ceil(diag * squash)) + lift_max + 24
    cx = cw // 2
    base_y = ch - int(math.ceil(diag * squash / 2)) - 6

    canvas = np.zeros((ch, cw, 4), dtype=np.uint8)
    depth = np.full((ch, cw), -1e9, dtype=np.float32)

    if shadow and len(pos):
        # ground footprint of the transformed voxels, same offset as official
        yy_g, xx_g = np.mgrid[0:ch, 0:cw]
        # project z=0 plane
        # Use a discrete splat of each voxel's xy at z=0
        for (z, y, x), _c in zip(pos, col):
            dx = (x - (w / 2.0)) * ca - (y - (h / 2.0)) * sa
            dy = (x - (w / 2.0)) * sa + (y - (h / 2.0)) * ca
            px = int(round(cx + 2 + dx))
            py = int(round((base_y + 3) + dy * squash))
            if 0 <= px < cw and 0 <= py < ch:
                if canvas[py, px, 3] == 0:
                    canvas[py, px] = (186, 198, 212, 255)

    if len(pos):
        z, y, x = pos[:, 0], pos[:, 1], pos[:, 2]
        dx = (x - (w / 2.0)) * ca - (y - (h / 2.0)) * sa
        dy = (x - (w / 2.0)) * sa + (y - (h / 2.0)) * ca
        px_f = cx + dx
        py_f = (base_y - z * spacing) + dy * squash
        dep = z * spacing + 0.05 * dy
        # 4-tap splat closes holes on rotated lid voxels; integer body voxels still land crisp
        order = np.argsort(dep)
        for i in order:
            x0 = int(np.floor(px_f[i]))
            y0 = int(np.floor(py_f[i]))
            fx = px_f[i] - x0
            fy = py_f[i] - y0
            # if almost on a pixel centre, write once; otherwise cover the 2x2
            taps = [(x0, y0)]
            if fx > 0.15:
                taps.append((x0 + 1, y0))
            if fy > 0.15:
                taps.append((x0, y0 + 1))
            if fx > 0.15 and fy > 0.15:
                taps.append((x0 + 1, y0 + 1))
            for xi, yi in taps:
                if 0 <= xi < cw and 0 <= yi < ch and dep[i] >= depth[yi, xi]:
                    depth[yi, xi] = dep[i]
                    canvas[yi, xi] = col[i]

    if outline:
        alpha = canvas[..., 3] > 0
        # don't outline the shadow (pale blue-grey)
        body = alpha & ~((canvas[..., 0] == 186) & (canvas[..., 1] == 198) & (canvas[..., 2] == 212))
        pad = np.pad(body, 1)
        ring = ~body & (pad[:-2, 1:-1] | pad[2:, 1:-1] | pad[1:-1, :-2] | pad[1:-1, 2:])
        # don't draw outline on shadow pixels
        canvas[ring] = (24, 28, 36, 255)
        # restore body over any overlap
        canvas[body] = canvas[body]

    return Image.fromarray(canvas)


# ---------------------------------------------------------------------------
# Motion helpers
# ---------------------------------------------------------------------------


def parse_keyframes(spec: str) -> list[float]:
    """'0:75:0' or '0,75,75,0' -> list of key values."""
    if ":" in spec:
        return [float(x) for x in spec.split(":")]
    return [float(x) for x in spec.split(",")]


def eval_keyframes(keys: list[float], t: float) -> float:
    """t in [0, 1], piecewise lerp with smoothstep between keys."""
    if len(keys) == 1:
        return keys[0]
    if t <= 0:
        return keys[0]
    if t >= 1:
        return keys[-1]
    pos = t * (len(keys) - 1)
    i = min(int(pos), len(keys) - 2)
    f = pos - i
    f = f * f * (3 - 2 * f)
    return keys[i] + (keys[i + 1] - keys[i]) * f


# ---------------------------------------------------------------------------
# IO
# ---------------------------------------------------------------------------


def load_parts(path: Path, vol: np.ndarray) -> tuple[list[dict], dict]:
    data = json.loads(Path(path).read_text())
    hollow_cfg = data.get("hollow") or {}
    parts = []
    for raw in data.get("parts") or []:
        mask = part_mask(vol, raw.get("select") or {})
        parts.append(
            {
                "name": raw["name"],
                "mode": raw["mode"],
                "mask": mask,
                "pivot": hinge_pivot(mask, raw.get("pivot", "back-seam")) if raw["mode"] == "hinge" else None,
                "angle": 0.0,
                "open_degrees": float(raw.get("open_degrees", 70)),
            }
        )
    return parts, hollow_cfg


def save_gif(frames: list[Image.Image], path: Path, duration_ms: int = 40) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    # composite onto a solid bg so GIF doesn't wreck alpha
    rgb = []
    for im in frames:
        bg = Image.new("RGBA", im.size, (11, 12, 16, 255))
        bg.alpha_composite(im)
        rgb.append(bg.convert("P", palette=Image.Palette.ADAPTIVE, colors=128))
    rgb[0].save(
        path,
        save_all=True,
        append_images=rgb[1:],
        duration=duration_ms,
        loop=0,
        optimize=True,
        disposal=2,
    )


def save_mp4(frames: list[Image.Image], path: Path, fps: int = 30) -> None:
    import subprocess

    path.parent.mkdir(parents=True, exist_ok=True)
    w, h = frames[0].size
    # even dimensions for yuv420p
    ww, hh = w + (w % 2), h + (h % 2)
    cmd = [
        "ffmpeg", "-y",
        "-f", "rawvideo", "-pix_fmt", "rgba",
        "-s", f"{w}x{h}", "-r", str(fps), "-i", "-",
        "-vf", f"scale={ww}:{hh}:flags=neighbor,format=yuv420p",
        "-c:v", "libx264", "-crf", "18", "-preset", "fast",
        "-movflags", "+faststart", "-an",
        str(path),
    ]
    proc = subprocess.Popen(cmd, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    try:
        for im in frames:
            if im.mode != "RGBA":
                im = im.convert("RGBA")
            proc.stdin.write(im.tobytes())
        proc.stdin.close()
        err = proc.stderr.read()
        rc = proc.wait()
        if rc != 0:
            raise SystemExit(err.decode()[-2000:])
    except Exception:
        try:
            proc.kill()
        except Exception:
            pass
        raise


def contact_sheet(images: list[tuple[str, Image.Image]], scale: int, path: Path) -> None:
    cells = [(lab, im.resize((im.width * scale, im.height * scale), Image.Resampling.NEAREST)) for lab, im in images]
    pad = 16
    cell_w = max(im.width for _, im in cells) + pad
    cell_h = max(im.height for _, im in cells) + pad + 18
    cols = len(cells)
    bg = Image.new("RGBA", (cell_w * cols + pad, cell_h + pad), (242, 245, 249, 255))
    from PIL import ImageDraw, ImageFont
    try:
        font = ImageFont.load_default()
    except Exception:
        font = None
    d = ImageDraw.Draw(bg)
    x = pad
    for lab, im in cells:
        bg.paste(im, (x + (cell_w - pad - im.width) // 2, pad + 16), im)
        d.text((x + (cell_w - pad) // 2, 4), lab, fill=(40, 40, 48), anchor="mt", font=font)
        x += cell_w
    path.parent.mkdir(parents=True, exist_ok=True)
    bg.convert("RGB").save(path)


def main() -> None:
    p = argparse.ArgumentParser(description="Carve a 4-view sheet (official slicer) and rig moving parts (Wrong Pixel).")
    p.add_argument("sheet", type=Path, help="4-view PNG")
    p.add_argument("--parts", type=Path, required=True, help="parts.json")
    p.add_argument("--slices", type=int, default=None)
    p.add_argument("--order", default="reading")
    p.add_argument("--top-nose", default="down")
    p.add_argument("--shade", type=float, default=0.2)
    p.add_argument("--frames", type=int, default=48)
    p.add_argument("--yaw", default="35", help="keyframe yaw in degrees, e.g. 35 or 0:360")
    p.add_argument("--part-motion", action="append", default=[], help="name=k0:k1:k2 degrees, repeatable")
    p.add_argument("--scale", type=int, default=8, help="integer nearest-neighbour upscale for gif/mp4")
    p.add_argument("--gif", type=Path, default=None)
    p.add_argument("--mp4", type=Path, default=None)
    p.add_argument("--preview", type=Path, default=None)
    p.add_argument("--rigid-preview", type=Path, default=None, help="official rigid render of the same volume (no rig)")
    p.add_argument("--vol", type=Path, default=None, help="optional .npy dump of the (hollowed) volume")
    p.add_argument("--no-hollow", action="store_true")
    args = p.parse_args()

    sheet = np.array(Image.open(args.sheet).convert("RGBA"))
    vol, views = views_to_slices(
        sheet,
        slices=args.slices,
        top_nose=args.top_nose,
        order=args.order,
        shade=args.shade,
    )
    print(f"carved {vol.shape[0]} slices of {vol.shape[2]} x {vol.shape[1]} px")
    for z0, z1 in thin_runs(vol):
        print(f"warning: thin part in slices {z0}-{z1}")

    parts, hollow_cfg = load_parts(args.parts, vol)
    if hollow_cfg and not args.no_hollow:
        body = hollow_cfg.get("body_z") or [0, parts[0]["pivot"][1] if parts else vol.shape[0]]
        vol = hollow_body(vol, int(body[0]), int(body[1]), wall=int(hollow_cfg.get("wall", 2)))
        if hollow_cfg.get("treasure"):
            floor_z = max(0, int(body[0]) - 1)
            vol = paint_cavity_floor(vol, floor_z)
            vol = plant_treasure(vol, int(body[0]))
        print(f"hollowed body slices {body[0]}..{body[1]} (exclusive end)")

    # refresh masks after hollow (interior gone, treasure added — lid mask unchanged)
    parts, _ = load_parts(args.parts, vol)

    if args.vol:
        args.vol.parent.mkdir(parents=True, exist_ok=True)
        np.save(args.vol, vol)

    motions = {}
    for item in args.part_motion:
        if "=" not in item:
            raise SystemExit(f"bad --part-motion {item}, expected name=0:75:0")
        name, spec = item.split("=", 1)
        motions[name] = parse_keyframes(spec)

    yaw_keys = parse_keyframes(args.yaw)
    n_frames = max(1, args.frames)
    frames = []
    preview_shots = []
    rigid_shots = []
    want_t = [0.0, 0.25, 0.5, 0.75] if n_frames > 1 else [0.0]

    for i in range(n_frames):
        t = 0.0 if n_frames == 1 else i / (n_frames - 1)
        yaw = eval_keyframes(yaw_keys, t)
        active = []
        for part in parts:
            ang = eval_keyframes(motions.get(part["name"], [0.0]), t)
            q = dict(part)
            q["angle"] = ang
            active.append(q)
        pos, col = transform_voxels(vol, active)
        im = render_voxels(pos, col, vol.shape[:3], yaw)
        frames.append(im)
        for wt in want_t:
            if abs(t - wt) < 1 / max(2, n_frames):
                lid = next((a["angle"] for a in active if a["name"] == (parts[0]["name"] if parts else "")), 0)
                preview_shots.append((f"yaw {yaw:.0f}°  lid {lid:.0f}°", im))
                break

    if args.preview:
        if not preview_shots:
            preview_shots = [("frame 0", frames[0])]
        # unique labels
        seen = set()
        uniq = []
        for lab, im in preview_shots:
            if lab in seen:
                continue
            seen.add(lab)
            uniq.append((lab, im))
        contact_sheet(uniq, max(2, args.scale // 2), args.preview)
        print(f"preview -> {args.preview}")

    if args.rigid_preview:
        # official renderer, lid closed, same yaws as the preview shots
        rigid = []
        for t in (0.0, 0.25, 0.5, 0.75):
            yaw = eval_keyframes(yaw_keys, t)
            rigid.append((f"rigid {yaw:.0f}°", render_stack_image(vol, yaw, squash=0.75, spacing=1.0)))
        contact_sheet(rigid, max(2, args.scale // 2), args.rigid_preview)
        print(f"rigid preview -> {args.rigid_preview}")

    scaled = [
        im.resize((im.width * args.scale, im.height * args.scale), Image.Resampling.NEAREST)
        for im in frames
    ]
    if args.gif:
        save_gif(scaled, args.gif)
        print(f"gif -> {args.gif}")
    if args.mp4:
        save_mp4(scaled, args.mp4, fps=30)
        print(f"mp4 -> {args.mp4}")


if __name__ == "__main__":
    main()
