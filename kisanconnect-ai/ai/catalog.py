"""Crop catalog shared by every AI module.

base     = typical fair price in INR per unit for an average-quality lot
harvest  = month when supply peaks (price is lowest)
pop      = how popular the crop is with buyers (1-10)
"""

CATEGORIES = ["Vegetables", "Fruits", "Grains", "Pulses", "Spices", "Dairy", "Oilseeds"]

CROPS = {
    # Vegetables
    "Tomato":        dict(base=30,  harvest=2,  cat="Vegetables", emoji="🍅", unit="kg",    pop=10),
    "Potato":        dict(base=22,  harvest=3,  cat="Vegetables", emoji="🥔", unit="kg",    pop=10),
    "Onion":         dict(base=28,  harvest=4,  cat="Vegetables", emoji="🧅", unit="kg",    pop=10),
    "Brinjal":       dict(base=35,  harvest=11, cat="Vegetables", emoji="🍆", unit="kg",    pop=6),
    "Cauliflower":   dict(base=40,  harvest=12, cat="Vegetables", emoji="🥦", unit="kg",    pop=6),
    "Cabbage":       dict(base=25,  harvest=1,  cat="Vegetables", emoji="🥬", unit="kg",    pop=6),
    "Okra":          dict(base=50,  harvest=7,  cat="Vegetables", emoji="🫛", unit="kg",    pop=6),
    "Spinach":       dict(base=30,  harvest=12, cat="Vegetables", emoji="🥬", unit="kg",    pop=5),
    "Carrot":        dict(base=40,  harvest=1,  cat="Vegetables", emoji="🥕", unit="kg",    pop=7),
    "Green Chilli":  dict(base=70,  harvest=11, cat="Vegetables", emoji="🌶️", unit="kg",    pop=7),
    # Fruits
    "Mango":         dict(base=90,  harvest=5,  cat="Fruits",     emoji="🥭", unit="kg",    pop=9),
    "Banana":        dict(base=45,  harvest=9,  cat="Fruits",     emoji="🍌", unit="kg",    pop=9),
    "Apple":         dict(base=150, harvest=9,  cat="Fruits",     emoji="🍎", unit="kg",    pop=8),
    "Papaya":        dict(base=35,  harvest=10, cat="Fruits",     emoji="🍈", unit="kg",    pop=5),
    "Pomegranate":   dict(base=140, harvest=11, cat="Fruits",     emoji="🍒", unit="kg",    pop=6),
    "Grapes":        dict(base=90,  harvest=3,  cat="Fruits",     emoji="🍇", unit="kg",    pop=6),
    "Watermelon":    dict(base=20,  harvest=4,  cat="Fruits",     emoji="🍉", unit="kg",    pop=7),
    # Grains
    "Rice":          dict(base=45,  harvest=11, cat="Grains",     emoji="🌾", unit="kg",    pop=10),
    "Wheat":         dict(base=32,  harvest=4,  cat="Grains",     emoji="🌾", unit="kg",    pop=10),
    "Maize":         dict(base=24,  harvest=10, cat="Grains",     emoji="🌽", unit="kg",    pop=6),
    "Bajra":         dict(base=38,  harvest=10, cat="Grains",     emoji="🌾", unit="kg",    pop=4),
    "Jowar":         dict(base=40,  harvest=10, cat="Grains",     emoji="🌾", unit="kg",    pop=4),
    # Pulses
    "Toor Dal":      dict(base=120, harvest=1,  cat="Pulses",     emoji="🫘", unit="kg",    pop=8),
    "Chana":         dict(base=75,  harvest=3,  cat="Pulses",     emoji="🫘", unit="kg",    pop=7),
    "Moong":         dict(base=110, harvest=10, cat="Pulses",     emoji="🫘", unit="kg",    pop=6),
    "Urad":          dict(base=115, harvest=10, cat="Pulses",     emoji="🫘", unit="kg",    pop=6),
    # Spices
    "Turmeric":      dict(base=120, harvest=3,  cat="Spices",     emoji="🌿", unit="kg",    pop=7),
    "Red Chilli":    dict(base=220, harvest=3,  cat="Spices",     emoji="🌶️", unit="kg",    pop=8),
    "Coriander Seed":dict(base=110, harvest=4,  cat="Spices",     emoji="🌿", unit="kg",    pop=5),
    # Dairy
    "Milk":          dict(base=60,  harvest=12, cat="Dairy",      emoji="🥛", unit="litre", pop=9),
    "Ghee":          dict(base=600, harvest=12, cat="Dairy",      emoji="🧈", unit="kg",    pop=7),
    # Oilseeds
    "Groundnut":     dict(base=85,  harvest=11, cat="Oilseeds",   emoji="🥜", unit="kg",    pop=6),
    "Sesame":        dict(base=140, harvest=11, cat="Oilseeds",   emoji="🌰", unit="kg",    pop=5),
}

# (month of peak demand, strength of the seasonal swing)
CAT_SEASON = {
    "Vegetables": (12, 0.30),
    "Fruits":     (5,  0.45),
    "Grains":     (11, 0.25),
    "Pulses":     (2,  0.20),
    "Spices":     (1,  0.30),
    "Dairy":      (5,  0.20),
    "Oilseeds":   (1,  0.30),
}

UNITS = ["kg", "litre", "dozen", "piece", "quintal"]
GRADES = {"A": "Premium", "B": "Good", "C": "Standard"}
MONTHS = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]


def crop_info(name):
    return CROPS.get(name)


def emoji_for(name, category=None):
    info = CROPS.get(name)
    if info:
        return info["emoji"]
    return {"Vegetables": "🥬", "Fruits": "🍎", "Grains": "🌾", "Pulses": "🫘",
            "Spices": "🌶️", "Dairy": "🥛", "Oilseeds": "🥜"}.get(category, "🌱")
