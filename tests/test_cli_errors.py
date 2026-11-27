import sys
import stat
from types import SimpleNamespace

import main as cli


def invoke_cli(monkeypatch, capsys, input_path, output_path, secret="synthetic-secret"):
    monkeypatch.setattr(
        sys,
        "argv",
        ["main.py", "--input", str(input_path), "--output", str(output_path)],
    )
    if secret is None:
        monkeypatch.delenv("RAKSHA_SECRET", raising=False)
    else:
        monkeypatch.setenv("RAKSHA_SECRET", secret)
    result = cli.main()
    captured = capsys.readouterr()
    assert captured.out == ""
    return result, captured.err


def test_invalid_input_reports_only_allowlisted_code(tmp_path, monkeypatch, capsys):
    result, error = invoke_cli(monkeypatch, capsys, tmp_path / "patient-secret", tmp_path / "out")

    assert result == 1
    assert error == "ERROR INVALID_INPUT_DIRECTORY\n"


def test_cli_rejects_reparse_input_before_resolving_it(tmp_path, monkeypatch, capsys):
    input_path = tmp_path / "input"
    input_path.mkdir()
    original_lstat = type(input_path).lstat

    def report_reparse(path):
        if path == input_path:
            return SimpleNamespace(st_mode=stat.S_IFLNK, st_file_attributes=0)
        return original_lstat(path)

    monkeypatch.setattr(type(input_path), "lstat", report_reparse)
    result, error = invoke_cli(monkeypatch, capsys, input_path, tmp_path / "out")

    assert result == 1
    assert error == "ERROR INVALID_INPUT_DIRECTORY\n"


def test_unsafe_output_reports_only_allowlisted_code(tmp_path, monkeypatch, capsys):
    input_path = tmp_path / "input"
    input_path.mkdir()
    result, error = invoke_cli(monkeypatch, capsys, input_path, input_path)

    assert result == 1
    assert error == "ERROR UNSAFE_OUTPUT_DIRECTORY\n"


def test_missing_secret_reports_only_allowlisted_code(tmp_path, monkeypatch, capsys):
    input_path = tmp_path / "input"
    input_path.mkdir()
    result, error = invoke_cli(monkeypatch, capsys, input_path, tmp_path / "out", secret=None)

    assert result == 1
    assert error == "ERROR SECRET_MISSING\n"


def test_model_initialization_error_does_not_expose_exception(
    tmp_path, monkeypatch, capsys
):
    input_path = tmp_path / "input"
    input_path.mkdir()

    def fail_model(*args, **kwargs):
        raise RuntimeError("synthetic secret and patient name")

    monkeypatch.setattr(cli, "load_model", fail_model)
    result, error = invoke_cli(monkeypatch, capsys, input_path, tmp_path / "out")

    assert result == 1
    assert error == "ERROR MODEL_UNAVAILABLE\n"


def test_output_error_does_not_expose_exception(tmp_path, monkeypatch, capsys):
    input_path = tmp_path / "input"
    input_path.mkdir()
    monkeypatch.setattr(cli, "load_model", lambda required=True: object())

    def fail_output(*args, **kwargs):
        raise OSError("patient-secret path and secret value")

    monkeypatch.setattr(cli, "run_pipeline", fail_output)
    result, error = invoke_cli(monkeypatch, capsys, input_path, tmp_path / "out")

    assert result == 1
    assert error == "ERROR OUTPUT_WRITE_FAILED\n"


def test_processing_error_does_not_expose_exception(tmp_path, monkeypatch, capsys):
    input_path = tmp_path / "input"
    input_path.mkdir()
    monkeypatch.setattr(cli, "load_model", lambda required=True: object())

    def fail_processing(*args, **kwargs):
        raise RuntimeError("patient-secret and arbitrary exception text")

    monkeypatch.setattr(cli, "run_pipeline", fail_processing)
    result, error = invoke_cli(monkeypatch, capsys, input_path, tmp_path / "out")

    assert result == 1
    assert error == "ERROR PROCESSING_FAILED\n"
