
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
# Versi 5.0 - Improved News Classification
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
    "fantasy football",
    "listen:",
    "bbc sounds"
]


# ==========================================
# KATEGORI KOMPETISI
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
    "england squad",
    "england national team",
    "england international",
    "scotland squad",
    "scotland national team",
    "scotland international",
    "wales squad",
    "wales national team",
    "wales international",
    "northern ireland squad",
    "northern ireland national team",
    "republic of ireland squad",
    "republic of ireland national team",
    "ireland national team",
    "croatia squad",
    "croatia national team",
    "croatia international",
    "france national team",
    "france squad",
    "germany national team",
    "germany squad",
    "spain national team",
    "spain squad",
    "italy national team",
    "italy squad",
    "portugal national team",
    "portugal squad",
    "netherlands national team",
    "netherlands squad",
    "belgium national team",
    "belgium squad",
    "switzerland national team",
    "switzerland squad",
    "austria national team",
    "austria squad",
    "denmark national team",
    "denmark squad",
    "sweden national team",
    "sweden squad",
    "norway national team",
    "norway squad",
    "poland national team",
    "poland squad",
    "brazil national team",
    "brazil squad",
    "argentina national team",
    "argentina squad",
    "uruguay national team",
    "colombia national team",
    "japan national team",
    "south korea national team",
    "australia national team",
    "morocco national team",
    "senegal national team",
    "nigeria national team",
    "united states national team",
    "mexico national team"
]

# ==========================================
# KATEGORI BERDASARKAN KLUB
# ==========================================

