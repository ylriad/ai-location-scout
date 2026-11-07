"""
Almaty candidate locations used as the default search space.
Each entry provides name, district, address, and precise lat/lng.

These cover a spread of central, mid-ring, and suburban areas so the
scoring model has meaningful variance to work with.
"""

ALMATY_CANDIDATES = [
    # ── Central / CBD ───────────────────────────────────────────────
    {
        "id":       "zhibek_zholy_market",
        "name":     "Zhibek Zholy Market Area",
        "district": "Almaly",
        "address":  "Zhibek Zholy Ave 50, Almaly, Almaty",
        "lat":      43.2575,
        "lng":      76.9456,
        "zone":     "central",
    },
    {
        "id":       "panfilov_park",
        "name":     "Panfilov Park Vicinity",
        "district": "Almaly",
        "address":  "Panfilov St 112, Almaly, Almaty",
        "lat":      43.2607,
        "lng":      76.9467,
        "zone":     "central",
    },
    {
        "id":       "medeu_district",
        "name":     "Medeu Foothills",
        "district": "Medeu",
        "address":  "Al-Farabi Ave 77, Medeu, Almaty",
        "lat":      43.2565,
        "lng":      76.9285,
        "zone":     "upscale",
    },
    # ── Business / Office Corridors ──────────────────────────────────
    {
        "id":       "alatau_biz",
        "name":     "Alatau Business District",
        "district": "Bostandyq",
        "address":  "Al-Farabi Ave 19, Bostandyq, Almaty",
        "lat":      43.2412,
        "lng":      76.8820,
        "zone":     "business",
    },
    {
        "id":       "nurly_tau",
        "name":     "Nurly Tau Mall Surroundings",
        "district": "Bostandyq",
        "address":  "Al-Farabi Ave 90, Bostandyq, Almaty",
        "lat":      43.2390,
        "lng":      76.9100,
        "zone":     "retail",
    },
    # ── University / Student zones ───────────────────────────────────
    {
        "id":       "kaz_national_uni",
        "name":     "KazNU Campus Area",
        "district": "Almaly",
        "address":  "Al-Farabi Ave 71, Almaly, Almaty",
        "lat":      43.2388,
        "lng":      76.9397,
        "zone":     "student",
    },
    # ── Residential Mid-ring ─────────────────────────────────────────
    {
        "id":       "auezov_center",
        "name":     "Auezov District Center",
        "district": "Auezov",
        "address":  "Raiymbek Ave 210, Auezov, Almaty",
        "lat":      43.2200,
        "lng":      76.8700,
        "zone":     "residential",
    },
    {
        "id":       "zhetysu_bazaar",
        "name":     "Zhetysu Bazaar Junction",
        "district": "Zhetysu",
        "address":  "Seifullin Ave 120, Zhetysu, Almaty",
        "lat":      43.2800,
        "lng":      76.9700,
        "zone":     "residential",
    },
    # ── Suburbs / Growth zones ───────────────────────────────────────
    {
        "id":       "alatau_suburb",
        "name":     "Alatau Suburb (Tech Zone)",
        "district": "Alatau",
        "address":  "Rozybakiev St 320, Alatau, Almaty",
        "lat":      43.3200,
        "lng":      76.8500,
        "zone":     "suburban",
    },
    {
        "id":       "turksib_station",
        "name":     "Turksib Railway Station Area",
        "district": "Turksib",
        "address":  "Turksib St 1, Turksib, Almaty",
        "lat":      43.3100,
        "lng":      77.0200,
        "zone":     "transit",
    },
]
