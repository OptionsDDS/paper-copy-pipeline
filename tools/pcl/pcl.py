#!/usr/bin/env python3
"""PCL 1.2 reference parser and command line tool.

Paper Copy Language encodes a printed paper line by line.  Instructions live
inside the delimiter pair U+27E6 / U+27E7; everything else is printed text.
This module parses PCL, validates it, and produces the PRINTED view, the
READING view and the ANNOTATIONS document.  Standard library only.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
import unicodedata
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Sequence, Tuple, Union

PCL_VERSION = "1.2"
PCL_VERSION_CHAIN = ("1.0", "1.1", "1.2")
OPEN = "\u27e6"
CLOSE = "\u27e7"
HYPHENS = ("\u002d", "\u2010")
SPAN_NAMES = ("italic", "bold", "sup", "sub", "furniture", "heading", "float")
NOTATION_NAMES = ("sup", "sub")

_HEX = re.compile(r"^U\+([0-9A-F]{4,6})$")
_NUM = re.compile(r"^[1-9][0-9]*$")
_ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:/-]*$")
_RULE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]*/[0-9]+\.[0-9]+$")
_SHA256 = re.compile(r"^[0-9a-f]{64}$")
_USES = re.compile(
    r"^[A-Za-z0-9][A-Za-z0-9._-]*/[0-9]+\.[0-9]+"
    r"(?:,[A-Za-z0-9][A-Za-z0-9._-]*/[0-9]+\.[0-9]+)*$"
)
_VERSION = re.compile(r"^([0-9]+)\.([0-9]+)$")
_GAP = re.compile(r"^[+-]?[0-9]+(?:\.[0-9]+)?$")


class PclError(Exception):
    """A PCL parse or validation error carrying a source offset."""

    def __init__(self, message: str, offset: Optional[int] = None) -> None:
        super().__init__(message)
        self.message = message
        self.offset = offset


@dataclass
class Text:
    text: str
    offset: int

    @property
    def raw(self) -> str:
        return self.text


@dataclass
class Break:
    offset: int

    @property
    def raw(self) -> str:
        return "\n"


@dataclass
class Instr:
    name: str
    offset: int
    raw: str
    args: Dict[str, object] = field(default_factory=dict)


Token = Union[Text, Break, Instr]


@dataclass
class Line:
    ordinal: int
    page: int
    page_instr: Optional[Instr]
    line_instr: Instr
    wrap: Optional[Instr]
    para: Optional[Instr]
    tokens: List[Token]


@dataclass
class Document:
    header: Instr
    lines: List[Line]


def _parse_uint(token: str, what: str, offset: int) -> int:
    if not _NUM.match(token):
        raise PclError(
            f"invalid {what} number {token!r} (expected a positive integer "
            "without leading zeros)",
            offset,
        )
    return int(token)


def _parse_codepoint(
    token: str, what: str, offset: int, allow_control: bool = False
) -> int:
    match = _HEX.match(token)
    if not match:
        raise PclError(
            f"invalid code point {token!r} for {what} "
            "(expected uppercase U+XXXX with 4 to 6 hex digits)",
            offset,
        )
    codepoint = int(match.group(1), 16)
    if 0xD800 <= codepoint <= 0xDFFF or codepoint > 0x10FFFF:
        raise PclError(f"code point {token} is not a Unicode scalar value", offset)
    if not allow_control and (codepoint < 0x20 or 0x7F <= codepoint <= 0x9F):
        raise PclError(
            f"code point {token} is a control character; control characters "
            "may appear only as the printed side of a glyph command",
            offset,
        )
    return codepoint


def _parse_id(token: str, what: str, offset: int) -> str:
    if not _ID.match(token):
        raise PclError(
            f"invalid {what} {token!r} (expected letters, digits or . _ : / -)",
            offset,
        )
    return token


def _parse_header(rest: Sequence[str], offset: int) -> Dict[str, object]:
    if not rest or not _VERSION.match(rest[0]):
        raise PclError(
            "header requires a version after paper-copy, as in "
            f"⟦paper-copy {PCL_VERSION} source=<sha256> uses=<rule/version,...>⟧",
            offset,
        )
    version = rest[0]
    major, minor = _VERSION.match(version).groups()
    if major != "1":
        raise PclError(
            f"unsupported PCL major version {version!r} (this parser "
            f"implements {PCL_VERSION}; a breaking change bumps the major "
            "version)",
            offset,
        )
    if int(minor) > 1 and version != "1.2":
        raise PclError(
            f"unsupported PCL version {version!r} (this parser implements "
            f"{', '.join(PCL_VERSION_CHAIN)})",
            offset,
        )
    if len(rest) != 3:
        raise PclError(
            "header requires exactly 'source=<sha256>' and "
            "'uses=<rule/version,...>' after the version",
            offset,
        )
    if not rest[1].startswith("source="):
        raise PclError(
            f"invalid header argument {rest[1]!r} (expected source=<sha256>)",
            offset,
        )
    digest = rest[1][len("source="):]
    if not _SHA256.match(digest):
        raise PclError(
            f"invalid source digest {digest!r} (expected 64 lowercase hex "
            "digits, the sha256 of the source PDF)",
            offset,
        )
    if not rest[2].startswith("uses="):
        raise PclError(
            f"invalid header argument {rest[2]!r} (expected "
            "uses=<rule/version,...>)",
            offset,
        )
    uses = rest[2][len("uses="):]
    if not _USES.match(uses):
        raise PclError(
            f"invalid uses list {uses!r} (expected comma separated "
            "name/version items)",
            offset,
        )
    if version == "1.2" and "pcl/1.2" not in uses.split(","):
        raise PclError("a paper-copy 1.2 file must list pcl/1.2 in uses=", offset)
    return {"version": version, "source": digest, "uses": uses.split(",")}


def parse_instruction(content: str, offset: int, raw: str,
                      version: str = "1.1") -> Instr:
    if content == "":
        raise PclError("empty instruction", offset)
    if "\n" in content or "\r" in content:
        raise PclError("instruction must not contain a line break", offset)
    for ch in content:
        if ch != " " and ch.isspace():
            raise PclError(
                "only spaces may separate instruction arguments", offset
            )
    if OPEN in content:
        raise PclError(
            f"unexpected {OPEN!r} inside an instruction "
            "(instructions do not nest; write a literal ⟦ as ⟦char U+27E6⟧)",
            offset + 1 + content.index(OPEN),
        )
    parts = [part for part in content.split(" ") if part]
    if not parts:
        raise PclError("empty instruction", offset)
    name = parts[0]
    rest = parts[1:]

    if name == "paper-copy":
        return Instr(name, offset, raw, _parse_header(rest, offset))

    if name in ("page", "line"):
        if len(rest) != 1:
            raise PclError(
                f"command {name!r} requires exactly one positive integer "
                "argument",
                offset,
            )
        return Instr(name, offset, raw, {"n": _parse_uint(rest[0], name, offset)})

    if name == "para":
        if rest:
            raise PclError("command 'para' takes no arguments", offset)
        return Instr(name, offset, raw, {})

    if name.lstrip("/") == "furniture" and version == "1.0":
        raise PclError("command 'furniture' requires paper-copy 1.1 (declared 1.0)", offset)

    if name.lstrip("/") in ("heading", "float") and version != "1.2":
        raise PclError(f"command {name.lstrip('/')!r} requires paper-copy 1.2", offset)

    if name == "wrap":
        has_from = any(arg.startswith("from=") for arg in rest)
        if has_from and version != "1.2":
            raise PclError("wrap argument 'from=' requires paper-copy 1.2", offset)
        if version == "1.2" and len(rest) not in (4, 5):
            raise PclError(
                "command 'wrap' requires four or five arguments: "
                "N [from=M] hyphen=keep|remove|none "
                "basis=witness|rule|review|lexicon|corpus ref=<id>", offset)
        if version != "1.2" and len(rest) != 4:
            raise PclError(
                "command 'wrap' requires exactly four arguments: "
                "N hyphen=keep|remove|none basis=witness|rule|review|lexicon|corpus "
                "ref=<id>",
                offset,
            )
        number = _parse_uint(rest[0], "wrap line", offset)
        origin = {}
        if len(rest) == 5:
            if not rest[1].startswith("from="):
                raise PclError(f"invalid wrap argument {rest[1]!r} (expected from=)", offset)
            value = rest[1][5:]
            # Zero names no printed line; diagnose it with the existence check.
            origin["from"] = 0 if value == "0" else _parse_uint(value, "from line", offset)
            rest = [rest[0], *rest[2:]]
        keys = ("hyphen", "basis", "ref")
        values: Dict[str, str] = {}
        for index, token in enumerate(rest[1:]):
            if "=" not in token:
                raise PclError(
                    f"invalid wrap argument {token!r} (expected "
                    "hyphen=, basis= and ref= in that order)",
                    offset,
                )
            key, value = token.split("=", 1)
            if key != keys[index]:
                raise PclError(
                    f"invalid wrap argument {token!r} (expected "
                    f"{keys[index]}=)",
                    offset,
                )
            values[key] = value
        hyphen = values["hyphen"]
        if hyphen not in ("keep", "remove", "none"):
            raise PclError(
                f"invalid value {hyphen!r} for 'hyphen' "
                "(expected keep, remove or none)",
                offset,
            )
        basis = values["basis"]
        if basis not in ("witness", "rule", "review", "lexicon", "corpus"):
            raise PclError(
                f"invalid value {basis!r} for 'basis' "
                "(expected witness, rule, review, lexicon or corpus)",
                offset,
            )
        ref = _parse_id(values["ref"], "ref", offset)
        return Instr(
            name,
            offset,
            raw,
            {"n": number, **origin, "hyphen": hyphen, "basis": basis, "ref": ref},
        )

    if name == "glyph":
        if len(rest) not in (3, 4):
            raise PclError(
                "command 'glyph' requires U+XXXX as=U+YYYY[,U+YYYY...] "
                "rule=<name/version>, or U+XXXX as=none rule=<name/version> "
                "gap=<em>",
                offset,
            )
        printed = _parse_codepoint(rest[0], "glyph", offset, allow_control=True)
        if not rest[2].startswith("rule="):
            raise PclError(
                f"invalid glyph argument {rest[2]!r} "
                "(expected rule=<name/version>)",
                offset,
            )
        rule = rest[2][len("rule="):]
        if not _RULE.match(rule):
            raise PclError(
                f"invalid rule {rule!r} (expected <name>/<version>)", offset
            )
        if not rest[1].startswith("as="):
            raise PclError(
                f"invalid glyph argument {rest[1]!r} (expected as=U+YYYY, a "
                "comma separated list of code points when one printed glyph "
                "becomes several reading characters, or as=none)",
                offset,
            )
        as_value = rest[1][len("as="):]
        reading: Optional[List[int]] = None
        gap: Optional[str] = None
        if as_value == "none":
            if len(rest) != 4 or not rest[3].startswith("gap="):
                raise PclError(
                    "glyph 'as=none' requires a 'gap=<em>' or 'gap=edge' "
                    "argument, as in ⟦glyph U+XXXX as=none "
                    "rule=<name/version> gap=-0.009⟧",
                    offset,
                )
            category = unicodedata.category(chr(printed))
            if category not in ("Zs", "Cc", "Cf"):
                raise PclError(
                    "glyph as=none is only allowed for whitespace or control "
                    "code points (Unicode categories Zs, Cc, Cf); "
                    f"{_codepoint_label(printed)} has category {category}",
                    offset,
                )
            gap = rest[3][len("gap="):]
            if gap == "edge":
                if version == "1.0":
                    raise PclError("glyph argument 'gap=edge' requires paper-copy 1.1 (declared 1.0)", offset)
            elif not _GAP.match(gap):
                raise PclError(
                    f"invalid gap {gap!r} (expected a decimal number of em "
                    "or 'edge' for a glyph at a line edge)",
                    offset,
                )
        else:
            as_tokens = as_value.split(",")
            if not as_tokens or any(token == "" for token in as_tokens):
                raise PclError(
                    "glyph 'as=' must list at least one code point, or be "
                    "'none'",
                    offset,
                )
            reading = [
                _parse_codepoint(token, "glyph 'as='", offset)
                for token in as_tokens
            ]
            if len(rest) == 4:
                if rest[3].startswith("gap="):
                    raise PclError(
                        "glyph 'gap=' is only allowed together with 'as=none'",
                        offset,
                    )
                raise PclError(
                    f"invalid glyph argument {rest[3]!r} (expected nothing "
                    "after rule=, or gap=<em> with as=none)",
                    offset,
                )
        if reading is not None and unicodedata.category(chr(printed)) in (
            "Zs",
            "Cc",
            "Cf",
        ):
            for value in reading:
                if unicodedata.category(chr(value)) != "Zs":
                    raise PclError(
                        f"glyph printed code point {_codepoint_label(printed)} "
                        "is whitespace or control; its as= substitution must "
                        "be whitespace (Zs) or as=none, not "
                        f"{chr(value)!r} ({_codepoint_label(value)})",
                        offset,
                    )
        return Instr(
            name,
            offset,
            raw,
            {"printed": printed, "as": reading, "gap": gap, "rule": rule},
        )

    if name == "gap":
        if rest:
            raise PclError("command 'gap' takes no arguments", offset)
        return Instr(name, offset, raw, {})

    if name == "char":
        if len(rest) != 1:
            raise PclError(
                "command 'char' requires exactly one argument: U+XXXX", offset
            )
        return Instr(
            name, offset, raw, {"cp": _parse_codepoint(rest[0], "char", offset)}
        )

    if name in ("table", "figure"):
        if len(rest) != 1:
            raise PclError(
                f"command {name!r} requires exactly one argument: ID", offset
            )
        return Instr(
            name, offset, raw, {"id": _parse_id(rest[0], name, offset)}
        )

    if name in ("heading", "float"):
        keys = ("level", "basis", "ref") if name == "heading" else ("id", "kind", "basis", "ref")
        form = ("level=L|? basis=map|review|rule ref=<id>" if name == "heading"
                else "id=<id> kind=table|figure|caption|note basis=map ref=<id>")
        if len(rest) != len(keys):
            count = "three" if name == "heading" else "four"
            raise PclError(f"command {name!r} requires exactly {count} arguments: {form}", offset)
        values = {}
        for key, arg in zip(keys, rest):
            if not arg.startswith(key + "="):
                raise PclError(f"invalid {name} argument {arg!r} (expected {key}=)", offset)
            values[key] = arg[len(key) + 1:]
        if name == "heading":
            level = values["level"]
            if level != "?" and not _NUM.fullmatch(level):
                raise PclError("heading level must be a positive integer or '?'", offset)
            values["level"] = None if level == "?" else int(level)
            allowed, expected = ("map", "review", "rule"), "map, review or rule"
        else:
            values["id"] = _parse_id(values["id"], "float id", offset)
            if values["kind"] not in ("table", "figure", "caption", "note"):
                raise PclError(f"invalid float kind {values['kind']!r} "
                               "(expected table, figure, caption or note)", offset)
            allowed, expected = ("map",), "map"
        if values["basis"] not in allowed:
            raise PclError(f"invalid value {values['basis']!r} for 'basis' (expected {expected})", offset)
        values["ref"] = _parse_id(values["ref"], "ref", offset)
        return Instr(name, offset, raw, values)

    if name in SPAN_NAMES:
        if rest:
            raise PclError(f"command {name!r} takes no arguments", offset)
        return Instr(name, offset, raw, {})

    if name.startswith("/"):
        if name[1:] in SPAN_NAMES:
            if rest:
                raise PclError(f"command {name!r} takes no arguments", offset)
            return Instr(name, offset, raw, {})
        raise PclError(f"unknown command {name!r}", offset)

    raise PclError(f"unknown command {name!r}", offset)


def scan(text: str) -> List[Token]:
    tokens: List[Token] = []
    index = 0
    length = len(text)
    version = "1.1"
    while index < length:
        ch = text[index]
        if ch == OPEN:
            end = text.find(CLOSE, index + 1)
            if end == -1:
                raise PclError(
                    "unterminated instruction: the ⟦ is never closed "
                    "(write a literal ⟦ as ⟦char U+27E6⟧)",
                    index,
                )
            raw = text[index:end + 1]
            instruction = parse_instruction(text[index + 1:end], index, raw, version)
            tokens.append(instruction)
            if instruction.name == "paper-copy":
                version = str(instruction.args["version"])
            index = end + 1
        elif ch == CLOSE:
            raise PclError(
                "unescaped ⟧ (write a literal ⟧ as ⟦char U+27E7⟧)", index
            )
        elif ch == "\r":
            raise PclError(
                "carriage return is not allowed; PCL 1.0 uses LF line breaks",
                index,
            )
        elif ch == "\n":
            tokens.append(Break(index))
            index += 1
        else:
            end = index
            while end < length:
                current = text[end]
                if current in (OPEN, CLOSE, "\n", "\r"):
                    break
                if unicodedata.category(current) == "Cc":
                    raise PclError(
                        f"literal control character {_codepoint_label(ord(current))} "
                        "is not allowed; control characters may appear only as "
                        "the printed side of a glyph command",
                        end,
                    )
                end += 1
            tokens.append(Text(text[index:end], index))
            index = end
    return tokens


def _render(line: Line) -> str:
    out: List[str] = []
    for token in line.tokens:
        if isinstance(token, Text):
            out.append(token.text)
        elif token.name == "char":
            out.append(chr(int(token.args["cp"])))
        elif token.name == "glyph":
            out.append(chr(int(token.args["printed"])))
        elif token.name == "gap":
            out.append(" ")
    return "".join(out)


def _effective_last_char(line: Line) -> str:
    for token in reversed(line.tokens):
        if isinstance(token, Text):
            return token.text[-1]
        if token.name == "char":
            return chr(int(token.args["cp"]))
        if token.name == "glyph":
            if token.args.get("gap") == "edge":
                continue
            return chr(int(token.args["printed"]))
        if token.name == "gap":
            return " "
    return ""


def _check_edge_gaps(lines: Sequence[Line]) -> None:
    for line in lines:
        content = [
            (index, token)
            for index, token in enumerate(line.tokens)
            if isinstance(token, Text)
            or (isinstance(token, Instr) and token.name in ("char", "glyph", "gap"))
        ]
        core = [
            index
            for index, token in content
            if not (
                isinstance(token, Instr)
                and token.name == "glyph"
                and token.args.get("gap") == "edge"
            )
        ]
        low = core[0] if core else None
        high = core[-1] if core else None
        for index, token in content:
            if not (
                isinstance(token, Instr)
                and token.name == "glyph"
                and token.args.get("gap") == "edge"
            ):
                continue
            if low is None or index < low or index > high:
                continue
            raise PclError(
                "glyph 'gap=edge' is only allowed at the first or last "
                "position of a printed line",
                token.offset,
            )


def _check_spans(lines: Sequence[Line]) -> None:
    flat = [token for line in lines for token in line.tokens]
    stack: List[Tuple[str, int, int]] = []
    for index, token in enumerate(flat):
        if not isinstance(token, Instr):
            continue
        if token.name in SPAN_NAMES:
            stack.append((token.name, token.offset, index))
        elif token.name.startswith("/"):
            name = token.name[1:]
            if not stack:
                raise PclError(
                    f"span {token.name!r} has no matching ⟦{name}⟧",
                    token.offset,
                )
            top = stack[-1]
            if top[0] != name:
                raise PclError(
                    f"span {token.name!r} would overlap the open span "
                    f"{top[0]!r} (spans must nest, not overlap)",
                    token.offset,
                )
            if index - top[2] == 1:
                raise PclError(
                    f"empty span {top[0]!r}: ⟦{top[0]}⟧ is immediately "
                    f"followed by ⟦/{top[0]}⟧, but a span must contain "
                    "something",
                    top[1],
                )
            stack.pop()
    if stack:
        name, offset, _ = stack[0]
        raise PclError(
            f"unclosed span {name!r} (close it with ⟦/{name}⟧)", offset
        )


def _check_gaps(lines: Sequence[Line]) -> None:
    for line in lines:
        rendered = _render(line)
        tokens = line.tokens
        column = 0
        for index, token in enumerate(tokens):
            if isinstance(token, Text):
                column += len(token.text)
                continue
            if token.name in ("char", "glyph"):
                column += 1
                continue
            if token.name != "gap":
                continue
            if column == 0:
                raise PclError(
                    "⟦gap⟧ may not be the first content of a printed line "
                    "(the line break already reads as a space)",
                    token.offset,
                )
            if column + 1 == len(rendered):
                raise PclError(
                    "⟦gap⟧ may not be the last content of a printed line "
                    "(the line break already reads as a space)",
                    token.offset,
                )
            if rendered[column - 1] == " ":
                previous = tokens[index - 1] if index > 0 else None
                if isinstance(previous, Instr) and previous.name == "gap":
                    raise PclError(
                        "⟦gap⟧ may not be adjacent to another ⟦gap⟧",
                        token.offset,
                    )
                raise PclError(
                    "⟦gap⟧ may not be adjacent to a printed space",
                    token.offset,
                )
            if column + 1 < len(rendered) and rendered[column + 1] == " ":
                following = tokens[index + 1] if index + 1 < len(tokens) else None
                if isinstance(following, Instr) and following.name == "gap":
                    raise PclError(
                        "⟦gap⟧ may not be adjacent to another ⟦gap⟧",
                        token.offset,
                    )
                raise PclError(
                    "⟦gap⟧ may not be adjacent to a printed space",
                    token.offset,
                )
            column += 1


def parse(text: str, filename: str = "<pcl>") -> Document:
    tokens = scan(text)
    segments: List[List[Token]] = []
    current: List[Token] = []
    for token in tokens:
        if isinstance(token, Break):
            segments.append(current)
            current = []
        else:
            current.append(token)
    if current:
        raise PclError(
            "file must end with a newline (LF)", current[-1].offset
        )
    if not segments:
        raise PclError("empty file: missing header", 0)

    first = segments[0]
    if not first or not isinstance(first[0], Instr) or first[0].name != "paper-copy":
        if first and isinstance(first[0], Instr):
            raise PclError(
                "missing header: the first instruction must be "
                f"⟦paper-copy {PCL_VERSION} source=<sha256> "
                "uses=<rule/version,...>⟧, found "
                f"⟦{first[0].name}⟧",
                first[0].offset,
            )
        raise PclError(
            "missing header: the file must begin with "
            f"⟦paper-copy {PCL_VERSION} source=<sha256> "
            "uses=<rule/version,...>⟧",
            first[0].offset if first else 0,
        )
    header = first[0]
    if len(segments) == 1 and len(first) == 1:
        return Document(header, [])

    lines: List[Line] = []
    page_number = 0
    for ordinal, segment in enumerate(segments, start=1):
        index = 1 if ordinal == 1 else 0
        page_instr: Optional[Instr] = None
        line_instr: Optional[Instr] = None
        wrap: Optional[Instr] = None
        para: Optional[Instr] = None

        if index < len(segment):
            token = segment[index]
            if isinstance(token, Instr) and token.name == "page":
                page_instr = token
                index += 1

        if (
            index >= len(segment)
            or not isinstance(segment[index], Instr)
            or segment[index].name != "line"
        ):
            offset = (
                segment[index].offset
                if index < len(segment)
                else (segment[-1].offset if segment else header.offset)
            )
            raise PclError(
                f"printed line {ordinal} must start with ⟦line {ordinal}⟧",
                offset,
            )
        line_instr = segment[index]
        index += 1

        if index < len(segment):
            token = segment[index]
            if isinstance(token, Instr) and token.name == "wrap":
                wrap = token
                index += 1
            elif isinstance(token, Instr) and token.name == "para":
                para = token
                index += 1

        content: List[Token] = []
        for token in segment[index:]:
            if isinstance(token, Instr):
                if token.name == "page":
                    raise PclError(
                        "⟦page …⟧ may appear only at the start of a printed "
                        "line, before ⟦line …⟧",
                        token.offset,
                    )
                if token.name == "line":
                    raise PclError(
                        "a printed line may contain only one ⟦line …⟧ "
                        "instruction",
                        token.offset,
                    )
                if token.name == "wrap":
                    raise PclError(
                        "⟦wrap …⟧ must be the first instruction after "
                        "⟦line …⟧",
                        token.offset,
                    )
                if token.name == "para" and header.args["version"] == "1.2":
                    content.append(token)
                    continue
                if token.name == "para":
                    if wrap is not None:
                        raise PclError(
                            "a printed line cannot both continue a word "
                            "(wrap) and begin a paragraph (para)",
                            token.offset,
                        )
                    raise PclError(
                        "⟦para⟧ must be the first instruction after "
                        "⟦line …⟧, or immediately before the text it starts",
                        token.offset,
                    )
                if token.name == "paper-copy":
                    raise PclError(
                        "header may appear only once, at the start of the file",
                        token.offset,
                    )
            content.append(token)

        if int(line_instr.args["n"]) != ordinal:
            raise PclError(
                f"line number {line_instr.args['n']} out of sequence on "
                f"printed line {ordinal} (expected {ordinal})",
                line_instr.offset,
            )

        if page_instr is not None:
            page_number += 1
            if int(page_instr.args["n"]) != page_number:
                raise PclError(
                    f"page number {page_instr.args['n']} out of sequence on "
                    f"printed line {ordinal} (expected {page_number})",
                    page_instr.offset,
                )
        elif ordinal == 1:
            raise PclError(
                "missing ⟦page 1⟧ before the first printed line", header.offset
            )

        lines.append(
            Line(ordinal, page_number, page_instr, line_instr, wrap, para, content)
        )

    if header.args["version"] == "1.2":
        _check_language12(lines)
        _check_spans(lines)
        _check_gaps(lines)
        _check_edge_gaps(lines)
        return Document(header, lines)

    rendered = [_render(line) for line in lines]
    for line in lines:
        if line.wrap is None:
            continue
        args = line.wrap.args
        ordinal = line.ordinal
        if ordinal == 1:
            raise PclError(
                "⟦wrap …⟧ may not appear on printed line 1", line.wrap.offset
            )
        if int(args["n"]) != ordinal:
            raise PclError(
                f"wrap refers to line {args['n']} but appears on printed line "
                f"{ordinal}",
                line.wrap.offset,
            )
        previous = rendered[ordinal - 2]
        last = _effective_last_char(lines[ordinal - 2])
        if previous == "" or last == "":
            raise PclError(
                f"wrap on printed line {ordinal}: previous printed line is "
                "empty",
                line.wrap.offset,
            )
        if args["hyphen"] in ("keep", "remove") and last not in HYPHENS:
            raise PclError(
                f"wrap on printed line {ordinal}: hyphen={args['hyphen']} but "
                f"the previous printed line ends with {last!r}, not a hyphen",
                line.wrap.offset,
            )
        if args["hyphen"] == "none" and last in HYPHENS:
            raise PclError(
                f"wrap on printed line {ordinal}: hyphen=none but the previous "
                "printed line ends with a hyphen",
                line.wrap.offset,
            )

    _check_spans(lines)
    _check_gaps(lines)
    _check_edge_gaps(lines)
    return Document(header, lines)


def render_lines(document: Document) -> List[str]:
    return [_render(line) for line in document.lines]


def printed(document: Document) -> str:
    return "".join(text + "\n" for text in render_lines(document))


def strip_instructions(text: str) -> str:
    out: List[str] = []
    index = 0
    while index < len(text):
        if text[index] == OPEN:
            end = text.find(CLOSE, index + 1)
            if end == -1:
                break
            body = text[index + 1:end]
            parts = [part for part in body.split(" ") if part]
            if parts and parts[0] == "char" and len(parts) == 2:
                out.append(chr(int(parts[1][2:], 16)))
            elif parts and parts[0] == "glyph" and len(parts) >= 2:
                out.append(chr(int(parts[1][2:], 16)))
            elif parts and parts[0] == "gap":
                out.append(" ")
            index = end + 1
        else:
            out.append(text[index])
            index += 1
    result = "".join(out)
    if OPEN + "line " not in text and result.endswith("\n"):
        result = result[:-1]
    return result


def serialize(document: Document) -> str:
    if not document.lines:
        return document.header.raw + "\n"
    out: List[str] = [document.header.raw]
    for line in document.lines:
        if line.page_instr is not None:
            out.append(line.page_instr.raw)
        out.append(line.line_instr.raw)
        if line.wrap is not None:
            out.append(line.wrap.raw)
        if line.para is not None:
            out.append(line.para.raw)
        for token in line.tokens:
            out.append(token.raw)
        out.append("\n")
    return "".join(out)


def _codepoint_label(value: int) -> str:
    return "U+%04X" % value


@dataclass
class Analysis:
    text: str
    annotations: Dict[str, object]


def analyse(document: Document) -> Analysis:
    if document.header.args["version"] == "1.2":
        return _analyse12(document)
    return _analyse_legacy(document)


def _analyse_legacy(document: Document) -> Analysis:
    reading: List[str] = []
    mapping: List[Dict[str, object]] = []
    spans: List[Dict[str, object]] = []
    wraps: List[Dict[str, object]] = []
    glyphs: List[Dict[str, object]] = []
    floats: List[Dict[str, object]] = []
    paras: List[Dict[str, object]] = []
    gaps: List[Dict[str, object]] = []
    line_records: List[Dict[str, object]] = []
    furniture_records: List[Dict[str, object]] = []
    stack: List[Dict[str, object]] = []
    rendered = render_lines(document)

    furniture_only: List[bool] = []
    for line in document.lines:
        depth = 0
        only = bool(line.tokens)
        for token in line.tokens:
            if not isinstance(token, Instr):
                if depth == 0:
                    only = False
                continue
            if token.name == "furniture":
                depth += 1
            elif token.name == "/furniture":
                depth -= 1
            elif depth == 0:
                only = False
        furniture_only.append(only)

    furniture_depth = 0
    furniture_start_offset = 0
    furniture_start_line = 0
    furniture_text: List[str] = []

    printed_offset = 0
    for index, line in enumerate(document.lines):
        ordinal = line.ordinal
        printed_text = rendered[index]
        reading_start = len(reading)

        if index > 0:
            if line.wrap is not None:
                args = line.wrap.args
                record: Dict[str, object] = {
                    "line": ordinal,
                    "hyphen": args["hyphen"],
                    "basis": args["basis"],
                    "ref": args["ref"],
                    "reading_offset": len(reading),
                }
                if args["hyphen"] in ("keep", "remove"):
                    entry = mapping[-1] if mapping else None
                    if (
                        entry is None
                        or "derived" in entry
                        or reading[-1] != _effective_last_char(document.lines[index - 1])
                    ):
                        raise PclError(
                            f"wrap hyphen={args['hyphen']}: the previous printed line's "
                            "hyphen is not its last reading character (it is "
                            "inside a notation span or substituted by a "
                            "glyph), which cannot be represented",
                            line.wrap.offset,
                        )
                if args["hyphen"] == "remove":
                    removed_printed = _effective_last_char(
                        document.lines[index - 1]
                    )
                    removed_reading = reading.pop()
                    mapping.pop()
                    line_records[-1]["reading_end"] = len(reading)
                    reading_start = len(reading)
                    record["reading_offset"] = len(reading)
                    record["removed"] = _codepoint_label(ord(removed_printed))
                    record["removed_reading"] = removed_reading
                wraps.append(record)
            elif (
                line.para is None
                and not furniture_only[index]
                and any(not flag for flag in furniture_only[:index])
            ):
                mapping.append(
                    {
                        "offset": len(reading),
                        "char": " ",
                        "derived": "line-break",
                        "after_line": ordinal - 1,
                    }
                )
                reading.append(" ")

        if line.para is not None:
            offset = len(reading)
            reading.append("\n")
            mapping.append(
                {
                    "offset": offset,
                    "char": "\n",
                    "derived": "para",
                    "line": ordinal,
                }
            )
            paras.append({"line": ordinal, "reading_offset": offset})

        column = 0
        for token in line.tokens:
            if isinstance(token, Instr) and token.name == "furniture":
                if furniture_depth == 0:
                    furniture_start_offset = len(reading)
                    furniture_start_line = ordinal
                    furniture_text = []
                furniture_depth += 1
                continue
            if isinstance(token, Instr) and token.name == "/furniture":
                furniture_depth -= 1
                if furniture_depth == 0:
                    furniture_records.append(
                        {
                            "start_line": furniture_start_line,
                            "end_line": ordinal,
                            "reading_offset": furniture_start_offset,
                            "printed_text": "".join(furniture_text),
                        }
                    )
                    spans.append(
                        {
                            "name": "furniture",
                            "start": furniture_start_offset,
                            "end": furniture_start_offset,
                            "start_line": furniture_start_line,
                            "end_line": ordinal,
                        }
                    )
                continue
            if furniture_depth > 0:
                if isinstance(token, Text):
                    furniture_text.append(token.text)
                    column += len(token.text)
                elif token.name == "char":
                    furniture_text.append(chr(int(token.args["cp"])))
                    column += 1
                elif token.name == "glyph":
                    furniture_text.append(chr(int(token.args["printed"])))
                    column += 1
                elif token.name == "gap":
                    furniture_text.append(" ")
                    column += 1
                continue
            if isinstance(token, Text):
                for ch in token.text:
                    mapping.append(
                        {
                            "offset": len(reading),
                            "char": ch,
                            "line": ordinal,
                            "column": column,
                        }
                    )
                    reading.append(ch)
                    column += 1
            elif token.name == "char":
                ch = chr(int(token.args["cp"]))
                mapping.append(
                    {
                        "offset": len(reading),
                        "char": ch,
                        "line": ordinal,
                        "column": column,
                    }
                )
                reading.append(ch)
                column += 1
            elif token.name == "glyph":
                glyph_offset = len(reading)
                label = _codepoint_label(int(token.args["printed"]))
                if token.args["as"] is None:
                    glyphs.append(
                        {
                            "line": ordinal,
                            "column": column,
                            "printed": label,
                            "as": "none",
                            "gap": token.args["gap"],
                            "rule": token.args["rule"],
                            "reading_start": glyph_offset,
                            "reading_end": glyph_offset,
                        }
                    )
                else:
                    for value in token.args["as"]:
                        ch = chr(int(value))
                        mapping.append(
                            {
                                "offset": len(reading),
                                "char": ch,
                                "line": ordinal,
                                "column": column,
                                "substituted": label,
                            }
                        )
                        reading.append(ch)
                    glyphs.append(
                        {
                            "line": ordinal,
                            "column": column,
                            "printed": label,
                            "as": [
                                _codepoint_label(int(v)) for v in token.args["as"]
                            ],
                            "rule": token.args["rule"],
                            "reading_start": glyph_offset,
                            "reading_end": len(reading),
                        }
                    )
                column += 1
            elif token.name == "gap":
                offset = len(reading)
                mapping.append(
                    {
                        "offset": offset,
                        "char": " ",
                        "derived": "gap",
                        "line": ordinal,
                    }
                )
                reading.append(" ")
                gaps.append(
                    {
                        "line": ordinal,
                        "column": column,
                        "reading_offset": offset,
                    }
                )
                column += 1
            elif token.name in SPAN_NAMES:
                start = len(reading)
                if token.name in ("sup", "sub"):
                    marker = "^" if token.name == "sup" else "_"
                    for ch in (marker, "{"):
                        mapping.append(
                            {
                                "offset": len(reading),
                                "char": ch,
                                "derived": f"{token.name}-open",
                                "line": ordinal,
                            }
                        )
                        reading.append(ch)
                    start = len(reading)
                stack.append(
                    {"name": token.name, "start": start, "line": ordinal}
                )
            elif token.name.startswith("/"):
                opened = stack.pop()
                end = len(reading)
                if opened["name"] in ("sup", "sub"):
                    mapping.append(
                        {
                            "offset": len(reading),
                            "char": "}",
                            "derived": f"{opened['name']}-close",
                            "line": ordinal,
                        }
                    )
                    reading.append("}")
                spans.append(
                    {
                        "name": opened["name"],
                        "start": opened["start"],
                        "end": end,
                        "start_line": opened["line"],
                        "end_line": ordinal,
                    }
                )
            elif token.name in ("table", "figure"):
                floats.append(
                    {
                        "kind": token.name,
                        "id": token.args["id"],
                        "line": ordinal,
                        "reading_offset": len(reading),
                    }
                )

        line_records.append(
            {
                "line": ordinal,
                "page": line.page,
                "printed_start": printed_offset,
                "printed_end": printed_offset + len(printed_text),
                "reading_start": reading_start,
                "reading_end": len(reading),
                "furniture": furniture_only[index],
            }
        )
        printed_offset += len(printed_text) + 1

    pages: List[Dict[str, object]] = []
    for record in line_records:
        if not pages or pages[-1]["page"] != record["page"]:
            pages.append(
                {
                    "page": record["page"],
                    "first_line": record["line"],
                    "last_line": record["line"],
                }
            )
        else:
            pages[-1]["last_line"] = record["line"]

    annotations: Dict[str, object] = {
        "pcl": document.header.args["version"],
        "header": {
            "version": document.header.args["version"],
            "source": document.header.args["source"],
            "uses": document.header.args["uses"],
        },
        "pages": pages,
        "lines": line_records,
        "spans": spans,
        "wraps": wraps,
        "glyphs": glyphs,
        "floats": floats,
        "paras": paras,
        "gaps": gaps,
        "furniture": furniture_records,
        "reading_map": mapping,
    }
    return Analysis("".join(reading), annotations)


def _layout12(lines: Sequence[Line]) -> List[dict]:
    """Check structural constraints and identify each line's reading stream."""
    stack = []
    layout = []
    for line in lines:
        n = line.ordinal
        info = {"heading": None, "float": None, "prose": False,
                "first_stream": None, "last_stream": None, "furniture": False}
        for opened in stack:
            if opened.name in ("heading", "float"):
                info[opened.name] = opened
        for index, token in enumerate(line.tokens):
            if isinstance(token, Instr) and token.name in SPAN_NAMES:
                name = token.name
                names = [t.name for t in stack]
                if "heading" in names and name in ("heading", "float", "furniture"):
                    raise PclError(f"heading on printed line {n} may not overlap {name!r}", token.offset)
                if "float" in names and name in ("heading", "float", "furniture"):
                    raise PclError(f"float on printed line {n} may not contain {name!r}", token.offset)
                if name == "heading" and "furniture" in names:
                    raise PclError(f"heading on printed line {n} may not overlap 'furniture'", token.offset)
                if name == "float" and "furniture" in names:
                    raise PclError(f"float on printed line {n} may not contain 'furniture'", token.offset)
                if name in ("heading", "float"):
                    info[name] = token
                    if name == "heading" and line.wrap:
                        raise PclError(f"wrap on printed line {n} may not join across a heading boundary", line.wrap.offset)
                    if name == "heading" and line.para:
                        raise PclError(f"printed line {n} may not begin a paragraph next to a heading", line.para.offset)
                    if name == "float" and line.para:
                        raise PclError(f"float on printed line {n} may not contain 'para'", line.para.offset)
                    if index != 0:
                        raise PclError(f"{name} on printed line {n} must open at the start of the line", token.offset)
                stack.append(token)
            elif isinstance(token, Instr) and token.name.startswith("/"):
                if not stack or stack[-1].name != token.name[1:]:
                    _check_spans(lines)  # retain the existing exact nesting errors
                name = stack.pop().name
                if name in ("heading", "float") and index != len(line.tokens) - 1:
                    raise PclError(f"{name} closing on printed line {n} must close at the end of the line", token.offset)
            elif isinstance(token, Instr) and token.name == "para":
                structural = next((t.name for t in stack if t.name in ("heading", "float")), None)
                if structural:
                    raise PclError(f"{structural} on printed line {n} may not contain 'para'", token.offset)
                if line.wrap:
                    raise PclError("a printed line cannot both continue a word (wrap) and begin a paragraph (para)", token.offset)
                raise PclError("⟦para⟧ must be the first instruction after ⟦line …⟧, or immediately before the text it starts", token.offset)
            if isinstance(token, Text) or (isinstance(token, Instr) and token.name in ("char", "glyph", "gap")):
                furniture = any(t.name == "furniture" for t in stack)
                floating = next((t for t in stack if t.name == "float"), None)
                stream = ("furniture",) if furniture else ("float", floating.offset) if floating else ("prose",)
                if info["first_stream"] is None:
                    info["first_stream"] = stream
                info["last_stream"] = stream
                info["furniture"] |= furniture
                info["prose"] |= stream == ("prose",)
        if line.para:
            structural = "heading" if info["heading"] else "float" if info["float"] else None
            if structural:
                raise PclError(f"{structural} on printed line {n} may not contain 'para'", line.para.offset)
            info["prose"] = True
        layout.append(info)
    return layout


