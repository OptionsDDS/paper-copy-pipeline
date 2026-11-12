#!/usr/bin/env python3
# Ported from trials/repair-trial/repair_apply.py (sha256 d514a45ff141819b5f8c042a1ca94cd1f8d206e30abada015cffcf2a9b21ff0a), unchanged.
"""Apply structural repairs to a paper copy using only the Python standard library.

Usage: python3 repair_apply.py PAPER_DIR

Reads copy.orig.md and ops.json; writes copy.md and apply-log.json. Log indices
are zero based, and character ranges are half open [start, end), in Unicode
characters, against the text immediately before/after that operation. Rejected
operations have identical before/after offsets because the copy is unchanged.

An optional integer occurrence selects that 1-based match for EACH anchor.
Short anchors are permitted on lines too short to supply 25 characters.
Existing numbered-list labels are words: none of these operations adds numbering,
so numbering is never discarded. A flag is the sole operation that adds words;
its single-line, page-referenced note is appended to the protected final section.
An end-of-page marker crossed by a join is retained after the joined paragraph,
since deleting its printed words would break the invariant.
"""

from __future__ import annotations

import argparse
from collections import Counter
from dataclasses import dataclass, field
import json
import os
from pathlib import Path
import re
import sys
import tempfile
from typing import Any


UNCERTAINTY_TITLE = "Places the program is not sure of"
PREFIX = re.compile(r"^[ \t]*(?:#{1,6}|>|-)[ \t]+")
BLANK_LINE = re.compile(r"\r?\n[ \t]*\r?\n")
JOIN_PREFIXES = re.compile(r"[ \t]*(?:(?:>|-)[ \t]+)+[ \t]*\Z")
PAGE_REFERENCE = re.compile(r"\b(?:pages?|pp?)\.?\s*(?:\d+[a-z]?|[ivxlcdm]+)\b", re.I)
FIELDS = {
    "move": {"op", "start", "end", "after", "as"},
    "join": {"op", "left", "right"},
    "split": {"op", "text", "at", "as"},
    "markup": {"op", "text", "as"},
    "remove_duplicate": {"op", "start", "end", "occurrence"},
    "flag": {"op", "note"},
}


class Rejected(ValueError):
    """An operation cannot safely be applied."""


def strip_prefixes(line: str) -> str:
    """Remove only supported line prefixes, never punctuation inside a word."""
    while (match := PREFIX.match(line)) is not None:
        line = line[match.end():]
    return line


def word_tokens(text: str) -> Counter[str]:
    """Count maximal non-whitespace runs after permitted Markdown is stripped."""
    normalized = "\n".join(strip_prefixes(line).replace("**", "")
                           for line in text.splitlines())
    return Counter(normalized.split())


def matches(text: str, quote: str) -> list[int]:
    """Include overlapping matches when deciding whether an anchor is unique."""
    found = []
    pos = text.find(quote)
    while pos != -1:
        found.append(pos)
        pos = text.find(quote, pos + 1)
    return found


def section_start(text: str) -> int | None:
    headings = []
    offset = 0
    for line in text.splitlines(keepends=True):
        clean = strip_prefixes(line.rstrip("\r\n")).replace("**", "").strip()
        if clean == UNCERTAINTY_TITLE:
            headings.append(offset)
        offset += len(line)
    if len(headings) > 1:
        raise Rejected("multiple uncertainty sections; cannot identify the protected tail")
    return headings[0] if headings else None


