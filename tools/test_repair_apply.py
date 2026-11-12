"""Behavior and CLI tests of the safe applier (tools/checkstage/repair_apply.py).

Ported unchanged from trials/repair-trial/tests/test_repair_apply.py (sha256 069d9f89...);
only the module path and the temporary folders (now under TMPDIR) differ."""

from collections import Counter
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parent / "checkstage"
sys.path.insert(0, str(ROOT))
import repair_apply as repair


A = "The first sentence contains all its original words."
B = "The second sentence contains another set of words."
C = "Figure one describes the original measured result."
D = "The final sentence closes this printed paragraph."
TAIL = "## Places the program is not sure of\n\n- Page 7: the original uncertain reading.\n"


class OperationTests(unittest.TestCase):
    def apply_one(self, text, operation):
        result, log = repair.apply_operations(text, [operation])
        self.assertEqual(len(log), 1)
        entry = log[0]
        self.assertEqual(entry["index"], 0)
        self.assertEqual(entry["op"], operation.get("op"))
        self.assertTrue(entry["reason"])
        self.assertIn("before", entry)
        self.assertIn("after", entry)
        return result, entry

    def accepted(self, text, operation, expected=None, same_words=True):
        result, entry = self.apply_one(text, operation)
        self.assertEqual(entry["status"], "accepted", entry["reason"])
        if expected is not None:
            self.assertEqual(result, expected)
        if same_words:
            self.assertEqual(repair.word_tokens(text), repair.word_tokens(result))
        return result, entry

    def rejected(self, text, operation, reason):
        result, entry = self.apply_one(text, operation)
        self.assertEqual(entry["status"], "rejected")
        self.assertIn(reason, entry["reason"])
        self.assertEqual(result, text)
        self.assertEqual(entry["before"], entry["after"])
        return entry

    def test_move_paragraph_forward_after_whole_paragraph(self):
        original = C + "\n\n" + A + "\n" + B + "\n\n" + D
        self.accepted(original, {"op": "move", "start": C, "end": C, "after": A, "as": "paragraph"},
                      A + "\n" + B + "\n\n" + C + "\n\n" + D)

    def test_move_paragraph_backward(self):
        original = A + "\n\n" + B + "\n\n" + C + "\n\n" + D
        self.accepted(original, {"op": "move", "start": C, "end": C, "after": A, "as": "paragraph"},
                      A + "\n\n" + C + "\n\n" + B + "\n\n" + D)

    def test_move_inline_both_directions(self):
        for original in (C + "\n\n" + A + "\n\n" + B, A + "\n\n" + C + "\n\n" + B):
            with self.subTest(original=original):
                result, entry = self.accepted(original, {"op": "move", "start": C, "end": C,
                                                         "after": A, "as": "inline"},
                                                  A + " " + C + "\n\n" + B)
                start, end = entry["after"]["span"]
                self.assertEqual(result[start:end], C)

    def test_move_multiline_span(self):
        original = C + "\n" + D + "\n\n" + A + "\n\n" + B
        self.accepted(original, {"op": "move", "start": C, "end": D, "after": A, "as": "paragraph"},
                      A + "\n\n" + C + "\n" + D + "\n\n" + B)

    def test_move_out_of_same_paragraph(self):
        original = A + " " + C + "\n\n" + B
        result, _ = self.accepted(original, {"op": "move", "start": C, "end": C,
                                            "after": A, "as": "paragraph"})
        self.assertIn(A + " \n\n" + C, result)

    def test_move_rejects_destination_in_span(self):
        original = A + "\n" + B + "\n" + C
        self.rejected(original, {"op": "move", "start": A, "end": C, "after": B, "as": "inline"},
                      "inside its own span")

    def test_move_rejects_destination_paragraph_ending_in_span(self):
        original = A + " " + B + "\n\n" + C + "\n\n" + D
        self.rejected(original, {"op": "move", "start": B, "end": C, "after": A, "as": "paragraph"},
                      "paragraph ends inside")

    def test_move_rejects_reverse_span(self):
        self.rejected(A + "\n\n" + B + "\n\n" + C,
                      {"op": "move", "start": B, "end": A, "after": C, "as": "paragraph"},
                      "malformed span")

    def test_move_rejects_missing_anchor(self):
        self.rejected(A + "\n\n" + B, {"op": "move", "start": C, "end": C, "after": A, "as": "inline"},
                      "anchor is missing")

    def test_move_rejects_word_fragment(self):
        word = "abcdefghijklmnopqrstuvwxyz0123456789"
        self.rejected("prefix" + word + "suffix\n\n" + A,
                      {"op": "move", "start": word, "end": word, "after": A, "as": "inline"},
                      "word invariant")

    def test_join_whitespace_and_prefixes(self):
        for gap in ("\n\n", "\n> ", "\n- ", "\n> - ", "\n> \n> ", "\t  "):
            with self.subTest(gap=gap):
                self.accepted(A + gap + B, {"op": "join", "left": A, "right": B}, A + " " + B)

    def test_join_keeps_line_end_hyphen(self):
        left = "The printed sentence ends with this hyphen-"
        self.accepted(left + "\n" + B, {"op": "join", "left": left, "right": B}, left + " " + B)

    def test_join_page_marker_preserves_words_and_suffix(self):
        for marker in ("end of page", "<!-- end of page 4 -->", "[End of page 4]", "--- end of page ---"):
            with self.subTest(marker=marker):
                original = A + "\n" + marker + "\n" + B + " " + D + "\n\n" + TAIL
                result, entry = self.accepted(original, {"op": "join", "left": A, "right": B})
                self.assertIn(A + " " + B + " " + D + "\n\n" + marker, result)
                self.assertTrue(result.endswith(TAIL))
                start, end = entry["after"]["markers"]
                self.assertEqual(result[start:end], marker)

    def test_join_rejects_nonadjacent_pieces(self):
        self.rejected(A + "\n\n" + C + "\n\n" + B,
                      {"op": "join", "left": A, "right": B}, "not adjacent")

    def test_join_rejects_inline_punctuation_as_prefix(self):
        self.rejected(A + " - " + B, {"op": "join", "left": A, "right": B}, "not adjacent")

    def test_join_rejects_unrecognized_marker(self):
        self.rejected(A + "\n<!-- important original words -->\n" + B,
                      {"op": "join", "left": A, "right": B}, "not adjacent")

    def test_join_rejects_reversed_and_overlapping_anchors(self):
        self.rejected(A + "\n" + B, {"op": "join", "left": B, "right": A}, "reverse order")
        self.rejected(A, {"op": "join", "left": A, "right": A}, "overlap")

    def test_join_rejects_splitting_one_word(self):
        left, right = "a" * 25, "b" * 25
        self.rejected(left + right, {"op": "join", "left": left, "right": right}, "word invariant")

    def test_split_styles_preserve_every_existing_character_and_log_offsets(self):
        quote = A + " \t  " + B
        original = "Café λ\r\n\r\n" + quote + "\r\n\r\n" + TAIL
        for style, separator in (("line", "\n"), ("paragraph", "\n\n")):
            with self.subTest(style=style):
                point = original.index(B)
                result, entry = self.accepted(
                    original, {"op": "split", "text": quote, "at": B, "as": style},
                    original[:point] + separator + original[point:])
                self.assertEqual(entry["before"]["insertion"], [point, point])
                self.assertEqual(entry["after"]["insertion"], [point, point + len(separator)])
                for name, expected in (("text", quote), ("at", B)):
                    start, end = entry["before"][name]
                    self.assertEqual(original[start:end], expected)
                for name, expected in (("text", A + " \t  " + separator + B), ("at", B)):
                    start, end = entry["after"][name]
                    self.assertEqual(result[start:end], expected)
                self.assertTrue(result.endswith(TAIL))

    def test_split_short_line_and_whitespace_boundary(self):
        for at, expected in (("Beta", "Alpha \nBeta"), (" Beta", "Alpha\n Beta")):
            with self.subTest(at=at):
                self.accepted("Alpha Beta", {"op": "split", "text": "Alpha Beta", "at": at, "as": "line"},
                              expected)

    def test_split_rejects_inside_word_including_punctuation_and_unicode(self):
        for left, right in (("alpha", "beta"), ("alpha-", "beta"), ("café", "λambda"),
                            ("cafe", "\u0301"), ("alpha", "**beta**")):
            with self.subTest(left=left, right=right):
                original = left + right
                self.rejected(original, {"op": "split", "text": original, "at": right, "as": "line"},
                              "word boundary")

    def test_split_rejects_at_outside_or_crossing_text(self):
        original = A + " " + B + " " + C
        for quote, at in ((A, B), (A + " " + B, B + " " + C)):
            with self.subTest(quote=quote, at=at):
                self.rejected(original, {"op": "split", "text": quote, "at": at, "as": "paragraph"},
                              "inside the text anchor")

    def test_split_rejects_at_start_of_text(self):
        self.rejected(A + " " + B, {"op": "split", "text": A + " " + B, "at": A, "as": "line"},
                      "strictly inside")

    def test_split_rejects_missing_text_or_at(self):
        for quote, at in ((C, B), (A + " " + B, C)):
            with self.subTest(quote=quote, at=at):
                self.rejected(A + " " + B, {"op": "split", "text": quote, "at": at, "as": "line"},
                              "anchor is missing")

    def test_split_rejects_ambiguous_text_or_at(self):
        quote = A + " " + B
        self.rejected(quote + "\n\n" + quote,
                      {"op": "split", "text": quote, "at": B, "as": "line"}, "text: anchor is ambiguous")
        self.rejected(A + " " + B + " " + B,
                      {"op": "split", "text": A + " " + B + " " + B, "at": B, "as": "line"},
                      "at: anchor is ambiguous")

    def test_split_occurrence_selects_repeated_anchors(self):
        quote = A + " " + B
        original = quote + "\n\n" + quote
        for occurrence in (1, 2):
            with self.subTest(occurrence=occurrence):
                copies = [quote, quote]
                copies[occurrence - 1] = A + " \n" + B
                self.accepted(original, {"op": "split", "text": quote, "at": B, "as": "line",
                                         "occurrence": occurrence}, "\n\n".join(copies))

    def test_split_rejects_invalid_occurrence(self):
        quote = A + " " + B
        for occurrence in (0, -1, True, None, 1.5, "1", 2):
            with self.subTest(occurrence=occurrence):
                self.rejected(quote, {"op": "split", "text": quote, "at": B, "as": "line",
                                      "occurrence": occurrence}, "occurrence")

    def test_split_rejects_short_anchors_on_long_lines(self):
        original = "Title " + B
        self.rejected(original, {"op": "split", "text": "Title", "at": B, "as": "line"}, "at least 25")
        self.rejected(original, {"op": "split", "text": original, "at": "The second", "as": "line"},
                      "at least 25")

    def test_split_validates_fields_styles_and_anchor_types(self):
        quote = A + " " + B
        operation = {"op": "split", "text": quote, "at": B, "as": "line"}
        for key in ("text", "at", "as"):
            with self.subTest(missing=key):
                self.rejected(quote, {name: value for name, value in operation.items() if name != key},
                              "missing fields")
        for style in ("inline", "heading2", "", None, []):
            with self.subTest(style=style):
                self.rejected(quote, {**operation, "as": style}, "invalid split style")
        for key in ("text", "at"):
            for value in ("", " \t", None, 7, []):
                with self.subTest(key=key, value=value):
                    self.rejected(quote, {**operation, key: value}, "nonempty text string")
        self.rejected(quote, {**operation, "replacement": C}, "unknown fields")

    def test_split_protects_uncertainty_section(self):
        heading = "## " + repair.UNCERTAINTY_TITLE
        item = "- Page 7: the original uncertain reading."
        for quote, at in ((TAIL, item), (A + "\n\n" + TAIL, heading)):
            with self.subTest(quote=quote):
                self.rejected(A + "\n\n" + TAIL,
                              {"op": "split", "text": quote, "at": at, "as": "line"}, "protected uncertainty")

    def test_split_rejects_word_changes_from_new_markdown_prefix(self):
        for prefix in ("# ", "> ", "- "):
            with self.subTest(prefix=prefix):
                at = prefix + B
                original = A + " " + at
                self.rejected(original, {"op": "split", "text": original, "at": at, "as": "paragraph"},
                              "word invariant")

    def test_split_rejects_creation_of_uncertainty_section(self):
        at = repair.UNCERTAINTY_TITLE
        original = A + " " + at
        self.rejected(original, {"op": "split", "text": original, "at": at, "as": "line"},
                      "creates an uncertainty section")

    def test_split_then_move_both_halves_into_column_blocks(self):
        left = "The left column begins with this original heading."
        right = "The right column begins with this original heading."
        original = left + "\n\n" + right + "\n\n" + A + " " + B + "\n" + C + " " + D + "\n\n" + TAIL
        operations = [
            {"op": "split", "text": A + " " + B, "at": B, "as": "line"},
            {"op": "split", "text": C + " " + D, "at": D, "as": "line"},
            {"op": "move", "start": A, "end": A, "after": left, "as": "paragraph"},
            {"op": "move", "start": C, "end": C, "after": A, "as": "inline"},
            {"op": "move", "start": B, "end": B, "after": right, "as": "paragraph"},
            {"op": "move", "start": D, "end": D, "after": B, "as": "inline"},
        ]
        result, log = repair.apply_operations(original, operations)
        self.assertEqual([entry["status"] for entry in log], ["accepted"] * len(operations), log)
        self.assertEqual(result, left + "\n\n" + A + " " + C + "\n\n" + right + "\n\n" + B + " " + D + "\n\n" + TAIL)
        self.assertEqual(repair.word_tokens(result), repair.word_tokens(original))

    def test_split_run_in_heading_then_markup_heading2(self):
        original = "Methods " + A
        result, log = repair.apply_operations(original, [
            {"op": "split", "text": original, "at": A, "as": "paragraph"},
            {"op": "markup", "text": "Methods ", "as": "heading2"},
        ])
        self.assertEqual([entry["status"] for entry in log], ["accepted", "accepted"], log)
        self.assertEqual(result, "## Methods \n\n" + A)
        self.assertEqual(repair.word_tokens(result), repair.word_tokens(original))

    def test_split_resolves_current_text_and_continues_after_rejections(self):
        quote = A + " " + B
        result, log = repair.apply_operations(quote, [
            {"op": "split", "text": quote, "at": C, "as": "line"},
            {"op": "split", "text": quote, "at": B, "as": "line"},
            {"op": "split", "text": quote, "at": B, "as": "paragraph"},
            {"op": "split", "text": A + " \n" + B, "at": B, "as": "line"},
        ])
        self.assertEqual([entry["status"] for entry in log], ["rejected", "accepted", "rejected", "accepted"], log)
        self.assertEqual(result, A + " \n\n" + B)
        self.assertEqual(repair.word_tokens(result), repair.word_tokens(quote))

    def test_markup_all_styles(self):
        for style, expected in (("heading2", "## " + A), ("heading3", "### " + A),
                                ("caption", "**" + A + "**"), ("paragraph", A), ("list_item", "- " + A)):
            with self.subTest(style=style):
                self.accepted("> - **" + A + "**\n", {"op": "markup", "text": "> - **" + A + "**", "as": style},
                              expected + "\n")

    def test_markup_preserves_internal_emphasis_and_numbering(self):
        line = "1. These **important** printed words must all remain."
        self.accepted(line, {"op": "markup", "text": line, "as": "heading2"}, "## " + line)

    def test_markup_short_line_allowed(self):
        self.accepted("Title\n", {"op": "markup", "text": "Title", "as": "heading2"}, "## Title\n")

    def test_markup_outer_emphasis_with_surrounding_whitespace(self):
        self.accepted("  **" + A + "**  \n", {"op": "markup", "text": "  **" + A + "**  ", "as": "paragraph"},
                      "  " + A + "  \n")
        self.accepted("  " + A + "  \n", {"op": "markup", "text": "  " + A + "  ", "as": "caption"},
                      "  **" + A + "**  \n")

    def test_markup_rejects_partial_line(self):
        self.rejected(A + " " + B, {"op": "markup", "text": A, "as": "heading2"}, "whole line")
        self.rejected(B + " " + A, {"op": "markup", "text": A, "as": "heading2"}, "whole line")

    def test_markup_rejects_multiline(self):
        self.rejected(A + "\n" + B, {"op": "markup", "text": A + "\n" + B, "as": "caption"}, "whole line")

    def test_markup_rejects_new_words_in_anchor(self):
        self.rejected(A, {"op": "markup", "text": A + " invented words", "as": "caption"}, "missing")

    def test_markup_rejects_word_changing_unmask(self):
        line = "**- These printed punctuation tokens must stay.**"
        self.rejected(line, {"op": "markup", "text": line, "as": "paragraph"}, "word invariant")

    def test_markup_rejects_unknown_style_or_extra_replacement(self):
        self.rejected(A, {"op": "markup", "text": A, "as": "rewritten words"}, "invalid markup style")
        self.rejected(A, {"op": "markup", "text": A, "as": "paragraph", "replacement": B}, "unknown fields")

    def test_duplicate_second_occurrence(self):
        original = A + "\n\n" + C + "\n\n" + A + "\n\n" + B
        result, entry = self.accepted(original, {"op": "remove_duplicate", "start": A, "end": A, "occurrence": 2},
                                      A + "\n\n" + C + "\n\n" + B, same_words=False)
        self.assertEqual(repair.word_tokens(result), repair.word_tokens(original) - repair.word_tokens(A))
        self.assertEqual(entry["before"]["span"], [len(A + "\n\n" + C + "\n\n"), len(original) - len(B) - 2])

    def test_duplicate_multiline_and_repeated_token_counts(self):
        duplicate = "The repeated word word word occurs in this block.\n" + B
        original = duplicate + "\n\n" + C + "\n\n" + duplicate
        result, _ = self.accepted(original, {"op": "remove_duplicate", "start": duplicate.splitlines()[0],
                                            "end": B, "occurrence": 1}, same_words=False)
        self.assertEqual(repair.word_tokens(result), repair.word_tokens(original) - repair.word_tokens(duplicate))
        self.assertEqual(result.count(duplicate), 1)

    def test_duplicate_rejects_only_copy(self):
        self.rejected(A + "\n\n" + B,
                      {"op": "remove_duplicate", "start": A, "end": B, "occurrence": 1}, "at least twice")

    def test_duplicate_rejects_equal_anchors_but_different_spans(self):
        original = A + "\n" + C + "\n" + B + "\n\n" + A + "\n" + D + "\n" + B
        self.rejected(original, {"op": "remove_duplicate", "start": A, "end": B, "occurrence": 1}, "at least twice")

    def test_duplicate_rejects_overlapping_occurrences_without_survivor(self):
        text = "a" * 26
        self.rejected(text, {"op": "remove_duplicate", "start": "a" * 25, "end": "a" * 25, "occurrence": 1},
                      "leave an exact occurrence")

    def test_duplicate_rejects_partial_word(self):
        quote = "abcdefghijklmnopqrstuvwxyz"
        original = "prefix" + quote + "suffix\n\n" + quote
        self.rejected(original, {"op": "remove_duplicate", "start": quote, "end": quote, "occurrence": 1},
                      "word invariant")

    def test_duplicate_rejects_reverse_span(self):
        self.rejected(A + "\n" + B + "\n" + A + "\n" + B,
                      {"op": "remove_duplicate", "start": B, "end": A, "occurrence": 1}, "malformed span")

    def test_flag_creates_final_section(self):
        note = "Page 4: a printed value is illegible."
        result, entry = self.accepted(A, {"op": "flag", "note": note}, same_words=False)
        expected = A + "\n\n## " + repair.UNCERTAINTY_TITLE + "\n\n- Checker: " + note + "\n"
        self.assertEqual(result, expected)
        self.assertEqual(entry["before"]["insertion"], [len(A), len(A)])
        self.assertEqual(entry["after"]["insertion"], [len(A), len(result)])

    def test_flags_append_and_preserve_existing_items_exactly(self):
        original = A + "\n\n" + TAIL.rstrip("\n")
        result, logs = repair.apply_operations(original, [{"op": "flag", "note": "p. 2: unclear letter."},
                                                          {"op": "flag", "note": "Page iv: missing text."}])
        self.assertEqual([item["status"] for item in logs], ["accepted", "accepted"])
        self.assertEqual(result, original + "\n- Checker: p. 2: unclear letter.\n- Checker: Page iv: missing text.\n")

    def test_flags_reject_missing_page_or_multiline_or_nonstring(self):
        for note in ("No page given.", "page 2\n## Forged heading", "page 2\rhidden", "page 2\u2028", "", 123):
            with self.subTest(note=note):
                self.rejected(A, {"op": "flag", "note": note}, "flag note")

    def test_all_anchor_operations_protect_tail(self):
        heading = "## " + repair.UNCERTAINTY_TITLE
        item = "- Page 7: the original uncertain reading."
        original = A + "\n\n" + TAIL
        operations = [
            {"op": "move", "start": item, "end": item, "after": A, "as": "paragraph"},
            {"op": "move", "start": A, "end": A, "after": item, "as": "inline"},
            {"op": "join", "left": A, "right": heading},
            {"op": "markup", "text": heading, "as": "paragraph"},
            {"op": "remove_duplicate", "start": item, "end": item, "occurrence": 1},
        ]
        for operation in operations:
            with self.subTest(operation=operation):
                self.rejected(original, operation, "protected uncertainty")

    def test_move_near_tail_leaves_section_at_end(self):
        original = C + "\n\n" + A + "\n\n" + TAIL
        result, _ = self.accepted(original, {"op": "move", "start": C, "end": C, "after": A, "as": "paragraph"})
        self.assertTrue(result.endswith("\n\n" + TAIL))
        self.assertLess(result.index(C), result.index(repair.UNCERTAINTY_TITLE))

    def test_all_anchor_operations_reject_ambiguity(self):
        original = A + "\n\n" + A + "\n\n" + B
        for operation in [
            {"op": "markup", "text": A, "as": "caption"},
            {"op": "join", "left": A, "right": B},
            {"op": "move", "start": A, "end": A, "after": B, "as": "paragraph"},
        ]:
            with self.subTest(operation=operation):
                self.rejected(original, operation, "ambiguous")

    def test_explicit_occurrence_for_markup(self):
        self.accepted(A + "\n\n" + A, {"op": "markup", "text": A, "as": "caption", "occurrence": 2},
                      A + "\n\n**" + A + "**")

    def test_occurrence_must_be_positive_integer_and_exist(self):
        for occurrence in (0, -1, 1.5, "1", True, None, 3):
            with self.subTest(occurrence=occurrence):
                self.rejected(A + "\n\n" + A,
                              {"op": "remove_duplicate", "start": A, "end": A, "occurrence": occurrence},
                              "occurrence")

    def test_short_partial_anchor_is_rejected_on_long_line(self):
        self.rejected(A + "\n\n" + B, {"op": "join", "left": "original words.", "right": B}, "at least 25")

    def test_short_complete_lines_can_move_and_join(self):
        self.accepted("Title\n\nSmall caption\n\nText", {"op": "move", "start": "Small caption", "end": "Small caption",
                                                               "after": "Title", "as": "inline"}, "Title Small caption\n\nText")
        self.accepted("Short\nline", {"op": "join", "left": "Short", "right": "line"}, "Short line")

    def test_resolution_uses_current_copy_and_continues_after_rejection(self):
        operations = [
            {"op": "markup", "text": A, "as": "heading2"},
            {"op": "markup", "text": "## " + A, "as": "caption"},
            {"op": "markup", "text": B, "as": "heading2"},
            {"op": "markup", "text": "## " + B, "as": "paragraph"},
            {"op": "flag", "note": "Page 5: original words are unclear."},
        ]
        result, log = repair.apply_operations(A, operations)
        self.assertEqual([item["status"] for item in log], ["accepted", "accepted", "rejected", "rejected", "accepted"])
        self.assertTrue(result.startswith("**" + A + "**\n\n"))
        self.assertEqual([item["index"] for item in log], list(range(5)))
        self.assertIn("missing", log[3]["reason"])

    def test_move_then_join_displaced_sentence(self):
        original = A + "\n\n" + C + "\n\n" + B + "\n\n" + D
        result, log = repair.apply_operations(original, [
            {"op": "move", "start": C, "end": C, "after": D, "as": "paragraph"},
            {"op": "join", "left": A, "right": B},
        ])
        self.assertEqual([item["status"] for item in log], ["accepted", "accepted"])
        self.assertTrue(result.startswith(A + " " + B + "\n\n" + D))
        self.assertEqual(repair.word_tokens(result), repair.word_tokens(original))

    def test_malformed_operations_do_not_stop_following_operations(self):
        malformed = [None, [], "move", {}, {"op": []}, {"op": "replace", "text": A},
                     {"op": "join", "left": A}, {"op": "markup", "text": 7, "as": "caption"},
                     {"op": "move", "start": A, "end": A, "after": B, "as": []}]
        result, log = repair.apply_operations(A, malformed + [{"op": "markup", "text": A, "as": "heading3"}])
        self.assertEqual([item["status"] for item in log], ["rejected"] * len(malformed) + ["accepted"])
        self.assertEqual(result, "### " + A)

    def test_crlf_and_unicode_character_offsets(self):
        line = "Café λ has a printed result with original words."
        original = line + "\r\n\r\n" + A + "\r\n"
        result, entry = self.accepted(original, {"op": "markup", "text": A, "as": "heading2"},
                                     line + "\r\n\r\n## " + A + "\r\n")
        self.assertEqual(entry["before"]["text"][0], len(line) + 4)
        start, end = entry["after"]["text"]
        self.assertEqual(result[start:end], "## " + A)