def _check_language12(lines: Sequence[Line]) -> None:
    layout = _layout12(lines)
    _check_spans(lines)
    for index, line in enumerate(lines):
        n = line.ordinal
        prior_heading = layout[index - 1]["heading"] if index else None
        heading = layout[index]["heading"]
        next_to_heading = prior_heading is not heading and (prior_heading or heading)
        if next_to_heading and line.para:
            raise PclError(f"printed line {n} may not begin a paragraph next to a heading", line.para.offset)
        wrap = line.wrap
        if wrap is None:
            continue
        args = wrap.args
        if n == 1:
            raise PclError("⟦wrap …⟧ may not appear on printed line 1", wrap.offset)
        if args["n"] != n:
            raise PclError(f"wrap refers to line {args['n']} but appears on printed line {n}", wrap.offset)
        m = int(args.get("from", n - 1))
        prefix = f"wrap on printed line {n}: "
        if "from" in args:
            if m >= n:
                raise PclError(prefix + f"from={m} must be less than {n}", wrap.offset)
            if m == n - 1:
                raise PclError(prefix + f"from={m} names the previous printed line; omit from=", wrap.offset)
            if not 1 <= m <= len(lines):
                raise PclError(prefix + f"from={m} but no printed line {m} exists", wrap.offset)
            for skipped in range(m + 1, n):
                if layout[skipped - 1]["prose"]:
                    raise PclError(prefix + f"from={m} but printed line {skipped} contributes reading text", wrap.offset)
        if next_to_heading or layout[m - 1]["heading"] is not heading:
            raise PclError(f"wrap on printed line {n} may not join across a heading boundary", wrap.offset)
        origin_stream = layout[m - 1]["last_stream"]
        target_stream = layout[index]["first_stream"]
        if origin_stream != target_stream or origin_stream in (None, ("furniture",)):
            detail = f"from={m} joins different reading streams" if "from" in args else "the previous printed line is in a different reading stream"
            raise PclError(prefix + detail, wrap.offset)
        last = _effective_last_char(lines[m - 1])
        subject = f"printed line {m}" if "from" in args else "the previous printed line"
        if last == "":
            raise PclError(prefix + (f"printed line {m} is empty" if "from" in args else "previous printed line is empty"), wrap.offset)
        if args["hyphen"] in ("keep", "remove") and last not in HYPHENS:
            raise PclError(prefix + f"hyphen={args['hyphen']} but {subject} ends with {last!r}, not a hyphen", wrap.offset)
        if args["hyphen"] == "none" and last in HYPHENS:
            raise PclError(prefix + f"hyphen=none but {subject} ends with a hyphen", wrap.offset)


