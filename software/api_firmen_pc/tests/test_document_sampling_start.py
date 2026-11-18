"""Exercise the real PowerShell argument assembly without credentials or API execution."""

import json

import pytest
from test_private_api_start import SCRIPTS, ps_literal, run_shell


@pytest.mark.parametrize("options,expected", [
    ("-Documents 3 -SampleSeed 42", ["--documents", "3", "--sample-seed", "42"]),
    ("-AllDocuments", ["--all-documents"]),
    ("", ["--prompt-documents"]),
])
def test_private_framework_forwards_sampling_options_without_model_calls(tmp_path, options, expected):
    scripts = tmp_path / "scripts"
    scripts.mkdir()
    executable = tmp_path / ".venv/Scripts/participant-api.exe"
    executable.parent.mkdir(parents=True)
    executable.write_bytes(b"unused executable placeholder")
    (scripts / "set-api-environment.ps1").write_text("param($EnvFile, [switch]$NoPrompt)\n", encoding="utf-8")
    source = (SCRIPTS / "run-private-api.ps1").read_text(encoding="utf-8-sig")
    # Replace only the process invocation; real parameter binding and argument logic stay intact.
    invocation = "& $benchmarkExecutable @frameworkArguments"
    assert source.count(invocation) == 1
    source = source.replace(invocation, "Write-Output ($frameworkArguments | ConvertTo-Json -Compress); $global:LASTEXITCODE = 0")
    helper = scripts / "run-private-api.ps1"
    helper.write_text(source, encoding="utf-8-sig")
    result = run_shell(tmp_path, f"& {ps_literal(helper)} -Testframework -NoPrompt {options}\nexit $LASTEXITCODE")
    assert result.returncode == 0, result.stderr
    args = json.loads(result.stdout.strip())
    assert args[:4] == ["benchmark", "run", "--config", "testframework/config.yaml"]
    assert args[4:] == expected
