
import json
import re
import html
import hashlib
import urllib.request
import xml.etree.ElementTree as ET
import difflib

from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from pathlib import Path
from urllib.parse import urlsplit, urlunsplit, parse_qsl, urlencode


# ==========================================
# FOOTBALL PULSE AI - NEWS FETCHER
# Versi 4.0 - Improved News Classification
# Gratis, tanpa AI, tanpa API Key
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


# ==========================================
# KATA KUNCI BERITA YANG DIKECUALIKAN
# ==========================================

EXCLUDED_KEYWORDS = [
    "quiz",
    "quizzes",
    "brainteaser",
    "football daily",
    "podcast",
    "who am i?",
    "crossword",
    "fantasy football"
]


# ==========================================
# KATEGORI KOMPETISI
# Urutan ini menjadi prioritas kategori.
# Women's Football tetap ditampilkan terakhir.
# ==========================================

COMPETITION_CATEGORIES = {
    "Champions League": [
        "uefa champions league",
        "champions league"
    ],

    "Premier League": [
        "premier league"
    ],

    "LaLiga": [
        "laliga",
        "la liga"
    ],

    "Serie A": [
        "serie a"
    ],

    "Bundesliga": [
        "bundesliga"
    ],

    "Ligue 1": [
        "ligue 1"
    ],

    "Europa League": [
        "uefa europa league",
        "europa league"
    ],

    "Conference League": [
        "uefa conference league",
        "conference league"
    ],

    "Liga 1 Indonesia": [
        "bri super league",
        "super league indonesia",
        "indonesia super league",
        "liga 1 indonesia",
        "bri liga 1",
        "liga 1"
    ],

    "Women's Football": [
        "women's champions league",
        "womens champions league",
        "women's super league",
        "women's football",
        "women's world cup",
        "women's euro",
        "women's olympic football"
    ]
}


# ==========================================
# KATA KUNCI TIMNAS INDONESIA
# ==========================================

INDONESIA_TEAM_KEYWORDS = [
    "timnas indonesia",
    "tim nasional indonesia",
    "indonesia national team",
    "indonesia national football team",
    "indonesia men's national team",
    "indonesia squad",
    "indonesia football team",
    "garuda squad",
    "skuad garuda",
    "timnas garuda"
]


# ==========================================
# KATA KUNCI TIM NASIONAL NEGARA LAIN
# ==========================================

NATIONAL_KEYWORDS = [
    "national team",
    "international break",
    "nations league",
    "world cup",
    "european championship",
    "euro 2028",
    "international football",
    "england squad",
    "brazil squad",
    "argentina squad",
    "france squad",
    "germany squad",
    "spain squad",
    "portugal squad"
]


# ==========================================
# KATEGORI BERDASARKAN KLUB
# ==========================================

CLUB_CATEGORIES = {
    "Premier League": [
        "manchester united",
        "manchester city",
        "liverpool",
        "arsenal",
        "chelsea",
        "tottenham",
        "newcastle united",
        "aston villa",
        "everton",
        "brighton",
        "west ham",
        "nottingham forest",
        "crystal palace",
        "brentford",
        "fulham",
        "bournemouth",
        "wolves",
        "sunderland"
    ],

    "LaLiga": [
        "real madrid",
        "barcelona",
        "atletico madrid",
        "sevilla",
        "valencia",
        "villarreal",
        "athletic bilbao"
    ],

    "Serie A": [
        "inter milan",
        "ac milan",
        "juventus",
        "napoli",
        "roma",
        "lazio",
        "atalanta"
    ],

    "Bundesliga": [
        "bayern munich",
        "borussia dortmund",
        "bayer leverkusen",
        "rb leipzig",
        "eintracht frankfurt"
    ],

    "Ligue 1": [
        "paris saint-germain",
        "psg",
        "marseille",
        "monaco",
        "lyon",
        "lille"
    ]
}


# ==========================================
# MEMBERSIHKAN TEKS BERITA
# ==========================================

def clean_text(value):
    if not value:
        return ""

    value = html.unescape(value)
    value = value.replace("’", "'").replace("‘", "'")
    value = re.sub(r"<[^>]+>", " ", value)
    value = re.sub(r"\s+", " ", value)

    return value.strip()


# ==========================================
# MEMBACA TANGGAL BERITA
# ==========================================

def parse_date(value):
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
    try:
        return datetime.fromisoformat(
            value.replace("Z", "+00:00")
        ).timestamp()

    except (ValueError, AttributeError):
        return 0


# ==========================================
# MEMBERSIHKAN URL DARI TRACKING
# ==========================================