def _analyse12(document: Document) -> Analysis:
    """Render line-local content, then place prose and float blocks.

    Annotation endpoints are mutable line-local anchors. Resolving them only
    after placement keeps glyph, notation and line offsets tied to the actual
    reading order, including a deferred block and a removed wrap hyphen.
    """
    lines = document.lines
    layout = _layout12(lines)
    chunks = [[] for _ in lines]
    anchors = [[] for _ in lines]
    collections = {key: [] for key in ("spans", "wraps", "glyphs", "floats", "paras", "gaps", "furniture", "headings", "float_spans")}
    stack = []
    blocks = []
    heading_records = {}

    def anchor(i):
        point = [i, len(chunks[i])]
        anchors[i].append(point)
        return point

    def emit(i, char, **fields):
        chunks[i].append({"char": char, **fields})

    def derived(i, text, reason):
        for char in text:
            emit(i, char, derived=reason, line=lines[i].ordinal)

    for i, line in enumerate(lines):
        column = 0
        for token in line.tokens:
            name = token.name if isinstance(token, Instr) else None
            hidden = any(record["name"] == "furniture" for record in stack)
            if name in SPAN_NAMES:
                if name in NOTATION_NAMES and not hidden:
                    derived(i, "^{" if name == "sup" else "_{", name + "-open")
                record = {"name": name, "start": anchor(i), "start_line": line.ordinal,
                          "token": token, "hidden": hidden, "printed": []}
                stack.append(record)
                if name == "float":
                    blocks.append(record)
                continue
            if name and name.startswith("/"):
                record = stack.pop()
                record["end"] = anchor(i)
                record["end_line"] = line.ordinal
                span_name = record["name"]
                if not record["hidden"]:
                    public = {key: record[key] for key in ("name", "start", "end", "start_line", "end_line")}
                    if span_name == "furniture":
                        public["end"] = public["start"]
                        collections["furniture"].append({"start_line": record["start_line"], "end_line": line.ordinal,
                            "reading_offset": record["start"], "printed_text": "".join(record["printed"])})
                    collections["spans"].append(public)
                    if span_name in ("heading", "float"):
                        extra = {**record["token"].args, **{key: public[key] for key in ("start", "end", "start_line", "end_line")}}
                        collections["headings" if span_name == "heading" else "float_spans"].append(extra)
                        if span_name == "heading":
                            heading_records[id(record["token"])] = extra
                    if span_name in NOTATION_NAMES:
                        derived(i, "}", span_name + "-close")
                continue
            printed_text = (token.text if isinstance(token, Text) else chr(int(token.args["cp"])) if name == "char"
                            else chr(int(token.args["printed"])) if name == "glyph" else " " if name == "gap" else "")
            for record in stack:
                if record["name"] == "furniture":
                    record["printed"].append(printed_text)
            if hidden:
                column += len(printed_text)
                continue
            if isinstance(token, Text) or name == "char":
                for char in printed_text:
                    emit(i, char, line=line.ordinal, column=column)
                    column += 1
            elif name == "glyph":
                args = token.args
                start = anchor(i)
                label = _codepoint_label(int(args["printed"]))
                for cp in args["as"] or []:
                    emit(i, chr(cp), line=line.ordinal, column=column, substituted=label)
                record = {"line": line.ordinal, "column": column, "printed": label,
                          "as": "none" if args["as"] is None else [_codepoint_label(cp) for cp in args["as"]],
                          "rule": args["rule"], "reading_start": start, "reading_end": anchor(i)}
                if args["as"] is None:
                    record["gap"] = args["gap"]
                collections["glyphs"].append(record)
                column += 1
            elif name == "gap":
                collections["gaps"].append({"line": line.ordinal, "column": column, "reading_offset": anchor(i)})
                derived(i, " ", "gap")
                column += 1
            elif name in ("table", "figure"):
                collections["floats"].append({"kind": name, "id": token.args["id"], "line": line.ordinal, "reading_offset": anchor(i)})
        for record in stack:
            if record["name"] == "furniture":
                record["printed"].append("\n")

    claimed = {}
    skipped_breaks = {}
    for i, line in enumerate(lines):
        if not line.wrap:
            continue
        args = line.wrap.args
        m = int(args.get("from", line.ordinal - 1))
        claimed[m] = line.ordinal
        stream = layout[i]["first_stream"]
        skipped_breaks.setdefault(stream, set()).update(range(m, i))
        record = {"line": line.ordinal, **{key: args[key] for key in ("hyphen", "basis", "ref")},
                  "reading_offset": [i, 0]}
        if "from" in args:
            record["from"] = m
        if args["hyphen"] in ("keep", "remove"):
            chunk = chunks[m - 1]
            if not chunk or "derived" in chunk[-1] or chunk[-1]["char"] != _effective_last_char(lines[m - 1]):
                raise PclError(f"wrap hyphen={args['hyphen']}: the previous printed line's hyphen is not its last reading character (it is inside a notation span or substituted by a glyph), which cannot be represented", line.wrap.offset)
        if args["hyphen"] == "remove":
            record["removed"] = _codepoint_label(ord(_effective_last_char(lines[m - 1])))
            record["removed_reading"] = chunk.pop()["char"]
            for point in anchors[m - 1]:
                point[1] = min(point[1], len(chunk))
        collections["wraps"].append(record)

    # Every page uses an anchor, including pages without prose. Defer until
    # neither a wrap nor a continuing heading claims that prose line's end.
    prose = [i for i, info in enumerate(layout) if info["prose"]]
    placements = {}
    for block in blocks:
        first = block["start_line"] - 1
        page = lines[first].page
        candidates = [i for i in prose if lines[i].page == page]
        site = candidates[-1] if candidates else max((i for i in prose if lines[i].page < page), default=-1)
        if site >= 0:
            for candidate in prose:
                if candidate < site or candidate + 1 in claimed:
                    continue
                heading = layout[candidate]["heading"]
                if heading and heading_records[id(heading)]["end_line"] > candidate + 1:
                    continue
                site = candidate
                break
        placements.setdefault(site, []).append(block)

    mapping = []
    bases = {}
    ranges = {}
    def boundary(reason, line_number=None, after_line=None):
        entry = {"char": " " if reason == "line-break" else "\n", "derived": reason}
        entry["after_line" if after_line is not None else "line"] = after_line if after_line is not None else line_number
        mapping.append(entry)

    def place(i, start=None):
        if start is None:
            start = len(mapping)
        bases[i] = len(mapping)
        mapping.extend(chunks[i])
        ranges[i] = (start, len(mapping))

    def place_blocks(site):
        pending = placements.get(site, [])
        for block in pending:
            first, last = block["start_line"] - 1, block["end_line"] - 1
            stream_breaks = skipped_breaks.get(("float", block["token"].offset), set())
            for i in range(first, last + 1):
                start = len(mapping)
                if i == first:
                    if mapping:
                        boundary("float", lines[first].ordinal)
                elif not lines[i].wrap and i not in stream_breaks:
                    boundary("line-break", after_line=lines[i - 1].ordinal)
                place(i, start)
        return pending[-1] if pending else None

    previous_block = place_blocks(-1)
    previous = None
    for i in prose:
        start = len(mapping)
        current_heading = layout[i]["heading"]
        previous_heading = layout[previous]["heading"] if previous is not None else None
        if previous_block:
            if current_heading and heading_records[id(current_heading)]["start_line"] == lines[i].ordinal:
                boundary("heading", lines[i].ordinal)
            else:
                if lines[i].para:
                    collections["paras"].append({"line": lines[i].ordinal, "reading_offset": len(mapping)})
                boundary("float", previous_block["end_line"])
        elif previous_heading is not current_heading and (current_heading or previous_heading):
            if mapping:
                record = heading_records[id(previous_heading or current_heading)]
                boundary("heading", record["end_line"] if previous_heading else record["start_line"])
        elif lines[i].para:
            collections["paras"].append({"line": lines[i].ordinal, "reading_offset": len(mapping)})
            boundary("para", lines[i].ordinal)
        elif previous is not None and not lines[i].wrap:
            boundary("line-break", after_line=lines[previous].ordinal)
        place(i, start)
        previous_block = place_blocks(i)
        previous = i
    # Omitted lines have zero-length ranges at their position in the prose.
    position = 0
    for i in range(len(lines)):
        if i in bases:
            if not layout[i]["float"]:
                position = ranges[i][1]
        else:
            bases[i] = position
            ranges[i] = (position, position)

    def resolve(value):
        if isinstance(value, list):
            return bases[value[0]] + value[1]
        return value

    for records in collections.values():
        for record in records:
            for key in ("start", "end", "reading_start", "reading_end", "reading_offset"):
                if key in record:
                    record[key] = resolve(record[key])
    for key in ("headings", "float_spans"):
        collections[key].sort(key=lambda record: record["start_line"])
    line_records, pages = [], []
    printed_offset = 0
    for i, line in enumerate(lines):
        size = len(_render(line))
        line_records.append({"line": line.ordinal, "page": line.page, "printed_start": printed_offset,
                             "printed_end": printed_offset + size, "reading_start": ranges[i][0],
                             "reading_end": ranges[i][1], "furniture": layout[i]["furniture"]})
        printed_offset += size + 1
        if not pages or pages[-1]["page"] != line.page:
            pages.append({"page": line.page, "first_line": line.ordinal, "last_line": line.ordinal})
        else:
            pages[-1]["last_line"] = line.ordinal
    for offset, entry in enumerate(mapping):
        entry["offset"] = offset
    return Analysis("".join(entry["char"] for entry in mapping), {
        "pcl": document.header.args["version"], "header": dict(document.header.args),
        "pages": pages, "lines": line_records, **collections, "reading_map": mapping})


