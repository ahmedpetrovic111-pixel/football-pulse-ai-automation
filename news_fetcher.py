# ==========================================
# FOOTBALL PULSE AI - NEWS FETCHER
# Versi 6.2 - Kategorisasi lintas kompetisi & deduplikasi konservatif
# Otomatis tanpa AI / tanpa API key AI tambahan
# Sumber berita aktif: Ajel Wire (Bahasa Indonesia)
# ==========================================

import os
import re
import json
import html
import hashlib
import logging
import urllib.request
import urllib.error
import difflib
import unicodedata

from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlencode, urlsplit, urlunsplit, parse_qsl


# ==========================================
# KONFIGURASI
# ==========================================

AJEL_BASE_URL = "https://ajel.sa/api/wire"
AJEL_LANGUAGE = "id"
AJEL_SECTION = "olahraga"
AJEL_PAGE_SIZE = 20
AJEL_MAX_PAGES = 6

OUTPUT_FILE = Path("news.json")
MAX_NEWS = 30
REQUEST_TIMEOUT = 30
USER_AGENT = "FootballPulseAI/6.2 (+https://huggingface.co/spaces/petrovic111/football-pulse-ai)"

# Secret GitHub: AJEL_WIRE_API_KEY
# Jangan pernah menulis API key langsung di file atau URL.
AJEL_API_KEY = os.environ.get("AJEL_WIRE_API_KEY", "").strip()


# ==========================================
# LOGGING
# ==========================================

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(message)s"
)
log = logging.getLogger("football-pulse-ai")


# ==========================================
# FILTER KONTEN YANG TIDAK DIINGINKAN
# ==========================================

EXCLUDED_KEYWORDS = [
    "quiz", "quizzes", "brainteaser", "football daily",
    "podcast", "who am i?", "crossword", "fantasy football",
    "listen:", "bbc sounds"
]

WOMENS_FOOTBALL_KEYWORDS = [
    "women's football", "womens football", "women football",
    "women's soccer", "womens soccer", "women soccer",
    "women's champions league", "womens champions league",
    "women champions league", "women's super league",
    "womens super league", "women's world cup", "womens world cup",
    "women's euro", "womens euro", "women's olympic football",
    "women's team", "women's teams", "women's game",
    "barcelona femeni", "barcelona femení", "arsenal wfc",
    "chelsea women", "manchester city women", "manchester united women",
    "lionesses", "uwcl", "female footballers",

    # Istilah sepak bola wanita dalam Bahasa Indonesia
    "sepak bola wanita", "sepak bola putri",
    "sepakbola wanita", "sepakbola putri",
    "timnas putri", "tim nasional putri",
    "timnas sepak bola putri",
    "tim nasional sepak bola putri",
    "tim sepak bola putri",
    "tim sepakbola putri",
    "liga sepak bola wanita", "liga sepak bola putri",
    "pemain wanita", "pemain putri",
    "pesepak bola wanita", "pesepak bola putri"
]

SAUDI_PRO_LEAGUE_KEYWORDS = [
    "saudi pro league",
    "roshn saudi league",
    "roshn league",
    "liga pro saudi",
    "liga profesional arab saudi",
    "liga arab saudi",
    "liga saudi",
    "dawrī roshn",
    "دوري روشن",
    "دوري المحترفين السعودي"
]

# Klub-klub Saudi yang sering menjadi pokok berita liga domestik.
# Berita mereka tetap dapat lolos jika konteks jelas menyebut kompetisi
# internasional yang termasuk cakupan Football Pulse AI.
SAUDI_CLUB_KEYWORDS = [
    "al-hilal", "al hilal", "al-nassr", "al nassr",
    "al-ittihad", "al ittihad", "al-ahli", "al ahli",
    "al-shabab", "al shabab", "al-fateh", "al fateh",
    "al-fayha", "al fayha", "al-qadsiah", "al qadsiah",
    "al-raed", "al raed", "al-kholood", "al kholood",
    "al-ettifaq", "al ettifaq", "al-riyadh", "al riyadh",
    "damac", "abha", "neom sc"
]

