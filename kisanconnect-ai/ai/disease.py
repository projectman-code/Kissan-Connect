"""Crop disease detector (leaf photo -> likely problem + treatment).

Colour-pattern analysis in HSV space: share of healthy green, yellowing,
brown/dark spots and powdery white patches on the leaf. It is a quick
screening aid, not a lab diagnosis. Swap `diagnose()` for a trained CNN
(e.g. PlantVillage) later and keep the same return shape.
"""
import numpy as np
from PIL import Image

KB = {
    "healthy": {
        "name": {"en": "Healthy leaf", "hi": "स्वस्थ पत्ती", "te": "ఆరోగ్యకరమైన ఆకు"},
        "cause": {"en": "No visible disease pattern found.", "hi": "कोई रोग का लक्षण नहीं दिखा।", "te": "వ్యాధి లక్షణాలు కనిపించలేదు."},
        "treatment": {
            "en": "Keep up regular watering and balanced nutrition. Check leaves once a week.",
            "hi": "नियमित सिंचाई और संतुलित खाद देते रहें। हर हफ्ते पत्तियां जांचें।",
            "te": "క్రమం తప్పకుండా నీరు, సమతుల్య ఎరువులు ఇవ్వండి. వారానికోసారి ఆకులను పరిశీలించండి.",
        },
    },
    "leaf_spot": {
        "name": {"en": "Leaf spot / blight", "hi": "पत्ती धब्बा / झुलसा रोग", "te": "ఆకు మచ్చ / ఎండు తెగులు"},
        "cause": {
            "en": "Fungal or bacterial infection, usually after humid or wet weather.",
            "hi": "फफूंद या जीवाणु संक्रमण, आमतौर पर नमी या बारिश के बाद।",
            "te": "తేమ లేదా వర్షం తర్వాత వచ్చే శిలీంధ్ర లేదా బ్యాక్టీరియా ఇన్ఫెక్షన్.",
        },
        "treatment": {
            "en": "Remove and destroy affected leaves. Spray neem oil (5 ml per litre) or a copper-based fungicide as per label. Avoid watering the leaves. Ask your local KVK for the exact dose.",
            "hi": "प्रभावित पत्तियां तोड़कर नष्ट करें। नीम तेल (5 मिली प्रति लीटर) या कॉपर फफूंदनाशक लेबल के अनुसार छिड़कें। पत्तियों पर पानी न डालें। सही मात्रा के लिए स्थानीय कृषि केंद्र से पूछें।",
            "te": "సోకిన ఆకులను తీసివేసి నాశనం చేయండి. వేప నూనె (లీటరుకు 5 మి.లీ) లేదా కాపర్ శిలీంధ్రనాశిని లేబుల్ ప్రకారం చల్లండి. ఆకులపై నీరు పోయవద్దు. సరైన మోతాదుకు స్థానిక KVK ను సంప్రదించండి.",
        },
    },
    "yellowing": {
        "name": {"en": "Yellowing (nutrient deficiency or virus)", "hi": "पत्तियों का पीलापन (पोषक कमी या वायरस)", "te": "ఆకులు పసుపు రంగులోకి మారడం (పోషక లోపం లేదా వైరస్)"},
        "cause": {
            "en": "Often low nitrogen or iron, waterlogging, or a virus spread by whitefly.",
            "hi": "अक्सर नाइट्रोजन या आयरन की कमी, जलभराव, या सफेद मक्खी से फैलने वाला वायरस।",
            "te": "తరచుగా నత్రజని లేదా ఇనుము లోపం, నీరు నిలవడం, లేదా తెల్లదోమ ద్వారా వ్యాపించే వైరస్.",
        },
        "treatment": {
            "en": "Check drainage first. Do a soil test and apply the recommended nutrients. If new leaves curl or show mosaic, remove the plant and control whitefly with yellow sticky traps.",
            "hi": "पहले जल निकासी जांचें। मिट्टी की जांच कराकर सुझाई गई खाद दें। नई पत्तियां मुड़ें या चितकबरी हों तो पौधा हटाएं और पीले चिपचिपे जाल से सफेद मक्खी रोकें।",
            "te": "ముందు నీటి పారుదల చూడండి. నేల పరీక్ష చేయించి సిఫార్సు చేసిన పోషకాలు వేయండి. కొత్త ఆకులు ముడుచుకుంటే లేదా మొజాయిక్ కనిపిస్తే మొక్కను తీసివేసి పసుపు జిగురు అట్టలతో తెల్లదోమను అరికట్టండి.",
        },
    },
    "mildew": {
        "name": {"en": "Powdery mildew", "hi": "चूर्णिल आसिता (पाउडरी मिल्ड्यू)", "te": "బూడిద తెగులు (పౌడరీ మిల్డ్యూ)"},
        "cause": {
            "en": "Fungus that spreads in dry days with humid nights and crowded plants.",
            "hi": "फफूंद जो सूखे दिन और नम रातों में घने पौधों पर फैलती है।",
            "te": "పొడి పగళ్లు, తేమ రాత్రులు, దట్టమైన మొక్కలలో వ్యాపించే శిలీంధ్రం.",
        },
        "treatment": {
            "en": "Improve air flow by thinning plants. Spray wettable sulphur or a milk-water mix (1:9) in the early morning. Repeat after 7 to 10 days if needed.",
            "hi": "पौधों को छांटकर हवा का प्रवाह बढ़ाएं। सुबह जल्दी घुलनशील गंधक या दूध-पानी (1:9) का घोल छिड़कें। जरूरत हो तो 7 से 10 दिन बाद दोहराएं।",
            "te": "మొక్కలను పలుచన చేసి గాలి ప్రసరణ పెంచండి. ఉదయాన్నే నీటిలో కరిగే గంధకం లేదా పాలు-నీరు (1:9) చల్లండి. అవసరమైతే 7-10 రోజులకు మళ్లీ చల్లండి.",
        },
    },
    "stress": {
        "name": {"en": "Early stress signs", "hi": "शुरुआती तनाव के लक्षण", "te": "ప్రారంభ ఒత్తిడి లక్షణాలు"},
        "cause": {
            "en": "Mixed colour changes. Could be water stress, heat, or the start of an infection.",
            "hi": "रंग में मिला-जुला बदलाव। पानी की कमी, गर्मी या संक्रमण की शुरुआत हो सकती है।",
            "te": "రంగులో మిశ్రమ మార్పులు. నీటి ఒత్తిడి, వేడి లేదా ఇన్ఫెక్షన్ ప్రారంభం కావచ్చు.",
        },
        "treatment": {
            "en": "Water in the morning, mulch the soil and recheck in 3 days. If spots spread, upload a new photo or visit your local agriculture officer.",
            "hi": "सुबह सिंचाई करें, मिट्टी पर मल्च बिछाएं और 3 दिन बाद फिर जांचें। धब्बे बढ़ें तो नई फोटो डालें या कृषि अधिकारी से मिलें।",
            "te": "ఉదయం నీరు పెట్టండి, నేలపై మల్చింగ్ చేయండి, 3 రోజుల తర్వాత మళ్లీ చూడండి. మచ్చలు పెరిగితే కొత్త ఫోటో పెట్టండి లేదా వ్యవసాయ అధికారిని కలవండి.",
        },
    },
}

