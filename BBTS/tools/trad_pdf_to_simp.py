#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Unified pipeline: OCR Traditional Chinese PDF -> merged Traditional TXT -> merged Simplified TXT.
"""

from __future__ import annotations

import argparse
import csv
import re
import statistics
import sys
import time
import urllib.request
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable


class MissingDependencyError(RuntimeError):
    pass


def ensure_dependencies() -> None:
    missing = []
    try:
        import numpy  # noqa: F401
    except Exception:
        missing.append("numpy")

    try:
        import pypdfium2  # noqa: F401
    except Exception:
        missing.append("pypdfium2")

    try:
        import PIL  # noqa: F401
    except Exception:
        missing.append("Pillow")

    try:
        import rapidocr_onnxruntime  # noqa: F401
    except Exception:
        missing.append("rapidocr_onnxruntime")

    try:
        import opencc  # noqa: F401
    except Exception:
        missing.append("opencc-python-reimplemented")

    if missing:
        raise MissingDependencyError(
            "Missing packages: "
            + ", ".join(missing)
            + "\nInstall with:\n"
            + "python -m pip install -r BBTS/tools/requirements.txt"
        )


def cjk_space_compact(text: str) -> str:
    return re.sub(r"(?<=[\u4e00-\u9fff])\s+(?=[\u4e00-\u9fff])", "", text)


def basic_normalize(text: str) -> str:
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    text = text.replace("\u3000", " ")
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    text = cjk_space_compact(text)
    return text.strip()


def load_custom_mapping(path: Path | None) -> dict[str, str]:
    mapping: dict[str, str] = {}
    if path is None:
        return mapping
    if not path.exists():
        raise FileNotFoundError(f"Custom mapping file not found: {path}")

    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        if "\t" in line:
            src, dst = line.split("\t", 1)
        elif "=>" in line:
            src, dst = line.split("=>", 1)
        else:
            raise ValueError(
                f"Invalid mapping line: {raw}\nUse TAB or '=>' separator."
            )
        mapping[src.strip()] = dst.strip()
    return mapping


def apply_custom_replacements(text: str, mapping: dict[str, str]) -> str:
    if not mapping:
        return text
    for src, dst in mapping.items():
        text = text.replace(src, dst)
    return text


@dataclass
class PageResult:
    page_number: int
    chars: int
    lines: int
    avg_conf: float
    ocr_seconds: float
    text: str


def _box_stats(box_points: list[list[float]]) -> tuple[float, float, float, float]:
    xs = [float(p[0]) for p in box_points]
    ys = [float(p[1]) for p in box_points]
    return min(xs), max(xs), min(ys), max(ys)


def _reorder_items(
    items: list[tuple[str, float, tuple[float, float, float, float]]], reading_order: str
) -> list[tuple[str, float, tuple[float, float, float, float]]]:
    if not items:
        return items
    if reading_order == "ocr":
        return items
    if reading_order == "ltr_tb":
        return sorted(items, key=lambda it: (it[2][2], it[2][0]))
    if reading_order == "rtl_tb":
        return sorted(items, key=lambda it: (-it[2][1], it[2][2]))

    tall = 0
    for _, _, (x_min, x_max, y_min, y_max) in items:
        if (y_max - y_min) > (x_max - x_min):
            tall += 1
    if tall >= (len(items) * 0.55):
        return sorted(items, key=lambda it: (-it[2][1], it[2][2]))
    return sorted(items, key=lambda it: (it[2][2], it[2][0]))


def extract_lines(result_obj, reading_order: str) -> tuple[list[str], list[float]]:
    lines: list[str] = []
    confs: list[float] = []
    if not result_obj:
        return lines, confs

    items: list[tuple[str, float, tuple[float, float, float, float]]] = []
    for item in result_obj:
        if not item or len(item) < 3:
            continue
        box_points = item[0] or []
        text = (item[1] or "").strip()
        score = item[2]
        if not text or not box_points:
            continue
        try:
            conf = float(score)
        except Exception:
            conf = 0.0
        items.append((text, conf, _box_stats(box_points)))

    items = _reorder_items(items, reading_order)
    for text, conf, _ in items:
        lines.append(text)
        confs.append(conf)
    return lines, confs


def download_pdf(url: str, target: Path) -> Path:
    target.parent.mkdir(parents=True, exist_ok=True)
    with urllib.request.urlopen(url) as response:  # nosec B310
        content = response.read()
    target.write_bytes(content)
    return target


def ocr_pdf(
    input_pdf: Path,
    out_dir: Path,
    start_page: int,
    end_page: int | None,
    dpi: int,
    opencc_config: str,
    custom_map_file: Path | None,
    low_conf_threshold: float,
    save_raw_per_page: bool,
    reading_order: str,
) -> tuple[list[PageResult], list[int], dict[str, str]]:
    import numpy as np
    import pypdfium2 as pdfium
    from opencc import OpenCC
    from rapidocr_onnxruntime import RapidOCR

    converter = OpenCC(opencc_config)
    custom_map = load_custom_mapping(custom_map_file)

    doc = pdfium.PdfDocument(str(input_pdf))
    page_count = len(doc)
    if page_count <= 0:
        raise RuntimeError("PDF has no pages.")

    start_idx = max(0, start_page - 1)
    end_idx = page_count - 1 if end_page is None else min(page_count - 1, end_page - 1)
    if start_idx > end_idx:
        raise ValueError(
            f"Invalid range: start_page={start_page}, end_page={end_page}, total_pages={page_count}"
        )

    ocr = RapidOCR()
    scale = dpi / 72.0

    pages_dir = out_dir / "pages_corrected"
    raw_dir = out_dir / "pages_raw"
    pages_dir.mkdir(parents=True, exist_ok=True)
    if save_raw_per_page:
        raw_dir.mkdir(parents=True, exist_ok=True)

    results: list[PageResult] = []
    low_conf_pages: list[int] = []
    total = end_idx - start_idx + 1

    for idx in range(start_idx, end_idx + 1):
        page_no = idx + 1
        t0 = time.time()

        page = doc[idx]
        pil_img = page.render(scale=scale).to_pil()
        img = np.array(pil_img.convert("RGB"))

        ocr_result, _ = ocr(img)
        lines, confs = extract_lines(ocr_result, reading_order=reading_order)

        raw_text = "\n".join(lines).strip()
        corrected = basic_normalize(raw_text)
        corrected = converter.convert(corrected)
        corrected = apply_custom_replacements(corrected, custom_map)

        avg_conf = statistics.mean(confs) if confs else 0.0
        elapsed = time.time() - t0

        if avg_conf < low_conf_threshold:
            low_conf_pages.append(page_no)

        (pages_dir / f"page_{page_no:04d}.txt").write_text(
            corrected + ("\n" if corrected else ""), encoding="utf-8"
        )
        if save_raw_per_page:
            (raw_dir / f"page_{page_no:04d}.txt").write_text(
                raw_text + ("\n" if raw_text else ""), encoding="utf-8"
            )

        results.append(
            PageResult(
                page_number=page_no,
                chars=len(corrected),
                lines=len(lines),
                avg_conf=avg_conf,
                ocr_seconds=elapsed,
                text=corrected,
            )
        )
        done = idx - start_idx + 1
        print(
            f"[{done}/{total}] page {page_no}: lines={len(lines)}, chars={len(corrected)}, conf={avg_conf:.3f}, sec={elapsed:.2f}"
        )

    meta = {
        "total_pages": str(page_count),
        "processed_pages": str(total),
        "start_page": str(start_idx + 1),
        "end_page": str(end_idx + 1),
        "opencc_config": opencc_config,
        "custom_mapping_count": str(len(custom_map)),
        "reading_order": reading_order,
    }
    return results, low_conf_pages, meta


def write_outputs(
    out_dir: Path,
    input_pdf: Path,
    results: Iterable[PageResult],
    low_conf_pages: list[int],
    meta: dict[str, str],
) -> None:
    out_dir.mkdir(parents=True, exist_ok=True)
    results = list(results)

    merged_blocks = []
    for r in results:
        merged_blocks.append(f"\n\n===== Page {r.page_number} =====\n")
        merged_blocks.append(r.text)
    merged_trad = "".join(merged_blocks).lstrip("\n")

    merged_trad_file = out_dir / "merged_corrected.txt"
    merged_trad_file.write_text(
        merged_trad + ("\n" if merged_trad else ""), encoding="utf-8"
    )

    from opencc import OpenCC

    converter = OpenCC("t2s")
    merged_simp = converter.convert(merged_trad)
    merged_simp_file = out_dir / "merged_simplified.txt"
    merged_simp_file.write_text(
        merged_simp + ("\n" if merged_simp else ""), encoding="utf-8"
    )

    stats_file = out_dir / "page_stats.csv"
    with stats_file.open("w", encoding="utf-8-sig", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(["page", "chars", "lines", "avg_conf", "ocr_seconds"])
        for r in results:
            writer.writerow(
                [
                    r.page_number,
                    r.chars,
                    r.lines,
                    f"{r.avg_conf:.4f}",
                    f"{r.ocr_seconds:.3f}",
                ]
            )

    low_file = out_dir / "low_conf_pages.txt"
    low_file.write_text(
        ("\n".join(str(p) for p in low_conf_pages) + "\n") if low_conf_pages else "",
        encoding="utf-8",
    )

    summary_file = out_dir / "README_result.txt"
    avg_conf_all = statistics.mean([r.avg_conf for r in results]) if results else 0.0
    summary = [
        f"Input PDF: {input_pdf}",
        f"Processed pages: {meta.get('processed_pages', '?')} / total {meta.get('total_pages', '?')}",
        f"Range: {meta.get('start_page', '?')} - {meta.get('end_page', '?')}",
        f"Average confidence: {avg_conf_all:.4f}",
        f"Low-confidence pages: {len(low_conf_pages)}",
        f"OpenCC config: {meta.get('opencc_config', 't2s')}",
        f"Custom mapping entries: {meta.get('custom_mapping_count', '0')}",
        f"Reading order: {meta.get('reading_order', 'auto')}",
        "",
        "Output files:",
        "- merged_corrected.txt",
        "- merged_simplified.txt",
        "- page_stats.csv",
        "- low_conf_pages.txt",
        "- pages_corrected/page_XXXX.txt",
        "- pages_raw/page_XXXX.txt (if --save-raw-per-page)",
    ]
    summary_file.write_text("\n".join(summary) + "\n", encoding="utf-8")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="OCR Traditional Chinese PDF and export both Traditional and Simplified merged TXT."
    )
    parser.add_argument("--input-pdf", type=Path, default=None, help="Local PDF file path")
    parser.add_argument("--input-url", default=None, help="Public PDF URL for cloud runs")
    parser.add_argument(
        "-o",
        "--out-dir",
        type=Path,
        default=Path("out"),
        help="Output directory (default: ./out)",
    )
    parser.add_argument("--start-page", type=int, default=1, help="1-based start page")
    parser.add_argument("--end-page", type=int, default=None, help="1-based end page")
    parser.add_argument("--dpi", type=int, default=300, help="Render DPI for OCR")
    parser.add_argument(
        "--opencc-config",
        default="t2s",
        help="OpenCC config for OCR text normalization (default: t2s)",
    )
    parser.add_argument("--custom-map", type=Path, default=None, help="Custom replacement map")
    parser.add_argument(
        "--low-conf-threshold",
        type=float,
        default=0.82,
        help="Mark page as low confidence under this threshold",
    )
    parser.add_argument(
        "--save-raw-per-page",
        action="store_true",
        help="Also save raw OCR text per page",
    )
    parser.add_argument(
        "--reading-order",
        choices=["auto", "ocr", "ltr_tb", "rtl_tb"],
        default="rtl_tb",
        help="Text ordering strategy (default: rtl_tb)",
    )
    return parser


def resolve_input_pdf(args: argparse.Namespace) -> Path:
    if args.input_pdf:
        if not args.input_pdf.exists():
            raise FileNotFoundError(f"Input PDF not found: {args.input_pdf}")
        return args.input_pdf

    if args.input_url:
        target = args.out_dir / "input.pdf"
        print(f"Downloading PDF: {args.input_url}")
        return download_pdf(args.input_url, target)

    raise ValueError("Provide either --input-pdf or --input-url.")


def main() -> int:
    args = build_parser().parse_args()

    try:
        ensure_dependencies()
    except MissingDependencyError as exc:
        print(str(exc))
        return 3

    args.out_dir.mkdir(parents=True, exist_ok=True)

    try:
        input_pdf = resolve_input_pdf(args)
    except Exception as exc:
        print(f"ERROR: {exc}")
        return 2

    print(f"Input: {input_pdf}")
    print(f"Output: {args.out_dir}")
    print(
        f"Range: {args.start_page} - {args.end_page if args.end_page else 'END'}, DPI={args.dpi}, order={args.reading_order}"
    )

    t_all = time.time()
    try:
        results, low_conf_pages, meta = ocr_pdf(
            input_pdf=input_pdf,
            out_dir=args.out_dir,
            start_page=args.start_page,
            end_page=args.end_page,
            dpi=args.dpi,
            opencc_config=args.opencc_config,
            custom_map_file=args.custom_map,
            low_conf_threshold=args.low_conf_threshold,
            save_raw_per_page=args.save_raw_per_page,
            reading_order=args.reading_order,
        )
        write_outputs(
            out_dir=args.out_dir,
            input_pdf=input_pdf,
            results=results,
            low_conf_pages=low_conf_pages,
            meta=meta,
        )
    except Exception as exc:
        print(f"ERROR: {exc}")
        return 1

    elapsed = time.time() - t_all
    print(f"Done. Processed {len(results)} page(s) in {elapsed / 60:.2f} min.")
    print(f"Check outputs: {args.out_dir}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