LIVE_OR_VIDEO_KEYWORDS = [
    "live blog", "live updates", "minute-by-minute",
    "as it happened", "live commentary", "match commentary",
    "follow live", "follow minute by minute",
    "watch highlights", "video highlights", "extended highlights",
    "match highlights", "cuplikan pertandingan", "video gol"
]


# ==========================================
# KATEGORI KOMPETISI
# ==========================================

COMPETITION_CATEGORIES = {
    "Saudi First Division": [
        "saudi first division", "first division league",
        "yelo league", "liga yelo", "liga divisi satu",
        "divisi satu arab saudi"
    ],
    "Africa Cup of Nations": [
        "africa cup of nations", "afcon", "piala afrika",
        "piala negara-negara afrika"
    ],
    # Kompetisi Asia tingkat kedua harus diperiksa sebelum kata kunci
    # umum Liga Champions Asia milik kompetisi Elite.
    "AFC Champions League Two": [
        "afc champions league two", "afc champions league 2",
        "acl two", "acl2", "liga champions asia 2",
        "liga champions asia dua", "champions league asia 2",
        "asian champions league two"
    ],
    "AFC Champions League Elite": [
        "afc champions league elite", "acl elite",
        "liga champions asia elite", "liga champions asia elit",
        "champions league asia elite", "asian champions league elite",
        # Ajel kadang menulis nama kompetisi Elite hanya sebagai
        # "Liga Champions Asia" tanpa kata Elite.
        "liga champions asia", "champions league asia"
    ],
    "Gulf Club Champions League": [
        "gulf club champions league", "gulf champions league",
        "gcc champions league", "liga champions klub teluk",
        "liga champions teluk", "champions league teluk",
        "champions league klub teluk"
    ],
    "UEFA Champions League": [
        "uefa champions league", "champions league europe",
        "champions league eropa", "liga champions eropa",
        "liga champions"
    ],
    "Premier League": [
        "premier league", "liga inggris"
    ],
    "LaLiga": [
        "laliga", "la liga", "liga spanyol"
    ],
    "Serie A": [
        "serie a", "liga italia"
    ],
    "Bundesliga": [
        "bundesliga", "liga jerman"
    ],
    "Ligue 1": [
        "ligue 1", "liga prancis"
    ],
    "Europa League": [
        "uefa europa league", "europa league", "liga europa"
    ],
    "Conference League": [
        "uefa conference league", "conference league",
        "liga konferensi eropa"
    ],
    "Liga 1 Indonesia": [
        "bri super league", "super league indonesia",
        "indonesia super league", "liga 1 indonesia",
        "bri liga 1", "liga 1", "liga indonesia",
        "super league"
    ]
}

INDONESIA_TEAM_KEYWORDS = [
    "timnas indonesia", "tim nasional indonesia",
    "indonesia national team", "indonesia national football team",
    "indonesia men's national team", "indonesia squad",
    "indonesia football team", "garuda squad", "skuad garuda",
    "timnas garuda", "tim nasional garuda"
]

NATIONAL_TEAM_KEYWORDS = [
    "national team", "tim nasional", "timnas",
    "international friendly", "friendly internasional",
    "laga persahabatan internasional", "pertandingan persahabatan",
    "laga persahabatan", "uji coba internasional",
    "uji coba tim nasional", "friendly match",
    "timnas inggris", "timnas jepang", "timnas korea",
    "timnas brasil", "timnas argentina", "timnas prancis",
    "timnas jerman", "timnas spanyol", "timnas italia",
    "timnas portugal", "timnas belanda", "timnas kroasia",
    "timnas maroko", "timnas senegal", "timnas nigeria",
    "england squad", "england national team",
    "scotland squad", "scotland national team",
    "wales squad", "wales national team",
    "northern ireland squad", "republic of ireland squad",
    "croatia squad", "croatia national team",
    "france national team", "france squad",
    "germany national team", "germany squad",
    "spain national team", "spain squad",
    "italy national team", "italy squad",
    "portugal national team", "portugal squad",
    "netherlands national team", "netherlands squad",
    "belgium national team", "belgium squad",
    "switzerland national team", "switzerland squad",
    "austria national team", "austria squad",
    "denmark national team", "denmark squad",
    "sweden national team", "sweden squad",
    "norway national team", "norway squad",
    "poland national team", "poland squad",
    "brazil national team", "brazil squad",
    "argentina national team", "argentina squad",
    "uruguay national team", "colombia national team",
    "japan national team", "south korea national team",
    "australia national team", "morocco national team",
    "senegal national team", "nigeria national team",
    "united states national team", "mexico national team"
]

