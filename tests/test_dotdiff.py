import io
import json
import os
import sys
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout
from unittest import mock

import dotdiff
from dotdiff import DotenvError


class ParseTest(unittest.TestCase):
    def test_simple_pair(self):
        entries = dotdiff.parse("PORT=8080\nDEBUG=true\n")
        self.assertEqual(list(entries), ["PORT", "DEBUG"])
        self.assertEqual(entries["PORT"].value, "8080")
        self.assertEqual(entries["DEBUG"].value, "true")

    def test_empty_file(self):
        self.assertEqual(dotdiff.parse(""), {})

    def test_blank_lines_are_skipped(self):
        entries = dotdiff.parse("\n\n  \nA=1\n\n")
        self.assertEqual(list(entries), ["A"])

    def test_comment_lines_are_skipped(self):
        entries = dotdiff.parse("# a comment\n   # another\nA=1\n")
        self.assertEqual(list(entries), ["A"])

    def test_export_prefix(self):
        entries = dotdiff.parse("export PORT=8080\n")
        self.assertEqual(entries["PORT"].value, "8080")

    def test_export_prefix_with_many_spaces(self):
        entries = dotdiff.parse("export    PORT=8080\n")
        self.assertEqual(entries["PORT"].value, "8080")

    def test_export_without_value(self):
        entries = dotdiff.parse("export FOO\n")
        self.assertEqual(entries["FOO"].value, "")

    def test_name_without_value(self):
        entries = dotdiff.parse("FOO\n")
        self.assertEqual(entries["FOO"].value, "")

    def test_spaces_around_the_equal_sign(self):
        entries = dotdiff.parse("  PORT  =  8080  \n")
        self.assertEqual(entries["PORT"].value, "8080")

    def test_value_keeps_inner_spaces(self):
        entries = dotdiff.parse("GREETING=hello there\n")
        self.assertEqual(entries["GREETING"].value, "hello there")

    def test_value_may_hold_an_equal_sign(self):
        entries = dotdiff.parse("QUERY=a=b=c\n")
        self.assertEqual(entries["QUERY"].value, "a=b=c")

    def test_single_quotes_are_literal(self):
        entries = dotdiff.parse("A='hello \\n world'\n")
        self.assertEqual(entries["A"].value, "hello \\n world")

    def test_double_quotes_read_escapes(self):
        entries = dotdiff.parse('A="hello\\nworld"\n')
        self.assertEqual(entries["A"].value, "hello\nworld")

    def test_double_quotes_keep_an_escaped_quote(self):
        entries = dotdiff.parse('A="say \\"hi\\""\n')
        self.assertEqual(entries["A"].value, 'say "hi"')

    def test_double_quotes_keep_a_backslash(self):
        entries = dotdiff.parse('A="C:\\\\Users"\n')
        self.assertEqual(entries["A"].value, "C:\\Users")

    def test_quoted_value_may_hold_an_equal_sign(self):
        entries = dotdiff.parse('A="a=b"\n')
        self.assertEqual(entries["A"].value, "a=b")

    def test_quoted_value_may_hold_a_hash(self):
        entries = dotdiff.parse('A="value # not a comment"\n')
        self.assertEqual(entries["A"].value, "value # not a comment")

    def test_inline_comment_is_cut_from_a_bare_value(self):
        entries = dotdiff.parse("A=value # a comment\n")
        self.assertEqual(entries["A"].value, "value")

    def test_hash_without_a_space_stays_in_the_value(self):
        entries = dotdiff.parse("A=value#1\n")
        self.assertEqual(entries["A"].value, "value#1")

    def test_multiline_double_quoted_value(self):
        entries = dotdiff.parse('A="line one\nline two"\nB=2\n')
        self.assertEqual(entries["A"].value, "line one\nline two")
        self.assertEqual(entries["B"].value, "2")

    def test_multiline_single_quoted_value(self):
        entries = dotdiff.parse("A='line one\nline two'\n")
        self.assertEqual(entries["A"].value, "line one\nline two")

    def test_multiline_value_keeps_the_following_lines(self):
        entries = dotdiff.parse('A="one\ntwo\nthree"\nB=2\n')
        self.assertEqual(entries["B"].value, "2")

    def test_the_last_value_of_a_name_wins(self):
        entries = dotdiff.parse("A=1\nA=2\n")
        self.assertEqual(entries["A"].value, "2")
        self.assertEqual(entries["A"].line, 2)

    def test_the_line_of_every_name_is_kept(self):
        entries = dotdiff.parse("# a comment\nA=1\n\nB=2\n")
        self.assertEqual(entries["A"].line, 2)
        self.assertEqual(entries["B"].line, 4)

    def test_an_empty_name_is_rejected(self):
        with self.assertRaises(DotenvError) as caught:
            dotdiff.parse("=value\n", ".env")
        self.assertIn(".env:1", str(caught.exception))

    def test_a_name_with_a_space_is_rejected(self):
        with self.assertRaises(DotenvError) as caught:
            dotdiff.parse("MY NAME=value\n", ".env")
        self.assertIn(".env:1", str(caught.exception))

    def test_an_unclosed_quote_is_rejected(self):
        with self.assertRaises(DotenvError) as caught:
            dotdiff.parse('A="never closed\n', ".env")
        self.assertIn(".env:1", str(caught.exception))

    def test_an_unclosed_quote_spans_the_file(self):
        with self.assertRaises(DotenvError):
            dotdiff.parse('A="never closed\nB=2\n', ".env")

    def test_a_name_with_a_dot_is_allowed(self):
        entries = dotdiff.parse("service.host=localhost\n")
        self.assertEqual(entries["service.host"].value, "localhost")


