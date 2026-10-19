import unicodedata
import re
from typing import Optional, Dict, Any

# =============================================================================
# BUSINESS TYPES
# =============================================================================

BUSINESS_TYPES = {
    "restaurant": {
        "en": "Restaurant",
        "ru": "Ресторан",
        "kk": "Мейрамхана",
        "search_ru": "ресторан",
        "aliases": ["restaurants", "рестораны", "мейрамханалар", "restoran", "restoranlar", "diner", "кафе", "рест"]
    },
    "coffee shop": {
        "en": "Coffee Shop",
        "ru": "Кофейня",
        "kk": "Кофехана",
        "search_ru": "кофейня",
        "aliases": ["cafe", "кафе", "кофе шоп", "kofe shop", "кофе", "кофейни", "coffee", "coffeeshop", "кофейня", "кофехана"]
    },
    "bar/nightclub": {
        "en": "Bar / Nightclub",
        "ru": "Бар / Ночной клуб",
        "kk": "Бар / Түнгі клуб",
        "search_ru": "бар, ночной клуб",
        "aliases": ["bar", "бар", "клуб", "club", "nightclub", "ночной клуб", "түнгі клуб"]
    },
    "hotel/lodging": {
        "en": "Hotel",
        "ru": "Гостиница",
        "kk": "Қонақ үй",
        "search_ru": "гостиница, отель",
        "aliases": ["hotel", "отель", "гостиницы", "отели", "қонақүй"]
    },
    "retail store": {
        "en": "Retail Store",
        "ru": "Магазин одежды/товаров",
        "kk": "Бөлшек сауда дүкені",
        "search_ru": "магазин",
        "aliases": ["магазин", "store", "дүкен", "retail", "бутик", "boutique"]
    },
    "grocery/supermarket": {
        "en": "Grocery / Supermarket",
        "ru": "Супермаркет / Продукты",
        "kk": "Супермаркет / Азық-түлік",
        "search_ru": "супермаркет, продукты",
        "aliases": ["grocery", "супермаркет", "продукты", "азық түлік", "азық-түлік", "supermarket"]
    },
    "shopping mall": {
        "en": "Shopping Mall",
        "ru": "Торговый центр",
        "kk": "Сауда орталығы",
        "search_ru": "торговый центр",
        "aliases": ["mall", "тц", "торговый дом", "сауда үйі", "сауда орталығы", "трц", "shopping center"]
    },
    "healthcare/medical": {
        "en": "Medical Center",
        "ru": "Медицинский центр",
        "kk": "Медициналық орталық",
        "search_ru": "медицинский центр, клиника",
        "aliases": ["clinic", "клиника", "больница", "емхана", "медицина", "medical", "hospital"]
    },
    "fitness center/gym": {
        "en": "Gym / Fitness Center",
        "ru": "Фитнес-клуб / Трен. зал",
        "kk": "Фитнес клубы / Жаттығу залы",
        "search_ru": "фитнес клуб, тренажерный зал",
        "aliases": ["gym", "фитнес", "тренажерный зал", "спортзал", "спорт", "fitness", "спорт кешені"]
    },
    "pharmacy": {
        "en": "Pharmacy",
        "ru": "Аптека",
        "kk": "Дәріхана",
        "search_ru": "аптека",
        "aliases": ["аптека", "аптеки", "дәріхана", "pharmacy", "drugstore"]
    },
    "salon/spa": {
        "en": "Beauty Salon / Spa",
        "ru": "Салон красоты / SPA",
        "kk": "Сұлулық салоны / SPA",
        "search_ru": "салон красоты",
        "aliases": ["salon", "spa", "салон красоты", "спа", "сұлулық салоны", "парикмахерская", "beauty salon"]
    },
    "professional services": {
        "en": "Professional Services",
        "ru": "Профессиональные услуги",
        "kk": "Кәсіби қызметтер",
        "search_ru": "офис, услуги",
        "aliases": ["услуги", "сервис", "қызмет көрсету", "офис", "юрист", "бухгалтерия", "office"]
    },
    "automotive services": {
        "en": "Auto Service",
        "ru": "Автосервис",
        "kk": "Автосервис",
        "search_ru": "автосервис, сто",
        "aliases": ["сто", "автосервис", "автомойка", "car wash", "auto service", "көлік жуу", "көлік жөндеу"]
    },
    "financial services/bank": {
        "en": "Bank / Financial Services",
        "ru": "Банк / Финансы",
        "kk": "Банк / Қаржы қызметтері",
        "search_ru": "банк",
        "aliases": ["bank", "банк", "финансы", "қаржы", "отделение банка"]
    },
    "education/school": {
        "en": "School / Education",
        "ru": "Школа / Образование",
        "kk": "Мектеп / Білім беру",
        "search_ru": "школа, учебный центр",
        "aliases": ["school", "школа", "мектеп", "образование", "учебный центр", "білім", "education", "college"]
    },
    "entertainment venue": {
        "en": "Entertainment Venue",
        "ru": "Развлекательный центр",
        "kk": "Ойын-сауық орталығы",
        "search_ru": "развлекательный центр, кинотеатр",
        "aliases": ["кинотеатр", "cinema", "развлечения", "ойын-сауық", "парк развлечений", "entertainment"]
    },
    "arts & culture": {
        "en": "Arts & Culture",
        "ru": "Искусство и Культура",
        "kk": "Өнер және мәдениет",
        "search_ru": "музей, театр, галерея",
        "aliases": ["museum", "театр", "музей", "галерея", "көрме", "мұражай", "art", "culture", "искусство"]
    },
    "real estate": {
        "en": "Real Estate Agency",
        "ru": "Агентство недвижимости",
        "kk": "Жылжымайтын мүлік агенттігі",
        "search_ru": "агентство недвижимости",
        "aliases": ["недвижимость", "риелтор", "жылжымайтын мүлік", "real estate", "agency", "агентство"]
    },
    "technology": {
        "en": "IT / Technology",
        "ru": "IT компания",
        "kk": "IT компаниясы",
        "search_ru": "it компания, офис",
        "aliases": ["it", "tech", "technology", "ит компания", "программисты", "технологии"]
    },
    "manufacturing": {
        "en": "Manufacturing",
        "ru": "Производство",
        "kk": "Өндіріс",
        "search_ru": "производство, завод",
        "aliases": ["завод", "производство", "өндіріс", "фабрика", "factory", "manufacturing"]
    }
}


