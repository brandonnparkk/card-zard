import zlib
from pathlib import Path

import httpx


PROJECT_ROOT = Path(__file__).resolve().parents[2]
RAW_DATA_DIR = PROJECT_ROOT / "data" / "raw"
OUTPUT_FILE = RAW_DATA_DIR / "oracle-cards.jsonl"

BULK_DATA_URL = "https://api.scryfall.com/bulk-data"

HEADERS = {
    "User-Agent": "mtg-deck-ai-assistant/0.1",
    "Accept": "application/json",
}


def get_oracle_cards_url() -> str:
    """Find Scryfall's current Oracle Cards bulk-data download URL."""
    print("Fetching Scryfall bulk-data metadata...")

    with httpx.Client(
        headers=HEADERS,
        timeout=30.0,
        follow_redirects=True,
    ) as client:
        response = client.get(BULK_DATA_URL)
        response.raise_for_status()

    payload = response.json()

    for dataset in payload["data"]:
        if dataset["type"] == "oracle_cards":
            # Scryfall now only publishes gzipped JSON Lines bulk files.
            return dataset["jsonl_download_uri"]

    raise RuntimeError("Could not find the Oracle Cards bulk dataset.")


def download_file(url: str, destination: Path) -> None:
    """Stream a gzipped file to disk, decompressing as it downloads."""
    print(f"Downloading Oracle Cards...")
    print(f"Destination: {destination}")

    destination.parent.mkdir(parents=True, exist_ok=True)

    with httpx.stream(
        "GET",
        url,
        headers=HEADERS,
        timeout=None,
        follow_redirects=True,
    ) as response:
        response.raise_for_status()

        total_bytes = int(response.headers.get("content-length", 0))
        downloaded_bytes = 0
        # wbits=31 tells zlib to expect a gzip header.
        decompressor = zlib.decompressobj(wbits=31)

        with destination.open("wb") as file:
            for chunk in response.iter_raw(chunk_size=1024 * 1024):
                file.write(decompressor.decompress(chunk))
                downloaded_bytes += len(chunk)

                if total_bytes:
                    percent = downloaded_bytes / total_bytes * 100
                    print(
                        f"\rProgress: {percent:6.2f}%",
                        end="",
                    )

            file.write(decompressor.flush())

    print("\nDownload complete.")


def main() -> None:
    url = get_oracle_cards_url()
    print(f"Oracle Cards URL: {url}")

    download_file(url, OUTPUT_FILE)

    print(f"Saved to: {OUTPUT_FILE}")


if __name__ == "__main__":
    main()