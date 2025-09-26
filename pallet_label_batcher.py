#!/usr/bin/env python3
"""Batch-generate pallet labels that combine QR codes with text metadata.

The script reads a CSV file where each row describes a pallet. It produces both
PNG and PDF label files sized for thermal printers so they can be dropped into
common print workflows. Use the ``--help`` flag for full CLI usage.
"""
from __future__ import annotations

import argparse
import csv
import json
import re
import sys
import textwrap
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Tuple

import qrcode
from PIL import Image, ImageDraw, ImageFont


DEFAULT_DPI = 203  # Common for 4x6 thermal printers.
DEFAULT_LABEL_WIDTH_IN = 4.0
DEFAULT_LABEL_HEIGHT_IN = 6.0
DEFAULT_BACKGROUND = 255  # white for "L" mode
DEFAULT_FONT_FALLBACK = "DejaVuSans.ttf"


class SafeDict(dict):
    """Format helper that replaces missing keys with empty strings."""

    def __missing__(self, key: str) -> str:  # pragma: no cover - trivial
        return ""


@dataclass
class TextBlock:
    text_template: str
    position: Tuple[int, int]
    font_size: int
    anchor: str = "la"
    fill: int = 0
    max_width: Optional[int] = None
    line_spacing: Optional[int] = None
    font_path: Optional[str] = None

    def build_text(self, row: Dict[str, str]) -> str:
        formatted = self.text_template.format_map(SafeDict({k: (v or "") for k, v in row.items()}))
        return formatted.strip()

    def get_font(self) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
        font_source = self.font_path or DEFAULT_FONT_FALLBACK
        try:
            return ImageFont.truetype(font_source, self.font_size)
        except OSError:
            # Fall back to Pillow's default bitmap font if DejaVuSans is not available.
            return ImageFont.load_default()


@dataclass
class Layout:
    size: Tuple[int, int]
    qr_box_size: int
    qr_border: int
    qr_position: Tuple[int, int]
    qr_render_size: int
    background: int = DEFAULT_BACKGROUND
    text_blocks: Tuple[TextBlock, ...] = ()


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--csv", required=True, type=Path, help="Path to the pallet data CSV.")
    parser.add_argument(
        "--output-dir",
        required=True,
        type=Path,
        help="Directory where generated labels (PNG/PDF) will be saved.",
    )
    parser.add_argument(
        "--template",
        type=Path,
        help=(
            "Optional JSON template that customises text layout, font sizes, and QR positioning. "
            "See README.md for the supported structure."
        ),
    )
    parser.add_argument(
        "--dpi",
        type=int,
        default=DEFAULT_DPI,
        help="Output resolution in dots per inch (controls label dimensions and clarity).",
    )
    return parser.parse_args()


def load_rows(csv_path: Path) -> Iterable[Dict[str, str]]:
    with csv_path.open(newline="", encoding="utf-8-sig") as handle:
        reader = csv.DictReader(handle)
        for idx, row in enumerate(reader, start=2):
            if not row:
                continue
            # Normalise keys to lower-case for easier template use.
            normalised = {k.strip().lower(): (v.strip() if isinstance(v, str) else v) for k, v in row.items()}
            pallet_id = normalised.get("pallet_id") or normalised.get("pallet")
            if not pallet_id:
                print(f"Skipping row {idx}: missing pallet_id column.", file=sys.stderr)
                continue
            normalised["pallet_id"] = pallet_id
            yield normalised


def load_template(path: Optional[Path], dpi: int) -> Layout:
    if path is None:
        return default_layout(dpi)

    data = json.loads(path.read_text(encoding="utf-8"))

    label_config = data.get("label", {})
    width_in = float(label_config.get("width_in", DEFAULT_LABEL_WIDTH_IN))
    height_in = float(label_config.get("height_in", DEFAULT_LABEL_HEIGHT_IN))
    background = int(label_config.get("background", DEFAULT_BACKGROUND))

    width_px = int(round(width_in * dpi))
    height_px = int(round(height_in * dpi))

    qr_config = data.get("qr", {})
    qr_box_size = int(qr_config.get("box_size", 10))
    qr_border = int(qr_config.get("border", 4))
    qr_render_size = int(round(qr_config.get("size_in", 2.5) * dpi)) if "size_in" in qr_config else int(
        qr_config.get("size_px", round(2.5 * dpi))
    )
    qr_position = tuple(
        int(value)
        for value in qr_config.get(
            "position", (width_px - qr_render_size - int(0.25 * dpi), int(0.25 * dpi))
        )
    )

    text_blocks = [
        TextBlock(
            text_template=block.get("text", ""),
            position=tuple(int(coord) for coord in block.get("position", (int(0.25 * dpi), int(0.25 * dpi)))),
            font_size=int(block.get("font_size", int(0.3 * dpi))),
            anchor=block.get("anchor", "la"),
            fill=int(block.get("fill", 0)),
            max_width=int(block["max_width"]) if "max_width" in block else None,
            line_spacing=int(block["line_spacing"]) if "line_spacing" in block else None,
            font_path=block.get("font_path"),
        )
        for block in data.get("text_blocks", [])
    ]

    return Layout(
        size=(width_px, height_px),
        qr_box_size=qr_box_size,
        qr_border=qr_border,
        qr_position=qr_position,
        qr_render_size=qr_render_size,
        background=background,
        text_blocks=tuple(text_blocks),
    )


