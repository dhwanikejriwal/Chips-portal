"""
Centralized District Name Mapping & Normalization for CHiPS Admin Portal.
Maps any district name variant/alias to the standard Master District Name in DB.
"""

DISTRICT_ALIAS_MAP = {
    # Balod
    "balod": "Balod",
    
    # Balodabazar-Bhatapara
    "balodabazar": "Balodabazar-Bhatapara",
    "baloda bazar": "Balodabazar-Bhatapara",
    "balodabazar-bhatapara": "Balodabazar-Bhatapara",
    "baloda bazar-bhatapara": "Balodabazar-Bhatapara",
    "balodabazar bhatapara": "Balodabazar-Bhatapara",
    
    # Balrampur-Ramanujganj
    "balrampur": "Balrampur-Ramanujganj",
    "balrampur-ramanujganj": "Balrampur-Ramanujganj",
    "balrampur ramanujganj": "Balrampur-Ramanujganj",
    
    # Bastar
    "baster": "Bastar",
    "bastar": "Bastar",
    
    # Bemetara
    "bemetara": "Bemetara",
    
    # Bijapur
    "bijapur": "Bijapur",
    
    # Bilaspur
    "bilaspur": "Bilaspur",
    
    # Dakshin Bastar Dantewada
    "dantewada": "Dantewada",
    "dakshin bastar dantewada": "Dantewada",
    "dakshin bastar (dantewada)": "Dantewada",
    "dakshin bastar": "Dantewada",
    
    # Dhamtari
    "dhamtari": "Dhamtari",
    
    # Durg
    "durg": "Durg",
    
    # Gariyaband
    "gariaband": "Gariyaband",
    "gariyaband": "Gariyaband",
    
    # Gaurela-Pendra-Marwahi
    "gourela pendra marvahi": "Gaurela-Pendra-Marwahi",
    "gourela-pendra-marvahi": "Gaurela-Pendra-Marwahi",
    "gourela pendra marwahi": "Gaurela-Pendra-Marwahi",
    "gourela-pendra-marwahi": "Gaurela-Pendra-Marwahi",
    "gaurela-pendra-marwahi": "Gaurela-Pendra-Marwahi",
    "gaurela pendra marwahi": "Gaurela-Pendra-Marwahi",
    "gpm": "Gaurela-Pendra-Marwahi",
    
    # Janjgir-Champa
    "janjgir - champa": "Janjgir-Champa",
    "janjgir-champa": "Janjgir-Champa",
    "janjgir champa": "Janjgir-Champa",
    "janjgir": "Janjgir-Champa",
    
    # Jashpur
    "jashpur": "Jashpur",
    
    # Kabeerdham
    "kawardha": "Kawardha",
    "kabeerdham": "Kawardha",
    "kabirdham": "Kawardha",
    "kabirdham (kawardha)": "Kawardha",
    
    # Khairagarh-Chhuikhadan-Gandai
    "khairagarh-chuikhadan-gandai": "Khairagarh-Chhuikhadan-Gandai",
    "khairagarh-chhuikhadan-gandai": "Khairagarh-Chhuikhadan-Gandai",
    "khairagarh chhuikhadan gandai": "Khairagarh-Chhuikhadan-Gandai",
    "khairagarh": "Khairagarh-Chhuikhadan-Gandai",
    "kcg": "Khairagarh-Chhuikhadan-Gandai",
    
    # Kondagaon
    "kondagaon": "Kondagaon",
    
    # Korba
    "korba": "Korba",
    
    # Korea
    "koriya": "Korea",
    "korea": "Korea",
    
    # Mahasamund
    "mahasamund": "Mahasamund",
    
    # Manendragarh-Chirmiri-Bharatpur (MCB)
    "manendragarh-chirmiri-bharatpur": "Manendragarh-Chirmiri-Bharatpur (MCB)",
    "manendragarh-chirmiri-bharatpur (mcb)": "Manendragarh-Chirmiri-Bharatpur (MCB)",
    "manendragarh-chirmiri-bharatpur(m c b)": "Manendragarh-Chirmiri-Bharatpur (MCB)",
    "manendragarh-chirmiri-bharatpur(mcb)": "Manendragarh-Chirmiri-Bharatpur (MCB)",
    "manendragarh chirmiri bharatpur": "Manendragarh-Chirmiri-Bharatpur (MCB)",
    "manendragarh": "Manendragarh-Chirmiri-Bharatpur (MCB)",
    "mcb": "Manendragarh-Chirmiri-Bharatpur (MCB)",
    
    # Mohla-Manpur-Ambagarh Chouki
    "mohla-manpur-chowki": "Mohla-Manpur-Ambagarh Chouki",
    "mohla-manpur-ambagarh chouki": "Mohla-Manpur-Ambagarh Chouki",
    "mohla-manpur-ambagarh chowki": "Mohla-Manpur-Ambagarh Chouki",
    "mohla manpur chowki": "Mohla-Manpur-Ambagarh Chouki",
    "mohla": "Mohla-Manpur-Ambagarh Chouki",
    
    # Mungeli
    "mungeli": "Mungeli",
    
    # Narayanpur
    "narayanpur": "Narayanpur",
    
    # Raigarh
    "raigarh": "Raigarh",
    
    # Raipur
    "raipur": "Raipur",
    
    # Rajnandgaon
    "rajnandgaon": "Rajnandgaon",
    
    # Sakti
    "sakti": "Sakti",
    
    # Sarangarh-Bilaigarh
    "sarangarh-bilaigarh": "Sarangarh-Bilaigarh",
    "sarangarh bilaigarh": "Sarangarh-Bilaigarh",
    "sarangarh": "Sarangarh-Bilaigarh",
    
    # Sukma
    "sukma": "Sukma",
    
    # Surajpur
    "surajpur": "Surajpur",
    
    # Surguja
    "surguja": "Surguja",
    
    # Uttar Bastar Kanker
    "kanker": "Kanker",
    "uttar bastar kanker": "Kanker",
    "uttar bastar (kanker)": "Kanker",
    "uttar bastar": "Kanker",
}

