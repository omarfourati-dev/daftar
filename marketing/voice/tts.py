#!/usr/bin/env python3
"""Sprachausgabe für die Daftar-Videos über Azure Neural TTS (REST, nur Python-Standardbibliothek).

Der Azure-Schlüssel bleibt in diesem Skript: Er wird nur aus ~/.claude/dp/tokens-for-scripts.json gelesen
(data["azure"]["token"], data["azure"]["region"]), ersatzweise aus den Umgebungsvariablen AZURE_TOKEN / AZURE_REGION.
Er wird nie ausgegeben, nie geloggt, nie als Argument angenommen. Fehlermeldungen nennen nur HTTP-Status und Art.

Aufrufe:
  python tts.py --check                       winziger Test-Aufruf → "OK" oder "Azure-Schlüssel fehlt/ungültig"
  python tts.py --jobs jobs.json --out m.json  Aufträge sprechen lassen (Cache), Ergebnisliste schreiben
  python tts.py --jobs … --out … --offline     nur den Cache lesen (kein Netz); fehlende Einträge mit "wav": null

jobs.json: [{ "id": "...", "voice": "fr-FR-DeniseNeural", "lang": "fr-FR", "body": "<SSML-Inhalt der Stimme>",
             "rate": "+0%" (optional) }]
m.json:    [{ "id": "...", "wav": "<absoluter Pfad>" | null, "seconds": 2.48 | null, "cached": true }]
Exit-Codes: 0 OK · 1 Fehler bei einem Auftrag · 2 Schlüssel fehlt/ungültig (Ursache ohne Werte auf stderr) · 3 Netz

Cache: marketing/voice/cache/<sha256(Stimme + SSML)>.wav – derselbe Text wird nie zweimal bezahlt.
Netzwerk: ausschließlich https://<region>.tts.speech.microsoft.com/cognitiveservices/v1.
"""
from __future__ import annotations

import argparse
import hashlib
import http.client
import json
import os
import re
import struct
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

HERE = Path(__file__).resolve().parent
CACHE = HERE / "cache"
TOKENS = Path.home() / ".claude" / "dp" / "tokens-for-scripts.json"
FORMAT = "riff-48khz-16bit-mono-pcm"
REGION_RE = re.compile(r"^[a-z0-9]{2,32}$")
MSG_KEY = "Azure-Schlüssel fehlt/ungültig"


class KeyError_(Exception):
    """Schlüssel fehlt oder wurde abgelehnt. Trägt nur eine Ursachen-Kategorie, nie einen Wert."""

    def __init__(self, why: str = "abgelehnt"):
        super().__init__(why)
        self.why = why


def _credentials() -> tuple[str, str]:
    token = region = None
    file_state = "Datei fehlt"
    try:
        data = json.loads(TOKENS.read_text(encoding="utf-8"))
        az = data.get("azure") if isinstance(data, dict) else None
        file_state = "kein Abschnitt azure" if not isinstance(az, dict) else "ok"
        if isinstance(az, dict):
            token, region = az.get("token"), az.get("region")
    except FileNotFoundError:
        pass
    except Exception:  # kaputtes JSON o. Ä. → Fallback; Inhalt wird nie gemeldet
        file_state = "Datei nicht lesbar (JSON)"
    if not token:
        token = os.environ.get("AZURE_TOKEN")
    # the region is no secret: AZURE_REGION may override the file (e.g. a wrongly copied region), the key never
    region = os.environ.get("AZURE_REGION") or region
    if not token or not isinstance(token, str):
        raise KeyError_(f"kein Schlüssel gefunden (tokens-for-scripts.json: {file_state}; AZURE_TOKEN nicht gesetzt)")
    region = (region or "").strip().lower() if isinstance(region, str) else ""
    if not REGION_RE.match(region):
        raise KeyError_("Region fehlt oder hat kein gültiges Format (azure.region bzw. AZURE_REGION)")
    return token.strip(), region


def ssml_for(voice: str, lang: str, body: str, rate: str | None = None) -> str:
    inner = f'<prosody rate="{rate}">{body}</prosody>' if rate and rate not in ("0%", "+0%") else body
    return (
        '<speak version="1.0" xmlns="http://www.w3.org/2001/10/synthesis" '
        f'xmlns:mstts="https://www.w3.org/2001/mstts" xml:lang="{lang}">'
        f'<voice name="{voice}">{inner}</voice></speak>'
    )


def _synthesize(ssml: str, creds: tuple[str, str], tries: int = 6) -> bytes:
    token, region = creds
    url = f"https://{region}.tts.speech.microsoft.com/cognitiveservices/v1"
    req = urllib.request.Request(
        url,
        data=ssml.encode("utf-8"),
        method="POST",
        headers={
            "Ocp-Apim-Subscription-Key": token,
            "Content-Type": "application/ssml+xml",
            "X-Microsoft-OutputFormat": FORMAT,
            "User-Agent": "daftar-marketing-tts",
        },
    )
    delay = 3.0
    for attempt in range(tries):
        try:
            with urllib.request.urlopen(req, timeout=60) as r:
                audio = r.read()
            if audio[:4] != b"RIFF" or len(audio) < 100:
                raise RuntimeError("Antwort ist keine WAV-Datei")
            return audio
        except urllib.error.HTTPError as e:
            if e.code in (401, 403):
                raise KeyError_(f"von Azure abgelehnt (HTTP {e.code})") from None
            if e.code in (429, 500, 502, 503, 504) and attempt < tries - 1:
                wait = delay
                ra = e.headers.get("Retry-After") if e.headers else None
                if ra and ra.isdigit():
                    wait = max(wait, float(ra))
                time.sleep(wait)
                delay = min(delay * 2, 60)
                continue
            raise RuntimeError(f"Azure TTS: HTTP {e.code}") from None
        except urllib.error.URLError as e:
            if attempt < tries - 1:
                time.sleep(delay)
                delay = min(delay * 2, 60)
                continue
            raise RuntimeError(f"Azure TTS nicht erreichbar ({type(e.reason).__name__})") from None
        except (http.client.IncompleteRead, ConnectionError, TimeoutError) as e:
            # the connection broke off mid-answer (seen with long tutorial texts): just ask again
            if attempt < tries - 1:
                time.sleep(delay)
                delay = min(delay * 2, 60)
                continue
            raise RuntimeError(f"Azure TTS: Verbindung abgebrochen ({type(e).__name__})") from None
    raise RuntimeError("Azure TTS: keine Antwort")


