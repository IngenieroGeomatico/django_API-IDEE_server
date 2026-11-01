"""Captura el corpus golden del servidor heredado (T-00.1).

Uso:
    python scripts/capture_golden.py --base-url https://componentes.idee.es/api-idee

Guarda, por cada URL, un JSON con estado y cabeceras y un fichero aparte con el
cuerpo. No sobrescribe capturas existentes salvo ``--force``.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import httpx
import yaml

ROOT = Path(__file__).resolve().parent.parent
CORPUS = ROOT / "tests" / "golden" / "urls.yaml"
OUTPUT = ROOT / "tests" / "golden" / "responses"


def load_corpus() -> dict:
    with CORPUS.open(encoding="utf-8") as handle:
        return yaml.safe_load(handle)


def capture(
    client: httpx.Client,
    base_url: str,
    entry: dict,
    output: Path,
    *,
    force: bool,
) -> None:
    identifier = entry["id"]
    metadata_path = output / f"{identifier}.json"
    if metadata_path.exists() and not force:
        print(f"= {identifier}: ya capturado")
        return

    url = base_url.rstrip("/") + entry["path"]
    method = entry.get("method", "GET").upper()
    request_kwargs = {}
    body = entry.get("body")
    if body and method != "GET":
        request_kwargs["data"] = body.get("fields", {})

    response = client.request(method, url, **request_kwargs)
    suffix = ".bin" if "image" in response.headers.get("Content-Type", "") else ".txt"
    body_path = output / f"{identifier}{suffix}"
    body_path.write_bytes(response.content)

    metadata = {
        "id": identifier,
        "url": url,
        "method": method,
        "status": response.status_code,
        "headers": dict(response.headers),
        "body_file": body_path.name,
        "body_bytes": len(response.content),
        "expected": entry.get("expect"),
    }
    metadata_path.write_text(json.dumps(metadata, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"+ {identifier}: {response.status_code} ({len(response.content)} B)")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base-url", required=True)
    parser.add_argument("--force", action="store_true")
    parser.add_argument("--timeout", type=float, default=20.0)
    args = parser.parse_args()

    corpus = load_corpus()
    OUTPUT.mkdir(parents=True, exist_ok=True)

    with httpx.Client(
        timeout=args.timeout,
        follow_redirects=False,
        headers={"User-Agent": "api-idee-golden/1.0"},
    ) as client:
        for entry in corpus.get("urls", []):
            capture(client, args.base_url, entry, OUTPUT, force=args.force)


if __name__ == "__main__":
    main()