def default_layout(dpi: int) -> Layout:
    width_px = int(round(DEFAULT_LABEL_WIDTH_IN * dpi))
    height_px = int(round(DEFAULT_LABEL_HEIGHT_IN * dpi))
    margin = int(round(0.3 * dpi))
    qr_render_size = int(round(2.4 * dpi))
    qr_position = (width_px - qr_render_size - margin, height_px - qr_render_size - margin)

    text_blocks: List[TextBlock] = [
        TextBlock(
            text_template="Pallet: {pallet_id}",
            position=(margin, margin),
            font_size=max(int(round(0.45 * dpi)), 24),
        ),
        TextBlock(
            text_template="Destination: {destination}",
            position=(margin, margin + int(round(0.7 * dpi))),
            font_size=max(int(round(0.28 * dpi)), 18),
            max_width=width_px - (2 * margin + qr_render_size + margin),
        ),
        TextBlock(
            text_template="Contents: {contents}",
            position=(margin, margin + int(round(1.2 * dpi))),
            font_size=max(int(round(0.26 * dpi)), 16),
            max_width=width_px - 2 * margin,
            line_spacing=int(round(0.1 * dpi)),
        ),
    ]

    return Layout(
        size=(width_px, height_px),
        qr_box_size=10,
        qr_border=4,
        qr_position=qr_position,
        qr_render_size=qr_render_size,
        background=DEFAULT_BACKGROUND,
        text_blocks=tuple(text_blocks),
    )


def wrap_text_to_width(text: str, font: ImageFont.ImageFont, max_width: Optional[int]) -> str:
    if not max_width or not text:
        return text

    # Estimate the number of characters that comfortably fit within ``max_width`` using the width of "M".
    try:
        ref_width = font.getlength("M")  # type: ignore[attr-defined]
    except AttributeError:
        try:
            bbox = font.getbbox("M")
            ref_width = bbox[2] - bbox[0]
        except AttributeError:
            ref_width = font.getsize("M")[0]
    ref_width = max(ref_width, 1)
    wrap_width = max(int(max_width / ref_width), 1)
    wrapper = textwrap.TextWrapper(width=wrap_width, break_long_words=True, break_on_hyphens=False)

    wrapped_lines: List[str] = []
    for paragraph in text.splitlines() or [text]:
        if not paragraph:
            wrapped_lines.append("")
            continue
        wrapped_lines.append(wrapper.fill(paragraph))
    return "\n".join(wrapped_lines)


def build_qr_image(data: str, box_size: int, border: int, target_size: int) -> Image.Image:
    qr = qrcode.QRCode(box_size=box_size, border=border, error_correction=qrcode.constants.ERROR_CORRECT_M)
    qr.add_data(data)
    qr.make(fit=True)
    img = qr.make_image(fill_color="black", back_color="white").convert("L")
    return img.resize((target_size, target_size), Image.NEAREST)


def sanitise_filename(value: str) -> str:
    return re.sub(r"[^A-Za-z0-9._-]+", "_", value).strip("_") or "label"


def render_label(row: Dict[str, str], layout: Layout, dpi: int) -> Image.Image:
    image = Image.new("L", layout.size, color=layout.background)
    draw = ImageDraw.Draw(image)

    qr_data = row.get("pallet_id") or next(iter(row.values()))
    qr_img = build_qr_image(qr_data, layout.qr_box_size, layout.qr_border, layout.qr_render_size)
    image.paste(qr_img, layout.qr_position)

    for block in layout.text_blocks:
        font = block.get_font()
        text = block.build_text(row)
        text = wrap_text_to_width(text, font, block.max_width)
        draw.multiline_text(
            block.position,
            text,
            font=font,
            fill=block.fill,
            spacing=block.line_spacing or max(int(font.size * 0.2) if hasattr(font, "size") else 4, 4),
            anchor=block.anchor or None,
        )

    return image


def export_label(image: Image.Image, base_path: Path, dpi: int) -> None:
    png_path = base_path.with_suffix(".png")
    pdf_path = base_path.with_suffix(".pdf")
    image.save(png_path, format="PNG", dpi=(dpi, dpi))
    image.save(pdf_path, format="PDF", resolution=dpi)


def process(csv_path: Path, output_dir: Path, layout: Layout, dpi: int) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    for row in load_rows(csv_path):
        pallet_id = (row.get("pallet_id") or "label").strip() or "label"
        filename = sanitise_filename(pallet_id)
        label_image = render_label(row, layout, dpi)
        base_path = output_dir / filename
        export_label(label_image, base_path, dpi)
        print(f"Generated {base_path.with_suffix('.png').name} and {base_path.with_suffix('.pdf').name}")


def main() -> None:
    args = parse_args()
    layout = load_template(args.template, args.dpi)
    process(args.csv, args.output_dir, layout, args.dpi)


if __name__ == "__main__":
    main()