# =============================================================================
# CITIES
# =============================================================================

CITIES = {
    "almaty": {
        "en": "Almaty",
        "ru": "Алматы",
        "kk": "Алматы",
        "search_ru": "Алматы",
        "aliases": ["алматы", "almaty", "алма-ата", "alma-ata", "алмата"]
    },
    "astana": {
        "en": "Astana",
        "ru": "Астана",
        "kk": "Астана",
        "search_ru": "Астана",
        "aliases": ["астана", "astana", "нур-султан", "nur-sultan"]
    },
    "shymkent": {
        "en": "Shymkent",
        "ru": "Шымкент",
        "kk": "Шымкент",
        "search_ru": "Шымкент",
        "aliases": ["шымкент", "shymkent"]
    }
}


# =============================================================================
# DESTINATIONS
# =============================================================================

DESTINATIONS = {
    "kbtu": {
        "en": "KBTU",
        "ru": "КБТУ",
        "kk": "ҚБТУ",
        "search_ru": "КБТУ, Алматы",
        "aliases": ["кбту", "kbtu", "казахстанско-британский технический университет", "қазақстан-британ техникалық университеті"]
    },
    "kaznu": {
        "en": "KazNU",
        "ru": "КазНУ",
        "kk": "ҚазҰУ",
        "search_ru": "КазНУ, Алматы",
        "aliases": ["казну", "kaznu", "казахский национальный университет", "қазақ ұлттық университеті"]
    },
    "mega_center": {
        "en": "MEGA Center",
        "ru": "MEGA Центр",
        "kk": "MEGA Орталығы",
        "search_ru": "Mega Center, Алматы",
        "aliases": ["мега", "mega", "mega center", "мега центр", "mega alma-ata", "мега алма-ата"]
    }
}


# =============================================================================
# DISTRICTS & ZONES
# =============================================================================