# Klasifikasi klub berdasarkan liga domestik yang menjadi fokus.
CLUB_CATEGORIES = {
    "Premier League": [
        "manchester united", "man utd", "man united",
        "manchester city", "man city", "liverpool",
        "arsenal", "chelsea", "tottenham", "spurs",
        "newcastle united", "newcastle", "aston villa",
        "everton", "brighton", "west ham", "nottingham forest",
        "crystal palace", "brentford", "fulham", "bournemouth",
        "wolves", "sunderland", "leeds united", "leeds"
    ],
    "LaLiga": [
        "real madrid", "barcelona", "atletico madrid",
        "atlético madrid", "sevilla", "valencia",
        "villarreal", "athletic bilbao", "real sociedad",
        "girona", "real betis"
    ],
    "Serie A": [
        "inter milan", "internazionale", "ac milan",
        "juventus", "napoli", "roma", "lazio", "atalanta",
        "fiorentina", "bologna"
    ],
    "Bundesliga": [
        "bayern munich", "bayern münchen", "borussia dortmund",
        "bayer leverkusen", "rb leipzig", "eintracht frankfurt",
        "stuttgart", "wolfsburg"
    ],
    "Ligue 1": [
        "paris saint-germain", "paris saint germain", "psg",
        "marseille", "monaco", "lyon", "lille", "nice"
    ]
}

FOOTBALL_CONTEXT_KEYWORDS = [
    "sepak bola", "football", "soccer", "klub sepak bola",
    "pemain sepak bola", "pesepak bola", "pertandingan",
    "liga sepak bola", "tim sepak bola", "gol", "mencetak gol",
    "striker", "penyerang", "bek", "kiper", "gelandang",
    "pelatih", "manajer", "transfer pemain", "bursa transfer",
    "timnas", "tim nasional", "liga champions", "premier league",
    "laliga", "la liga", "serie a", "bundesliga", "ligue 1",
    "europa league", "conference league", "liga 1 indonesia"
]


# ==========================================
# UTILITAS TEKS, TANGGAL, DAN URL
# ==========================================

def clean_text(value):
    """Membersihkan HTML dan whitespace tanpa mengubah isi kalimat."""
    if value is None:
        return ""

    if not isinstance(value, str):
        value = str(value)

    value = html.unescape(value)
    value = re.sub(r"<script\b[^>]*>.*?</script>", " ", value,
                   flags=re.IGNORECASE | re.DOTALL)
    value = re.sub(r"<style\b[^>]*>.*?</style>", " ", value,
                   flags=re.IGNORECASE | re.DOTALL)
    value = re.sub(r"<[^>]+>", " ", value)
    value = re.sub(r"\s+", " ", value)
    return value.strip()


def normalize_text(value):
    value = clean_text(value).casefold()
    value = unicodedata.normalize("NFKC", value)
    return value


def parse_datetime(value):
    if not value:
        return ""

    if isinstance(value, (int, float)):
        try:
            return datetime.fromtimestamp(
                value, tz=timezone.utc
            ).isoformat()
        except (ValueError, OverflowError, OSError):
            return ""

    value = str(value).strip()

    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=timezone.utc)
        return parsed.astimezone(timezone.utc).isoformat()
    except (TypeError, ValueError, OverflowError):
        return ""


def date_timestamp(value):
    try:
        parsed = datetime.fromisoformat(
            str(value).replace("Z", "+00:00")
        )
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=timezone.utc)
        return parsed.timestamp()
    except (TypeError, ValueError, OverflowError):
        return 0


