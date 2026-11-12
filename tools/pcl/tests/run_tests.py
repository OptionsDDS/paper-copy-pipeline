#!/usr/bin/env python3
"""PCL 1.2 conformance runner.

Runs every case under tests/cases/ through the pcl.py CLI and compares the
printed view, reading view and annotations with the frozen expectations.
Negative cases under tests/negative/ must fail with exactly the recorded
error.  All positive cases also face a set of independent invariant checks.

Usage: python3 tests/run_tests.py
"""

from __future__ import annotations

import json
from collections import Counter
import os
import re
import subprocess
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

import pcl  # noqa: E402

CASE_DIR = os.path.join(ROOT, "tests", "cases")
NEG_DIR = os.path.join(ROOT, "tests", "negative")
PCL = os.path.join(ROOT, "pcl.py")
INSTRUCTION = re.compile("\u27e6[^\u27e7]*\u27e7")


class Failure(Exception):
    pass


def read_bytes(path):
    with open(path, "rb") as handle:
        return handle.read()


def run_cli(*args):
    return subprocess.run(
        [sys.executable, "-I", "-B", PCL, *args],
        cwd=ROOT,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )


def check(condition, message):
    if not condition:
        raise Failure(message)


def check_annotations(name, annotations, printed_text, reading_text):
    mapping = annotations["reading_map"]
    check(
        len(mapping) == len(reading_text),
        f"{name}: reading_map has {len(mapping)} entries for "
        f"{len(reading_text)} reading characters",
    )
    printed_lines = printed_text.split("\n")
    if printed_lines and printed_lines[-1] == "":
        printed_lines = printed_lines[:-1]
    check(
        len(printed_lines) == len(annotations["lines"]),
        f"{name}: reading_map printed line count mismatch",
    )
    derived: dict = {}
    for offset, entry in enumerate(mapping):
        check(entry["offset"] == offset, f"{name}: reading_map offset drift")
        check(
            entry["char"] == reading_text[offset],
            f"{name}: reading_map char mismatch at {offset}",
        )
        if "derived" in entry:
            reason = entry["derived"]
            allowed = (
                "line-break",
                "para",
                "gap",
                "sup-open",
                "sup-close",
                "sub-open",
                "sub-close",
                "heading",
                "float",
            )
            check(
                reason in allowed,
                f"{name}: unknown derived reason {reason!r}",
            )
            derived[reason] = derived.get(reason, 0) + 1
            continue
        line = entry["line"]
        column = entry["column"]
        check(
            1 <= line <= len(printed_lines),
            f"{name}: reading_map line {line} out of range",
        )
        printed_line = printed_lines[line - 1]
        check(
            0 <= column < len(printed_line),
            f"{name}: reading_map column {column} out of range on line {line}",
        )
        actual = printed_line[column]
        if "substituted" in entry:
            expected_cp = int(entry["substituted"][2:], 16)
            check(
                ord(actual) == expected_cp,
                f"{name}: substitution at {offset} points at {actual!r}, "
                f"not {entry['substituted']}",
            )
        else:
            check(
                actual == entry["char"],
                f"{name}: reading_map at {offset} says {entry['char']!r} "
                f"but printed line {line} column {column} is {actual!r}",
            )

    para_breaks = len(annotations["paras"])
    for paragraph in annotations["paras"]:
        separator = mapping[paragraph["reading_offset"]]
        shared_float = annotations["pcl"] == "1.2" and separator.get("derived") == "float"
        check(separator["char"] == "\n" and (separator.get("derived") == "para" or shared_float),
              f"{name}: paragraph does not record a derived newline")
        para_breaks -= shared_float
    furniture_lines = {
        record["line"] for record in annotations["lines"] if record.get("furniture")
    }
    wrap_lines = {record["line"] for record in annotations["wraps"]}
    para_lines = {record["line"] for record in annotations["paras"]}
    joins = 0
    for break_index in range(1, len(printed_lines)):
        next_line = break_index + 1
        if next_line in furniture_lines:
            continue
        if next_line in wrap_lines or next_line in para_lines:
            continue
        if any(
            line_number not in furniture_lines
            for line_number in range(1, next_line)
        ):
            joins += 1
    if annotations["pcl"] != "1.2":
        check(
            derived.get("line-break", 0) == joins,
            f"{name}: {derived.get('line-break', 0)} derived joining spaces "
            f"for {joins} joins",
        )
    check(
        derived.get("para", 0) == para_breaks,
        f"{name}: derived paragraph newlines do not match paras",
    )
    check(
        derived.get("gap", 0) == len(annotations["gaps"]),
        f"{name}: derived gap spaces do not match the gaps list",
    )
    for record in annotations.get("furniture", []):
        check(
            record["printed_text"]
            and record["printed_text"] in printed_text,
            f"{name}: furniture text missing from the printed view",
        )
        for line_number in range(record["start_line"], record["end_line"] + 1):
            check(
                line_number in furniture_lines,
                f"{name}: furniture span does not mark line {line_number}",
            )

    for gap in annotations["gaps"]:
        offset = gap["reading_offset"]
        check(
            reading_text[offset] == " " and mapping[offset]["derived"] == "gap",
            f"{name}: gap at {offset} is not a derived space",
        )
        check(
            printed_lines[gap["line"] - 1][gap["column"]] == " ",
            f"{name}: gap at line {gap['line']} is not a printed space",
        )

    spans = annotations["spans"]
    for span in spans:
        check(
            0 <= span["start"] <= span["end"] <= len(reading_text),
            f"{name}: span {span['name']} out of range",
        )
    for span_name, marker in (("sup", "^"), ("sub", "_")):
        typed = [span for span in spans if span["name"] == span_name]
        expected_open = marker + "{"
        check(
            derived.get(f"{span_name}-open", 0) == 2 * len(typed),
            f"{name}: {span_name}-open markers do not match its spans",
        )
        check(
            derived.get(f"{span_name}-close", 0) == len(typed),
            f"{name}: {span_name}-close markers do not match its spans",
        )
        for span in typed:
            check(
                span["start"] >= 2
                and reading_text[span["start"] - 2:span["start"]] == expected_open,
                f"{name}: {span_name} span at {span['start']} lacks its open "
                "marker",
            )
            check(
                span["end"] < len(reading_text)
                and reading_text[span["end"]] == "}",
                f"{name}: {span_name} span at {span['end']} lacks its close "
                "marker",
            )

    for glyph in annotations["glyphs"]:
        if glyph["as"] == "none":
            check(
                "gap" in glyph,
                f"{name}: invisible glyph lacks its measured gap",
            )
            check(
                glyph["reading_start"] == glyph["reading_end"],
                f"{name}: invisible glyph still contributes reading text",
            )
        else:
            check(
                glyph["reading_end"] - glyph["reading_start"] == len(glyph["as"]),
                f"{name}: glyph reading range does not match its as= list",
            )

    check(
        all(
            annotations["lines"][i]["printed_end"]
            <= annotations["lines"][i + 1]["printed_start"]
            for i in range(len(annotations["lines"]) - 1)
        ),
        f"{name}: printed line ranges overlap",
    )
    ordered_lines = sorted((row for row in annotations["lines"] if row["reading_start"] != row["reading_end"]), key=lambda row: (row["reading_start"], row["reading_end"]))
    check(
        all(
            ordered_lines[i]["reading_end"]
            <= ordered_lines[i + 1]["reading_start"]
            for i in range(len(ordered_lines) - 1)
        ),
        f"{name}: reading line ranges overlap",
    )
    for record in annotations["wraps"]:
        if record["hyphen"] == "remove":
            check(
                "removed" in record and record["removed_reading"] != "",
                f"{name}: remove wrap lacks removal record",
            )


