import asyncio
import logging
import os
import statistics
import urllib.parse

import httpx

logger = logging.getLogger(__name__)

APIFY_TOKEN  = os.getenv("APIFY_API_TOKEN", "")
HH_APP_TOKEN = os.getenv("HH_APP_TOKEN", "")   # optional hh.ru application token

HH_API_URL   = "https://api.hh.ru/vacancies"
HH_HEADERS   = {"User-Agent": "LocationScout/1.0", "HH-User-Agent": "LocationScout/1.0"}
# hh.ru area ids: Almaty 160, Astana 159, whole Kazakhstan 40
HH_AREAS     = {"almaty": 160, "astana": 159}
APIFY_TIMEOUT_S = 60

CATEGORY_KEYWORD_MAP = {
    "restaurant": ["шеф-повар", "повар", "официант", "управляющий рестораном"],
    "coffee shop": ["бариста", "управляющий кофейней", "кассир кофе"],
    "bar/nightclub": ["бармен", "диджей", "охранник клуб", "управляющий баром"],
    "hotel/lodging": ["администратор гостиницы", "горничная", "портье"],
    "retail store": ["продавец-консультант", "управляющий магазином"],
    "grocery/supermarket": ["кассир", "продавец продуктов", "заведующий складом"],
    "shopping mall": ["администратор ТЦ", "охранник торговый центр"],
    "healthcare/medical": ["врач", "медсестра", "администратор клиника"],
    "fitness center/gym": ["персональный тренер", "инструктор фитнес", "администратор зал"],
    "pharmacy": ["провизор", "фармацевт", "первостольник"],
    "salon/spa": ["парикмахер", "косметолог", "мастер маникюра", "массажист"],
    "professional services": ["юрист", "бухгалтер", "менеджер проектов"],
    "automotive services": ["автомеханик", "мастер автосервис", "автоэлектрик"],
    "financial services/bank": ["операционист банк", "кредитный специалист"],
    "education/school": ["учитель", "репетитор", "воспитатель", "администратор учебный центр"],
    "entertainment venue": ["аниматор", "звукорежиссер", "организатор мероприятий"],
    "arts & culture": ["художник", "экскурсовод", "библиотекарь", "музейный работник"],
    "real estate": ["риелтор", "агент недвижимость", "менеджер по аренде"],
    "technology": ["разработчик", "системный администратор", "техническая поддержка"],
    "manufacturing": ["оператор станка", "инженер производство", "сборщик", "кладовщик"]
}

RESUME_PAGE_FUNCTION = r"""
                async function pageFunction(context) {
                    const elements = Array.from(document.querySelectorAll('[data-qa="resume-serp__resume"]')).slice(0, 5);
                    const resumes = elements.map(el => {
                        const titleEl = el.querySelector('[data-qa="resume-serp__resume-title"], h2, h3, a[href*="/resume/"]');
                        const linkEl = el.querySelector('a[href*="/resume/"]');
                        const expEl = el.querySelector('[data-qa="resume-serp__resume-excpeience-sum"]');
                        const ageEl = el.querySelector('[data-qa="resume-serp__resume-age"]');
                        
                        const title = titleEl ? titleEl.innerText.trim() : 'Кандидат';
                        const link = linkEl ? 'https://hh.kz' + linkEl.getAttribute('href') : '';
                        const exp = expEl ? expEl.innerText.trim() : 'Опыт не указан';
                        const age = ageEl ? ageEl.innerText.trim() : '';
                        
                        let salary = 'по договорённости';
                        const salMatch = el.innerText.match(/(\d[\d\s]+(₸|KZT|руб\.|USD))/);
                        if (salMatch) salary = salMatch[1];
                        
                        return {
                            name: age ? 'Кандидат (' + age + ')' : 'Кандидат',
                            title: title,
                            link: link,
                            experience: exp,
                            salary: salary
                        };
                    });
                    
                    if (resumes.length === 0) {
                        return [{error: true, html: document.body.innerHTML.slice(0, 300)}];
                    }
                    return resumes;
                }
            """

# Fallback when hh.ru gives no data (since April 2026 the public vacancy API
# answers 403 without an employer/partner token). Official statistics:
# Bureau of National Statistics (BNS) of Kazakhstan, median monthly wage by
# economic activity, 2026 (published by NUR.KZ on 04.11.2026).
BNS_SECTOR_MEDIAN = {
    "coffee shop":        ("food",   335_605),
    "restaurant":         ("food",   335_605),
    "retail store":       ("trade",  345_472),
    "grocery/supermarket":("trade",  345_472),
    "fitness center/gym": ("arts",   251_749),
    "salon/spa":          ("other",  409_352),
}
BNS_ALMATY_MEDIAN = 429_633
BNS_SECTOR_NAMES = {
    "food":  {"en": "accommodation & food services", "ru": "услуги по проживанию и питанию", "kk": "тұру және тамақтану қызметтері"},
    "trade": {"en": "wholesale & retail trade",      "ru": "оптовая и розничная торговля",    "kk": "көтерме және бөлшек сауда"},
    "arts":  {"en": "arts, entertainment & recreation", "ru": "искусство, развлечения и отдых", "kk": "өнер, ойын-сауық және демалыс"},
    "other": {"en": "other service activities",       "ru": "предоставление прочих видов услуг", "kk": "өзге де қызметтер"},
}