class InvariantTests(unittest.TestCase):
    def test_normalization_preserves_punctuation_and_original_numbers(self):
        text = "## Title\n> - **Bold** words.\n1. Original numbering\n-foo #tag x-y a>b 12.\n"
        self.assertEqual(repair.word_tokens(text), Counter("Title Bold words. 1. Original numbering -foo #tag x-y a>b 12.".split()))

    def test_guard_rejects_drop_duplicate_and_word_replacement(self):
        for candidate in (A, A + "\n\n" + B + "\n\n" + B, A + "\n\n" + C):
            with self.subTest(candidate=candidate):
                with self.assertRaisesRegex(repair.Rejected, "word invariant"):
                    repair.check_invariant(A + "\n\n" + B, candidate, "move", Counter())

    def test_candidate_is_not_committed_when_invariant_fails(self):
        def bad_move(ctx):
            return ctx.text + "\n" + ctx.text, {"span": [0, len(ctx.text)]}, Counter()
        with patch.dict(repair.HANDLERS, {"move": bad_move}):
            result, log = repair.apply_operations(A, [
                {"op": "move", "start": A, "end": A, "after": A, "as": "inline"},
                {"op": "markup", "text": A, "as": "caption"},
            ])
        self.assertEqual([item["status"] for item in log], ["rejected", "accepted"])
        self.assertEqual(result, "**" + A + "**")

    def test_guard_rejects_tail_moved_before_body_even_with_same_words(self):
        with self.assertRaisesRegex(repair.Rejected, "uncertainty section"):
            repair.check_invariant(A + "\n\n" + TAIL, TAIL + "\n" + A, "move", Counter())