def check_stream_joins(name, annotations, printed_text):
    """Count derived joins independently in prose and in each float span.

    A wrap suppresses breaks only in the stream containing both endpoints.
    Check provenance per stream, so lost spaces cannot cancel extra ones.
    """
    blocks = annotations["float_spans"]
    printed_lines = printed_text.split("\n")[:-1]
    float_lines = {n for block in blocks
                   for n in range(block["start_line"], block["end_line"] + 1)}
    furniture_lines = {row["line"] for row in annotations["lines"] if row.get("furniture")}
    para_lines = {row["line"] for row in annotations["paras"]}
    heading_lines = {n: index for index, span in enumerate(annotations["headings"])
                     for n in range(span["start_line"], span["end_line"] + 1)}
    streams = [("prose", [n for n in range(1, len(printed_lines) + 1)
                          if n not in float_lines | furniture_lines
                          and (printed_lines[n - 1] or n in para_lines)])]
    streams += [(f"float at line {block['start_line']}",
                 list(range(block["start_line"], block["end_line"] + 1))) for block in blocks]
    checked = 0
    for label, stream in streams:
        members = set(stream)
        wraps = [wrap for wrap in annotations["wraps"]
                 if wrap["line"] in members and wrap.get("from", wrap["line"] - 1) in members]
        suppressed = {n for wrap in wraps
                      for n in range(wrap.get("from", wrap["line"] - 1) + 1, wrap["line"] + 1)}
        expected = Counter(left for left, right in zip(stream, stream[1:])
                           if right not in suppressed | para_lines
                           and heading_lines.get(left) == heading_lines.get(right)
                           and not any(annotations["lines"][left - 1]["reading_end"] <= block["start"]
                                       and block["end"] <= annotations["lines"][right - 1]["reading_start"]
                                       for block in blocks))
        actual = Counter(entry["after_line"] for entry in annotations["reading_map"]
                         if entry.get("derived") == "line-break" and entry["after_line"] in members)
        check(actual == expected,
              f"{name}: {label}: {sum(actual.values())} derived joining spaces for "
              f"{sum(expected.values())} joins; origins {dict(actual)} != {dict(expected)}")
        checked += sum(actual.values())
    check(checked == sum(entry.get("derived") == "line-break" for entry in annotations["reading_map"]),
          f"{name}: joining space has no reading stream")


