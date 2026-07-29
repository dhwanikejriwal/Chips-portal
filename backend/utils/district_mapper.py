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
    "dantewada": "Dakshin Bastar Dantewada",
    "dakshin bastar dantewada": "Dakshin Bastar Dantewada",
    "dakshin bastar (dantewada)": "Dakshin Bastar Dantewada",
    "dakshin bastar": "Dakshin Bastar Dantewada",
    
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
    "kawardha": "Kabeerdham",
    "kabeerdham": "Kabeerdham",
    "kabirdham": "Kabeerdham",
    "kabirdham (kawardha)": "Kabeerdham",
    
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
    
    # Manendragarh-Chirmiri-Bharatpur(M C B)
    "manendragarh-chirmiri-bharatpur": "Manendragarh-Chirmiri-Bharatpur(M C B)",
    "manendragarh-chirmiri-bharatpur(m c b)": "Manendragarh-Chirmiri-Bharatpur(M C B)",
    "manendragarh chirmiri bharatpur": "Manendragarh-Chirmiri-Bharatpur(M C B)",
    "manendragarh": "Manendragarh-Chirmiri-Bharatpur(M C B)",
    "mcb": "Manendragarh-Chirmiri-Bharatpur(M C B)",
    
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
    "kanker": "Uttar Bastar Kanker",
    "uttar bastar kanker": "Uttar Bastar Kanker",
    "uttar bastar (kanker)": "Uttar Bastar Kanker",
    "uttar bastar": "Uttar Bastar Kanker",
}

def normalize_district_name(district_name: str) -> str:
    """
    Returns the standard DB master district name for any variant or alias.
    If unknown, returns title-cased trimmed original string.
    """
    if not district_name:
        return ""
    clean_val = str(district_name).strip().lower()
    return DISTRICT_ALIAS_MAP.get(clean_val, str(district_name).strip().title())
