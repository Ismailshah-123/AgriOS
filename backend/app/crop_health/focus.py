"""Plain-language summary of a class activation map (deterministic; no LLM).

Input: the normalised CAM grid (rows x cols, 0..1) over the model's centre crop.
Output: where the strong activation sits (3x3 position names), what share of the crop is
strongly highlighted (>= 0.5), and how many separate hotspots there are. This describes
WHERE THE MODEL LOOKED. It is not a measurement of disease severity or of lesion area.
"""

from __future__ import annotations

from typing import Any

STRONG = 0.5
_POS_EN = {
    (0, 0): "upper left",
    (0, 1): "upper centre",
    (0, 2): "upper right",
    (1, 0): "centre left",
    (1, 1): "centre",
    (1, 2): "centre right",
    (2, 0): "lower left",
    (2, 1): "lower centre",
    (2, 2): "lower right",
}
_POS_UR = {
    (0, 0): "اوپر بائیں",
    (0, 1): "اوپر درمیان",
    (0, 2): "اوپر دائیں",
    (1, 0): "درمیان بائیں",
    (1, 1): "درمیان",
    (1, 2): "درمیان دائیں",
    (2, 0): "نیچے بائیں",
    (2, 1): "نیچے درمیان",
    (2, 2): "نیچے دائیں",
}


def _hotspots(strong: list[list[bool]]) -> int:
    rows, cols = len(strong), len(strong[0])
    seen = [[False] * cols for _ in range(rows)]
    n = 0
    for r in range(rows):
        for c in range(cols):
            if strong[r][c] and not seen[r][c]:
                n += 1
                stack = [(r, c)]
                seen[r][c] = True
                while stack:
                    y, x = stack.pop()
                    for dy, dx in ((1, 0), (-1, 0), (0, 1), (0, -1)):
                        ny, nx = y + dy, x + dx
                        if (
                            0 <= ny < rows
                            and 0 <= nx < cols
                            and strong[ny][nx]
                            and not seen[ny][nx]
                        ):
                            seen[ny][nx] = True
                            stack.append((ny, nx))
    return n


def summarise(grid: list[list[float]]) -> dict[str, Any] | None:
    if not grid or not grid[0]:
        return None
    rows, cols = len(grid), len(grid[0])
    strong = [[v >= STRONG for v in row] for row in grid]
    cells = [(r, c, grid[r][c]) for r in range(rows) for c in range(cols) if strong[r][c]]
    if not cells:
        return None
    w = sum(v for _, _, v in cells)
    cy = sum(r * v for r, _, v in cells) / w / max(rows - 1, 1)
    cx = sum(c * v for _, c, v in cells) / w / max(cols - 1, 1)
    pos = (min(int(cy * 3), 2), min(int(cx * 3), 2))
    share = round(100 * len(cells) / (rows * cols))
    spots = _hotspots(strong)
    en = (
        f"The model focused mostly on the {_POS_EN[pos]} of the analysed area; "
        f"about {share}% of it is strongly highlighted, in {spots} "
        f"{'spot' if spots == 1 else 'separate spots'}."
    )
    ur = (
        f"ماڈل نے زیادہ تر تجزیہ شدہ حصے کے {_POS_UR[pos]} پر توجہ دی؛ "
        f"تقریباً {share}% حصہ نمایاں ہے، {spots} جگہوں پر۔"
    )
    return {
        "position": _POS_EN[pos],
        "strong_share_pct": share,
        "hotspots": spots,
        "text_en": en,
        "text_ur": ur,
        "caveat": "Shows where the model looked, not how severe the disease is.",
    }
