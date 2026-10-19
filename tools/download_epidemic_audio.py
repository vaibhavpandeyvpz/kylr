"""Download licensed SFX through Epidemic's MCP API into an ignored local cache."""
import argparse
import hashlib
import json
from pathlib import Path
import time
import urllib.parse
import urllib.request
import uuid

from epidemic_mcp import EpidemicMCP, ROOT

CACHE = ROOT / "library/.local/epidemic"


def tool_data(result):
    if "structuredContent" in result:
        return result["structuredContent"]
    for block in result.get("content", []):
        if block.get("type") == "text":
            try:
                return json.loads(block["text"])
            except json.JSONDecodeError:
                continue
    raise ValueError("MCP tool returned no structured JSON content")


def safe_audio_url(url):
    parsed = urllib.parse.urlsplit(url)
    if parsed.scheme != "https" or not (parsed.hostname or "").endswith(".epidemicsound.com"):
        raise ValueError("Download URL is not an HTTPS Epidemic Sound CDN URL")
    return url


class AudioRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, request, file, code, message, headers, url):
        safe_audio_url(url)
        return super().redirect_request(request, file, code, message, headers, url)


def download(client, identifier, destination, kind="soundEffect"):
    identifier = str(uuid.UUID(identifier))
    options = {"fileType": "WAV", "bundle": False}
    if kind=="recording":
        options["stemType"]="FULL"
    result = tool_data(client.call("DownloadRecording" if kind=="recording" else "DownloadSoundEffect", {
        "id": identifier, "options": options}))
    url = safe_audio_url(result["data"][kind+"Download"]["assetUrl"])
    temporary = destination.with_suffix(".partial")
    try:
        # The API key is sent only to MCP, never to the audio CDN.
        with urllib.request.build_opener(AudioRedirect()).open(url, timeout=60) as response:
            safe_audio_url(response.url)
            with temporary.open("wb") as output:
                total = 0
                while block := response.read(1024 * 1024):
                    total += len(block)
                    if total > 512 * 1024 * 1024:
                        raise ValueError("Sound effect exceeds the 512 MiB download limit")
                    output.write(block)
        with temporary.open("rb") as stream:
            header = stream.read(12)
        if header[:4] not in (b"RIFF", b"RF64") or header[8:12] != b"WAVE":
            raise ValueError("Epidemic did not return WAV audio")
        temporary.replace(destination)
    finally:
        temporary.unlink(missing_ok=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--history", type=Path, help="JSON history pages or [{id: UUID}] list")
    group.add_argument("--id", help="One sound-effect UUID")
    group.add_argument("--search", help="Search the catalog; does not download or substitute cues")
    group.add_argument("--tools", action="store_true", help="Show available MCP tool input schemas")
    args = parser.parse_args()
    CACHE.mkdir(parents=True, exist_ok=True)
    client = EpidemicMCP().connect()
    if args.tools:
        print(json.dumps(client.tools, indent=2))
        return
    if args.search:
        result = tool_data(client.call("SearchSoundEffects", {"query": {"term": args.search}, "first": 20}))
        for node in result["data"]["soundEffects"]["nodes"]:
            item = node["soundEffect"]
            print(item["id"], item["title"])
        return
    if args.id:
        entries = [{"id": args.id}]
    else:
        raw = args.history.read_text(encoding="utf-8-sig")
        # Accept pasted adjacent JSON history pages as well as one JSON object.
        decoder = json.JSONDecoder()
        entries = []
        while raw.strip():
            page, position = decoder.raw_decode(raw.lstrip())
            raw = raw.lstrip()[position:]
            entries.extend(page if isinstance(page, list) else page.get("results", []))
    ids = sorted({str(uuid.UUID(entry.get("kosmosId") or entry["id"])) for entry in entries})
    metadata = {}
    for offset in range(0, len(ids), 25):
        result = tool_data(client.call("SearchSoundEffects", {
            "filter": {"soundEffectIDs": ids[offset:offset+25]}, "first": 25}))
        for node in result["data"]["soundEffects"]["nodes"]:
            item = node["soundEffect"]
            metadata[item["id"]] = {"id": item["id"], "title": item["title"],
                                     "duration_ms": item["audioFile"]["durationInMilliseconds"], "kind":"soundEffect"}
    # Account download histories may also contain music recordings.
    remaining = [identifier for identifier in ids if identifier not in metadata]
    for offset in range(0,len(remaining),25):
        result=tool_data(client.call("SearchRecordings", {
            "filter":{"recordingIDs":remaining[offset:offset+25]},"first":25}))
        for node in result["data"]["recordings"]["nodes"]:
            item=node["recording"]
            metadata[item["id"]]={"id":item["id"],"title":item["title"],
                                  "duration_ms":item["audioFile"]["durationInMilliseconds"],"kind":"recording"}
    report_path = CACHE / "downloads.json"
    report = json.loads(report_path.read_text()) if report_path.exists() else {}
    failures = 0
    for index, identifier in enumerate(ids, 1):
        destination = CACHE / (identifier + ".wav")
        try:
            if identifier not in metadata:
                raise ValueError("ID is not available in the sound-effect catalog")
            previous = report.get(identifier, {})
            current_hash = hashlib.sha256(destination.read_bytes()).hexdigest() if destination.exists() else None
            if not current_hash or current_hash != previous.get("sha256"):
                for attempt in range(3):
                    try:
                        download(client, identifier, destination, metadata[identifier]["kind"])
                        break
                    except (ValueError, OSError):
                        if attempt == 2:
                            raise
                        time.sleep(2 ** attempt)
            record = {**metadata[identifier], "sha256": hashlib.sha256(destination.read_bytes()).hexdigest(),
                      "bytes": destination.stat().st_size, "file": destination.name}
            report[identifier] = record
            report_path.write_text(json.dumps(report, indent=2) + "\n")
            print(f"DOWNLOADED {index}/{len(ids)} {identifier} {record['title']}", flush=True)
        except (ValueError, OSError, KeyError):
            # Signed URLs and credential-bearing response bodies stay out of logs.
            failures += 1
            print(f"FAILED {index}/{len(ids)} {identifier}; check license/access or retry", flush=True)
    print(f"Epidemic cache complete: {len(ids)-failures}/{len(ids)} requested assets available", flush=True)
    if failures:
        raise SystemExit(1)


if __name__ == "__main__":
    try:
        main()
    except (ValueError, OSError, KeyError) as error:
        raise SystemExit(f"Epidemic setup failed ({type(error).__name__}); check credentials, input and network access") from None