def canonical_url(url):
    if not url:
        return ""

    try:
        parts = urlsplit(str(url).strip())
        tracking = {
            "utm_source", "utm_medium", "utm_campaign",
            "utm_content", "utm_term", "at_medium",
            "at_campaign", "fbclid", "gclid"
        }
        query = [
            (key, value)
            for key, value in parse_qsl(parts.query)
            if key.lower() not in tracking
        ]
        return urlunsplit((
            parts.scheme, parts.netloc, parts.path,
            urlencode(query), ""
        ))
    except Exception:
        return str(url).strip()


def make_article_id(article_id, url):
    seed = str(article_id or canonical_url(url) or "").strip()
    return hashlib.sha256(seed.encode("utf-8")).hexdigest()[:16]


# ==========================================
# REQUEST AJEL WIRE
# ==========================================

def ajel_get(path, params=None):
    if not AJEL_API_KEY:
        raise RuntimeError(
            "Secret AJEL_WIRE_API_KEY belum tersedia di environment."
        )

    query = urlencode(params or {})
    url = f"{AJEL_BASE_URL}{path}"
    if query:
        url = f"{url}?{query}"

    request = urllib.request.Request(
        url,
        headers={
            "Accept": "application/json",
            "User-Agent": USER_AGENT,
            "x-api-key": AJEL_API_KEY
        },
        method="GET"
    )

    with urllib.request.urlopen(
        request, timeout=REQUEST_TIMEOUT
    ) as response:
        raw = response.read()

    try:
        return json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as error:
        raise RuntimeError(
            f"Respons Ajel bukan JSON UTF-8 yang valid: {error}"
        ) from error


# ==========================================
# PEMERIKSAAN IZIN DAN ATRIBUSI AJEL
# ==========================================

def usage_permissions(article):
    usage = article.get("usage") or {}
    if not isinstance(usage, dict):
        usage = {}

    # Artikel hanya diproses jika izin publikasi ulang dan penggunaan
    # komersial dinyatakan secara eksplisit oleh metadata Ajel.
    republication = usage.get(
        "republication_allowed",
        usage.get("republish_allowed")
    )
    commercial = usage.get("commercial_use_allowed")

    return republication is True and commercial is True


def get_attribution(article, source_url):
    attribution = article.get("attribution") or {}
    if not isinstance(attribution, dict):
        attribution = {}

    brand = (
        attribution.get("brand")
        or attribution.get("brand_latin")
        or "Ajel"
    )
    text = attribution.get("text") or f"Sumber: {brand}"
    url = attribution.get("url") or source_url

    return {
        "brand": clean_text(brand),
        "text": clean_text(text),
        "url": canonical_url(url)
    }


def get_reusable_image(article):
    """
    Hanya mengambil media gambar yang ditandai reuse_allowed=true.
    Media tanpa izin eksplisit tidak digunakan.
    """
    media_items = article.get("media") or []
    if not isinstance(media_items, list):
        return ""

    for media in media_items:
        if not isinstance(media, dict):
            continue

        media_type = str(media.get("type") or "").lower()
        media_url = str(media.get("url") or "").strip()

        if media.get("reuse_allowed") is not True:
            continue
        if not media_url.startswith(("https://", "http://")):
            continue
        if media_type not in ("image", "photo", "thumbnail", "cover"):
            continue

        return media_url

    return ""


# ==========================================
# FILTER DAN KLASIFIKASI BERITA
# ==========================================

def contains_any(text, keywords):
    return any(keyword in text for keyword in keywords)


def is_womens_football(text):
    return contains_any(text, WOMENS_FOOTBALL_KEYWORDS)


def is_saudi_pro_league_story(text):
    text = normalize_text(text)

    # Penyebutan kompetisi domestik secara eksplisit selalu disaring.
    if contains_any(text, SAUDI_PRO_LEAGUE_KEYWORDS):
        return True

    # Nama klub Saudi saja tidak cukup untuk menyimpulkan bahwa berita
    # membahas Saudi Pro League. Harus ada konteks laga/kompetisi domestik.
    mentions_saudi_club = contains_any(text, SAUDI_CLUB_KEYWORDS)
    if not mentions_saudi_club:
        return False

    mentions_international_competition = contains_any(
        text,
        [
            "champions league", "liga champions",
            "afc champions league", "acl elite",
            "fifa club world cup", "piala dunia antarklub"
        ]
    )
    if mentions_international_competition:
        return False

    domestic_match_context = [
        "pertandingan", "laga", "mengalahkan", "dikalahkan",
        "menang", "kalah", "imbang", "hasil pertandingan",
        "klasemen", "poin", "pekan ke", "matchday",
        "league match", "liga domestik", "domestic league",
        "saudi league", "liga saudi"
    ]
    return contains_any(text, domestic_match_context)