@dataclass
class Context:
    text: str
    operation: dict[str, Any]
    before: dict[str, list[int]] = field(default_factory=dict)

    def anchor(self, name: str) -> tuple[int, int]:
        quote = self.operation[name]
        if not isinstance(quote, str) or not quote.strip():
            raise Rejected(f"{name}: anchor must be a nonempty text string")
        positions = matches(self.text, quote)
        if not positions:
            raise Rejected(f"{name}: anchor is missing")
        occurrence = self.operation.get("occurrence")
        if occurrence is None:
            if len(positions) != 1:
                raise Rejected(f"{name}: anchor is ambiguous ({len(positions)} matches)")
            start = positions[0]
        else:
            if occurrence > len(positions):
                raise Rejected(f"{name}: occurrence {occurrence} does not exist")
            start = positions[occurrence - 1]
        end = start + len(quote)
        self.before[name] = [start, end]
        if len(quote) < 25:
            line_start = self.text.rfind("\n", 0, start) + 1
            line_end = self.text.find("\n", end)
            if line_end == -1:
                line_end = len(self.text)
            if len(self.text[line_start:line_end].strip()) >= 25:
                raise Rejected(f"{name}: anchor must be at least 25 characters on this line")
        return start, end

    def span(self) -> tuple[int, int]:
        start, start_end = self.anchor("start")
        end_start, end = self.anchor("end")
        if end_start < start or end < start_end:
            raise Rejected("malformed span: end is before start or cuts the start anchor")
        self.before["span"] = [start, end]
        return start, end

    def body(self) -> tuple[str, str]:
        start = section_start(self.text)
        return (self.text, "") if start is None else (self.text[:start], self.text[start:])

    def require_body(self, *ranges: tuple[int, int]) -> tuple[str, str]:
        body, tail = self.body()
        if any(start >= len(body) or end > len(body) for start, end in ranges):
            raise Rejected("anchor touches the protected uncertainty section")
        return body, tail


def validate_operation(operation: Any) -> None:
    if not isinstance(operation, dict):
        raise Rejected("operation must be an object")
    name = operation.get("op")
    if not isinstance(name, str) or name not in FIELDS:
        raise Rejected("unknown operation")
    required = FIELDS[name]
    optional = {"occurrence"} if name != "flag" else set()
    missing = required - operation.keys()
    extra = operation.keys() - required - optional
    if missing:
        raise Rejected("missing fields: " + ", ".join(sorted(missing)))
    if extra:
        raise Rejected("unknown fields: " + ", ".join(sorted(extra)))
    if "occurrence" in operation:
        value = operation["occurrence"]
        if type(value) is not int or value < 1:
            raise Rejected("occurrence must be a positive, 1-based integer")
    if name in {"move", "markup"}:
        allowed = ({"paragraph", "inline"} if name == "move" else
                   {"heading2", "heading3", "caption", "paragraph", "list_item"})
        if not isinstance(operation["as"], str) or operation["as"] not in allowed:
            raise Rejected(f"invalid {name} style")
    if name == "split":
        if not isinstance(operation["as"], str) or operation["as"] not in {"paragraph", "line"}:
            raise Rejected("invalid split style")


def paragraph_end(text: str, position: int) -> int:
    """Find the end of the paragraph containing the preceding nonblank text."""
    while position and text[position - 1].isspace():
        position -= 1
    separator = BLANK_LINE.search(text, position)
    return separator.start() if separator else len(text)


def insert_paragraph(text: str, position: int, content: str) -> tuple[str, list[int]]:
    left, right = text[:position], text[position:]
    # Preserve existing whitespace; add only the paragraph boundaries needed.
    lead = "" if not left or re.search(r"\r?\n[ \t]*\r?\n\Z", left) else ("\n" if left.endswith("\n") else "\n\n")
    trail = "" if not right or re.match(r"\r?\n[ \t]*\r?\n", right) else ("\n" if right.startswith("\n") else "\n\n")
    start = len(left) + len(lead)
    return left + lead + content + trail + right, [start, start + len(content)]


def cut_span(text: str, start: int, end: int) -> tuple[str, int, int]:
    """Remove whole standalone lines together with their trailing blank lines."""
    line_start = text.rfind("\n", 0, start) + 1
    line_end = text.find("\n", end)
    if line_end == -1:
        line_end = len(text)
    if not text[line_start:start].strip() and not text[end:line_end].strip():
        start = line_start
        end = min(line_end + 1, len(text))
        while end < len(text):
            next_end = text.find("\n", end)
            if next_end == -1:
                next_end = len(text)
            if text[end:next_end].strip():
                break
            end = min(next_end + 1, len(text))
    return text[:start] + text[end:], start, end


