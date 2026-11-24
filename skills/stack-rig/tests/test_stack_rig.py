"""Tests for Wrong Pixel's stack-rig feature (hinge + hollow). Run: python3 tests/test_stack_rig.py"""
from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path

import numpy as np
from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from stack_rig import (  # noqa: E402
    eval_keyframes,
    hinge_pivot,
    hollow_body,
    parse_keyframes,
    part_mask,
    plant_treasure,
    render_voxels,
    transform_voxels,
)
from views_to_slices import views_to_slices  # noqa: E402


def _box_sheet() -> np.ndarray:
    """A tiny 4-view sheet: a 10x10x10 wood box, lid colour on the top 4 px."""
    # TOP 10x10 brown, SIDE/FRONT/BACK 10x10 with lower 6 body, upper 4 lid (lighter)
    body, lid, k = (140, 80, 40, 255), (200, 140, 70, 255), (20, 16, 12, 255)

    def outlined(fill_fn, w, h):
        im = Image.new("RGBA", (w, h), (0, 0, 0, 0))
        px = im.load()
        for y in range(h):
            for x in range(w):
                px[x, y] = fill_fn(x, y)
        # 1px outline
        src = im.copy().load()
        for y in range(h):
            for x in range(w):
                if im.getpixel((x, y))[3] == 0:
                    for dx, dy in ((-1, 0), (1, 0), (0, -1), (0, 1)):
                        nx, ny = x + dx, y + dy
                        if 0 <= nx < w and 0 <= ny < h and src[nx, ny][3] > 0:
                            px[x, y] = k
                            break
        return im

    top = outlined(lambda x, y: lid if 1 <= x < 9 and 1 <= y < 9 else (0, 0, 0, 0), 10, 10)
    # SIDE: front left, body at bottom (high y)
    def side_px(x, y):
        if not (1 <= x < 9 and 1 <= y < 9):
            return (0, 0, 0, 0)
        return lid if y <= 4 else body

    side = outlined(side_px, 10, 10)
    front = outlined(side_px, 10, 10)
    back = outlined(side_px, 10, 10)

    gap, pad = 40, 40
    views = [top, side, front, back]
    W = pad * 2 + sum(v.width for v in views) + gap * 3
    H = pad * 2 + 10
    canvas = Image.new("RGBA", (W, H), (255, 255, 255, 255))
    x = pad
    for v in views:
        canvas.paste(v, (x, pad), v)
        x += v.width + gap
    return np.array(canvas.convert("RGB").convert("RGBA"))


def test_keyframes():
    assert parse_keyframes("0:75:0") == [0.0, 75.0, 0.0]
    assert eval_keyframes([0.0, 80.0], 0.0) == 0.0
    assert eval_keyframes([0.0, 80.0], 1.0) == 80.0
    mid = eval_keyframes([0.0, 80.0], 0.5)
    assert 30 < mid < 70, mid  # smoothstep, not linear, but in range


def test_hinge_raises_lid():
    sheet = _box_sheet()
    vol, _ = views_to_slices(sheet, slices=10, top_nose="down", order="reading", shade=0.0)
    n = vol.shape[0]
    # lid = upper 40% of slices
    z_from = int(round(n * 0.55))
    mask = part_mask(vol, {"z_from": z_from})
    assert mask.any(), "lid mask empty"
    pivot = hinge_pivot(mask, "back-seam")
    def lid_mean_z(angle):
        p, c = transform_voxels(vol, [{"name": "lid", "mode": "hinge", "mask": mask, "pivot": pivot, "angle": angle}])
        # lid voxels are the first chunk (claimed first)
        n_lid = int(mask.sum())
        return float(p[:n_lid, 0].mean())

    def body_mean_z(angle):
        p, c = transform_voxels(vol, [{"name": "lid", "mode": "hinge", "mask": mask, "pivot": pivot, "angle": angle}])
        n_lid = int(mask.sum())
        return float(p[n_lid:, 0].mean())

    z_lid_0 = lid_mean_z(0.0)
    z_lid_80 = lid_mean_z(80.0)
    z_body_0 = body_mean_z(0.0)
    z_body_80 = body_mean_z(80.0)
    assert z_lid_80 > z_lid_0 + 1.0, f"lid did not rise: {z_lid_0} -> {z_lid_80}"
    assert abs(z_body_80 - z_body_0) < 1e-6, f"body moved: {z_body_0} -> {z_body_80}"
    # renderer returns an image with pixels
    p, c = transform_voxels(vol, [{"name": "lid", "mode": "hinge", "mask": mask, "pivot": pivot, "angle": 70.0}])
    im = render_voxels(p, c, vol.shape[:3], 35)
    assert im.size[0] > 10 and im.size[1] > 10
    arr = np.array(im)
    assert (arr[..., 3] > 0).sum() > 20, "render is empty"


def test_hollow_clears_interior():
    vol = np.zeros((8, 20, 20, 4), dtype=np.uint8)
    vol[:, 1:19, 1:19] = (140, 80, 40, 255)
    before = int((vol[..., 3] > 0).sum())
    out = hollow_body(vol, 0, 8, wall=2)
    after = int((out[..., 3] > 0).sum())
    assert after < before * 0.7, f"hollow did too little: {before} -> {after}"
    # shell remains
    assert out[4, 1, 10, 3] > 0 or out[4, 2, 10, 3] > 0
    # very centre is empty
    assert out[4, 10, 10, 3] == 0


def test_chest_example_carves_and_opens():
    views = ROOT / "examples/chest/views.png"
    parts_path = ROOT / "examples/chest/parts.json"
    assert views.exists() and parts_path.exists()
    sheet = np.array(Image.open(views).convert("RGBA"))
    vol, _ = views_to_slices(sheet, slices=24, top_nose="down", order="reading", shade=0.2)
    assert vol.shape[0] == 24
    data = json.loads(parts_path.read_text())
    z_from = int(data["parts"][0]["select"]["z_from"])
    mask = part_mask(vol, {"z_from": z_from})
    assert int(mask.sum()) > 100
    pivot = hinge_pivot(mask, "back-seam")
    z0 = transform_voxels(vol, [{"name": "lid", "mode": "hinge", "mask": mask, "pivot": pivot, "angle": 0.0}])[0]
    z1 = transform_voxels(vol, [{"name": "lid", "mode": "hinge", "mask": mask, "pivot": pivot, "angle": 70.0}])[0]
    n_lid = int(mask.sum())
    assert z1[:n_lid, 0].mean() > z0[:n_lid, 0].mean() + 1.5


if __name__ == "__main__":
    test_keyframes()
    test_hollow_clears_interior()
    test_hinge_raises_lid()
    test_chest_example_carves_and_opens()
    print("ok")