def is_relevant(title, summary, section_slug=""):
    content = normalize_text(f"{title} {summary}")

    if not title.strip():
        return False

    if is_womens_football(content):
        return False

    if is_saudi_pro_league_story(content):
        return False

    if contains_any(content, EXCLUDED_KEYWORDS):
        return False

    if contains_any(content, LIVE_OR_VIDEO_KEYWORDS):
        return False

    # Bagian olahraga Ajel memuat olahraga non-sepak bola.
    # Berita harus memiliki sinyal sepak bola yang jelas.
    if not contains_any(content, FOOTBALL_CONTEXT_KEYWORDS):
        return False

    return True


def classify_article(title, summary):
    title_text = normalize_text(title)
    content = normalize_text(f"{title} {summary}")

    # Timnas Indonesia harus diprioritaskan.
    if contains_any(content, INDONESIA_TEAM_KEYWORDS):
        return "Timnas Indonesia"

    # Tim nasional negara lain, termasuk pertandingan persahabatan,
    # masuk kategori Tim Nasional (bukan Friendly Match).
    if contains_any(content, NATIONAL_TEAM_KEYWORDS):
        return "Tim Nasional"

    # Berita tim junior/akademi klub yang bukan berita tim nasional.
    if contains_any(
        content,
        [
            "tim junior", "junior team", "youth team",
            "tim muda", "pemain muda", "youth squad",
            "under-17", "under 17", "u-17", "u17"
        ]
    ):
        return "Sepak Bola Usia Muda"

    # Berita pengelolaan dan aktivitas klub yang tidak terkait
    # langsung dengan kompetisi tertentu.
    if contains_any(
        content,
        [
            "tunjuk", "menunjuk", "pelatih sementara",
            "interim coach", "appoints", "appointed as coach"
        ]
    ) and contains_any(
        content,
        ["klub", "club", "al ahly", "al-ahly"]
    ):
        return "Berita Klub"

    # Berita kondisi atau aktivitas individu pemain.
    if contains_any(
        content,
        [
            "kiper", "penjaga gawang", "goalkeeper",
            "striker", "penyerang", "gelandang",
            "bek", "pemain kembali berlatih", "resumes training"
        ]
    ):
        return "Berita Pemain"

    # Kompetisi yang disebut secara eksplisit.
    for category, keywords in COMPETITION_CATEGORIES.items():
        if contains_any(title_text, keywords):
            return category

    # Klub yang disebut langsung di judul.
    for category, clubs in CLUB_CATEGORIES.items():
        if contains_any(title_text, clubs):
            return category

    # Jika judul kurang spesifik, gunakan ringkasan.
    for category, keywords in COMPETITION_CATEGORIES.items():
        if contains_any(content, keywords):
            return category

    for category, clubs in CLUB_CATEGORIES.items():
        if contains_any(content, clubs):
            return category

    # Liga Indonesia dan timnas Indonesia sudah diperiksa di atas.
    return "Berita Sepak Bola"


# ==========================================
# MEMBANGUN RINGKASAN TANPA AI
# ==========================================

def make_summary(article):
    """
    Tanpa AI: gunakan summary Ajel yang sudah tersedia.
    Tidak membuat fakta, skor, kutipan, atau konteks baru.
    """
    summary = clean_text(article.get("summary") or "")

    if summary:
        return summary[:700].rstrip()

    # Beberapa respons detail mungkin menyediakan content_text.
    # Jika tidak ada summary, ambil kalimat pembuka secara konservatif.
    content = clean_text(
        article.get("content_text")
        or article.get("content")
        or ""
    )

    if not content:
        return ""

    sentences = re.split(r"(?<=[.!?])\s+", content)
    selected = " ".join(sentences[:2]).strip()
    return selected[:700].rstrip()