TEXT = {
    "en": {"market": "Labour market", "vacancies": "open vacancies", "median": "Median salary",
           "range": "Range", "examples": "Who is hiring now", "candidates": "Candidates (public hh.kz resumes)",
           "no_cands": "Live resume parsing is unavailable right now — use the links below.",
           "no_market": "hh.ru vacancy data is unavailable right now.", "bns_title": "Official average (hh.ru data unavailable)", "bns_sector": "Median wage in the sector", "bns_city": "Median wage in Almaty, all sectors", "bns_note": "Source: Bureau of National Statistics of Kazakhstan, 2026. hh.ru closed its public vacancy API in April 2026; live salaries require an employer token (HH_APP_TOKEN).",
           "search": "Search", "on_hh": "on HeadHunter", "note": "Salary data: official hh.ru API (vacancies with a stated salary)."},
    "ru": {"market": "Рынок труда", "vacancies": "открытых вакансий", "median": "Медианная зарплата",
           "range": "Диапазон", "examples": "Кто сейчас нанимает", "candidates": "Кандидаты (открытые резюме hh.kz)",
           "no_cands": "Живой парсинг резюме сейчас недоступен — воспользуйтесь ссылками ниже.",
           "no_market": "Данные о вакансиях hh.ru сейчас недоступны.", "bns_title": "Официальная статистика (данные hh.ru недоступны)", "bns_sector": "Медианная зарплата в отрасли", "bns_city": "Медианная зарплата в Алматы, все отрасли", "bns_note": "Источник: Бюро национальной статистики РК, 2026. С апреля 2026 hh.ru закрыл публичный API вакансий; живые зарплаты доступны по токену работодателя (HH_APP_TOKEN).",
           "search": "Искать", "on_hh": "на HeadHunter", "note": "Зарплаты: официальный API hh.ru (вакансии с указанной зарплатой)."},
    "kk": {"market": "Еңбек нарығы", "vacancies": "ашық вакансия", "median": "Медиандық жалақы",
           "range": "Диапазон", "examples": "Қазір кім жалдап жатыр", "candidates": "Үміткерлер (hh.kz ашық түйіндемелері)",
           "no_cands": "Түйіндемелерді талдау қазір қолжетімсіз — төмендегі сілтемелерді пайдаланыңыз.",
           "no_market": "hh.ru вакансия деректері қазір қолжетімсіз.", "bns_title": "Ресми статистика (hh.ru деректері қолжетімсіз)", "bns_sector": "Саладағы медиандық жалақы", "bns_city": "Алматыдағы медиандық жалақы, барлық салалар", "bns_note": "Дереккөз: ҚР Ұлттық статистика бюросы, 2026. 2026 жылдың сәуірінен hh.ru ашық вакансия API-ін жапты; нақты жалақылар үшін жұмыс беруші токені қажет (HH_APP_TOKEN).",
           "search": "Іздеу", "on_hh": "HeadHunter-де", "note": "Жалақы: hh.ru ресми API (жалақысы көрсетілген вакансиялар)."},
}


def _fmt_kzt(v: float) -> str:
    return f"{v:,.0f}".replace(",", " ") + " ₸"


async def _hh_vacancy_market(keyword: str, city: str) -> dict | None:
    """Salary stats + example vacancies from the public hh.ru API."""
    from app.i18n.terms import get_city_key
    area = HH_AREAS.get(get_city_key(city or "").lower(), 40)
    headers = dict(HH_HEADERS)
    if HH_APP_TOKEN:
        headers["Authorization"] = f"Bearer {HH_APP_TOKEN}"
    params = {"text": keyword, "area": area, "per_page": 50, "only_with_salary": "true"}
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.get(HH_API_URL, params=params, headers=headers)
            if resp.status_code != 200:
                # 403 = hh.ru closed anonymous vacancy search (April 2026);
                # an employer/partner token is required (HH_APP_TOKEN).
                logger.warning("hh.ru API %s: %s", resp.status_code, resp.text[:200])
                return None
            data = resp.json()
    except Exception as e:
        logger.warning("hh.ru API error: %s", e)
        return None

    salaries, examples = [], []
    for v in data.get("items", []):
        sal = v.get("salary") or {}
        if sal.get("currency") != "KZT":
            continue
        lo, hi = sal.get("from"), sal.get("to")
        if not lo and not hi:
            continue
        mid = ((lo or hi) + (hi or lo)) / 2
        if sal.get("gross"):
            mid *= 0.9  # rough net
        salaries.append(mid)
        if len(examples) < 5:
            examples.append({
                "name": v.get("name", ""),
                "employer": (v.get("employer") or {}).get("name", ""),
                "salary": mid,
                "url": v.get("alternate_url", ""),
            })
    if not salaries:
        return {"found": data.get("found", 0), "median": None, "examples": examples}
    return {
        "found":   data.get("found", len(salaries)),
        "median":  statistics.median(salaries),
        "p25":     statistics.quantiles(salaries, n=4)[0] if len(salaries) >= 4 else min(salaries),
        "p75":     statistics.quantiles(salaries, n=4)[2] if len(salaries) >= 4 else max(salaries),
        "examples": examples,
    }


