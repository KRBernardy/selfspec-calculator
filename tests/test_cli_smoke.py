import json
from pathlib import Path

from selfspec_calculator.cli import main


def test_cli_runs_on_examples(capsys) -> None:
    repo_root = Path(__file__).resolve().parents[1]
    rc = main(
        [
            "--model",
            str(repo_root / "examples" / "model.yaml"),
            "--hardware",
            str(repo_root / "examples" / "hardware.yaml"),
            "--stats",
            str(repo_root / "examples" / "stats.json"),
            "--prompt-lengths",
            "64",
            "128",
        ]
    )
    assert rc == 0

    out = capsys.readouterr().out
    payload = json.loads(out)
    assert payload["k"] == 4
    assert payload["reuse_policy"] in {"reuse", "reread"}
    assert isinstance(payload["points"], list)
    assert len(payload["points"]) == 2
    assert "area" in payload

