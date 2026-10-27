"""Check private launch helpers in child shells, using synthetic credentials only."""

import shutil
import subprocess
import sys
from pathlib import Path

import pytest

SCRIPTS = Path(__file__).resolve().parents[1] / "scripts"
VARIABLES = (
    "BMW_AI_API_KEY",
    "BMW_AI_CLIENT_ID",
    "BMW_AI_CLIENT_SECRET",
    "BMW_AI_BASE_URL",
    "BMW_AI_TOKEN_URL",
    "BMW_AI_API_KEY_HEADER",
    "BMW_LLM_MODEL",
    "BMW_VLM_MODEL",
    "BMW_AI_CHAT_PATH",
    "BMW_AI_SCOPE",
    "BMW_AI_RESOURCE",
    "BMW_AI_CA_BUNDLE",
    "BMW_CA_BUNDLE",
    "LLM_API_BASE_URL",
    "LLM_API_MODEL",
    "LLM_API_KEY",
    "VLM_API_BASE_URL",
    "VLM_API_MODEL",
    "VLM_API_KEY",
)
FAKE_KEY = "synthetic-private-test-key-54"


def ps_literal(value):
    return "'" + str(value).replace("'", "''") + "'"


def run_shell(tmp_path, body):
    shell = shutil.which("powershell") or shutil.which("pwsh")
    if not shell:
        pytest.skip("PowerShell required to exercise the Windows launch helpers")
    # Do not inspect or use any existing credential values inherited by the child.
    clear = "\n".join(
        f"[Environment]::SetEnvironmentVariable('{name}', $null, 'Process')" for name in VARIABLES
    )
    path = tmp_path / "synthetic-check.ps1"
    path.write_text("$ErrorActionPreference = 'Stop'\n" + clear + "\n" + body, encoding="utf-8-sig")
    return subprocess.run(
        [shell, "-NoProfile", "-NonInteractive", "-ExecutionPolicy", "RemoteSigned", "-File", str(path)],
        capture_output=True,
        text=True,
        timeout=20,
    )


def test_external_env_is_literal_process_only_and_not_printed(tmp_path):
    external = tmp_path / "synthetic.env"
    external.write_text(
        f"# synthetic only\nBMW_AI_API_KEY='{FAKE_KEY}'\nBMW_AI_CLIENT_ID=fake-client\n"
        "BMW_AI_CLIENT_SECRET=\"$(throw 'not executable')`n$HOME\"\n"
        "BMW_CA_BUNDLE=C:\\synthetic\\company-ca.pem\n",
        encoding="utf-8",
    )
    expected_literal = "$(throw 'not executable')`n$HOME"
    result = run_shell(
        tmp_path,
        f"""
. {ps_literal(SCRIPTS / "set-api-environment.ps1")} -EnvFile {ps_literal(external)} -NoPrompt
if ($env:BMW_AI_API_KEY -cne {ps_literal(FAKE_KEY)}) {{ throw 'Synthetic key mismatch' }}
if ($env:BMW_AI_CLIENT_SECRET -cne {ps_literal(expected_literal)}) {{ throw 'Value was interpreted' }}
if ($env:BMW_AI_CA_BUNDLE -cne 'C:\\synthetic\\company-ca.pem') {{ throw 'Remote CA alias was not imported' }}
& {ps_literal(sys.executable)} -c "import os; assert os.environ['BMW_AI_API_KEY'] == '{FAKE_KEY}'"
if ($LASTEXITCODE -ne 0) {{ throw 'Application did not inherit synthetic key' }}
Write-Output 'Synthetic process inheritance OK'
""",
    )
    assert result.returncode == 0, result.stderr
    assert "Synthetic process inheritance OK" in result.stdout
    assert FAKE_KEY not in result.stdout + result.stderr
    assert expected_literal not in result.stdout + result.stderr


def test_defaults_match_test_script_and_only_model_and_credentials_need_input(tmp_path):
    result = run_shell(
        tmp_path,
        f"""
$env:BMW_AI_API_KEY = 'synthetic-api-key'
$env:BMW_AI_CLIENT_ID = 'synthetic-client-id'
$env:BMW_AI_CLIENT_SECRET = 'synthetic-client-secret'
$env:BMW_VLM_MODEL = 'synthetic-vision-model'
. {ps_literal(SCRIPTS / "set-api-environment.ps1")} -NoPrompt
if ($env:BMW_AI_BASE_URL -cne 'https://api.int.gcp.cloud.bmw/llmapi/v1') {{ throw 'API base URL default mismatch' }}
if ($env:BMW_AI_TOKEN_URL -cne 'https://emea.int.alpha.sso.bmwgroup.com/auth/oauth2/realms/root/realms/alpha/access_token') {{ throw 'Token URL default mismatch' }}
if ($env:BMW_AI_API_KEY_HEADER -cne 'x-apikey') {{ throw 'API key header default mismatch' }}
if ($env:BMW_AI_SCOPE -cne 'machine2machine') {{ throw 'OAuth scope default mismatch' }}
if ($env:BMW_AI_CHAT_PATH -cne 'chat/completions') {{ throw 'Chat path default mismatch' }}
if (-not (Test-Path -LiteralPath $env:BMW_AI_CA_BUNDLE -PathType Leaf)) {{ throw 'Bundled CA certificate was not selected' }}
if ($env:BMW_LLM_MODEL) {{ throw 'The unused text model should not be requested' }}
Write-Output 'Defaults and required inputs OK'
""",
    )
    assert result.returncode == 0, result.stderr
    assert "Defaults and required inputs OK" in result.stdout
    assert "synthetic-" not in result.stdout + result.stderr