def normalize_district_name(district_name: str) -> str:
    """
    Returns the standard DB master district name for any variant or alias.
    If unknown, returns title-cased trimmed original string.
    """
    if not district_name:
        return ""
    clean_val = str(district_name).strip()
    # Normalize Mojibake UTF-8 artifacts (â€“) and Unicode dashes (–, —) to ASCII hyphens (-)
    clean_val = clean_val.replace('â€“', '-').replace('â€”', '-').replace('â€', '')
    clean_val = clean_val.replace('–', '-').replace('—', '-').strip().lower()
    clean_val = ' '.join(clean_val.split())

    mapped = DISTRICT_ALIAS_MAP.get(clean_val)
    if mapped:
        return mapped

    # Substring & keyword fallbacks matching normalize_districts.py rules
    if 'kanker' in clean_val:
        return "Kanker"
    if 'dantewada' in clean_val:
        return "Dantewada"
    if any(k in clean_val for k in ['kawardha', 'kabeerdham', 'kabirdham']):
        return "Kawardha"
    if 'balodabazar' in clean_val:
        return "Balodabazar-Bhatapara"
    if 'balrampur' in clean_val:
        return "Balrampur-Ramanujganj"
    if 'janjgir' in clean_val:
        return "Janjgir-Champa"
    if 'khairagarh' in clean_val or 'kcg' in clean_val:
        return "Khairagarh-Chhuikhadan-Gandai"
    if any(k in clean_val for k in ['manendragarh', 'mcb']):
        return "Manendragarh-Chirmiri-Bharatpur (MCB)"
    if 'mohla' in clean_val:
        return "Mohla-Manpur-Ambagarh Chouki"
    if 'sarangarh' in clean_val:
        return "Sarangarh-Bilaigarh"
    if any(k in clean_val for k in ['gpm', 'pendra', 'gaurela', 'gourela']):
        return "Gaurela-Pendra-Marwahi"

    result = str(district_name).strip()
    result = result.replace('â€“', '-').replace('â€”', '-').replace('â€', '').replace('–', '-').replace('—', '-')
    return ' '.join(result.split()).title()


DIVISIONS_MASTER_MAP = {
    "Raipur Div": [
        "Balodabazar-Bhatapara",
        "Dhamtari",
        "Gariyaband",
        "Mahasamund",
        "Raipur"
    ],
    "Durg Div": [
        "Balod",
        "Bemetara",
        "Durg",
        "Kawardha",
        "Khairagarh-Chhuikhadan-Gandai",
        "Mohla-Manpur-Ambagarh Chouki",
        "Rajnandgaon"
    ],
    "Bilaspur Div": [
        "Bilaspur",
        "Gaurela-Pendra-Marwahi",
        "Janjgir-Champa",
        "Korba",
        "Mungeli",
        "Raigarh",
        "Sakti",
        "Sarangarh-Bilaigarh"
    ],
    "Surguja Div": [
        "Balrampur-Ramanujganj",
        "Jashpur",
        "Korea",
        "Manendragarh-Chirmiri-Bharatpur (MCB)",
        "Surajpur",
        "Surguja"
    ],
    "Bastar Div": [
        "Bastar",
        "Bijapur",
        "Dantewada",
        "Kanker",
        "Kondagaon",
        "Narayanpur",
        "Sukma"
    ]
}

LWE_MASTER_DISTRICTS = {
    "Bastar",
    "Bijapur",
    "Dantewada",
    "Mohla-Manpur-Ambagarh Chouki",
    "Narayanpur",
    "Sukma",
    "Kanker"
}

def is_lwe_district(district_name: str) -> str:
    if not district_name:
        return "No"
    norm = normalize_district_name(str(district_name))
    return "Yes" if norm in LWE_MASTER_DISTRICTS else "No"

def get_division_for_district(district_name: str):
    """
    Returns the division name for a given district name or alias by resolving it
    via centralized DISTRICT_ALIAS_MAP first, then checking DIVISIONS_MASTER_MAP.
    """
    if not district_name:
        return None
    normalized = normalize_district_name(district_name)
    for div_name, master_districts in DIVISIONS_MASTER_MAP.items():
        if normalized in master_districts:
            return div_name
    return None

def is_district_in_division(district_name: str, division_key: str) -> bool:
    """
    Checks if a district input belongs to a division by resolving the district via 
    DISTRICT_ALIAS_MAP and comparing with the target division key.
    """
    if not district_name or not division_key:
        return False
    target_div = get_division_for_district(district_name)
    if not target_div:
        return False
    norm_key = str(division_key).lower().replace('div', '').strip()
    return norm_key in target_div.lower()


