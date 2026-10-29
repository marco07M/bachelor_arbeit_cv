"""Workers process documents with networking disabled, including implicit model downloads."""

import os
import socket


def disable_network():
    for name, value in {
        "HF_HUB_OFFLINE": "1", "TRANSFORMERS_OFFLINE": "1", "HF_HUB_DISABLE_TELEMETRY": "1",
        "PADDLE_PDX_DISABLE_MODEL_SOURCE_CHECK": "True", "PADDLE_PDX_DISABLE_TELEMETRY": "True",
        "DO_NOT_TRACK": "1", "FLAGS_enable_pir_api": "1",
    }.items():
        os.environ[name] = value

    def blocked(*args, **kwargs):
        raise OSError("Network disabled in local document worker; provision models with setup-structures")

    socket.create_connection = blocked
    socket.socket.connect = blocked
    socket.socket.connect_ex = blocked