def with_tail(body: str, tail: str) -> str:
    if tail and body and not re.search(r"\r?\n[ \t]*\r?\n\Z", body):
        body += "\n" if body.endswith("\n") else "\n\n"
    return body + tail


def move(ctx: Context) -> tuple[str, dict[str, list[int]], Counter[str]]:
    start, end = ctx.span()
    target_start, target_end = ctx.anchor("after")
    body, tail = ctx.require_body((start, end), (target_start, target_end))
    if max(start, target_start) < min(end, target_end):
        raise Rejected("move destination is inside its own span")
    destination = paragraph_end(body, target_end) if ctx.operation["as"] == "paragraph" else target_end
    if start < destination < end:
        raise Rejected("move destination paragraph ends inside its own span")
    span = body[start:end].strip()
    if not span:
        raise Rejected("move span is empty")
    remainder, cut_start, cut_end = cut_span(body, start, end)
    ctx.before["removed"] = [cut_start, cut_end]
    ctx.before["destination"] = [destination, destination]
    if cut_start < destination < cut_end:
        # A paragraph ending at the source boundary is now the cut point.
        destination = cut_start
    elif destination >= cut_end:
        destination -= cut_end - cut_start
    if ctx.operation["as"] == "paragraph":
        result, placed = insert_paragraph(remainder, destination, span)
    else:
        left, right = remainder[:destination].rstrip(), remainder[destination:]
        placed = [len(left) + 1, len(left) + 1 + len(span)]
        result = left + " " + span + (" " if right and not right[0].isspace() else "") + right
    return with_tail(result, tail), {"span": placed}, Counter()


def is_page_marker(line: str) -> bool:
    clean = strip_prefixes(line).strip()
    wrappers = (("<!--", "-->"), ("[", "]"), ("(", ")"), ("---", "---"), ("===", "==="))
    for opening, closing in wrappers:
        if clean.startswith(opening) and clean.endswith(closing):
            clean = clean[len(opening):-len(closing)].strip()
            break
    return re.fullmatch(r"end\s+of\s+page(?:\s+\d+)?", clean, re.I) is not None


def join(ctx: Context) -> tuple[str, dict[str, list[int]], Counter[str]]:
    left_start, left_end = ctx.anchor("left")
    right_start, right_end = ctx.anchor("right")
    body, tail = ctx.require_body((left_start, left_end), (right_start, right_end))
    if right_start < left_end:
        raise Rejected("join pieces overlap or are in reverse order")
    ctx.before["gap"] = [left_end, right_start]
    gap = body[left_end:right_start]
    markers = []
    offset = left_end
    for fragment in gap.splitlines(keepends=True):
        line = fragment.rstrip("\r\n")
        if line.strip():
            physical_start = body.rfind("\n", 0, offset) + 1
            if body[physical_start:offset].strip():
                raise Rejected("join pieces are not adjacent: intervening text")
            if JOIN_PREFIXES.fullmatch(line):
                pass
            elif is_page_marker(line) and fragment.endswith("\n"):
                markers.append(line)
            else:
                raise Rejected("join pieces are not adjacent: intervening text")
        offset += len(fragment)
    result = body[:left_end] + " " + body[right_start:]
    after = {"left": [left_start, left_end],
             "right": [left_end + 1, left_end + 1 + right_end - right_start],
             "gap": [left_end, left_end + 1]}
    if markers:
        destination = paragraph_end(result, after["right"][1])
        result, after["markers"] = insert_paragraph(result, destination, "\n".join(markers))
    return with_tail(result, tail), after, Counter()