async def _scrape_resumes_apify(search_url: str) -> list[dict]:
    """Optional: public hh.kz resume cards via Apify web-scraper (slow, may be blocked)."""
    if not APIFY_TOKEN:
        return []
    try:
        from apify_client import ApifyClientAsync
        client = ApifyClientAsync(APIFY_TOKEN)
        run_input = {
            "startUrls": [{"url": search_url}],
            "pageFunction": RESUME_PAGE_FUNCTION,
            "proxyConfiguration": {"useApifyProxy": True},
        }
        logger.info("Triggering Apify scraper for URL: %s", search_url)
        run = await asyncio.wait_for(
            client.actor("apify/web-scraper").call(run_input=run_input, timeout_secs=APIFY_TIMEOUT_S),
            timeout=APIFY_TIMEOUT_S + 15,
        )
        if not run:
            return []
        items = (await client.dataset(run["defaultDatasetId"]).list_items()).items
    except Exception as e:
        logger.warning("Apify HH scraping failed: %r", e)
        return []

    candidates = []
    for item in items or []:
        for c in (item if isinstance(item, list) else [item]):
            if isinstance(c, dict) and not c.get("error") and c.get("title"):
                candidates.append(c)
    return candidates[:5]


async def get_workers(business_type: str, city: str, lang: str = "en") -> dict:
    from app.i18n.terms import get_business_type_key, get_display_label
    t = TEXT.get((lang or "en").lower(), TEXT["en"])

    bt_key = get_business_type_key(business_type.strip())
    keywords = CATEGORY_KEYWORD_MAP.get(bt_key) or ["менеджер", "администратор"]
    top_keywords = keywords[:2]
    primary_keyword = top_keywords[0]

    from app.i18n.terms import get_search_ru
    city_ru = get_search_ru(city, "city") or city

    def resume_url(kw: str) -> str:
        q = urllib.parse.quote_plus(f"{kw} {city_ru}")
        return f"https://hh.kz/search/resume?text={q}&logic=normal&pos=full_text&exp_period=all_time"

    market, candidates = await asyncio.gather(
        _hh_vacancy_market(primary_keyword, city),
        _scrape_resumes_apify(resume_url(primary_keyword)),
    )

    city_label = get_display_label(city, "city", lang)
    md = f"### 💰 {t['market']}: «{primary_keyword}», {city_label}\n\n"
    if market and market.get("median"):
        md += f"- **{t['median']}**: {_fmt_kzt(market['median'])}\n"
        md += f"- **{t['range']}** (25–75%): {_fmt_kzt(market['p25'])} – {_fmt_kzt(market['p75'])}\n"
        md += f"- **{market['found']}** {t['vacancies']}\n\n"
        if market["examples"]:
            md += f"**{t['examples']}:**\n\n"
            for v in market["examples"]:
                md += f"- {v['name']} — {v['employer']}, ~{_fmt_kzt(v['salary'])} [hh.kz]({v['url']})\n"
            md += "\n"
    else:
        sector_key, sector_median = BNS_SECTOR_MEDIAN.get(bt_key, ("other", BNS_ALMATY_MEDIAN))
        lang_key = (lang or "en").lower() if (lang or "en").lower() in ("en", "ru", "kk") else "en"
        md += f"**{t['bns_title']}**\n\n"
        md += f"- **{t['bns_sector']}** ({BNS_SECTOR_NAMES[sector_key][lang_key]}): {_fmt_kzt(sector_median)}\n"
        md += f"- **{t['bns_city']}**: {_fmt_kzt(BNS_ALMATY_MEDIAN)}\n\n"
        md += f"*{t['bns_note']}*\n\n"
        market = {"source": "BNS", "median": None, "sector_median": sector_median,
                  "city_median": BNS_ALMATY_MEDIAN, "estimated": True}

    md += f"### 🧑‍💼 {t['candidates']}\n\n"
    if candidates:
        for c in candidates:
            md += (f"- **{c.get('name', 'Кандидат')}** — *{c.get('title', '')}* · "
                   f"💼 {c.get('experience', 'Опыт не указан')} · 💰 {c.get('salary', 'по договорённости')} "
                   f"[hh.kz]({c.get('link') or resume_url(primary_keyword)})\n")
        md += "\n"
    else:
        md += f"*{t['no_cands']}*\n\n"

    md += "---\n"
    for kw in top_keywords:
        md += f"🔎 [{t['search']} «{kw}» {t['on_hh']}]({resume_url(kw)})\n\n"
    if market and market.get("source") != "BNS":
        md += f"*{t['note']}*\n"
    return {"workers_md": md, "market": market, "candidates": candidates}