class CompareTest(unittest.TestCase):
    def test_identical_files(self):
        left = dotdiff.parse("A=1\nB=2\n")
        right = dotdiff.parse("A=1\nB=2\n")
        differences = dotdiff.compare(left, right)
        self.assertTrue(dotdiff.is_identical(differences))
        self.assertEqual(differences["unchanged"], ["A", "B"])

    def test_added_name(self):
        left = dotdiff.parse("A=1\n")
        right = dotdiff.parse("A=1\nB=2\n")
        differences = dotdiff.compare(left, right)
        self.assertFalse(dotdiff.is_identical(differences))
        self.assertEqual([entry.key for entry in differences["added"]], ["B"])
        self.assertEqual(differences["removed"], [])
        self.assertEqual(differences["changed"], [])

    def test_removed_name(self):
        left = dotdiff.parse("A=1\nB=2\n")
        right = dotdiff.parse("A=1\n")
        differences = dotdiff.compare(left, right)
        self.assertEqual([entry.key for entry in differences["removed"]], ["B"])

    def test_changed_name(self):
        left = dotdiff.parse("A=1\n")
        right = dotdiff.parse("A=2\n")
        differences = dotdiff.compare(left, right)
        self.assertEqual(len(differences["changed"]), 1)
        before, after = differences["changed"][0]
        self.assertEqual(before.value, "1")
        self.assertEqual(after.value, "2")

    def test_a_name_that_moved_is_not_a_change(self):
        left = dotdiff.parse("A=1\nB=2\n")
        right = dotdiff.parse("B=2\nA=1\n")
        differences = dotdiff.compare(left, right)
        self.assertTrue(dotdiff.is_identical(differences))

    def test_a_comment_does_not_make_a_change(self):
        left = dotdiff.parse("A=1\n")
        right = dotdiff.parse("# a comment\nA=1\n")
        differences = dotdiff.compare(left, right)
        self.assertTrue(dotdiff.is_identical(differences))

    def test_a_quote_does_not_make_a_change(self):
        left = dotdiff.parse("A=1\n")
        right = dotdiff.parse("A='1'\n")
        differences = dotdiff.compare(left, right)
        self.assertTrue(dotdiff.is_identical(differences))

    def test_the_order_of_the_groups_follows_the_files(self):
        left = dotdiff.parse("A=1\nB=2\nC=3\n")
        right = dotdiff.parse("C=9\nB=2\nD=4\n")
        differences = dotdiff.compare(left, right)
        self.assertEqual([entry.key for entry in differences["added"]], ["D"])
        self.assertEqual([entry.key for entry in differences["removed"]], ["A"])
        self.assertEqual(differences["changed"][0][1].key, "C")

    def test_an_empty_file_against_a_full_one(self):
        differences = dotdiff.compare(dotdiff.parse(""), dotdiff.parse("A=1\n"))
        self.assertEqual([entry.key for entry in differences["added"]], ["A"])