DISTRICTS = {
    "almaly": {
        "en": "Almaly",
        "ru": "Алмалинский",
        "kk": "Алмалы",
        "aliases": ["алмалы", "almaly", "алмалинский", "алмалинском", "алмалинского"]
    },
    "bostandyq": {
        "en": "Bostandyq",
        "ru": "Бостандыкский",
        "kk": "Бостандық",
        "aliases": ["бостандык", "бостандыкский", "bostandyk", "bostandyq", "бостандық", "бостандыкском", "бостандыкского"]
    },
    "medeu": {
        "en": "Medeu",
        "ru": "Медеуский",
        "kk": "Медеу",
        "aliases": ["медеу", "медеуский", "medeu", "медеуском", "медеуского"]
    },
    "auezov": {
        "en": "Auezov",
        "ru": "Ауэзовский",
        "kk": "Әуезов",
        "aliases": ["ауэзов", "ауэзовский", "auezov", "әуезов", "ауэзовском", "ауэзовского"]
    },
    "alatau": {
        "en": "Alatau",
        "ru": "Алатауский",
        "kk": "Алатау",
        "aliases": ["алатау", "алатауский", "alatau", "алатауда", "алатауского"]
    },
    "zhetysu": {
        "en": "Zhetysu",
        "ru": "Жетысуский",
        "kk": "Жетісу",
        "aliases": ["жетысу", "жетысуский", "zhetysu", "zhetysу", "жетісу", "жетысуском"]
    },
    "turksib": {
        "en": "Turksib",
        "ru": "Турксибский",
        "kk": "Түрксіб",
        "aliases": ["турксиб", "турксибский", "turksib", "түрксіб", "турксибском"]
    },
    "nauryzbay": {
        "en": "Nauryzbay",
        "ru": "Наурызбайский",
        "kk": "Наурызбай",
        "aliases": ["наурызбай", "наурызбайский", "nauryzbay", "наурызбайда"]
    }
}

ZONES = {
    "central": {"en": "Central", "ru": "Центральная", "kk": "Орталық"},
    "upscale": {"en": "Upscale / Elite", "ru": "Элитная", "kk": "Элиталық"},
    "business": {"en": "Business Corridor", "ru": "Деловой район", "kk": "Іскерлік аудан"},
    "retail": {"en": "Commercial / Retail", "ru": "Торговая", "kk": "Сауда аймағы"},
    "student": {"en": "Student / University", "ru": "Студенческая", "kk": "Студенттік"},
    "student-friendly": {"en": "Student Campus", "ru": "Студенческая зона", "kk": "Студенттік аймақ"},
    "residential": {"en": "Residential", "ru": "Жилая", "kk": "Тұрғын үй"},
    "suburban": {"en": "Suburban", "ru": "Пригородная", "kk": "Қала маңы"},
    "transit": {"en": "Transit / Transport Hub", "ru": "Транспортная развязка", "kk": "Көлік торабы"},
    "commercial": {"en": "Commercial", "ru": "Коммерческая", "kk": "Коммерциялық"},
}


# =============================================================================
# NORMALIZATION
# =============================================================================

def _normalize_string(s: str) -> str:
    """Lowercase, strip, and remove basic punctuation."""
    if not s:
        return ""
    s = s.lower().strip()
    s = re.sub(r'[^\w\s]', '', s)
    return s


def normalize_entity(query: str, entity_dict: Dict[str, Any]) -> str:
    """
    1. Exact Match (canonical key or EN/RU/KZ exact display name)
    2. Fuzzy Match (aliases, transliteration)
    3. AI Fallback (placeholder for Claude call, returning the closest or 'unknown')
    """
    norm_query = _normalize_string(query)
    
    # 1. Exact match on keys and main display names
    for key, data in entity_dict.items():
        if norm_query == _normalize_string(key):
            return key
        if norm_query == _normalize_string(data.get("en", "")):
            return key
        if norm_query == _normalize_string(data.get("ru", "")):
            return key
        if norm_query == _normalize_string(data.get("kk", "")):
            return key
            
    # 2. Fuzzy match on aliases
    for key, data in entity_dict.items():
        aliases = [_normalize_string(a) for a in data.get("aliases", [])]
        if norm_query in aliases:
            return key
            
    # Substring match on aliases as fallback
    for key, data in entity_dict.items():
        aliases = [_normalize_string(a) for a in data.get("aliases", [])]
        for a in aliases:
            if norm_query in a or a in norm_query:
                return key

    # 3. AI Fallback would go here. For now, if we can't match it, 
    # we return the original string to avoid breaking things, 
    # but ideally we'd map to a fallback canonical key.
    # We will return original query as key if not found.
    return query


