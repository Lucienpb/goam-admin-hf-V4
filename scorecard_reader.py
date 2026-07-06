import argparse
import json
import re
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import numpy as np
from PIL import Image, ImageFilter, ImageOps

try:
    from rapidocr_onnxruntime import RapidOCR
except Exception:
    RapidOCR = None


def _clean_name(text: str) -> str:
    value = re.sub(r"\s+", " ", str(text or "")).strip()
    value = re.sub(r"\b(sap\s*id|name|marker\s*[a-d]|player\s*[a-d])\b", "", value, flags=re.IGNORECASE)
    value = re.sub(r"[^A-Za-z '\-]", "", value).strip(" -|:;,.\t")
    return " ".join(token.capitalize() for token in value.split())


def _normalize_numeric_artifacts(text: str) -> str:
    value = str(text or "")
    value = re.sub(r"(?<=\d)[oO](?=\d)", "0", value)
    value = re.sub(r"(?<=\d)[iIlL](?=\d)", "1", value)
    value = re.sub(r"(?<=\d)[sS](?=\d)", "5", value)
    return value


def _is_name_like(text: str) -> bool:
    cleaned = _clean_name(text)
    if len(cleaned) < 3:
        return False
    # Require at least one letter token to avoid numeric/table fragments.
    return bool(re.search(r"[A-Za-z]", cleaned))


def _score_lines_quality(lines: List[str]) -> int:
    if not lines:
        return 0

    score = len(lines)
    for line in lines:
        lower = line.lower()
        if re.search(r"\d\s*[/|\\]\s*\d", line):
            score += 4
        if re.search(r"\d+", line):
            score += 1
        if any(k in lower for k in ("player", "marker", "total", "out", "in", "alliance", "competition")):
            score += 3
    return score


def _extract_lines_from_result(result_obj: Any) -> List[str]:
    lines: List[str] = []
    if isinstance(result_obj, list):
        for item in result_obj:
            if not isinstance(item, (list, tuple)) or len(item) < 2:
                continue
            text = str(item[1]).strip()
            if text:
                lines.append(text)
    return lines


def _run_ocr_multi_pass(image: Image.Image) -> Tuple[List[str], str]:
    if RapidOCR is None:
        raise RuntimeError("rapidocr-onnxruntime is not installed.")

    engine = RapidOCR()
    rgb = image.convert("RGB")
    gray = image.convert("L")

    # Multi-pass preprocessing helps with skewed and handwritten scorecards.
    candidates = [
        rgb,
        ImageOps.autocontrast(gray).convert("RGB"),
        ImageOps.equalize(gray).convert("RGB"),
        ImageOps.autocontrast(gray).filter(ImageFilter.SHARPEN).convert("RGB"),
        ImageOps.autocontrast(gray).point(lambda x: 255 if x > 145 else 0, mode="1").convert("RGB"),
        ImageOps.invert(ImageOps.autocontrast(gray).point(lambda x: 255 if x > 145 else 0, mode="1").convert("L")).convert("RGB"),
        rgb.rotate(-1.2, expand=True, fillcolor="white"),
        rgb.rotate(1.2, expand=True, fillcolor="white"),
    ]

    best_lines: List[str] = []
    best_score = -1
    all_lines: List[str] = []
    pass_lines_list: List[List[str]] = []
    debug: List[str] = []

    for idx, candidate in enumerate(candidates, start=1):
        try:
            result, _ = engine(np.array(candidate))
            lines = _extract_lines_from_result(result)
        except Exception as exc:
            debug.append(f"Pass {idx}: OCR error ({exc})")
            continue

        debug.append(f"Pass {idx}: {len(lines)} lines")
        pass_lines_list.append(lines)
        all_lines.extend(lines)

        score = _score_lines_quality(lines)
        if score > best_score:
            best_score = score
            best_lines = lines

    if pass_lines_list:
        # Keep consensus lines (seen in >=2 passes) and all best-pass lines.
        vote_counts: Dict[str, int] = {}
        first_seen_text: Dict[str, str] = {}
        for pass_lines in pass_lines_list:
            seen_in_pass = set()
            for line in pass_lines:
                key = re.sub(r"\s+", " ", line.strip().lower())
                if not key or key in seen_in_pass:
                    continue
                seen_in_pass.add(key)
                vote_counts[key] = vote_counts.get(key, 0) + 1
                if key not in first_seen_text:
                    first_seen_text[key] = line.strip()

        merged: List[str] = []
        merged_keys = set()

        for line in best_lines:
            key = re.sub(r"\s+", " ", line.strip().lower())
            if not key or key in merged_keys:
                continue
            merged_keys.add(key)
            merged.append(line.strip())

        for key, count in vote_counts.items():
            if count < 2 or key in merged_keys:
                continue
            merged_keys.add(key)
            merged.append(first_seen_text[key])

        if merged:
            best_lines = merged[:180]

    return best_lines, "\n".join(debug)


def _extract_slot_names(lines: List[str]) -> Dict[str, str]:
    slots = {"A": "", "B": "", "C": "", "D": ""}
    label_pattern = re.compile(r"\b(?:player|plaver|play|marker|markcr)\s*([abcd])\b", flags=re.IGNORECASE)

    for idx, raw in enumerate(lines):
        line = re.sub(r"\s+", " ", str(raw or "")).strip()
        if not line:
            continue

        match = label_pattern.search(line)
        if not match:
            continue

        slot = match.group(1).upper()
        if slots[slot]:
            continue

        tail = line[match.end() :].strip(" :-")
        name = _clean_name(tail)

        if not _is_name_like(name):
            for offset in (1, 2):
                next_idx = idx + offset
                if next_idx >= len(lines):
                    break
                candidate = re.sub(r"\s+", " ", str(lines[next_idx] or "")).strip()
                if _is_name_like(candidate):
                    name = _clean_name(candidate)
                    break

        if _is_name_like(name):
            slots[slot] = name

    return slots