@pytest.mark.parametrize(
    "content",
    [f"INVALID {FAKE_KEY}", f"PATH={FAKE_KEY}", f"BMW_AI_API_KEY={FAKE_KEY}\nBMW_AI_API_KEY=duplicate"],
)
def test_invalid_env_is_rejected_before_loading_any_values(tmp_path, content):
    external = tmp_path / "synthetic.env"
    external.write_text(content, encoding="utf-8")
    result = run_shell(
        tmp_path,
        f"""
try {{
    . {ps_literal(SCRIPTS / "set-api-environment.ps1")} -EnvFile {ps_literal(external)} -NoPrompt
    throw 'Expected rejection'
}} catch {{
    if ($_.Exception.Message -eq 'Expected rejection') {{ throw }}
    if ($env:BMW_AI_API_KEY) {{ throw 'Partially imported invalid file' }}
    Write-Output $_.Exception.Message
}}
""",
    )
    assert result.returncode == 0, result.stderr
    assert "Zeile" in result.stdout and FAKE_KEY not in result.stdout + result.stderr


def test_env_inside_repository_is_rejected_before_reading(tmp_path):
    # This deliberately does not exist: location must be rejected before a read is attempted.
    internal = SCRIPTS.parent / "synthetic-private-test.env"
    result = run_shell(
        tmp_path,
        f"""
try {{
    . {ps_literal(SCRIPTS / "set-api-environment.ps1")} -EnvFile {ps_literal(internal)} -NoPrompt
    throw 'Expected rejection'
}} catch {{
    if ($_.Exception.Message -eq 'Expected rejection') {{ throw }}
    Write-Output $_.Exception.Message
}}
""",
    )
    assert result.returncode == 0, result.stderr
    assert "ausserhalb" in result.stdout


def test_check_only_launches_no_api_and_clears_process_credentials(tmp_path):
    if sys.platform != "win32":
        pytest.skip("Launcher uses the Windows project executable")
    external = tmp_path / "synthetic.env"
    external.write_text(
        f"BMW_AI_API_KEY={FAKE_KEY}\nBMW_AI_CLIENT_ID=fake-client\nBMW_AI_CLIENT_SECRET=fake-secret\n"
        "BMW_AI_BASE_URL=https://synthetic.invalid/v1\nBMW_AI_TOKEN_URL=https://synthetic.invalid/token\n"
        "BMW_AI_API_KEY_HEADER=X-Test-Key\nBMW_LLM_MODEL=synthetic-text\nBMW_VLM_MODEL=synthetic-vision\n"
        "BMW_CA_BUNDLE=C:\\synthetic\\company-ca.pem\n",
        encoding="utf-8",
    )
    result = run_shell(
        tmp_path,
        f"""
& {ps_literal(SCRIPTS / "run-private-api.ps1")} -EnvFile {ps_literal(external)} -NoPrompt -CheckOnly
if ($LASTEXITCODE -ne 0) {{ throw 'Configuration check failed' }}
if ($env:BMW_AI_API_KEY -or $env:BMW_AI_CLIENT_SECRET -or $env:BMW_AI_CLIENT_ID -or
    $env:BMW_AI_CA_BUNDLE -or $env:BMW_CA_BUNDLE) {{
    throw 'Credentials were retained'
}}
Write-Output 'Private launcher cleanup OK'
""",
    )
    assert result.returncode == 0, result.stderr
    assert '"network_contacted": false' in result.stdout and "Private launcher cleanup OK" in result.stdout
    assert FAKE_KEY not in result.stdout + result.stderr


def test_launch_failure_also_clears_credentials_without_printing_values(tmp_path):
    if sys.platform != "win32":
        pytest.skip("Launcher uses the Windows project executable")
    external = tmp_path / "synthetic-invalid.env"
    external.write_text(f"INVALID {FAKE_KEY}", encoding="utf-8")
    result = run_shell(
        tmp_path,
        f"""
$env:BMW_AI_API_KEY = {ps_literal(FAKE_KEY)}
try {{
    & {ps_literal(SCRIPTS / "run-private-api.ps1")} -EnvFile {ps_literal(external)} -NoPrompt -CheckOnly
    throw 'Expected rejection'
}} catch {{
    if ($_.Exception.Message -eq 'Expected rejection') {{ throw }}
    if ($env:BMW_AI_API_KEY) {{ throw 'Credential retained after failure' }}
    Write-Output 'Private launcher failure cleanup OK'
}}
""",
    )
    assert result.returncode == 0, result.stderr
    assert "Private launcher failure cleanup OK" in result.stdout
    assert FAKE_KEY not in result.stdout + result.stderr
