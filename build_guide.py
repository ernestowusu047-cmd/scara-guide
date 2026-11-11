"""
Builds a small TV guide (XMLTV) for SCARA's live sports channels.

It reads the same two playlists as the app (live.m3u in this folder, and the Sports group of
iptv-org's online list), downloads epg.pw's full free guide (about 50 MB compressed, 500 MB of
XML) as a stream, and keeps only the programmes of those channels for the next day and a half.
The result, guide.xml and guide.xml.gz, is a few hundred KB: light enough for any TV or phone.

Run it with Python 3.9+ and nothing else installed:  python build_guide.py
GitHub runs it on a schedule (.github/workflows/build-guide.yml).
"""

import gzip
import re
import sys
import time
import urllib.request
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from xml.sax.saxutils import escape

ONLINE_PLAYLIST = "https://iptv-org.github.io/iptv/index.category.m3u"
ONLINE_GROUP = "Sports"
GUIDE_SOURCE = "https://epg.pw/xmltv/epg.xml.gz"
LOCAL_PLAYLIST = "live.m3u"
KEEP_BEFORE_H = 3
KEEP_AFTER_H = 36
UA = {"User-Agent": "Mozilla/5.0 (SCARA guide builder)"}

ATTR = re.compile(r'([a-zA-Z-]+)="([^"]*)"')
NOTES = re.compile(r"\s*[\[(][^\])]*[\])]")


def open_url(url, timeout=120):
    return urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=timeout)


def parse_playlist(lines, group=None):
    """(url, name, tvg-id, country) for each channel, as the app reads them."""
    out, info = [], None
    for raw in lines:
        line = raw.strip()
        if line.startswith("#EXTINF"):
            info = line
        elif line and not line.startswith("#"):
            values = dict((k.lower(), v) for k, v in ATTR.findall(info or ""))
            groups = [g.strip().lower() for g in values.get("group-title", "").split(";")]
            if group is None or group.lower() in groups:
                title = (info or "").rsplit(",", 1)[-1].strip() if info else ""
                tvg = values.get("tvg-id", "")
                country = values.get("tvg-country", "").upper()
                if not country and tvg:
                    tail = tvg.split("@")[0].rsplit(".", 1)
                    country = tail[1].upper() if len(tail) == 2 and len(tail[1]) == 2 else ""
                out.append((line, NOTES.sub("", title).strip(), tvg, country))
            info = None
    return out


def key(name):
    """The app's name matching: lower case, no 'HD'/'TV'/quality words, letters and digits only."""
    n = name.lower()
    n = re.sub(r"\b(hd|sd|fhd|uhd|4k|tv|channel|1080p|720p)\b", "", n)
    return re.sub(r"[\W_]", "", n)


def load_channels():
    with open(LOCAL_PLAYLIST, encoding="utf-8") as f:
        local = parse_playlist(f.read().splitlines())
    try:
        with open_url(ONLINE_PLAYLIST) as r:
            online = parse_playlist(r.read().decode("utf-8", "replace").splitlines(), ONLINE_GROUP)
    except Exception as e:
        print("online playlist unavailable:", e, file=sys.stderr)
        online = []
    seen, channels = set(), []
    for c in local + online:
        if c[0] not in seen and c[1]:
            seen.add(c[0])
            channels.append(c)
    return channels


def xmltv_time(value):
    try:
        return datetime.strptime(value.strip(), "%Y%m%d%H%M%S %z").timestamp()
    except Exception:
        return None


def main():
    channels = load_channels()
    by_name, by_id = {}, {}
    for url, name, tvg, country in channels:
        k = key(name)
        if len(k) >= 3:
            by_name.setdefault(k, []).append((name, country))
        if tvg:
            by_id[tvg.lower()] = (name, country)
    print(f"{len(channels)} channels in the playlists")

    now = time.time()
    start_from, until = now - KEEP_BEFORE_H * 3600, now + KEEP_AFTER_H * 3600

    # Guide channel id -> (our name, how good the match is). One guide channel per name of ours:
    # when several share a name ("beIN Sports 3" in different regions), the one whose country
    # matches the playlist's wins.
    candidates = {}
    channel_id, langs, names = None, set(), []
    programmes = {}
    with open_url(GUIDE_SOURCE, timeout=600) as response:
        stream = gzip.GzipFile(fileobj=response)
        for event, el in ET.iterparse(stream, events=("start", "end")):
            if event == "start":
                if el.tag == "channel":
                    channel_id, langs, names = el.get("id"), set(), []
                continue
            if el.tag == "display-name" and channel_id is not None:
                names.append(el.text or "")
                if el.get("lang"):
                    langs.add(el.get("lang").upper())
            elif el.tag == "channel":
                hit = by_id.get((channel_id or "").lower())
                matches = [hit] if hit else [m for n in names for m in by_name.get(key(n), [])]
                for our_name, country in matches:
                    score = 2 if hit else (1 if country and country in langs else 0)
                    best = candidates.get(our_name)
                    if best is None or score > best[1]:
                        candidates[our_name] = (channel_id, score)
                channel_id = None
                el.clear()
            elif el.tag == "programme":
                cid = el.get("channel")
                start, stop = xmltv_time(el.get("start", "")), xmltv_time(el.get("stop", ""))
                if start and stop and stop > start_from and start < until:
                    title = (el.findtext("title") or "").strip()
                    if title:
                        category = (el.findtext("category") or "").strip()
                        programmes.setdefault(cid, []).append((el.get("start"), el.get("stop"), title, category))
                el.clear()
            # Programmes of channels we don't have are dropped as they're read; nothing big is kept.

    wanted = {cid: our for our, (cid, _) in candidates.items()}
    kept = 0
    with open("guide.xml", "w", encoding="utf-8") as out:
        out.write('<?xml version="1.0" encoding="UTF-8"?>\n')
        out.write(f'<tv generator-info-name="SCARA guide builder" source-info-url="{escape(GUIDE_SOURCE)}">\n')
        for cid, our in wanted.items():
            if cid in programmes:
                out.write(f'  <channel id="{escape(cid)}"><display-name>{escape(our)}</display-name></channel>\n')
        for cid, our in wanted.items():
            for start, stop, title, category in sorted(set(programmes.get(cid, []))):
                out.write(f'  <programme start="{escape(start)}" stop="{escape(stop)}" channel="{escape(cid)}">'
                          f'<title>{escape(title)}</title>')
                if category:
                    out.write(f'<category>{escape(category)}</category>')
                out.write('</programme>\n')
                kept += 1
        out.write("</tv>\n")
    with open("guide.xml", "rb") as src, gzip.open("guide.xml.gz", "wb") as dst:
        dst.write(src.read())
    covered = sum(1 for cid in wanted if cid in programmes)
    print(f"{covered} channels with programmes, {kept} programmes kept "
          f"({datetime.now(timezone.utc):%Y-%m-%d %H:%M} UTC)")


if __name__ == "__main__":
    main()