def check_structural_invariants(name, annotations, printed_text, reading_text):
    """Invariants 7–8, including independent printed-character accounting."""
    if annotations["pcl"] == "1.2":
        check_stream_joins(name, annotations, printed_text)
    mapping = annotations["reading_map"]
    for heading in annotations.get("headings", []):
        start, end = heading["start"], heading["end"]
        check("\n" not in reading_text[start:end], f"{name}: heading has an internal newline")
        for offset in (start - 1, end):
            if 0 <= offset < len(reading_text):
                check(reading_text[offset] == "\n" and "derived" in mapping[offset],
                      f"{name}: heading does not stand alone")
    printed_lines = printed_text.split("\n")[:-1]
    glyphs = {(g["line"], g["column"]): g for g in annotations["glyphs"]}
    gaps = {(g["line"], g["column"]): g for g in annotations["gaps"]}
    removals = {w.get("from", w["line"] - 1) for w in annotations["wraps"]
                if w["hyphen"] == "remove"}
    blocks = annotations.get("float_spans", [])
    expected_boundaries = {}
    for block in blocks:
        start, end = block["start"], block["end"]
        if start:
            expected_boundaries[start - 1] = ("float", block["start_line"])
        if end < len(reading_text):
            next_block = next((b for b in blocks if b["start"] == end + 1), None)
            next_heading = next((h for h in annotations["headings"] if h["start"] == end + 1), None)
            expected_boundaries[end] = (("float", next_block["start_line"]) if next_block else
                                        ("heading", next_heading["start_line"]) if next_heading else
                                        ("float", block["end_line"]))
            check(end + 1 < len(reading_text) and reading_text[end + 1] != "\n",
                  f"{name}: float has a trailing or doubled boundary")
        source_lines = set(range(block["start_line"], block["end_line"] + 1))
        expected = Counter()
        for number in source_lines:
            text = printed_lines[number - 1]
            for column, char in enumerate(text):
                if number in removals and column == len(text) - 1 and char in ("-", "‐"):
                    continue
                glyph = glyphs.get((number, column))
                chars = ([] if glyph["as"] == "none" else [chr(int(cp[2:], 16)) for cp in glyph["as"]]) if glyph else [char]
                expected.update((number, column, ch) for ch in chars)
        actual = Counter()
        for entry in mapping:
            if entry.get("line") not in source_lines:
                continue
            if "column" in entry:
                check(start <= entry["offset"] < end, f"{name}: float character leaked into prose")
                actual[(entry["line"], entry["column"], entry["char"])] += 1
        for (number, column), gap in gaps.items():
            if number in source_lines:
                check(start <= gap["reading_offset"] < end, f"{name}: float gap leaked into prose")
                actual[(number, column, " ")] += 1
        check(actual == expected, f"{name}: float characters were lost or duplicated")
        for entry in mapping[start:end]:
            if "column" in entry:
                check(entry["line"] in source_lines, f"{name}: prose character leaked into float")
        for wrap in annotations["wraps"]:
            origin = wrap.get("from", wrap["line"] - 1)
            check((origin in source_lines) == (wrap["line"] in source_lines),
                  f"{name}: wrap joins separate float spans or prose")
    for offset, (reason, line) in expected_boundaries.items():
        check(mapping[offset].get("derived") == reason and mapping[offset].get("line") == line
              and reading_text[offset] == "\n", f"{name}: incorrect float boundary at {offset}")
    actual_float = {entry["offset"] for entry in mapping if entry.get("derived") == "float"}
    check(actual_float == {offset for offset, (reason, _) in expected_boundaries.items() if reason == "float"},
          f"{name}: stray or missing float newline")


