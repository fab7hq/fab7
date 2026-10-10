"""fab7's check refuses a harness file that does not say where its received prompt is
(Weft ADR-0033 D4), on made-up harnesses."""

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


def bench(signal):
    tmp = pathlib.Path(tempfile.mkdtemp())
    plugin = tmp / "plugins" / "loom"
    (plugin / "hooks").mkdir(parents=True)
    (plugin / "hooks.json").write_text(HOOKS)
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


if __name__ == "__main__":
    unittest.main()