NO_LEAF = {
    "en": "We could not find a leaf in this photo. Place one leaf on a plain background and upload again.",
    "hi": "इस फोटो में पत्ती नहीं मिली। एक पत्ती को सादे पीछे के रंग पर रखकर दोबारा डालें।",
    "te": "ఈ ఫోటోలో ఆకు కనిపించలేదు. ఒక ఆకును సాదా నేపథ్యంపై ఉంచి మళ్లీ అప్‌లోడ్ చేయండి.",
}
SEVERITY = {
    "mild": {"en": "Mild", "hi": "हल्का", "te": "తక్కువ"},
    "moderate": {"en": "Moderate", "hi": "मध्यम", "te": "మధ్యస్థం"},
    "severe": {"en": "Severe", "hi": "गंभीर", "te": "తీవ్రం"},
}


def _masks(img):
    arr = np.asarray(img, dtype=np.float32) / 255.0
    hsv = np.asarray(img.convert("HSV"), dtype=np.float32) / 255.0
    hue, sat, val = hsv[..., 0] * 360, hsv[..., 1], hsv[..., 2]

    ring = np.concatenate([arr[0], arr[-1], arr[:, 0], arr[:, -1]])
    bg = np.median(ring, axis=0)
    leaf = np.sqrt(((arr - bg) ** 2).sum(-1)) > 0.22
    if leaf.mean() < 0.08:          # leaf fills the frame
        leaf = (sat > 0.18) & (val > 0.10)
    return hue, sat, val, leaf


