"""Turn a YouTube @handle into the UC... channel id its RSS feed needs.

YouTube's feed endpoint only accepts channel ids, and the id isn't shown
anywhere in the interface. This fetches the channel page and pulls it out.

    python tools/resolve_youtube.py @veritasium @pbsspacetime
    python tools/resolve_youtube.py --check        # verify every id in config.yaml
"""

import re
import sys
import urllib.request

UA = ("Mozilla/5.0 (compatible; AInstein/0.3; "
      "+https://github.com/AyaRudek/ainstein)")
ID_RE = re.compile(r'"(?:channelId|externalId)"\s*:\s*"(UC[\w-]{22})"')


def resolve(handle: str) -> str | None:
    handle = handle if handle.startswith("@") else "@" + handle
    req = urllib.request.Request(f"https://www.youtube.com/{handle}",
                                 headers={"User-Agent": UA})
    with urllib.request.urlopen(req, timeout=30) as resp:
        html = resp.read().decode("utf-8", "replace")
    m = ID_RE.search(html)
    return m.group(1) if m else None


def check_config() -> None:
    import pathlib
    import yaml

    root = pathlib.Path(__file__).resolve().parent.parent
    cfg = yaml.safe_load((root / "config.yaml").read_text(encoding="utf-8"))
    for ch in cfg.get("youtube", []):
        cid = ch.get("channel_id")
        status = "set" if cid else "MISSING"
        print(f"  {ch['name']:<24} {cid or '—':<26} {status}")


if __name__ == "__main__":
    args = sys.argv[1:]
    if not args or args[0] == "--check":
        check_config()
    else:
        for handle in args:
            try:
                print(f"{handle:<24} {resolve(handle) or 'not found'}")
            except Exception as exc:
                print(f"{handle:<24} failed: {exc}")