class ResultTest(unittest.TestCase):
    def test_the_result_names_the_two_files(self):
        result = dotdiff.build_result("a", "b", dotdiff.parse(""), dotdiff.parse(""))
        self.assertEqual(result["left"], "a")
        self.assertEqual(result["right"], "b")
        self.assertTrue(result["identical"])

    def test_the_mask_hides_the_values(self):
        left = dotdiff.parse("A=secret\n")
        right = dotdiff.parse("A=other\n")
        result = dotdiff.build_result("a", "b", left, right, mask=True)
        self.assertEqual(result["changed"][0]["left"], "***")
        self.assertEqual(result["changed"][0]["right"], "***")

    def test_the_keys_mode_leaves_the_values_out(self):
        left = dotdiff.parse("A=secret\n")
        right = dotdiff.parse("A=other\nB=more\n")
        result = dotdiff.build_result("a", "b", left, right, keys_only=True)
        self.assertIsNone(result["changed"][0]["left"])
        self.assertIsNone(result["added"][0]["value"])


class RenderTest(unittest.TestCase):
    def setUp(self):
        self.left = dotdiff.parse("PORT=8080\nOLD=bye\n")
        self.right = dotdiff.parse("PORT=9090\nNEW=hello\n")
        self.result = dotdiff.build_result("a.env", "b.env", self.left, self.right)

    def test_the_text_shows_the_signs(self):
        text = dotdiff.render_text(self.result)
        self.assertIn("+ NEW=hello", text)
        self.assertIn("~ PORT=8080 -> 9090", text)
        self.assertIn("- OLD=bye", text)

    def test_the_text_counts_the_changes(self):
        text = dotdiff.render_text(self.result)
        self.assertIn("3 changes between a.env and b.env", text)

    def test_one_change_is_singular(self):
        left = dotdiff.parse("A=1\n")
        right = dotdiff.parse("A=2\n")
        result = dotdiff.build_result("a", "b", left, right)
        self.assertIn("1 change between a and b", dotdiff.render_text(result))

    def test_identical_files_say_so(self):
        left = dotdiff.parse("A=1\n")
        right = dotdiff.parse("A=1\n")
        result = dotdiff.build_result("a", "b", left, right)
        self.assertEqual(
            dotdiff.render_text(result), "No differences between a and b"
        )

    def test_the_keys_mode_drops_the_values(self):
        text = dotdiff.render_text(self.result, keys_only=True)
        self.assertIn("+ NEW", text)
        self.assertIn("~ PORT", text)
        self.assertIn("- OLD", text)
        self.assertNotIn("hello", text)

    def test_a_value_with_a_line_break_stays_on_one_line(self):
        left = dotdiff.parse("")
        right = dotdiff.parse('A="one\ntwo"\n')
        result = dotdiff.build_result("a", "b", left, right)
        text = dotdiff.render_text(result)
        self.assertIn("A=one\\ntwo", text)
        self.assertEqual(len(text.splitlines()), 3)

    def test_the_json_holds_the_same_information(self):
        payload = json.loads(dotdiff.render_json(self.result))
        self.assertEqual(payload["added"][0]["key"], "NEW")
        self.assertEqual(payload["changed"][0]["left"], "8080")
        self.assertEqual(payload["removed"][0]["key"], "OLD")
        self.assertFalse(payload["identical"])


class ReadFileTest(unittest.TestCase):
    def test_a_missing_file_raises(self):
        with self.assertRaises(DotenvError):
            dotdiff.read_file("does-not-exist.env")

    def test_a_byte_order_mark_is_dropped(self):
        with tempfile.TemporaryDirectory() as folder:
            path = os.path.join(folder, ".env")
            with open(path, "wb") as handle:
                handle.write(b"\xef\xbb\xbfA=1\n")
            text = dotdiff.read_file(path)
        self.assertEqual(dotdiff.parse(text)["A"].value, "1")

    def test_the_standard_input_is_read(self):
        with mock.patch("sys.stdin", io.StringIO("A=1\n")):
            self.assertEqual(dotdiff.read_file("-"), "A=1\n")