def get_business_type_key(query: str) -> str:
    # Special cases handling
    if query.lower() == "coffee shop":
        return "coffee shop"
    return normalize_entity(query, BUSINESS_TYPES)

def get_city_key(query: str) -> str:
    return normalize_entity(query, CITIES)

def get_destination_key(query: str) -> str:
    # Because destinations can be random addresses, if it doesn't match our known 
    # landmarks, we just return the raw query.
    norm = normalize_entity(query, DESTINATIONS)
    if norm in DESTINATIONS:
        return norm
    return query


# =============================================================================
# LOOKUP UTILS
# =============================================================================

def get_search_ru(query: str, entity_type: str) -> str:
    if entity_type == "business_type":
        key = get_business_type_key(query)
        return BUSINESS_TYPES.get(key, {}).get("search_ru", query)
    elif entity_type == "city":
        key = get_city_key(query)
        return CITIES.get(key, {}).get("search_ru", query)
    elif entity_type == "destination":
        key = get_destination_key(query)
        return DESTINATIONS.get(key, {}).get("search_ru", query)
    return query


def get_display_label(query: str, entity_type: str, lang: str = "en") -> str:
    lang = lang.lower()
    if lang not in ["en", "ru", "kk"]:
        lang = "en"
        
    if entity_type == "business_type":
        key = get_business_type_key(query)
        return BUSINESS_TYPES.get(key, {}).get(lang, query.title())
    elif entity_type == "city":
        key = get_city_key(query)
        return CITIES.get(key, {}).get(lang, query.title())
    elif entity_type == "destination":
        key = get_destination_key(query)
        return DESTINATIONS.get(key, {}).get(lang, query)
    elif entity_type == "district":
        key = normalize_entity(query, DISTRICTS)
        return DISTRICTS.get(key, {}).get(lang, query)
    elif entity_type == "zone":
        norm = query.lower().strip()
        return ZONES.get(norm, {}).get(lang, query)
    return query