# ==========================================
# KONVERSI ARTIKEL AJEL KE FORMAT FRONTEND
# ==========================================

def normalize_ajel_article(article):
    if not isinstance(article, dict):
        return None

    title = clean_text(article.get("title") or "")
    summary = make_summary(article)

    source_url = canonical_url(
        article.get("canonical_url")
        or article.get("url")
        or ""
    )

    article_id = article.get("id")

    if not title or not source_url:
        return None

    # Status eksplisit yang menandakan artikel tidak layak tampil.
    status = str(article.get("status") or "").strip().lower()
    if status in {
        "withdrawn", "deleted", "removed",
        "unpublished", "draft", "retracted"
    }:
        return None

    # Wajib ada izin publikasi ulang dan komersial dari metadata.
    if not usage_permissions(article):
        log.info("Lewati artikel tanpa izin publikasi/komersial eksplisit: %s", title)
        return None

    if not summary:
        return None

    if not is_relevant(title, summary):
        return None

    category = classify_article(title, summary)

    # Jangan membuat kategori khusus Friendly Match atau Women's Football.
    if category in {"Friendly Match", "Women's Football"}:
        return None

    attribution = get_attribution(article, source_url)
    usage = article.get("usage") or {}
    if not isinstance(usage, dict):
        usage = {}

    return {
        "id": make_article_id(article_id, source_url),
        "title": title,
        "summary": summary,
        "category": category,
        "source": "Ajel",
        "source_url": source_url,
        "published_at": parse_datetime(article.get("published_at")),
        "image_url": get_reusable_image(article),
        "language": "id",
        "status": "source_only",
        "attribution": attribution,
        "attribution_required": usage.get("attribution_required", True),
        "license_source": "Ajel Wire Usage and Attribution Policy"
    }


# ==========================================
# PENGAMBILAN BERITA AJEL DENGAN PAGINATION
# ==========================================

def fetch_ajel_news():
    log.info("Mengambil berita dari Ajel Wire API...")

    collected = []
    cursor = None
    seen_cursors = set()
    successful_pages = 0

    for page_number in range(1, AJEL_MAX_PAGES + 1):
        params = {
            "language": AJEL_LANGUAGE,
            "section": AJEL_SECTION,
            "limit": AJEL_PAGE_SIZE
        }

        if cursor:
            params["cursor"] = cursor

        payload = ajel_get("/v1/latest", params)

        if not isinstance(payload, dict):
            raise RuntimeError("Format respons Ajel tidak sesuai: objek JSON tidak ditemukan.")

        data = payload.get("data")
        if not isinstance(data, list):
            raise RuntimeError("Format respons Ajel tidak sesuai: field 'data' bukan daftar.")

        successful_pages += 1
        log.info("Halaman Ajel %s: %s item mentah", page_number, len(data))

        for item in data:
            normalized = normalize_ajel_article(item)
            if normalized:
                collected.append(normalized)

        pagination = payload.get("pagination") or {}
        if not isinstance(pagination, dict):
            pagination = {}

        next_cursor = pagination.get("next_cursor")
        if not next_cursor:
            break

        next_cursor = str(next_cursor)
        if next_cursor in seen_cursors:
            log.warning("Cursor Ajel berulang; pagination dihentikan untuk mencegah loop.")
            break

        seen_cursors.add(next_cursor)
        cursor = next_cursor

        if len(collected) >= MAX_NEWS * 2:
            break

    log.info(
        "Ajel berhasil: %s halaman, %s berita lolos filter",
        successful_pages, len(collected)
    )

    return collected, successful_pages


# ==========================================
# DEDUPLIKASI
# ==========================================

def normalize_title(title):
    text = normalize_text(title)
    # \w mempertahankan huruf Unicode, termasuk aksen.
    text = re.sub(r"[^\w\s]", " ", text, flags=re.UNICODE)
    return " ".join(text.split())