def canonical_url(url):
    try:
        parts = urlsplit(url)

        tracking = {
            "at_medium",
            "at_campaign",
            "utm_source",
            "utm_medium",
            "utm_campaign",
            "utm_content",
            "utm_term"
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


# ==========================================
# FILTER BERITA TIDAK RELEVAN
# ==========================================

def is_relevant(title, summary):

    content = (title + " " + summary).lower()

    for keyword in EXCLUDED_KEYWORDS:
        if keyword in content:
            return False

    live_blog_patterns = [
        "live blog",
        "live updates",
        "minute-by-minute",
        "as it happened",
        "live:",
        "live -",
        "live scores",
        "live commentary",
        "match commentary",
        "follow live",
        "follow minute by minute"
    ]

    combined_text = f"{title} {summary}".lower()

    for phrase in live_blog_patterns:
        if phrase in combined_text:
            return False

    return True


# ==========================================
# SISTEM KLASIFIKASI BERITA
# ==========================================

def classify_article(title, summary):

    content = (title + " " + summary).lower()

    # 1. Women's Football diperiksa terlebih dahulu.
    # Agar Women's Champions League tidak salah
    # masuk ke kategori Champions League biasa.

    women's_keywords = COMPETITION_CATEGORIES[
        "Women's Football"
    ]

    if any(keyword in content for keyword in women's_keywords):
        return "Women's Football"

    # 2. Timnas Indonesia.
    # Diperiksa sebelum kategori umum seperti World Cup.

    if any(
        keyword in content
        for keyword in INDONESIA_TEAM_KEYWORDS
    ):
        return "Timnas Indonesia"

    # 3. Kompetisi sepak bola.
    # Termasuk kompetisi Eropa dan Liga 1 Indonesia.

    for category, keywords in COMPETITION_CATEGORIES.items():

        if category == "Women's Football":
            continue

        if any(keyword in content for keyword in keywords):
            return category

    # 4. Tim nasional negara lain.

    if any(
        keyword in content
        for keyword in NATIONAL_KEYWORDS
    ):
        return "Tim Nasional"

    # 5. Kategori berdasarkan nama klub.

    for category, keywords in CLUB_CATEGORIES.items():

        if any(keyword in content for keyword in keywords):
            return category

    # 6. Kategori umum jika tidak ditemukan kecocokan.

    return "Berita Sepak Bola"


# ==========================================
# MEMBUAT ID UNIK BERITA
# ==========================================

def make_article_id(url):

    return hashlib.sha256(
        canonical_url(url).encode("utf-8")
    ).hexdigest()[:16]


# ==========================================
# MENGAMBIL BERITA DARI RSS
# ==========================================

def fetch_feed(feed):

    print(f"Mengambil berita: {feed['name']}")

    request = urllib.request.Request(
        feed["url"],
        headers={
            "User-Agent": "Mozilla/5.0 FootballPulseAI/4.0"
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

            title = clean_text(
                item.findtext("title")
            )

            link = (
                item.findtext("link") or ""
            ).strip()

            summary = clean_text(
                item.findtext("description")
            )

            published_at = parse_date(
                item.findtext("pubDate")
            )

            if not title or not link:
                continue

            # Menghindari berita live blog dan live match.
            url_lower = link.lower()

            if (
                "/live-blog/" in url_lower
                or "/football/live/" in url_lower
                or "/live/" in url_lower
            ):
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


# ==========================================
# NORMALISASI JUDUL BERITA
# ==========================================

def normalize_title(title):

    title = title.lower()

    title = re.sub(
        r"[^a-z0-9]+",
        " ",
        title
    )

    return " ".join(title.split())


# ==========================================
# MENGHAPUS JUDUL BERITA YANG MIRIP
# ==========================================

def remove_similar_duplicates(
    articles,
    threshold=0.92
):

    unique_articles = []

    for article in articles:

        title = normalize_title(
            article.get("title", "")
        )

        if not title:
            continue

        is_duplicate = False

        for existing in unique_articles:

            if (
                article.get("category")
                != existing.get("category")
            ):
                continue

            existing_title = normalize_title(
                existing.get("title", "")
            )

            similarity = difflib.SequenceMatcher(
                None,
                title,
                existing_title
            ).ratio()

            if similarity >= threshold:

                is_duplicate = True

                break

        if not is_duplicate:

            unique_articles.append(article)

    return unique_articles


# ==========================================
# PROSES UTAMA FOOTBALL PULSE AI
# ==========================================

def main():

    all_articles = []

    successful_feeds = 0

    # Mengambil berita dari semua sumber RSS.

    for feed in FEEDS:

        articles = fetch_feed(feed)

        if articles is not None:

            successful_feeds += 1

            all_articles.extend(articles)

    if successful_feeds == 0:

        print("\nSemua sumber gagal diakses.")

        print(
            "File news.json lama tetap dipertahankan."
        )

        return

    # Menghapus duplikat berdasarkan URL.

    unique_articles = {}

    for article in all_articles:

        key = canonical_url(
            article["source_url"]
        )

        if key not in unique_articles:

            unique_articles[key] = article

    news = list(unique_articles.values())

    # Mengurutkan berita terbaru terlebih dahulu.

    news.sort(
        key=lambda article: date_timestamp(
            article["published_at"]
        ),
        reverse=True
    )

    # Menghapus berita dengan judul sangat mirip.

    before_count = len(news)

    news = remove_similar_duplicates(news)

    removed_count = before_count - len(news)

    print(
        "Duplikat URL dan judul berhasil disaring."
    )

    print(
        f"Berita dengan judul mirip dihapus: {removed_count}"
    )

    # Membatasi jumlah berita.

    news = news[:MAX_NEWS]

    # Menyiapkan data JSON.

    output = {
        "site": "Football Pulse AI",
        "updated_at": datetime.now(
            timezone.utc
        ).isoformat(),
        "total": len(news),
        "sources_checked": successful_feeds,
        "articles": news
    }

    # Menyimpan berita ke news.json.

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
