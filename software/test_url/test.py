import os

import main
import requests


def required_environment(name: str) -> str:
    value = os.environ.get(name, "").strip()
    if not value:
        raise SystemExit(f"Fehlende Umgebungsvariable: {name}")
    return value


client_id = required_environment("CLIENT_ID")
client_secret = required_environment("CLIENT_SECRET")
api_key = required_environment("BMW_AI_API_KEY")
base_url = "https://api.int.gcp.cloud.bmw/llmapi/v1"

access_token = main.get_access_token(
    client_id=client_id,
    client_secret=client_secret,
)
cert_path = main.download_bmw_ca_cert()

response = requests.get(
    f"{base_url}/models",
    headers={
        "x-apikey": api_key,
        "Authorization": f"Bearer {access_token}",
    },
    verify=cert_path,
    timeout=30,
)
response.raise_for_status()

payload = response.json()
if not isinstance(payload, dict) or "data" not in payload:
    keys = ", ".join(payload.keys()) if isinstance(payload, dict) else type(payload).__name__
    raise RuntimeError(
        f"Modelllisten-Antwort enthält kein 'data' (HTTP {response.status_code}; "
        f"Antwortstruktur: {keys}). GATE kann /models eventuell nicht unterstützen."
    )

models = payload["data"]
if not isinstance(models, list):
    raise RuntimeError("Das Feld 'data' in der Modelllisten-Antwort ist keine Liste.")

for model in models:
    if isinstance(model, dict) and isinstance(model.get("id"), str):
        print(model["id"])