def wav_seconds(data: bytes) -> float:
    """Dauer aus dem RIFF-Kopf (fmt + data)."""
    if data[:4] != b"RIFF" or data[8:12] != b"WAVE":
        raise ValueError("keine WAV-Datei")
    p, rate, block, size = 12, None, None, None
    while p + 8 <= len(data):
        cid, clen = data[p:p + 4], struct.unpack("<I", data[p + 4:p + 8])[0]
        if cid == b"fmt ":
            _, ch, rate, _, block, _ = struct.unpack("<HHIIHH", data[p + 8:p + 24])
        elif cid == b"data":
            size = min(clen, len(data) - p - 8)
            break
        p += 8 + clen + (clen & 1)
    if not rate or not block or size is None:
        raise ValueError("WAV ohne fmt/data")
    return size / block / rate


def cache_path(voice: str, ssml: str) -> Path:
    h = hashlib.sha256((voice + "\n" + ssml).encode("utf-8")).hexdigest()[:32]
    return CACHE / f"{h}.wav"


def cmd_check() -> int:
    try:
        creds = _credentials()
        _synthesize(ssml_for("fr-FR-DeniseNeural", "fr-FR", "OK"), creds, tries=2)
    except KeyError_ as e:
        print(MSG_KEY)
        print(f"  Ursache: {e.why}", file=sys.stderr)
        return 2
    except Exception as e:  # Netzwerk o. Ä. – Meldung enthält nie den Schlüssel
        print(f"{MSG_KEY} (Prüfung nicht möglich: {e})")
        return 3
    print("OK")
    return 0


def cmd_jobs(jobs_file: Path, out_file: Path, offline: bool = False) -> int:
    jobs = json.loads(jobs_file.read_text(encoding="utf-8"))
    CACHE.mkdir(parents=True, exist_ok=True)
    creds = None
    result, made, missing = [], 0, 0
    for i, job in enumerate(jobs):
        voice, lang, body = job["voice"], job["lang"], job["body"]
        ssml = ssml_for(voice, lang, body, job.get("rate"))
        path = cache_path(voice, ssml)
        cached = path.exists() and path.stat().st_size > 100
        if not cached and offline:
            missing += 1
            result.append({"id": job.get("id", str(i)), "wav": None, "seconds": None, "cached": False})
            continue
        if not cached:
            if creds is None:
                try:
                    creds = _credentials()
                except KeyError_ as e:
                    print(MSG_KEY)
                    print(f"  Ursache: {e.why}", file=sys.stderr)
                    return 2
            try:
                audio = _synthesize(ssml, creds)
            except KeyError_ as e:
                print(MSG_KEY)
                print(f"  Ursache: {e.why}", file=sys.stderr)
                return 2
            except RuntimeError as e:
                print(f"Auftrag {job.get('id')}: {e}", file=sys.stderr)
                return 1
            tmp = path.with_suffix(".tmp")
            tmp.write_bytes(audio)
            tmp.replace(path)
            made += 1
            if made % 10 == 0:
                print(f"  {made} neu gesprochen …", flush=True)
        data = path.read_bytes()
        result.append({"id": job.get("id", str(i)), "wav": str(path), "seconds": round(wav_seconds(data), 4), "cached": cached})
    out_file.write_text(json.dumps(result, ensure_ascii=False, indent=1), encoding="utf-8")
    if offline:
        print(f"{len(result)} Aufträge, {len(result) - missing} im Cache, {missing} fehlen (ohne Netz, kein Azure-Aufruf).")
    else:
        print(f"{len(result)} Aufträge, {made} neu gesprochen, {len(result) - made} aus dem Cache.")
    return 0


def main() -> int:
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8")
        except Exception:
            pass
    ap = argparse.ArgumentParser(description="Azure Neural TTS für die Daftar-Videos (Schlüssel bleibt im Skript).")
    ap.add_argument("--check", action="store_true", help="Test-Aufruf: OK oder Azure-Schlüssel fehlt/ungültig")
    ap.add_argument("--jobs", type=Path, help="JSON-Datei mit Aufträgen")
    ap.add_argument("--out", type=Path, help="JSON-Datei für die Ergebnisliste")
    ap.add_argument("--offline", action="store_true", help="nur den Cache lesen, nie Azure aufrufen")
    a = ap.parse_args()
    if a.check:
        return cmd_check()
    if a.jobs and a.out:
        return cmd_jobs(a.jobs, a.out, a.offline)
    ap.print_help()
    return 1


if __name__ == "__main__":
    sys.exit(main())