class MainTest(unittest.TestCase):
    def run_tool(self, *arguments):
        stdout = io.StringIO()
        stderr = io.StringIO()
        with redirect_stdout(stdout), redirect_stderr(stderr):
            code = dotdiff.main(list(arguments))
        return code, stdout.getvalue(), stderr.getvalue()

    def write(self, folder, name, text):
        path = os.path.join(folder, name)
        with open(path, "w", encoding="utf-8", newline="") as handle:
            handle.write(text)
        return path

    def test_the_same_files_give_zero(self):
        with tempfile.TemporaryDirectory() as folder:
            left = self.write(folder, "a.env", "A=1\n")
            right = self.write(folder, "b.env", "A=1\n")
            code, output, _ = self.run_tool(left, right)
        self.assertEqual(code, dotdiff.EXIT_SAME)
        self.assertIn("No differences", output)

    def test_different_files_give_one(self):
        with tempfile.TemporaryDirectory() as folder:
            left = self.write(folder, "a.env", "A=1\n")
            right = self.write(folder, "b.env", "A=2\n")
            code, output, _ = self.run_tool(left, right)
        self.assertEqual(code, dotdiff.EXIT_DIFFERENT)
        self.assertIn("~ A=1 -> 2", output)

    def test_a_missing_file_gives_two(self):
        with tempfile.TemporaryDirectory() as folder:
            right = self.write(folder, "b.env", "A=2\n")
            code, _, error = self.run_tool("missing.env", right)
        self.assertEqual(code, dotdiff.EXIT_ERROR)
        self.assertIn("missing.env", error)

    def test_a_broken_file_gives_two(self):
        with tempfile.TemporaryDirectory() as folder:
            left = self.write(folder, "a.env", "=value\n")
            right = self.write(folder, "b.env", "A=2\n")
            code, _, error = self.run_tool(left, right)
        self.assertEqual(code, dotdiff.EXIT_ERROR)
        self.assertIn("a.env:1", error)

    def test_the_json_flag(self):
        with tempfile.TemporaryDirectory() as folder:
            left = self.write(folder, "a.env", "A=1\n")
            right = self.write(folder, "b.env", "A=2\n")
            code, output, _ = self.run_tool(left, right, "--json")
        payload = json.loads(output)
        self.assertEqual(code, dotdiff.EXIT_DIFFERENT)
        self.assertEqual(payload["changed"][0]["right"], "2")

    def test_the_mask_flag(self):
        with tempfile.TemporaryDirectory() as folder:
            left = self.write(folder, "a.env", "A=secret\n")
            right = self.write(folder, "b.env", "A=other\n")
            code, output, _ = self.run_tool(left, right, "--mask")
        self.assertNotIn("secret", output)
        self.assertIn("***", output)

    def test_the_keys_flag(self):
        with tempfile.TemporaryDirectory() as folder:
            left = self.write(folder, "a.env", "A=secret\n")
            right = self.write(folder, "b.env", "A=other\nB=more\n")
            code, output, _ = self.run_tool(left, right, "--keys")
        self.assertNotIn("secret", output)
        self.assertNotIn("more", output)
        self.assertIn("~ A", output)

    def test_the_quiet_flag_prints_nothing(self):
        with tempfile.TemporaryDirectory() as folder:
            left = self.write(folder, "a.env", "A=1\n")
            right = self.write(folder, "b.env", "A=2\n")
            code, output, error = self.run_tool(left, right, "--quiet")
        self.assertEqual(code, dotdiff.EXIT_DIFFERENT)
        self.assertEqual(output, "")
        self.assertEqual(error, "")

    def test_the_standard_input_can_be_read(self):
        with tempfile.TemporaryDirectory() as folder:
            right = self.write(folder, "b.env", "A=2\n")
            with mock.patch("sys.stdin", io.StringIO("A=1\n")):
                code, output, _ = self.run_tool("-", right)
        self.assertEqual(code, dotdiff.EXIT_DIFFERENT)
        self.assertIn("~ A=1 -> 2", output)

    def test_the_parser_is_built(self):
        parser = dotdiff.build_parser()
        arguments = parser.parse_args(["a", "b", "--json", "--mask", "--keys"])
        self.assertTrue(arguments.as_json)
        self.assertTrue(arguments.mask)
        self.assertTrue(arguments.keys_only)


if __name__ == "__main__":
    unittest.main()
