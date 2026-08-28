import json

from orion.cli.main import main


def test_status_command_outputs_json(capsys) -> None:
    main(["status"])
    payload = json.loads(capsys.readouterr().out)
    assert payload["root"] == "src/orion"
    assert payload["mode"] == "local"


def test_analyze_command_outputs_symbol(capsys) -> None:
    main(["analyze", "AAPL", "--prices", "100", "101", "102", "103", "104", "105", "106"])
    payload = json.loads(capsys.readouterr().out)
    assert payload["asset"] == "AAPL"
    assert payload["prediction"]["model_name"] == "ensemble"


def test_doctor_command_reports_risk_protection(capsys) -> None:
    main(["doctor"])
    payload = json.loads(capsys.readouterr().out)
    assert payload["status"] == "HEALTHY"
    assert payload["checks"]["live_trading_disabled"] == "PASS"
