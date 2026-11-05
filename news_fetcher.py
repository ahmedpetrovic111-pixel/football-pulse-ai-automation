
import json
import re
import urllib.request
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from pathlib import Path

# Football Pulse AI - News Fetcher
# Mengambil metadata berita dari RSS, bukan menyalin artikel lengkap.

FEEDS = [
    {
        "name": "BBC Sport",
        "url": "https://feeds.bbci.co.uk/sport/football/rss.xml"
    }
]

OUTPUT_FILE = Path("news.json")
MAX_NEWS = 30


def clean_text(value):
    """Membersihkan tag HTML dan spasi berlebih."""
    if not value:
        return ""

    value = re.sub(r"<[^>]+>", " ", value)
    value = re.sub(r"&nbsp;|&#160;", " ", value)
    value = re.sub(r"\s+", " ", value)

    return value.strip()


def parse_date(value):
    """Mengubah tanggal RSS menjadi format ISO."""
    if not value:
        return ""

    try:
        return parsedate_to_datetime(value).isoformat()
    except (TypeError, ValueError, OverflowError):
        return value


def fetch_feed(feed):
    """Mengambil berita dari satu RSS feed."""
    print(f"Mengambil berita: {feed['name']}")

    request = urllib.request.Request(
        feed["url"],
        headers={"User-Agent": "FootballPulseAI/1.0"}
    )

    try:
        with urllib.request.urlopen(request, timeout=20) as response:
            xml_data = response.read()

        root = ET.fromstring(xml_data)
        articles = []

        for item in root.findall(".//item"):
            title = clean_text(item.findtext("title"))
            link = (item.findtext("link") or "").strip()
            description = clean_text(item.findtext("description"))
            pub_date = parse_date(item.findtext("pubDate"))

            if not title or not link:
                continue

            articles.append({
                "title": title,
                "summary": description[:500],
                "source": feed["name"],
                "source_url": link,
                "published_at": pub_date,
                "image_url": "",
                "language": "en",
                "status": "source_only"
            })

        print(f"  Berhasil: {len(articles)} berita")
        return articles

    except Exception as error:
        print(f"  Gagal mengambil feed: {error}")
        return []


def main():
    all_articles = []

    for feed in FEEDS:
        all_articles.extend(fetch_feed(feed))

    # Menghindari berita ganda berdasarkan tautan asli.
    unique_articles = {}
    for article in all_articles:
        unique_articles[article["source_url"]] = article

    news = list(unique_articles.values())
    news = news[:MAX_NEWS]

    output = {
        "updated_at": datetime.now(timezone.utc).isoformat(),
        "total": len(news),
        "articles": news
    }

    OUTPUT_FILE.write_text(
        json.dumps(output, ensure_ascii=False, indent=2),
        encoding="utf-8"
    )

    print(f"\nSelesai. Total berita tersimpan: {len(news)}")
    print(f"File dibuat: {OUTPUT_FILE}")


if __name__ == "__main__":
    main()