def remove_similar_duplicates(articles, threshold=0.91,
                               content_overlap_threshold=0.50):
    """
    Deduplikasi konservatif:
    1. Judul yang hampir identik tetap disaring.
    2. Artikel dengan gabungan judul + ringkasan yang sangat tumpang
       tindih juga disaring.
    Ambang konten dibuat tinggi agar berita berbeda tentang pertandingan
    yang sama (preview, hasil, dan momen gol) tetap dipertahankan.
    """
    unique = []

    for article in articles:
        current_title = normalize_title(article.get("title", ""))
        if not current_title:
            continue

        current_content = normalize_title(
            f"{article.get('title', '')} {article.get('summary', '')}"
        )
        current_tokens = {
            token for token in current_content.split() if len(token) > 2
        }

        duplicate = False

        for existing in unique:
            existing_title = normalize_title(existing.get("title", ""))

            title_similarity = difflib.SequenceMatcher(
                None, current_title, existing_title
            ).ratio()

            existing_content = normalize_title(
                f"{existing.get('title', '')} {existing.get('summary', '')}"
            )
            existing_tokens = {
                token for token in existing_content.split() if len(token) > 2
            }

            union = current_tokens | existing_tokens
            content_overlap = (
                len(current_tokens & existing_tokens) / len(union)
                if union else 0.0
            )

            if (
                title_similarity >= threshold
                or content_overlap >= content_overlap_threshold
            ):
                duplicate = True
                log.info(
                    "Duplikat konservatif disaring (judul %.2f, konten %.2f): %s",
                    title_similarity, content_overlap,
                    article.get("title", "")
                )
                break

        if not duplicate:
            unique.append(article)

    return unique


# ==========================================
# PENYIMPANAN JSON YANG AMAN
# ==========================================

def write_news_json(news, pages_checked):
    output = {
        "site": "Football Pulse AI",
        "updated_at": datetime.now(timezone.utc).isoformat(),
        "total": len(news),
        "sources_checked": 1,
        "articles": news
    }

    temp_file = OUTPUT_FILE.with_suffix(".json.tmp")

    temp_file.write_text(
        json.dumps(output, ensure_ascii=False, indent=2),
        encoding="utf-8"
    )

    temp_file.replace(OUTPUT_FILE)

    log.info("========================================")
    log.info("FOOTBALL PULSE AI NEWS UPDATE - v6.2")
    log.info("Total berita: %s", len(news))
    log.info("Sumber aktif: Ajel Wire")
    log.info("Halaman Ajel diperiksa: %s", pages_checked)
    log.info("File tersimpan: %s", OUTPUT_FILE)
    log.info("========================================")


# ==========================================
# PROSES UTAMA
# ==========================================

def main():
    if not AJEL_API_KEY:
        log.error(
            "AJEL_WIRE_API_KEY tidak ditemukan. "
            "Pastikan GitHub Secret sudah dipasang ke workflow."
        )
        raise SystemExit(1)

    try:
        articles, pages_checked = fetch_ajel_news()

    except urllib.error.HTTPError as error:
        # Jangan menampilkan URL request atau header agar secret aman.
        log.error("Ajel API mengembalikan HTTP %s.", error.code)
        log.error("news.json lama dipertahankan.")
        raise SystemExit(1)

    except urllib.error.URLError as error:
        log.error("Koneksi ke Ajel gagal: %s", error.reason)
        log.error("news.json lama dipertahankan.")
        raise SystemExit(1)

    except Exception as error:
        log.exception("Pengambilan Ajel gagal: %s", error)
        log.error("news.json lama dipertahankan.")
        raise SystemExit(1)

    # Jika API berhasil tetapi tidak ada berita yang lolos filter,
    # tulis daftar kosong secara valid. Ini berbeda dari API gagal.
    unique_by_url = {}

    for article in articles:
        key = canonical_url(article.get("source_url", ""))
        if key and key not in unique_by_url:
            unique_by_url[key] = article

    news = list(unique_by_url.values())

    news.sort(
        key=lambda item: date_timestamp(item.get("published_at", "")),
        reverse=True
    )

    before_dedupe = len(news)
    news = remove_similar_duplicates(news)
    log.info("Duplikat judul disaring: %s", before_dedupe - len(news))

    # Tidak ada batas usia berita. Batas 30 hanya jumlah berita di frontend.
    news = news[:MAX_NEWS]

    write_news_json(news, pages_checked)


if __name__ == "__main__":
    main()