def reading(document: Document) -> str:
    return analyse(document).text


def annotations(document: Document) -> Dict[str, object]:
    return analyse(document).annotations


def locate(text: str, offset: Optional[int]) -> Tuple[int, int]:
    if offset is None:
        return 1, 1
    if offset > len(text):
        offset = len(text)
    line = text.count("\n", 0, offset) + 1
    last_newline = text.rfind("\n", 0, offset)
    column = offset - last_newline
    return line, column


def load(path: str) -> str:
    try:
        with open(path, "rb") as handle:
            data = handle.read()
    except OSError as error:
        raise PclError(f"cannot read file: {error}") from None
    try:
        return data.decode("utf-8")
    except UnicodeDecodeError as error:
        raise PclError(
            f"file is not valid UTF-8: {error.reason} at byte {error.start}"
        ) from None


def main(argv: Optional[Sequence[str]] = None) -> int:
    parser = argparse.ArgumentParser(
        prog="pcl",
        description=f"Paper Copy Language {PCL_VERSION} reference parser",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)
    for name in ("validate", "printed", "reading", "annotations"):
        sub = subparsers.add_parser(name)
        sub.add_argument("file")
    args = parser.parse_args(argv)

    text = ""
    try:
        text = load(args.file)
        document = parse(text, args.file)
        if args.command == "validate":
            analyse(document)
            sys.stdout.write(f"{args.file}: OK\n")
        elif args.command == "printed":
            sys.stdout.write(printed(document))
        elif args.command == "reading":
            sys.stdout.write(reading(document))
        else:
            sys.stdout.write(
                json.dumps(annotations(document), ensure_ascii=False, indent=2)
                + "\n"
            )
    except PclError as error:
        line, column = locate(text, error.offset)
        sys.stderr.write(
            f"pcl: {args.file}:{line}:{column}: error: {error.message}\n"
        )
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