def run_positive(directory):
    name = os.path.basename(directory)
    relative = os.path.relpath(os.path.join(directory, "input.pcl"), ROOT)
    text = read_bytes(os.path.join(directory, "input.pcl")).decode("utf-8")
    expected_printed = read_bytes(os.path.join(directory, "expected.printed"))
    expected_reading = read_bytes(os.path.join(directory, "expected.reading"))
    with open(
        os.path.join(directory, "expected.annotations.json"), encoding="utf-8"
    ) as handle:
        expected_annotations = json.load(handle)

    result = run_cli("printed", relative)
    check(result.returncode == 0, f"{name}: printed exited {result.returncode}")
    check(result.stdout == expected_printed, f"{name}: printed view differs")

    result = run_cli("reading", relative)
    check(result.returncode == 0, f"{name}: reading exited {result.returncode}")
    check(result.stdout == expected_reading, f"{name}: reading view differs")

    result = run_cli("annotations", relative)
    check(result.returncode == 0, f"{name}: annotations exited {result.returncode}")
    annotations = json.loads(result.stdout.decode("utf-8"))
    check(result.stdout == (json.dumps(expected_annotations, ensure_ascii=False, indent=2) + "\n").encode("utf-8"),
          f"{name}: annotations are not canonical")

    result = run_cli("validate", relative)
    check(result.returncode == 0, f"{name}: validate exited {result.returncode}")

    document = pcl.parse(text, relative)
    check(pcl.serialize(document) == text, f"{name}: round trip differs")
    check(
        pcl.serialize(document).encode("utf-8")
        == read_bytes(os.path.join(directory, "input.pcl")),
        f"{name}: round trip is not byte for byte",
    )
    check(
        pcl.strip_instructions(text) == expected_printed.decode("utf-8"),
        f"{name}: stripping instructions does not give the printed view",
    )
    reading_text = expected_reading.decode("utf-8")
    printed_text = expected_printed.decode("utf-8")
    check_annotations(name, annotations, printed_text, reading_text)
    check_structural_invariants(name, annotations, printed_text, reading_text)
    for raw in INSTRUCTION.findall(text):
        check(
            raw not in printed_text and raw not in reading_text,
            f"{name}: instruction text leaked into a view: {raw!r}",
        )
    return name


def run_negative(directory):
    name = os.path.basename(directory)
    relative = os.path.relpath(os.path.join(directory, "input.pcl"), ROOT)
    with open(os.path.join(directory, "expected.stderr"), encoding="utf-8") as handle:
        expected = handle.read()
    result = run_cli("validate", relative)
    check(result.returncode == 1, f"{name}: expected exit 1, got {result.returncode}")
    check(result.stdout == b"", f"{name}: expected empty stdout")
    wanted = f"pcl: {relative}:{expected}".encode("utf-8")
    check(
        result.stderr == wanted,
        f"{name}: error differs\n  expected: {wanted.decode()!r}\n"
        f"  actual:   {result.stderr.decode()!r}",
    )
    message = expected.strip().split(": ", 2)[-1]
    return name, message


def main():
    failures = []
    positives = []
    negatives = []

    for entry in sorted(os.listdir(CASE_DIR)):
        directory = os.path.join(CASE_DIR, entry)
        if not os.path.isdir(directory):
            continue
        try:
            positives.append(run_positive(directory))
            print(f"PASS case {entry}")
        except Failure as error:
            failures.append(str(error))
            print(f"FAIL case {entry}: {error}")

    for entry in sorted(os.listdir(NEG_DIR)):
        directory = os.path.join(NEG_DIR, entry)
        if not os.path.isdir(directory):
            continue
        try:
            name, message = run_negative(directory)
            negatives.append((name, message))
            print(f"PASS negative {entry}: {message}")
        except Failure as error:
            failures.append(str(error))
            print(f"FAIL negative {entry}: {error}")

    print()
    print(
        f"positive cases: {len(positives)} passed, "
        f"negative cases: {len(negatives)} passed"
    )
    if failures:
        print(f"failures: {len(failures)}")
        for failure in failures:
            print(f"  - {failure}")
        return 1
    print("all checks passed")
    return 0


if __name__ == "__main__":
    sys.exit(main())