def translate_location_name(name: str, lang: str = "en") -> str:
    """Translates common candidate location names and patterns to target language."""
    if not name or lang == "en":
        return name
    
    lang = lang.lower()
    
    # Specific landmark/candidate mapping
    name_translations = {
        "Zhibek Zholy Market Area": {
            "ru": "Район рынка Жибек Жолы",
            "kk": "Жібек Жолы базарының аумағы"
        },
        "Panfilov Park Vicinity": {
            "ru": "Район парка 28 Панфиловцев",
            "kk": "28 Панфиловшылар саябағының маңы"
        },
        "Medeu Foothills": {
            "ru": "Предгорья Медеу",
            "kk": "Медеу баурайы"
        },
        "Alatau Business District": {
            "ru": "Деловой район Алатау",
            "kk": "Алатау іскерлік ауданы"
        },
        "Nurly Tau Mall Surroundings": {
            "ru": "Окрестности ТРЦ Нурлы Тау",
            "kk": "Нұрлы Тау маңы"
        },
        "KazNU Campus Area": {
            "ru": "Кампус КазНУ им. аль-Фараби",
            "kk": "Әл-Фараби атындағы ҚазҰУ кампусы"
        },
        "Auezov District Center": {
            "ru": "Центр Ауэзовского района",
            "kk": "Әуезов ауданының орталығы"
        },
        "Zhetysу Bazaar Junction": {
            "ru": "Район базара Жетысу",
            "kk": "Жетісу базары торабы"
        },
        "Alatau Suburb (Tech Zone)": {
            "ru": "Пригород Алатау (Технозона)",
            "kk": "Алатау қала маңы (Техноаймақ)"
        },
        "Turksib Railway Station Area": {
            "ru": "Район вокзала Турксиб (Алматы-1)",
            "kk": "Түрксіб теміржол вокзалы аймағы"
        },
        "Student Flat near KBTU": {
            "ru": "Студенческая квартира возле КБТУ",
            "kk": "ҚБТУ жанындағы студенттік пәтер"
        },
        "Cozy Apartment near KazNU Campus": {
            "ru": "Уютная квартира возле кампуса КазНУ",
            "kk": "ҚазҰУ кампусы жанындағы жайлы пәтер"
        },
        "Spacious Room near Satbayev University": {
            "ru": "Просторная комната возле Satbayev University",
            "kk": "Satbayev University жанындағы кең бөлме"
        },
        "Luxury Apartment in Medeu District": {
            "ru": "Элитная квартира в Медеуском районе",
            "kk": "Медеу ауданындағы элиталық пәтер"
        },
        "Renovated Flat in Auezov District": {
            "ru": "Отремонтированная квартира в Ауэзовском районе",
            "kk": "Әуезов ауданындағы жөнделген пәтер"
        }
    }
    
    if name in name_translations and lang in name_translations[name]:
        return name_translations[name][lang]

    # Pattern translation
    translated = name
    if lang == "ru":
        translated = re.sub(r'(?i)\bnear\b', 'возле', translated)
        translated = re.sub(r'(?i)\bapartment\b', 'квартира', translated)
        translated = re.sub(r'(?i)\bflat\b', 'квартира', translated)
        translated = re.sub(r'(?i)\broom\b', 'комната', translated)
        translated = re.sub(r'(?i)\bcandidate\b', 'Кандидат', translated)
        translated = re.sub(r'(?i)\blocation\b', 'Локация', translated)
    elif lang == "kk":
        translated = re.sub(r'(?i)\bnear\b', 'жанында', translated)
        translated = re.sub(r'(?i)\bapartment\b', 'пәтер', translated)
        translated = re.sub(r'(?i)\bflat\b', 'пәтер', translated)
        translated = re.sub(r'(?i)\broom\b', 'бөлме', translated)
        translated = re.sub(r'(?i)\bcandidate\b', 'Кандидат', translated)
        translated = re.sub(r'(?i)\blocation\b', 'Орын', translated)
        
    return translated


def translate_address(address: str, lang: str = "en") -> str:
    """Translates street, ave, district, and city names in an address."""
    if not address or lang == "en":
        return address
        
    lang = lang.lower()
    res = address
    
    if lang == "ru":
        # Street keywords
        res = re.sub(r'(?i)\bAve\b\.?', 'просп.', res)
        res = re.sub(r'(?i)\bSt\b\.?', 'ул.', res)
        res = re.sub(r'(?i)\bStreet\b', 'ул.', res)
        res = re.sub(r'(?i)\bAvenue\b', 'просп.', res)
        res = re.sub(r'(?i)\bMicrodistrict\b', 'мкр.', res)
        res = re.sub(r'(?i)\bmkr\b\.?', 'мкр.', res)
        res = re.sub(r'(?i)\bdistrict\b', 'район', res)
        # Districts
        for d_key, d_info in DISTRICTS.items():
            en_val = d_info["en"]
            ru_val = d_info["ru"] + " р-н"
            res = re.sub(rf'(?i)\b{en_val}\b', ru_val, res)
    elif lang == "kk":
        res = re.sub(r'(?i)\bAve\b\.?', 'даңғ.', res)
        res = re.sub(r'(?i)\bSt\b\.?', 'көш.', res)
        res = re.sub(r'(?i)\bStreet\b', 'көшесі', res)
        res = re.sub(r'(?i)\bAvenue\b', 'даңғылы', res)
        res = re.sub(r'(?i)\bMicrodistrict\b', 'шағынауданы', res)
        res = re.sub(r'(?i)\bmkr\b\.?', 'ш/а', res)
        res = re.sub(r'(?i)\bdistrict\b', 'ауданы', res)
        for d_key, d_info in DISTRICTS.items():
            en_val = d_info["en"]
            kk_val = d_info["kk"] + " ауд."
            res = re.sub(rf'(?i)\b{en_val}\b', kk_val, res)
            
    return res
