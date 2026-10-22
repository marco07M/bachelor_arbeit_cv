#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.10"
# dependencies = [
#     "httpx",
#     "openai",
#     "requests",
# ]
# ///
import base64
import os

import httpx
import openai
import requests


def download_bmw_ca_cert(
    path: str = "BMW_Trusted_Certificates_Latest.pem",
    ca_certificate_url: str = "https://trustbundle.bmwgroup.net/BMW_Trusted_Certificates_Latest.pem"
) -> str:
    """Download the CA certificate from BMW's PKI server.

    Checks if the CA certificate file already exists at the specified path.
    If it does not exist, it downloads the certificate from the specified URL
    and saves it to the path.

    Args:
        path: Path to save the CA certificate file.
        ca_certificate_url: URL to download the CA certificate from.

    Returns:
        Path to the downloaded CA certificate file.

    Raises:
        requests.HTTPError: If the request to download the certificate fails.
    """
    if os.path.exists(path):
        return path

    response = requests.get(ca_certificate_url)
    response.raise_for_status()

    with open(path, "wb") as f:
        f.write(response.content)

    return path

def get_access_token(
    client_id: str,
    client_secret: str,
    auth_endpoint: str = "https://emea.int.alpha.sso.bmwgroup.com/auth/oauth2/realms/root/realms/alpha/access_token",
) -> str:
    """Obtain an access token from the WebEAM service.

    Sends a request to the WebEAM service with the provided client ID and
    secret, and retrieves an access token for authenticating requests to
    the GATE.

    Args:
        client_id: The client ID obtained from WebEAM.
        client_secret: The client secret obtained from WebEAM.
        auth_endpoint: The endpoint to obtain the access token.

    Returns:
        The access token obtained from the WebEAM service.

    Raises:
        requests.HTTPError: If the request to obtain the access token fails.
    """
    data = {
        "grant_type": "client_credentials",
        "scope": f"machine2machine client_{client_id}",
    }
    credentials = base64.b64encode(f"{client_id}:{client_secret}".encode("utf-8")).decode("ascii")
    response = requests.post(
        auth_endpoint,
        headers={
            "Authorization": f"Basic {credentials}",
            "Content-Type": "application/x-www-form-urlencoded",
        },
        data=data,
    )
    if not response.ok:
        raise requests.HTTPError(
            f"{response.status_code} for {auth_endpoint}: {response.text}",
            response=response,
        )

    token = response.json().get("access_token")

    return token

def main() -> None:
    client_id = os.environ["CLIENT_ID"]
    client_secret = os.environ["CLIENT_SECRET"]

    with httpx.Client(
        headers={"x-apikey": os.environ["BMW_AI_API_KEY"]},
        verify=download_bmw_ca_cert(),
        timeout=30,
    ) as http_client:
        client = openai.OpenAI(
            base_url="https://api.int.gcp.cloud.bmw/llmapi/v1",
            api_key=get_access_token(
                client_id=client_id,
                client_secret=client_secret,
            ),
            http_client=http_client,
        )
        response = client.chat.completions.create(
            model=os.environ["BMW_LLM_MODEL"],
            messages=[{"role": "user", "content": "Hello, world!"}],
        )

    print(response.choices[0].message.content)


if __name__ == "__main__":
    main()
