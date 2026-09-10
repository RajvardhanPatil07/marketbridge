from pathlib import Path
import subprocess


ROOT = Path(__file__).resolve().parents[1]


def test_local_serve_loads_backend_provider_environment():
    command = subprocess.run(
        ["make", "-n", "serve"], cwd=ROOT, check=True, capture_output=True, text=True
    ).stdout

    assert "uv run --env-file .env uvicorn" in command
