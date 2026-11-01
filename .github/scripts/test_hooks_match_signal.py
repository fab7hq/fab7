"""fab7's check refuses a harness file that does not say where its received prompt is,
on made-up harnesses."""

import pathlib
import sys
import tempfile
import unittest

sys.path.insert(0, str(pathlib.Path(__file__).parent))
import hooks_match_signal  # noqa: E402

HOOKS = """{"hooks": {
  "Began": [{"hooks": [{"type": "command", "command": "${PLUGIN_ROOT}/hooks/weft-signal loom Began"}]}],
  "Submitted": [{"hooks": [{"type": "command", "command": "${PLUGIN_ROOT}/hooks/weft-signal loom Submitted"}]}]
}}"""

SIGNAL = """[signal]
session = "session_id"
workspace = "cwd"
{prompt}on = [
  {{ hook = "Began",     state = "ready" }},
  {{ hook = "Submitted", state = "working"{forward} }},
]
"""


def bench(signal, module=None):
    tmp = pathlib.Path(tempfile.mkdtemp())
    plugin = tmp / "plugins" / "loom"
    (plugin / "hooks").mkdir(parents=True)
    hooks = HOOKS
    if module is not None:
        hooks = '{"modules": ["./turn.ts"],' + HOOKS[1:]
        (plugin / "turn.ts").write_text(module)
    (plugin / "hooks.json").write_text(hooks)
    (plugin / "hooks" / "weft-signal").write_text("#!/bin/sh\n")
    harnesses = tmp / "harnesses"
    harnesses.mkdir()
    (harnesses / "loom.toml").write_text('title = "Loom"\nprogram = "loom"\n' + signal)
    return hooks_match_signal.check(tmp / "plugins", harnesses)


class ReceivedPrompt(unittest.TestCase):
    def test_a_harness_file_that_names_its_received_prompt_passes(self):
        good = SIGNAL.format(prompt='prompt = "prompt"\n', forward=', forward = "prompt"')
        self.assertEqual(bench(good), [])

    def test_a_harness_file_without_prompt_is_refused(self):
        bad = bench(SIGNAL.format(prompt="", forward=', forward = "prompt"'))
        self.assertTrue(any("loom" in b and "prompt" in b for b in bad), bad)

    def test_a_harness_file_whose_rows_forward_no_prompt_is_refused(self):
        bad = bench(SIGNAL.format(prompt='prompt = "prompt"\n', forward=""))
        self.assertTrue(any("forwards the received prompt" in b for b in bad), bad)

    def test_a_harness_file_without_signal_is_refused(self):
        tmp = pathlib.Path(tempfile.mkdtemp())
        (tmp / "plugins").mkdir()
        (tmp / "harnesses").mkdir()
        (tmp / "harnesses" / "loom.toml").write_text('title = "Loom"\n')
        bad = hooks_match_signal.check(tmp / "plugins", tmp / "harnesses")
        self.assertTrue(any("loom" in b for b in bad), bad)


ENDED = SIGNAL.replace('state = "working"{forward} }},', 'state = "working"{forward} }},\n  {{ hook = "Ended", state = "turn_ended" }},')
MODULE = "const signal = [`${{$.plugin.root}}/hooks/weft-signal`, 'loom', '{hook}'];\n"


class HooksModule(unittest.TestCase):
    def test_a_row_the_hooks_module_reports_through_the_shim_is_registered(self):
        good = ENDED.format(prompt='prompt = "prompt"\n', forward=', forward = "prompt"')
        self.assertEqual(bench(good, MODULE.format(hook="Ended")), [])

    def test_a_row_no_module_reports_is_still_refused(self):
        bad = bench(ENDED.format(prompt='prompt = "prompt"\n', forward=', forward = "prompt"'))
        self.assertTrue(any("Ended" in b and "not registered" in b for b in bad), bad)

    def test_a_module_that_reports_a_hook_no_row_names_is_refused(self):
        good = SIGNAL.format(prompt='prompt = "prompt"\n', forward=', forward = "prompt"')
        bad = bench(good, MODULE.format(hook="Other"))
        self.assertTrue(any("Other" in b for b in bad), bad)


if __name__ == "__main__":
    unittest.main()