CLUB_CATEGORIES = {
    
    "Premier League": [
        "manchester united",
        "man utd",
        "man united",
        "manchester city",
        "man city",
        "liverpool",
        "arsenal",
        "chelsea",
        "tottenham",
        "spurs",
        "newcastle united",
        "newcastle",
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

    
    # Menolak seluruh berita sepak bola wanita.
    womens_excluded_keywords = [
        "women's football",
        "womens football",
        "women's champions league",
        "womens champions league",
        "women champions league",
        "women's super league",
        "womens super league",
        "women's world cup",
        "womens world cup",
        "women's euro",
        "womens euro",
        "women's olympic football",
        "women's team",
        "women's teams",
        "women's game",
        "women's soccer",
        "barcelona femeni",
        "barcelona femení",
        "arsenal wfc",
        "chelsea women",
        "manchester city women",
        "manchester united women",
        "lionesses",
        "uwcl",
        "caroline weir",
        "moving the goalposts",
        "pregnant players",
        "female footballers",
        "pregnancy-womens-football"
    ]

    if any(keyword in content for keyword in womens_excluded_keywords):
        return False

    
    # Menolak kartun David Squires.
    if "david squires" in content:
        return False
        
    # Menolak berita yang tidak diinginkan.
    for keyword in EXCLUDED_KEYWORDS:
        if keyword in content:
            return False

    # Menolak live blog dan live commentary.
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

    for phrase in live_blog_patterns:
        if phrase in content:
            return False

    # Menolak video dan highlight.
    video_patterns = [
        "highlights:",
        "highlights from",
        "watch highlights",
        "free to watch",
        "watch video",
        "video highlights",
        "goal:",
        "goal -",
        "extended highlights",
        "match highlights"
    ]

    for phrase in video_patterns:
        if phrase in content:
            return False

    # Menolak kompetisi di luar prioritas.
    excluded_competitions = [
        "fa cup",
        "championship",
        "league one",
        "league two",
        "national league",
        "national league north",
        "national league south",
        "southern premier league",
        "fa trophy",
        "carabao cup",
        "efl cup",
        "efl trophy"
    ]

    for competition in excluded_competitions:
        if competition in content:
            return False

    return True


# ==========================================
# KLASIFIKASI BERITA
# ==========================================




def classify_article(title, summary):

    title_content = title.lower()
    summary_content = summary.lower()
    content = title_content + " " + summary_content

    # 1. Timnas Indonesia berdasarkan judul.
    if any(
        keyword in title_content
        for keyword in INDONESIA_TEAM_KEYWORDS
    ):
        return "Timnas Indonesia"

    # 2. Klub yang disebutkan langsung di judul.
    for category, clubs in CLUB_CATEGORIES.items():

        if any(club in title_content for club in clubs):
            return category

    # 3. Kompetisi yang disebutkan langsung di judul.
    for category, keywords in COMPETITION_CATEGORIES.items():

        if category == "Liga 1 Indonesia":
            continue

        if any(keyword in title_content for keyword in keywords):
            return category
            
    # 4. Premier League berdasarkan frasa khusus dalam ringkasan.
    if "premier league panel" in summary_content:
        return "Premier League"
        
    # 5. Timnas Indonesia berdasarkan ringkasan.
    if any(
        keyword in summary_content
        for keyword in INDONESIA_TEAM_KEYWORDS
    ):
        return "Timnas Indonesia"

    # 6. Liga 1 Indonesia.
    indonesia_keywords = COMPETITION_CATEGORIES[
        "Liga 1 Indonesia"
    ]

    if any(keyword in content for keyword in indonesia_keywords):
        return "Liga 1 Indonesia"

      # 7. Tim nasional negara lain berdasarkan judul.
      national_title_keywords = [
        "scotland cap",
        "scotland u21",
        "scotland under-21",
        "spain boss",
        "spain head coach",
        "tuchel committed to england",
        "england moments",
        "wales' james",
        "wales james",
        "peter shilton",
        "nations league's meanest defence",
        "robertson set to make history",
        "england's blues brothers"
    ]

    if any(
        keyword in title_content
        for keyword in NATIONAL_KEYWORDS
    ):
        return "Tim Nasional"

    if any(
        keyword in title_content
        for keyword in national_title_keywords
    ):
        return "Tim Nasional"

    national_summary_keywords = [
        "england career",
        "england's record appearance",
        "england record appearance",
        "england cap",
        "scotland career",
        "scotland head coach",
        "scotland manager",
        "scotland squad",
        "northern ireland manager",
        "northern ireland squad",
        "republic of ireland defender",
        "republic of ireland manager",
        "croatian football",
        "croatia prepare to face",
        "croatia manager",
        "national team squad",
        "national team coach"
    ]

    if any(
        keyword in summary_content
        for keyword in national_summary_keywords
    ):
        return "Tim Nasional"

    # 8. Berita sepak bola umum.
    return "Berita Sepak Bola"



# ==========================================
# MEMBUAT ID BERITA
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
            "User-Agent": "Mozilla/5.0 FootballPulseAI/5.0"
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

            url_lower = link.lower()
            # Menolak konten audio BBC Sounds.
            if (
                "bbc.co.uk/sounds/" in url_lower
                or "bbc.com/sounds/" in url_lower
            ):
                continue

            # Menolak tautan video.
            if (
                "/videos/" in url_lower
                or "/watch/video/" in url_lower
                or "/football/video/" in url_lower
            ):
                continue

            # Menolak live blog dan live match.
            if (
                "/live-blog/" in url_lower
                or "/football/live/" in url_lower
                or "/live/" in url_lower
            ):
                continue

            # Menyaring berita yang tidak relevan.
            if not is_relevant(title, summary):
                continue

            # Menentukan kategori berita.
            category = classify_article(
                title,
                summary
            )

            # Membuang berita di luar kategori prioritas.
            if category == "Tidak Ditampilkan":
                continue

            article = {
                "id": make_article_id(link),
                "title": title,
                "summary": summary[:500],
                "category": category,
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
# NORMALISASI JUDUL
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
# V4 - Event-Based Detection
# ==========================================



def remove_similar_duplicates(articles, threshold=0.90):

    unique_articles = []

    entity_stop_words = {
        "the", "this", "that", "after", "before",
        "former", "new", "latest", "today", "yesterday",
        "monday", "tuesday", "wednesday", "thursday",
        "friday", "saturday", "sunday",
        "premier", "league", "champions", "football",
        "sport", "season", "manager", "coach",
        "club", "team", "united", "city",
        "report", "reports", "says", "said",
        "reveals", "explains", "speaks", "talks"
    }

    event_groups = {
        "manager_change": [
            "manager", "coach", "appointed",
            "sacked", "fired", "resigns",
            "resigned", "departure"
        ],

        "contract": [
            "contract", "extension", "extends",
            "renewal", "signs new deal",
            "new deal"
        ],

        "transfer": [
            "transfer", "signing", "signed",
            "joins", "joined", "move",
            "bid", "loan"
        ],

        "injury": [
            "injury", "injured", "fitness",
            "surgery", "sidelined",
            "ruled out", "hamstring"
        ],

        "discipline": [
            "suspended", "suspension",
            "ban", "banned", "red card",
            "charged", "misconduct"
        ],

        "international_exile": [
            "exile", "unavailable", "booed",
            "boos", "jeered", "omitted",
            "left out", "dropped from squad"
        ],

        "match_result": [
            "beat", "beats", "beaten",
            "defeat", "defeated", "draw",
            "drew", "win", "wins", "won",
            "lose", "loses", "lost",
            "victory", "loss"
        ]
    }

    def get_entities(article):

        text = (
            article.get("title", "") + " " +
            article.get("summary", "")
        )

        words = re.findall(
            r"\b[A-Z][a-zA-ZÀ-ÿ’'-]{2,}\b",
            text
        )

        entities = set()

        for word in words:

            entity = normalize_title(word)

            if (
                entity
                and entity not in entity_stop_words
            ):
                entities.add(entity)

        return entities

    def get_events(article):

        text = normalize_title(
            article.get("title", "") + " " +
            article.get("summary", "")
        )

        events = set()

        for event_name, keywords in event_groups.items():

            for keyword in keywords:

                normalized_keyword = normalize_title(keyword)

                if normalized_keyword in text:
                    events.add(event_name)
                    break

        return events

    for article in articles:

        is_duplicate = False

        current_title = normalize_title(
            article.get("title", "")
        )

        current_entities = get_entities(article)
        current_events = get_events(article)

        current_time = date_timestamp(
            article.get("published_at", "")
        )

        for existing in unique_articles:

            # Hanya membandingkan berita dalam kategori yang sama.
            if article.get("category") != existing.get("category"):
                continue

            existing_title = normalize_title(
                existing.get("title", "")
            )

            # Aturan 1: kemiripan judul sangat tinggi.
            title_similarity = difflib.SequenceMatcher(
                None,
                current_title,
                existing_title
            ).ratio()

            if title_similarity >= threshold:
                is_duplicate = True
                break

            # Aturan 2: entitas dan jenis peristiwa sama
            # dalam rentang waktu maksimal 72 jam.
            existing_time = date_timestamp(
                existing.get("published_at", "")
            )

            if not current_time or not existing_time:
                continue

            time_difference = abs(
                current_time - existing_time
            )

            if time_difference > 72 * 60 * 60:
                continue

            existing_entities = get_entities(existing)
            existing_events = get_events(existing)

            common_entities = (
                current_entities & existing_entities
            )

            common_events = (
                current_events & existing_events
            )

            if (
                len(common_entities) >= 2
                and len(common_events) >= 1
            ):
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

    # Jika semua sumber gagal, pertahankan news.json lama.
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