class CLITests(unittest.TestCase):
    def run_cli(self, directory):
        return subprocess.run([sys.executable, "-I", str(ROOT / "repair_apply.py"), str(directory)],
                              cwd=ROOT, capture_output=True, text=True)

    def test_cli_accepts_split_without_schema_flag(self):
        with tempfile.TemporaryDirectory(prefix="paper-") as temp:
            directory = Path(temp)
            original = "Methods " + A
            (directory / "copy.orig.md").write_text(original, encoding="utf-8")
            (directory / "ops.json").write_text(json.dumps({"paper": "synthetic", "ops": [
                {"op": "split", "text": original, "at": B, "as": "line"},
                {"op": "split", "text": original, "at": A, "as": "paragraph"},
                {"op": "markup", "text": "Methods ", "as": "heading2"},
            ]}), encoding="utf-8")
            process = self.run_cli(directory)
            self.assertEqual(process.returncode, 0, process.stderr)
            self.assertIn("Applied 2 operation(s); rejected 1", process.stdout)
            self.assertEqual((directory / "copy.orig.md").read_text(encoding="utf-8"), original)
            self.assertEqual((directory / "copy.md").read_text(encoding="utf-8"), "## Methods \n\n" + A)
            log = json.loads((directory / "apply-log.json").read_text(encoding="utf-8"))
            self.assertEqual([entry["status"] for entry in log["ops"]], ["rejected", "accepted", "accepted"])

    def test_cli_writes_outputs_preserves_inputs_and_is_repeatable(self):
        with tempfile.TemporaryDirectory(prefix="paper-") as temp:
            directory = Path(temp)
            original = (A + "\r\n\r\n" + B + "\r\n").encode("utf-8")
            (directory / "copy.orig.md").write_bytes(original)
            operations = json.dumps({"paper": "synthetic", "ops": [
                {"op": "markup", "text": A, "as": "heading2"},
                {"op": "remove_duplicate", "start": B, "end": B, "occurrence": 1},
                {"op": "flag", "note": "Page 2: λ is unclear."},
            ]}, ensure_ascii=False).encode("utf-8")
            (directory / "ops.json").write_bytes(operations)
            process = self.run_cli(directory)
            self.assertEqual(process.returncode, 0, process.stderr)
            self.assertIn("rejected 1", process.stdout)
            self.assertEqual((directory / "copy.orig.md").read_bytes(), original)
            self.assertEqual((directory / "ops.json").read_bytes(), operations)
            log = json.loads((directory / "apply-log.json").read_text(encoding="utf-8"))
            self.assertEqual(log["paper"], "synthetic")
            self.assertEqual([entry["status"] for entry in log["ops"]], ["accepted", "rejected", "accepted"])
            first_copy = (directory / "copy.md").read_bytes()
            first_log = (directory / "apply-log.json").read_bytes()
            self.assertEqual(self.run_cli(directory).returncode, 0)
            self.assertEqual((directory / "copy.md").read_bytes(), first_copy)
            self.assertEqual((directory / "apply-log.json").read_bytes(), first_log)
            self.assertFalse(list(directory.glob(".repair-*")))

    def test_invalid_input_leaves_existing_outputs_unchanged(self):
        for payload in ("{", "[]", '{"paper":"x","ops":{}}'):
            with self.subTest(payload=payload), tempfile.TemporaryDirectory(prefix="paper-") as temp:
                directory = Path(temp)
                (directory / "copy.orig.md").write_text(A, encoding="utf-8")
                (directory / "ops.json").write_text(payload, encoding="utf-8")
                (directory / "copy.md").write_text("old copy", encoding="utf-8")
                (directory / "apply-log.json").write_text("old log", encoding="utf-8")
                process = self.run_cli(directory)
                self.assertEqual(process.returncode, 1)
                self.assertIn("repair_apply:", process.stderr)
                self.assertEqual((directory / "copy.md").read_text(), "old copy")
                self.assertEqual((directory / "apply-log.json").read_text(), "old log")

    def test_empty_paper_and_empty_operations(self):
        with tempfile.TemporaryDirectory(prefix="paper-") as temp:
            directory = Path(temp)
            (directory / "copy.orig.md").write_text("", encoding="utf-8")
            (directory / "ops.json").write_text('{"paper":"empty","ops":[]}', encoding="utf-8")
            self.assertEqual(self.run_cli(directory).returncode, 0)
            self.assertEqual((directory / "copy.md").read_text(), "")
            self.assertEqual(json.loads((directory / "apply-log.json").read_text())["ops"], [])

    def test_missing_input_is_reported_without_outputs(self):
        with tempfile.TemporaryDirectory(prefix="paper-") as temp:
            directory = Path(temp)
            self.assertEqual(self.run_cli(directory).returncode, 1)
            self.assertEqual(list(directory.iterdir()), [])

    def test_output_directory_error_does_not_replace_copy(self):
        with tempfile.TemporaryDirectory(prefix="paper-") as temp:
            directory = Path(temp)
            (directory / "copy.orig.md").write_text(A, encoding="utf-8")
            (directory / "ops.json").write_text('{"paper":"x","ops":[]}', encoding="utf-8")
            (directory / "copy.md").write_text("old copy", encoding="utf-8")
            (directory / "apply-log.json").mkdir()
            self.assertEqual(self.run_cli(directory).returncode, 1)
            self.assertEqual((directory / "copy.md").read_text(), "old copy")
            self.assertFalse(list(directory.glob(".repair-*")))


if __name__ == "__main__":
    unittest.main()