def split(ctx: Context) -> tuple[str, dict[str, list[int]], Counter[str]]:
    start, end = ctx.anchor("text")
    at_start, at_end = ctx.anchor("at")
    ctx.require_body((start, end), (at_start, at_end))
    if not start < at_start < end or at_end > end:
        raise Rejected("split at anchor must be strictly inside the text anchor")
    ctx.before["insertion"] = [at_start, at_start]
    # Words are whitespace-delimited tokens, including their punctuation.
    # The shared invariant also catches Markdown newly exposed by the break.
    if not (ctx.text[at_start - 1].isspace() or ctx.text[at_start].isspace()):
        raise Rejected("split must be at a word boundary, never inside a word")
    separator = "\n\n" if ctx.operation["as"] == "paragraph" else "\n"
    result = ctx.text[:at_start] + separator + ctx.text[at_start:]
    added = len(separator)
    after = {"text": [start, end + added],
             "at": [at_start + added, at_end + added],
             "insertion": [at_start, at_start + added]}
    return result, after, Counter()


def markup(ctx: Context) -> tuple[str, dict[str, list[int]], Counter[str]]:
    start, end = ctx.anchor("text")
    body, tail = ctx.require_body((start, end))
    quote = body[start:end]
    if "\n" in quote or "\r" in quote or (start and body[start - 1] != "\n"):
        raise Rejected("markup anchor must be an exact whole line, without its line ending")
    if end < len(body) and body[end] not in "\r\n":
        raise Rejected("markup anchor must be an exact whole line")
    content = strip_prefixes(quote)
    indent = content[:len(content) - len(content.lstrip(" \t"))]
    content = content[len(indent):]
    trailing = content[len(content.rstrip(" \t")):]
    content = content.rstrip(" \t")
    # Only outer emphasis is changed; internal emphasis and literal punctuation stay.
    while len(content) >= 4 and content.startswith("**") and content.endswith("**"):
        content = strip_prefixes(content[2:-2])
    style = ctx.operation["as"]
    if style == "caption":
        replacement = "**" + content + "**"
    else:
        replacement = {"heading2": "## ", "heading3": "### ", "paragraph": "", "list_item": "- "}[style] + content
    replacement = indent + replacement + trailing
    result = body[:start] + replacement + body[end:]
    return with_tail(result, tail), {"text": [start, start + len(replacement)]}, Counter()


def remove_duplicate(ctx: Context) -> tuple[str, dict[str, list[int]], Counter[str]]:
    start, end = ctx.span()
    body, tail = ctx.require_body((start, end))
    span = body[start:end]
    if len(matches(ctx.text, span)) < 2:
        raise Rejected("remove_duplicate span does not occur at least twice")
    result, cut_start, cut_end = cut_span(body, start, end)
    ctx.before["removed"] = [cut_start, cut_end]
    result = with_tail(result, tail)
    if span not in result:
        raise Rejected("remove_duplicate must leave an exact occurrence of the span")
    removed = word_tokens(span)
    return result, {"removed": [cut_start, cut_start]}, Counter({word: -count for word, count in removed.items()})


def flag(ctx: Context) -> tuple[str, dict[str, list[int]], Counter[str]]:
    note = ctx.operation["note"]
    if (not isinstance(note, str) or not note.strip() or len(note.splitlines()) != 1
            or any(ord(char) < 32 or char in "\x85\u2028\u2029" for char in note)):
        raise Rejected("flag note must be a nonempty single line")
    if not PAGE_REFERENCE.search(note):
        raise Rejected("flag note must include a page reference, such as 'page 3'")
    ctx.before["insertion"] = [len(ctx.text), len(ctx.text)]
    section = section_start(ctx.text)
    if section is None:
        prefix = "" if not ctx.text else ("\n" if ctx.text.endswith("\n") else "\n\n")
        added = prefix + "## " + UNCERTAINTY_TITLE + "\n\n- Checker: " + note + "\n"
    else:
        added = ("" if ctx.text.endswith("\n") else "\n") + "- Checker: " + note + "\n"
    result = ctx.text + added
    # This explicit, generated suffix is the only authorized addition of words.
    return result, {"insertion": [len(ctx.text), len(result)]}, word_tokens(added)


HANDLERS = {"move": move, "join": join, "split": split, "markup": markup,
            "remove_duplicate": remove_duplicate, "flag": flag}


