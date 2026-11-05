
import json
import re
import html
import hashlib
import urllib.request
import xml.etree.ElementTree as ET

from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from pathlib import Path
from urllib.parse import urlsplit, urlunsplit, parse_qsl, urlencode


# ==========================================
# FOOTBALL PULSE AI - NEWS FETCHER
# Versi 2.0 - Tanpa AI / Tanpa API Key
# ==========================================

FEEDS = [
    {
        "name": "BBC Sport",
        "url": "https://feeds.bbci.co.uk/sport/football/rss.xml"
    },
    {
        "name": "Sky Sports",
        "url": "https://www.skysports.com/rss/11095"
    },
    {
        "name": "The Guardian",
        "url": "https://www.theguardian.com/football/rss"
    }
]

OUTPUT_FILE = Path("news.json")
MAX_NEWS = 30

# Konten yang tidak diprioritaskan sebagai berita utama
EXCLUDED_KEYWORDS = [
    "quiz",
    "quizzes",
    "brainteaser",
    "football daily",
    "podcast",
    "who am i?"
]

# Kategori kompetisi dan topik
CATEGORIES = {
    "Premier League": [
        "premier league", "manchester united", "manchester city",
        "liverpool", "arsenal", "chelsea", "tottenham",
        "newcastle", "aston villa", "everton", "brighton",
        "west ham", "nottingham forest", "crystal palace",
        "brentford", "fulham", "bournemouth", "wolves"
    ],
    "LaLiga": [
        "laliga", "la liga", "real madrid", "barcelona",
        "atletico madrid", "sevilla", "valencia", "villarreal"
    ],
    "Serie A": [
        "serie a", "inter milan", "ac milan", "juventus",
        "napoli", "roma", "lazio", "atalanta"
    ],
    "Bundesliga": [
        "bundesliga", "bayern munich", "borussia dortmund",
        "bayer leverkusen", "rb leipzig", "eintracht frankfurt"
    ],
    "Ligue 1": [
        "ligue 1", "paris saint-germain", "psg", "marseille",
        "monaco", "lyon", "lille"
    ],
    "Champions League": [
        "champions league", "uefa champions league"
    ],
    "Europa League": [
        "europa league", "uefa europa league"
    ],
    "Tim Nasional": [
        "england", "portugal", "brazil", "argentina",
        "france", "germany", "spain", "italy",
        "world cup", "nations league", "international football"
    ]
}


def clean_text(value):
    """Membersihkan HTML dan karakter yang tidak diperlukan."""
    if not value:
        return ""

    value = html.unescape(value)
    value = re.sub(r"<[^>]+>", " ", value)
    value = re.sub(r"\s+", " ", value)

    return value.strip()


def parse_date(value):
    """Mengubah tanggal RSS menjadi format ISO."""
    if not value:
        return ""

    try:
        date = parsedate_to_datetime(value)

        if date.tzinfo is None:
            date = date.replace(tzinfo=timezone.utc)

        return date.astimezone(timezone.utc).isoformat()

    except (TypeError, ValueError, OverflowError):
        return ""


def date_timestamp(value):
    """Mengubah tanggal menjadi angka untuk pengurutan."""
    try:
        return datetime.fromisoformat(
            value.replace("Z", "+00:00")
        ).timestamp()
    except (ValueError, AttributeError):
        return 0


def canonical_url(url):
    """Menghapus parameter pelacakan untuk mendeteksi duplikasi."""
    try:
        parts = urlsplit(url)

        tracking = {
            "at_medium",
            "at_campaign",
            "utm_source",
            "utm_medium",
            "utm_campaign"
        }

        query = [
            (key, value)
            for key, value in parse_qsl(parts.query)
            if key.lower() not in tracking
        ]

        return urlunsplit((
            parts.scheme,
            parts.netloc,
            parts.path,
            urlencode(query),
            ""
        ))

    except Exception:
        return url


def is_relevant(title, summary):
    """Menyaring konten yang bukan berita utama sepak bola."""
    content = (title + " " + summary).lower()

    for keyword in EXCLUDED_KEYWORDS:
        if keyword in content:
            return False

    return True


def classify_article(title, summary):
    """Menentukan kategori berita berdasarkan kata kunci."""
    content = (title + " " + summary).lower()

    for category, keywords in CATEGORIES.items():
        for keyword in keywords:
            if keyword in content:
                return category

    return "Berita Sepak Bola"


def make_article_id(url):
    """Membuat ID unik berdasarkan tautan berita."""
    return hashlib.sha256(
        canonical_url(url).encode("utf-8")
    ).hexdigest()[:16]


def fetch_feed(feed):
    """Mengambil metadata berita dari RSS."""
    print(f"Mengambil berita: {feed['name']}")

    request = urllib.request.Request(
        feed["url"],
        headers={
            "User-Agent": "FootballPulseAI/2.0"
        }
    )

    try:
        with urllib.request.urlopen(
            request,
            timeout=25
        ) as response:
            xml_data = response.read()

        root = ET.fromstring(xml_data)
        articles = []

        for item in root.findall(".//item"):

            title = clean_text(item.findtext("title"))
            link = (item.findtext("link") or "").strip()

            summary = clean_text(
                item.findtext("description")
            )

            published_at = parse_date(
                item.findtext("pubDate")
            )

            if not title or not link:
                continue

            if not is_relevant(title, summary):
                continue

            article = {
                "id": make_article_id(link),
                "title": title,
                "summary": summary[:500],
                "category": classify_article(
                    title,
                    summary
                ),
                "source": feed["name"],
                "source_url": link,
                "published_at": published_at,
                "image_url": "",
                "language": "en",
                "status": "source_only"
            }

            articles.append(article)

        print(
            f"  Berhasil mengambil "
            f"{len(articles)} berita relevan"
        )

        return articles

    except Exception as error:
        print(f"  Gagal mengambil RSS: {error}")
        return None


def main():

    all_articles = []
    successful_feeds = 0

    for feed in FEEDS:

        articles = fetch_feed(feed)

        if articles is not None:
            successful_feeds += 1
            all_articles.extend(articles)

    # Jangan menimpa berita lama jika semua RSS gagal.
    if successful_feeds == 0:
        print("\nSemua sumber gagal diakses.")
        print("File news.json lama tetap dipertahankan.")
        return

    # Hilangkan berita ganda.
    unique_articles = {}

    for article in all_articles:
        key = canonical_url(article["source_url"])
        unique_articles[key] = article

    news = list(unique_articles.values())

    # Urutkan berita terbaru terlebih dahulu.
    news.sort(
        key=lambda article: date_timestamp(
            article["published_at"]
        ),
        reverse=True
    )

    # Batasi jumlah berita.
    news = news[:MAX_NEWS]

    output = {
        "site": "Football Pulse AI",
        "updated_at": datetime.now(
            timezone.utc
        ).isoformat(),
        "total": len(news),
        "sources_checked": successful_feeds,
        "articles": news
    }

    OUTPUT_FILE.write_text(
        json.dumps(
            output,
            ensure_ascii=False,
            indent=2
        ),
        encoding="utf-8"
    )

    print("\n================================")
    print("FOOTBALL PULSE AI NEWS UPDATE")
    print("================================")
    print(f"Total berita: {len(news)}")
    print(f"Sumber berhasil: {successful_feeds}")
    print(f"File tersimpan: {OUTPUT_FILE}")
    print("================================")


if __name__ == "__main__":
    main()