def diagnose(file_or_path, crop=None, lang="en"):
    lang = lang if lang in ("en", "hi", "te", "ta") else "en"
    img = Image.open(file_or_path).convert("RGB")
    img.thumbnail((320, 320))
    hue, sat, val, leaf = _masks(img)
    total = int(leaf.sum())
    if total < 0.03 * leaf.size:
        return {"ok": False, "message": NO_LEAF[lang]}

    def share(mask):
        return float((mask & leaf).sum() / total)

    green = share((hue >= 65) & (hue <= 170) & (sat > 0.22) & (val > 0.20))
    yellow = share((hue >= 38) & (hue < 65) & (sat > 0.30) & (val > 0.45))
    brown = share((hue >= 8) & (hue < 38) & (sat > 0.22) & (val >= 0.15) & (val <= 0.75))
    dark = share(val < 0.18)
    white = share((sat < 0.18) & (val > 0.72))
    spots = brown + dark

    if spots >= 0.06:
        key, ratio = "leaf_spot", spots
        conf = min(0.92, 0.60 + spots)
    elif yellow >= 0.22:
        key, ratio = "yellowing", yellow
        conf = min(0.90, 0.50 + yellow)
    elif white >= 0.10 and green >= 0.25:
        key, ratio = "mildew", white
        conf = min(0.88, 0.50 + white)
    elif green >= 0.60:
        key, ratio = "healthy", 0.0
        conf = min(0.95, 0.60 + 0.4 * (green - 0.6) / 0.4)
    else:
        key, ratio = "stress", max(yellow, spots, white)
        conf = 0.55

    severity = None
    if key not in ("healthy", "stress"):
        severity = "mild" if ratio < 0.15 else "moderate" if ratio < 0.30 else "severe"

    item = KB[key]
    return {
        "ok": True, "key": key, "crop": crop or "",
        "name": item["name"][lang], "cause": item["cause"][lang],
        "treatment": item["treatment"][lang],
        "severity": SEVERITY[severity][lang] if severity else None,
        "severity_key": severity,
        "confidence": round(conf * 100),
        "breakdown": {
            "healthy green": round(green * 100), "yellow": round(yellow * 100),
            "brown or dark spots": round(spots * 100), "white powder": round(white * 100),
        },
    }


# ---- Tamil -------------------------------------------------------------
_TA = {'healthy': ('ஆரோக்கியமான இலை', 'நோய் அறிகுறி எதுவும் தெரியவில்லை.', 'வழக்கமான நீர்ப்பாசனமும் சமச்சீர் ஊட்டச்சத்தும் தொடருங்கள். வாரம் ஒருமுறை இலைகளைச் சரிபார்க்கவும்.'), 'leaf_spot': ('இலைப்புள்ளி / கருகல் நோய்', 'ஈரப்பதம் அல்லது மழைக்குப் பின் பொதுவாக ஏற்படும் பூஞ்சை அல்லது பாக்டீரியா தொற்று.', 'பாதிக்கப்பட்ட இலைகளை அகற்றி அழிக்கவும். வேப்ப எண்ணெய் (லிட்டருக்கு 5 மி.லி) அல்லது தாமிர பூஞ்சைக்கொல்லியை லேபிள் படி தெளிக்கவும். இலைகளின் மேல் நீர் ஊற்ற வேண்டாம். சரியான அளவுக்கு உள்ளூர் KVK ஐக் கேளுங்கள்.'), 'yellowing': ('மஞ்சளாதல் (சத்துக் குறைபாடு அல்லது வைரஸ்)', 'பெரும்பாலும் தழைச்சத்து அல்லது இரும்புச்சத்து குறைவு, நீர் தேக்கம் அல்லது வெள்ளை ஈ பரப்பும் வைரஸ்.', 'முதலில் நீர் வடிகாலைச் சரிபாருங்கள். மண் பரிசோதனை செய்து பரிந்துரைத்த சத்துகளை இடுங்கள். புதிய இலைகள் சுருண்டாலோ மொசைக் தெரிந்தாலோ செடியை அகற்றி மஞ்சள் ஒட்டும் பொறிகளால் வெள்ளை ஈயைக் கட்டுப்படுத்துங்கள்.'), 'mildew': ('சாம்பல் நோய் (பவுடரி மில்டியூ)', 'வறண்ட பகல், ஈரமான இரவு, நெருக்கமான செடிகளில் பரவும் பூஞ்சை.', 'செடிகளை மெலிதாக்கி காற்றோட்டத்தை அதிகரிக்கவும். அதிகாலையில் நீரில் கரையும் கந்தகம் அல்லது பால்-நீர் (1:9) கலவை தெளிக்கவும். தேவைப்பட்டால் 7-10 நாட்களில் மீண்டும் தெளிக்கவும்.'), 'stress': ('ஆரம்ப அழுத்த அறிகுறிகள்', 'கலவையான நிற மாற்றங்கள். நீர் அழுத்தம், வெப்பம் அல்லது தொற்றின் தொடக்கமாக இருக்கலாம்.', 'காலையில் நீர் பாய்ச்சுங்கள், மண்ணில் மூடாக்கு இடுங்கள், 3 நாட்களில் மீண்டும் பாருங்கள். புள்ளிகள் பரவினால் புதிய புகைப்படம் பதிவேற்றவும் அல்லது வேளாண் அதிகாரியைச் சந்திக்கவும்.')}
for _k, (_n, _c, _t) in _TA.items():
    KB[_k]["name"]["ta"] = _n
    KB[_k]["cause"]["ta"] = _c
    KB[_k]["treatment"]["ta"] = _t
NO_LEAF["ta"] = "இந்த புகைப்படத்தில் இலை தெரியவில்லை. ஒரு இலையை சாதாரண பின்னணியில் வைத்து மீண்டும் பதிவேற்றவும்."
SEVERITY["mild"]["ta"] = "லேசானது"
SEVERITY["moderate"]["ta"] = "மிதமானது"
SEVERITY["severe"]["ta"] = "தீவிரம்"