def check_invariant(before: str, after: str, name: str, delta: Counter[str]) -> None:
    expected = word_tokens(before)
    expected.update(delta)
    expected = Counter({word: count for word, count in expected.items() if count})
    actual = word_tokens(after)
    if expected != actual:
        missing = list((expected - actual).elements())[:5]
        added = list((actual - expected).elements())[:5]
        raise Rejected(f"word invariant violated (missing={missing!r}, added={added!r})")
    old_section = section_start(before)
    new_section = section_start(after)
    if name != "flag":
        if old_section is None:
            if new_section is not None:
                raise Rejected("operation creates an uncertainty section instead of a flag")
        elif new_section is None or after[new_section:] != before[old_section:]:
            raise Rejected("protected uncertainty section must remain unchanged at the end")
    elif not after.startswith(before):
        raise Rejected("flags must only append to the copy")
    if new_section is not None and new_section and after[new_section - 1] != "\n":
        raise Rejected("uncertainty section must start on its own line")


def apply_operations(text: str, operations: list[Any]) -> tuple[str, list[dict[str, Any]]]:
    """Apply operations independently, committing only checked candidates."""
    if not isinstance(operations, list):
        raise ValueError("ops must be a list")
    section_start(text)
    log = []
    for index, operation in enumerate(operations):
        ctx = Context(text, operation)
        name = operation.get("op") if isinstance(operation, dict) else None
        entry = {"index": index, "op": name, "status": "rejected", "reason": "",
                 "before": ctx.before, "after": {}}
        try:
            validate_operation(operation)
            candidate, offsets, delta = HANDLERS[name](ctx)
            check_invariant(text, candidate, name, delta)
        except Rejected as error:
            entry["reason"] = str(error)
            entry["after"] = dict(ctx.before)
        else:
            text = candidate
            entry.update(status="accepted", reason="applied", after=offsets)
        log.append(entry)
    return text, log


def read_utf8(path: Path) -> str:
    with path.open("r", encoding="utf-8", newline="") as stream:
        return stream.read()


def write_outputs(directory: Path, copy: str, report: dict[str, Any]) -> None:
    """Stage both outputs locally before replacing either destination."""
    staged = []
    try:
        for filename, content in (("copy.md", copy),
                                  ("apply-log.json", json.dumps(report, ensure_ascii=False, indent=2) + "\n")):
            with tempfile.NamedTemporaryFile(mode="w", encoding="utf-8", newline="",
                                             dir=directory, prefix=".repair-", delete=False) as stream:
                staged.append((Path(stream.name), directory / filename))
                stream.write(content)
            # Fail before either replacement when the requested output is a directory.
            if (directory / filename).is_dir():
                raise OSError(f"output is a directory: {directory / filename}")
        for temporary, destination in staged:
            os.replace(temporary, destination)
    finally:
        for temporary, _ in staged:
            temporary.unlink(missing_ok=True)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n", 1)[0])
    parser.add_argument("paper_dir", type=Path, metavar="PAPER_DIR")
    args = parser.parse_args(argv)
    try:
        original = read_utf8(args.paper_dir / "copy.orig.md")
        document = json.loads(read_utf8(args.paper_dir / "ops.json"))
        if not isinstance(document, dict) or not isinstance(document.get("paper"), str):
            raise ValueError("ops.json must be an object with a string 'paper' and an 'ops' list")
        if not isinstance(document.get("ops"), list):
            raise ValueError("ops.json 'ops' must be a list")
        result, entries = apply_operations(original, document["ops"])
        report = {"paper": document["paper"], "offsets": "zero-based, half-open Unicode character ranges",
                  "ops": entries}
        write_outputs(args.paper_dir, result, report)
    except (OSError, UnicodeError, ValueError) as error:
        print(f"repair_apply: {error}", file=sys.stderr)
        return 1
    accepted = sum(entry["status"] == "accepted" for entry in entries)
    print(f"Applied {accepted} operation(s); rejected {len(entries) - accepted}. "
          f"Wrote {args.paper_dir / 'copy.md'} and {args.paper_dir / 'apply-log.json'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
