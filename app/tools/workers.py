import logging
import urllib.parse
from apify_client import ApifyClientAsync
import os

logger = logging.getLogger(__name__)

# User provided specific Token:
APIFY_TOKEN = os.getenv("APIFY_API_TOKEN", "")

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

async def get_workers(business_type: str, city: str) -> dict:
    from app.i18n.terms import get_business_type_key
    bt_key = get_business_type_key(business_type.strip())
    keywords = CATEGORY_KEYWORD_MAP.get(bt_key) or CATEGORY_KEYWORD_MAP.get(business_type.lower().strip())
    
    if not keywords:
        keywords = ["менеджер", "администратор"]

    top_keywords = keywords[:2]
    primary_keyword = top_keywords[0]
    
    query = f"{primary_keyword} {city}"
    safe_query = urllib.parse.quote_plus(query)
    search_url = f"https://hh.kz/search/resume?text={safe_query}&logic=normal&pos=full_text&exp_period=all_time"
    
    candidates = []
    
    try:
        # Initialise the Apify client
        client = ApifyClientAsync(APIFY_TOKEN)
        
        # Run the Web Scraper Actor (apify/web-scraper)
        run_input = {
            "startUrls": [{"url": search_url}],
            "pageFunction": r"""
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
            """,
            "proxyConfiguration": {"useApifyProxy": True}
        }

        logger.info(f"Triggering Apify scraper for URL: {search_url}")
        run = await client.actor("apify/web-scraper").call(run_input=run_input)
        
        # Retrieve results
        dataset_items = (await client.dataset(run["defaultDatasetId"]).list_items()).items
        
        if dataset_items and len(dataset_items) > 0:
            for item in dataset_items:
                if type(item) is list:
                    for c in item:
                        if not c.get("error"):
                            candidates.append(c)
                elif not item.get("error"):
                    candidates.append(item)
                    
    except Exception as e:
        logger.error(f"Failed to scrape HH using Apify: {e}")
        
    md = f"🔎 **Top {len(candidates) if candidates else 0} Local Candidates in {city.capitalize()} for {business_type}**\n\n"
    
    if candidates:
        for idx, c in enumerate(candidates[:5], 1):
            md += f"{idx}️⃣ **{c.get('name', 'Candidate')}** — *{c.get('title', 'Unknown')}*\n"
            md += f"   📍 {city.capitalize()}\n"
            md += f"   💼 {c.get('experience', 'Опыт не указан')}\n"
            md += f"   💰 {c.get('salary', 'по договорённости')}\n"
            link = c.get('link') or search_url
            md += f"   🔗 [View Profile]({link})\n\n"
    else:
        md += "⚠️ *Apify scraping failed or no visible candidates found. Anti-bot proxies might be rate-limited.*\n\n"
        
    md += "---\n"
    md += "⚠️ *Data sourced from public hh.kz profiles. Please contact candidates through the official platform.*\n"
    md += f"🔄 [Search '{primary_keyword}' More on HeadHunter]({search_url})\n"
    
    if len(top_keywords) > 1:
        sec_query = urllib.parse.quote_plus(f"{top_keywords[1]} {city}")
        sec_url = f"https://hh.kz/search/resume?text={sec_query}&logic=normal&pos=full_text&exp_period=all_time"
        md += f"🔄 [Search '{top_keywords[1]}' More on HeadHunter]({sec_url})\n"
        
    return {"workers_md": md}
