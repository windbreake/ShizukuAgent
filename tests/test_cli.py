from __future__ import annotations

import unittest
from io import StringIO
from unittest.mock import patch

from app.cli import _build_parser, main, run_chat


class FakeService:
    def __init__(self) -> None:
        self.runs: list[dict] = []
        self.resets: list[tuple[str, str]] = []

    def default_persona(self) -> str:
        return "shizuku"

    def available_personas(self) -> list[dict]:
        return [{"id": "shizuku"}, {"id": "kaguya"}]

    def run(self, question: str, **options):
        self.runs.append({"question": question, **options})
        return {"reply": f"收到:{question}", "active_model": "primary"}

    def reset_session(self, thread_id: str, persona: str | None = None) -> None:
        self.resets.append((thread_id, persona or self.default_persona()))


class CliTests(unittest.TestCase):
    def test_parser_defaults_to_chat(self) -> None:
        args = _build_parser().parse_args([])
        self.assertIsNone(args.command)

    def test_parser_web_flags(self) -> None:
        args = _build_parser().parse_args(["web", "--no-frontend", "--no-reload"])
        self.assertEqual("web", args.command)
        self.assertTrue(args.no_frontend)
        self.assertTrue(args.no_reload)

    def test_chat_loop_handles_commands_and_messages(self) -> None:
        service = FakeService()
        inputs = iter(["/help", "/persona kaguya", "你好", "/clear", "/exit"])
        with patch("builtins.input", side_effect=lambda _: next(inputs)), patch("sys.stdout", new=StringIO()) as stdout:
            code = run_chat(service)

        self.assertEqual(0, code)
        self.assertEqual("你好", service.runs[0]["question"])
        self.assertEqual("kaguya", service.runs[0]["persona"])
        self.assertEqual([("cli:kaguya", "kaguya")], service.resets)
        self.assertIn("已切换人格: kaguya", stdout.getvalue())
        self.assertIn("收到:你好", stdout.getvalue())

    def test_main_dispatches_web(self) -> None:
        with patch("app.cli.run_web", return_value=7) as mocked:
            code = main(["web", "--no-frontend"])
        mocked.assert_called_once_with(no_frontend=True, no_reload=False)
        self.assertEqual(7, code)


if __name__ == "__main__":
    unittest.main()