def _extract_score_ips_pairs(line: str) -> List[Tuple[int, int]]:
    pairs: List[Tuple[int, int]] = []
    normalized = _normalize_numeric_artifacts(line)

    for match in re.finditer(r"(\d{2,3})\s*[/|\\]\s*(\d{1,2})", normalized):
        strokes = int(match.group(1))
        ips = int(match.group(2))
        if 55 <= strokes <= 130 and 0 <= ips <= 50:
            pairs.append((strokes, ips))

    if len(pairs) >= 4:
        return pairs[:4]

    nums = [int(x) for x in re.findall(r"\d{1,3}", normalized)]
    guess_pairs: List[Tuple[int, int]] = []
    i = 0
    while i < len(nums) - 1:
        strokes = nums[i]
        ips = nums[i + 1]
        if 55 <= strokes <= 130 and 0 <= ips <= 50:
            guess_pairs.append((strokes, ips))
            i += 2
            continue
        i += 1

    if len(guess_pairs) >= 4:
        return guess_pairs[:4]

    return pairs


def _extract_meta(lines: List[str]) -> Dict[str, Optional[str]]:
    meta: Dict[str, Optional[str]] = {
        "date": None,
        "time": None,
        "competition": None,
    }

    for line in lines:
        lower = line.lower()

        if meta["date"] is None:
            m = re.search(r"\b(\d{1,2}[/-]\d{1,2}[/-]\d{2,4})\b", line)
            if m:
                meta["date"] = m.group(1)

        if meta["time"] is None:
            m = re.search(r"\b(\d{1,2}[:h]\d{2})\b", lower)
            if m:
                meta["time"] = m.group(1).replace("h", ":")

        if meta["competition"] is None and "competition" in lower:
            m = re.search(r"competition\s*[:\-]?\s*(.+)$", line, flags=re.IGNORECASE)
            if m:
                value = re.sub(r"\s+", " ", m.group(1)).strip(" .")
                meta["competition"] = value or None

    return meta


def parse_scorecard(lines: List[str]) -> Dict[str, Any]:
    slots = _extract_slot_names(lines)
    if not any(slots.values()):
        slots = {"A": "Player A", "B": "Player B", "C": "Player C", "D": "Player D"}

    best_line = ""
    best_pairs: List[Tuple[int, int]] = []

    for raw in lines:
        line = re.sub(r"\s+", " ", str(raw or "")).strip()
        if not line:
            continue

        pairs = _extract_score_ips_pairs(line)
        if not pairs:
            continue

        lower = line.lower()
        keyword_weight = 6 if any(k in lower for k in ("total", "out", "in", "alliance")) else 0
        slash_weight = min(6, len(re.findall(r"[/|\\]", line)))
        big_number_penalty = sum(1 for n in re.findall(r"\d+", line) if int(n) > 200)
        line_score = (len(pairs) * 10) + keyword_weight + slash_weight - (big_number_penalty * 2)

        current_best_score = (len(best_pairs) * 10)
        if line_score > current_best_score:
            best_pairs = pairs
            best_line = line

    players: List[Dict[str, Any]] = []
    for idx, slot in enumerate(["A", "B", "C", "D"]):
        strokes = None
        ips = None
        confidence = "low"

        if idx < len(best_pairs):
            strokes, ips = best_pairs[idx]
            confidence = "medium"

        name_value = slots.get(slot) or f"Player {slot}"
        if not name_value.lower().startswith("player ") and strokes is not None and ips is not None:
            confidence = "high"

        players.append(
            {
                "slot": slot,
                "name": name_value,
                "strokes": strokes,
                "ips": ips,
                "liv": "",
                "confidence": confidence,
            }
        )

    return {
        "meta": _extract_meta(lines),
        "players": players,
        "totals_source_line": best_line,
        "detected_pairs": len(best_pairs),
    }


def read_scorecard_image(image_path: str, include_raw: bool = True) -> Dict[str, Any]:
    image = Image.open(image_path).convert("RGB")
    lines, debug = _run_ocr_multi_pass(image)
    parsed = parse_scorecard(lines)

    output: Dict[str, Any] = {
        "source_image": str(image_path),
        "extracted_at_utc": datetime.utcnow().isoformat() + "Z",
        "ocr_debug": debug,
        **parsed,
    }

    if include_raw:
        output["raw_ocr_lines"] = lines

    return output


def _build_cli_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Standalone scorecard OCR reader")
    parser.add_argument("--image", required=True, help="Path to scorecard image")
    parser.add_argument("--output", default="", help="Output JSON file path")
    parser.add_argument("--no-raw", action="store_true", help="Exclude raw OCR lines from output")
    parser.add_argument("--compact", action="store_true", help="Emit compact JSON")
    return parser


def main() -> None:
    parser = _build_cli_parser()
    args = parser.parse_args()

    image_path = Path(args.image)
    if not image_path.exists():
        raise FileNotFoundError(f"Image not found: {image_path}")

    result = read_scorecard_image(str(image_path), include_raw=not args.no_raw)

    if args.compact:
        payload = json.dumps(result, separators=(",", ":"), ensure_ascii=True)
    else:
        payload = json.dumps(result, indent=2, ensure_ascii=True)

    if args.output:
        out_path = Path(args.output)
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(payload, encoding="utf-8")
        print(f"Wrote JSON output to {out_path}")
    else:
        print(payload)


if __name__ == "__main__":
    main()
