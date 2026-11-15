"""Multilingual farming assistant (English / Hindi / Telugu).

Works fully offline with a built-in knowledge base. If the environment
variable ANTHROPIC_API_KEY is set, answers come from an LLM instead and the
offline knowledge base is used as a fallback.
"""
import os
import re

LANGS = ("en", "hi", "te", "ta")

KB = [
    {"id": "greeting",
     "keys": ["hello", "hi ", "hey", "namaste", "नमस्ते", "नमस्कार", "నమస్తే", "హలో"],
     "en": "Hello! I am the KisanConnect assistant. Ask me about crop care, prices, diseases, orders or how to sell.",
     "hi": "नमस्ते! मैं किसानकनेक्ट सहायक हूं। फसल देखभाल, भाव, रोग, ऑर्डर या बेचने के बारे में पूछिए।",
     "te": "నమస్తే! నేను కిసాన్‌కనెక్ట్ సహాయకుడిని. పంటల సంరక్షణ, ధరలు, వ్యాధులు, ఆర్డర్లు లేదా అమ్మకం గురించి అడగండి."},
    {"id": "sell",
     "keys": ["sell", "list my", "listing", "add product", "बेच", "बिक्री", "అమ్మ", "అమ్మకం"],
     "en": "To sell: log in as a farmer, open Sell > Add produce, choose your crop, upload a photo for the AI quality grade, tap Suggest price, then save. New farmers need admin approval first.",
     "hi": "बेचने के लिए: किसान खाते से लॉगिन करें, Sell > Add produce खोलें, फसल चुनें, AI ग्रेड के लिए फोटो डालें, Suggest price दबाएं और सेव करें। नए किसानों को पहले एडमिन की मंजूरी चाहिए।",
     "te": "అమ్మడానికి: రైతు ఖాతాతో లాగిన్ అయి Sell > Add produce తెరవండి, పంటను ఎంచుకోండి, AI గ్రేడ్ కోసం ఫోటో అప్‌లోడ్ చేయండి, Suggest price నొక్కి సేవ్ చేయండి. కొత్త రైతులకు ముందుగా అడ్మిన్ ఆమోదం కావాలి."},
    {"id": "price",
     "keys": ["price", "rate", "cost", "how much", "भाव", "कीमत", "दाम", "ధర", "రేటు"],
     "en": "Use the Suggest price button on the Add produce page. The AI looks at the crop, month, quality grade and organic status and gives a fair price range. You can also check the Demand forecast page.",
     "hi": "Add produce पेज पर Suggest price बटन दबाएं। AI फसल, महीना, गुणवत्ता और जैविक स्थिति देखकर उचित भाव की सीमा बताता है। Demand forecast पेज भी देखें।",
     "te": "Add produce పేజీలో Suggest price బటన్ నొక్కండి. AI పంట, నెల, నాణ్యత, సేంద్రీయ స్థితిని చూసి సరైన ధర పరిధి చెబుతుంది. Demand forecast పేజీని కూడా చూడండి."},
    {"id": "disease",
     "keys": ["disease", "spot", "yellow", "fungus", "blight", "mildew", "leaf", "रोग", "बीमारी", "धब्बा", "पीली", "వ్యాధి", "తెగులు", "మచ్చ", "ఆకు"],
     "en": "Open Crop doctor, upload a clear photo of one leaf on a plain background, and the AI will show the likely problem and what to do. For serious damage, also visit your local agriculture officer (KVK).",
     "hi": "Crop doctor खोलें, सादे पीछे के रंग पर एक पत्ती की साफ फोटो डालें। AI संभावित रोग और उपाय बताएगा। ज्यादा नुकसान हो तो स्थानीय कृषि अधिकारी (KVK) से भी मिलें।",
     "te": "Crop doctor తెరిచి, సాదా నేపథ్యంపై ఒక ఆకు స్పష్టమైన ఫోటో అప్‌లోడ్ చేయండి. AI సంభావ్య సమస్య, చేయాల్సినది చూపుతుంది. ఎక్కువ నష్టం ఉంటే స్థానిక వ్యవసాయ అధికారిని (KVK) కూడా కలవండి."},
    {"id": "pest",
     "keys": ["pest", "insect", "worm", "aphid", "whitefly", "कीट", "कीड़ा", "इल्ली", "పురుగు", "కీటకం"],
     "en": "Start with neem oil spray (5 ml per litre of water) in the evening, use yellow sticky traps for whitefly and aphids, and remove badly infested plants. Use chemical pesticides only as advised by your local KVK.",
     "hi": "शाम को नीम तेल (5 मिली प्रति लीटर पानी) छिड़कें, सफेद मक्खी और माहू के लिए पीले चिपचिपे जाल लगाएं और ज्यादा प्रभावित पौधे हटा दें। रासायनिक कीटनाशक केवल KVK की सलाह पर इस्तेमाल करें।",
     "te": "సాయంత్రం వేప నూనె (లీటరు నీటికి 5 మి.లీ) చల్లండి, తెల్లదోమ, పేనుబంక కోసం పసుపు జిగురు అట్టలు వాడండి, ఎక్కువగా సోకిన మొక్కలను తీసివేయండి. రసాయన పురుగుమందులు స్థానిక KVK సలహా మేరకే వాడండి."},
    {"id": "fertilizer",
     "keys": ["fertilizer", "fertiliser", "urea", "npk", "manure", "compost", "खाद", "उर्वरक", "यूरिया", "ఎరువు", "యూరియా"],
     "en": "Do a soil test first and follow your Soil Health Card. Mix compost or farmyard manure before sowing, split nitrogen into 2 or 3 doses, and avoid too much urea because it attracts pests and lowers quality.",
     "hi": "पहले मिट्टी की जांच कराएं और सॉइल हेल्थ कार्ड के अनुसार खाद दें। बुवाई से पहले कम्पोस्ट या गोबर की खाद मिलाएं, नाइट्रोजन 2-3 बार में दें और ज्यादा यूरिया से बचें, इससे कीट बढ़ते हैं।",
     "te": "ముందు నేల పరీక్ష చేయించి సాయిల్ హెల్త్ కార్డు ప్రకారం ఎరువులు వేయండి. విత్తనం ముందు కంపోస్ట్ లేదా పశువుల ఎరువు కలపండి, నత్రజనిని 2-3 విడతలుగా వేయండి, ఎక్కువ యూరియా వద్దు, అది పురుగులను పెంచుతుంది."},
    {"id": "irrigation",
     "keys": ["water", "irrigation", "drip", "watering", "सिंचाई", "पानी", "ड्रिप", "నీరు", "నీటి", "డ్రిప్"],
     "en": "Water early in the morning, not at noon. Drip irrigation saves 30 to 50 percent water and keeps leaves dry, which lowers disease. Mulching with straw keeps soil moisture longer.",
     "hi": "सिंचाई सुबह जल्दी करें, दोपहर में नहीं। ड्रिप सिंचाई से 30 से 50 प्रतिशत पानी बचता है और पत्तियां सूखी रहती हैं, जिससे रोग कम होते हैं। पुआल की मल्चिंग से नमी ज्यादा समय रहती है।",
     "te": "ఉదయాన్నే నీరు పెట్టండి, మధ్యాహ్నం వద్దు. డ్రిప్ సేద్యంతో 30-50 శాతం నీరు ఆదా అవుతుంది, ఆకులు పొడిగా ఉండి వ్యాధులు తగ్గుతాయి. గడ్డితో మల్చింగ్ చేస్తే తేమ ఎక్కువ కాలం ఉంటుంది."},
    {"id": "tomato",
     "keys": ["tomato", "टमाटर", "టమాటా", "టమోటా"],
     "en": "Tomato tips: stake the plants, water evenly (uneven water causes fruit cracking and blossom-end rot), remove lower leaves touching the soil, and pick when fruits turn pink-red for better shelf life.",
     "hi": "टमाटर के लिए: पौधों को सहारा दें, बराबर सिंचाई करें (असमान पानी से फल फटते हैं), मिट्टी को छूती निचली पत्तियां हटाएं और अच्छी शेल्फ लाइफ के लिए फल गुलाबी-लाल होने पर तोड़ें।",
     "te": "టమాటా చిట్కాలు: మొక్కలకు కర్రలతో ఆసరా ఇవ్వండి, సమానంగా నీరు పెట్టండి (అసమాన నీటితో కాయలు పగులుతాయి), నేలను తాకే కింది ఆకులు తీసేయండి, ఎక్కువ రోజులు నిల్వ ఉండాలంటే గులాబీ-ఎరుపు రంగులో ఉన్నప్పుడు కోయండి."},
    {"id": "rice",
     "keys": ["rice", "paddy", "धान", "चावल", "వరి", "బియ్యం"],
     "en": "Paddy tips: keep 2 to 5 cm standing water during tillering, use certified seed, and drain the field about 10 days before harvest. Alternate wetting and drying can save water without losing yield.",
     "hi": "धान के लिए: कल्ले निकलते समय 2 से 5 सेमी पानी रखें, प्रमाणित बीज लें और कटाई से लगभग 10 दिन पहले खेत से पानी निकाल दें। बारी-बारी से गीला और सूखा रखने से पानी बचता है।",
     "te": "వరి చిట్కాలు: పిలకలు వేసే సమయంలో 2-5 సెం.మీ నీరు ఉంచండి, ధృవీకరించిన విత్తనాలు వాడండి, కోతకు సుమారు 10 రోజుల ముందు పొలం నుంచి నీరు తీసేయండి. తడి-పొడి పద్ధతితో నీరు ఆదా అవుతుంది."},
    {"id": "wheat",
     "keys": ["wheat", "गेहूं", "गेहू", "గోధుమ"],
     "en": "Wheat tips: sow in November for best yield, give the first irrigation about 21 days after sowing (crown root stage), and watch for yellow rust in cool humid weather.",
     "hi": "गेहूं के लिए: अच्छी उपज के लिए नवंबर में बुवाई करें, पहली सिंचाई बुवाई के लगभग 21 दिन बाद (ताज जड़ अवस्था) दें और ठंडे नम मौसम में पीले रतुआ पर नजर रखें।",
     "te": "గోధుమ చిట్కాలు: మంచి దిగుబడికి నవంబర్‌లో విత్తండి, విత్తిన సుమారు 21 రోజులకు మొదటి నీటి తడి ఇవ్వండి, చల్లని తేమ వాతావరణంలో పసుపు తుప్పు తెగులును గమనించండి."},
    {"id": "organic",
     "keys": ["organic", "natural farming", "जैविक", "प्राकृतिक", "సేంద్రీయ", "సేంద్రియ"],
     "en": "Tick the Organic box when listing. Organic lots usually fetch a higher price from buyers. Keep records of the inputs you use, such as compost, neem and bio-fertilisers, so buyers can trust the label.",
     "hi": "लिस्टिंग में Organic बॉक्स चुनें। जैविक उपज को आमतौर पर बेहतर भाव मिलता है। कम्पोस्ट, नीम, जैव उर्वरक जैसे इस्तेमाल किए गए इनपुट का रिकॉर्ड रखें ताकि खरीदार भरोसा करें।",
     "te": "లిస్టింగ్‌లో Organic బాక్స్ ఎంచుకోండి. సేంద్రీయ పంటలకు సాధారణంగా మంచి ధర వస్తుంది. కంపోస్ట్, వేప, జీవ ఎరువులు వంటి ఉపయోగించిన ఇన్‌పుట్‌ల రికార్డు ఉంచండి, కొనుగోలుదారులు నమ్ముతారు."},
    {"id": "storage",
     "keys": ["storage", "store", "shelf life", "fresh", "भंडारण", "स्टोर", "रखना", "నిల్వ"],
     "en": "Store grains below 12 percent moisture in clean dry bags. Keep onions and potatoes in a cool, ventilated place away from each other. Sell leafy vegetables within a day and use shade or wet cloth to keep them fresh.",
     "hi": "अनाज को 12 प्रतिशत से कम नमी पर साफ सूखे बोरों में रखें। प्याज और आलू को ठंडी हवादार जगह पर अलग-अलग रखें। पत्तेदार सब्जियां एक दिन में बेचें और छांव या गीले कपड़े से ताजा रखें।",
     "te": "ధాన్యాన్ని 12 శాతం కంటే తక్కువ తేమతో శుభ్రమైన పొడి సంచుల్లో నిల్వ చేయండి. ఉల్లి, బంగాళాదుంపలను చల్లని గాలి వచ్చే చోట వేర్వేరుగా ఉంచండి. ఆకుకూరలను ఒక రోజులో అమ్మండి, నీడ లేదా తడి గుడ్డతో తాజాగా ఉంచండి."},
    {"id": "payment",
     "keys": ["cod", "cash", "payment", "pay ", "भुगतान", "नकद", "पैसे", "చెల్లింపు", "డబ్బు", "క్యాష్"],
     "en": "KisanConnect supports Cash on Delivery only. The buyer pays the farmer when the order arrives, and the order is marked Payment collected once delivered.",
     "hi": "किसानकनेक्ट में केवल कैश ऑन डिलीवरी है। ऑर्डर पहुंचने पर खरीदार किसान को पैसे देता है और डिलीवरी के बाद ऑर्डर में Payment collected दिखता है।",
     "te": "కిసాన్‌కనెక్ట్‌లో కేవలం క్యాష్ ఆన్ డెలివరీ మాత్రమే ఉంది. ఆర్డర్ చేరినప్పుడు కొనుగోలుదారు రైతుకు డబ్బు ఇస్తారు, డెలివరీ తర్వాత ఆర్డర్‌లో Payment collected అని చూపిస్తుంది."},
    {"id": "order",
     "keys": ["order", "delivery", "track", "cancel", "ऑर्डर", "डिलीवरी", "ट्रैक", "రద్దు", "ఆర్డర్", "డెలివరీ"],
     "en": "Open Orders to track status: Placed, Confirmed, Packed, Out for delivery, Delivered. You can cancel while the order is Placed or Confirmed. You can also chat with the farmer from the product page.",
     "hi": "स्थिति देखने के लिए Orders खोलें: Placed, Confirmed, Packed, Out for delivery, Delivered। ऑर्डर Placed या Confirmed होने तक रद्द कर सकते हैं। प्रोडक्ट पेज से किसान से चैट भी कर सकते हैं।",
     "te": "స్థితి చూడటానికి Orders తెరవండి: Placed, Confirmed, Packed, Out for delivery, Delivered. ఆర్డర్ Placed లేదా Confirmed దశలో ఉన్నంతవరకు రద్దు చేయవచ్చు. ఉత్పత్తి పేజీ నుంచి రైతుతో చాట్ కూడా చేయవచ్చు."},
    {"id": "schemes",
     "keys": ["scheme", "subsidy", "pm-kisan", "pm kisan", "msp", "e-nam", "enam", "loan", "insurance", "योजना", "सब्सिडी", "बीमा", "पीएम किसान", "పథకం", "సబ్సిడీ", "బీమా"],
     "en": "Useful schemes: PM-KISAN (income support for farmers), e-NAM (online national agri market), Minimum Support Price for notified crops, and PM Fasal Bima Yojana (crop insurance). Check eligibility and dates on the official portals or at your nearest agriculture office.",
     "hi": "उपयोगी योजनाएं: पीएम-किसान (किसानों को आय सहायता), ई-नाम (ऑनलाइन राष्ट्रीय कृषि बाजार), अधिसूचित फसलों का न्यूनतम समर्थन मूल्य और पीएम फसल बीमा योजना। पात्रता और तारीखें सरकारी पोर्टल या नजदीकी कृषि कार्यालय से जांचें।",
     "te": "ఉపయోగకరమైన పథకాలు: పీఎం-కిసాన్ (రైతులకు ఆదాయ మద్దతు), ఈ-నామ్ (ఆన్‌లైన్ జాతీయ వ్యవసాయ మార్కెట్), నోటిఫై చేసిన పంటలకు కనీస మద్దతు ధర, పీఎం ఫసల్ బీమా యోజన. అర్హత, తేదీలను అధికారిక పోర్టల్ లేదా సమీప వ్యవసాయ కార్యాలయంలో చూడండి."},
    {"id": "soil",
     "keys": ["soil", "मिट्टी", "मृदा", "నేల", "మట్టి"],
     "en": "Test your soil every 2 to 3 years for pH and nutrients. Add compost to improve structure, rotate crops (for example cereal, then pulse) and avoid leaving soil bare between seasons.",
     "hi": "हर 2 से 3 साल में मिट्टी का pH और पोषक तत्व जांचें। संरचना सुधारने के लिए कम्पोस्ट डालें, फसल चक्र अपनाएं (जैसे अनाज के बाद दलहन) और सीजन के बीच खेत खाली न छोड़ें।",
     "te": "ప్రతి 2-3 ఏళ్లకు నేల pH, పోషకాలను పరీక్షించండి. నిర్మాణం మెరుగుపడటానికి కంపోస్ట్ వేయండి, పంట మార్పిడి చేయండి (ఉదా. ధాన్యం తర్వాత పప్పు), సీజన్ల మధ్య నేలను ఖాళీగా ఉంచవద్దు."},
    {"id": "quality",
     "keys": ["quality", "grade", "grading", "गुणवत्ता", "ग्रेड", "నాణ్యత", "గ్రేడ్"],
     "en": "Upload a clear daylight photo when you add produce. The AI scores colour, brightness, sharpness and blemishes and gives Grade A (premium), B (good) or C (standard). A grade builds trust and a better price.",
     "hi": "उपज जोड़ते समय दिन की रोशनी में साफ फोटो डालें। AI रंग, चमक, स्पष्टता और दागों को जांचकर ग्रेड A (प्रीमियम), B (अच्छा) या C (सामान्य) देता है। ग्रेड से भरोसा और बेहतर भाव मिलता है।",
     "te": "ఉత్పత్తిని చేర్చేటప్పుడు పగటి వెలుతురులో స్పష్టమైన ఫోటో పెట్టండి. AI రంగు, ప్రకాశం, స్పష్టత, మచ్చలను చూసి గ్రేడ్ A (ప్రీమియం), B (మంచి) లేదా C (సాధారణ) ఇస్తుంది. గ్రేడ్ నమ్మకాన్ని, మంచి ధరను ఇస్తుంది."},
    {"id": "register",
     "keys": ["register", "signup", "sign up", "account", "approval", "पंजीकरण", "रजिस्टर", "खाता", "నమోదు", "ఖాతా"],
     "en": "Tap Register, choose Farmer or Buyer and fill in your details. Buyers can shop right away. Farmers are approved by the admin first, which keeps the marketplace trusted.",
     "hi": "Register दबाएं, Farmer या Buyer चुनें और जानकारी भरें। खरीदार तुरंत खरीदारी कर सकते हैं। किसानों को पहले एडमिन से मंजूरी मिलती है ताकि बाजार भरोसेमंद रहे।",
     "te": "Register నొక్కి Farmer లేదా Buyer ఎంచుకుని వివరాలు నింపండి. కొనుగోలుదారులు వెంటనే కొనవచ్చు. మార్కెట్ నమ్మకంగా ఉండటానికి రైతులకు ముందుగా అడ్మిన్ ఆమోదం ఉంటుంది."},
]

FALLBACK = {
    "en": "I can help with crop care, pests, fertiliser, water, prices, quality grades, orders and schemes. Try one of the suggestions below.",
    "hi": "मैं फसल देखभाल, कीट, खाद, सिंचाई, भाव, गुणवत्ता ग्रेड, ऑर्डर और योजनाओं में मदद कर सकता हूं। नीचे दिए सुझावों में से कोई चुनें।",
    "te": "పంట సంరక్షణ, పురుగులు, ఎరువులు, నీరు, ధరలు, నాణ్యత గ్రేడ్‌లు, ఆర్డర్లు, పథకాల్లో నేను సహాయం చేయగలను. కింది సూచనల్లో ఒకటి ఎంచుకోండి."
}
SUGGESTIONS = {
    "en": ["How do I sell my produce?", "Tomato tips", "Pest control", "Government schemes"],
    "hi": ["मैं अपनी उपज कैसे बेचूं?", "टमाटर की देखभाल", "कीट नियंत्रण", "सरकारी योजनाएं"],
    "te": ["నా పంటను ఎలా అమ్మాలి?", "టమాటా చిట్కాలు", "పురుగుల నివారణ", "ప్రభుత్వ పథకాలు"],
}


def detect_lang(text, default="en"):
    if re.search(r"[\u0B80-\u0BFF]", text):
        return "ta"
    if re.search(r"[\u0C00-\u0C7F]", text):
        return "te"
    if re.search(r"[\u0900-\u097F]", text):
        return "hi"
    return default if default in LANGS else "en"


def _offline(message, lang):
    text = " " + message.lower().strip() + " "
    best, best_score = None, 0
    for entry in KB:
        score = sum(len(k) for k in entry["keys"] if k in text)
        if score > best_score:
            best, best_score = entry, score
    return best[lang] if best else FALLBACK[lang]


def _llm(message, lang):
    key = os.environ.get("ANTHROPIC_API_KEY")
    if not key:
        return None
    try:
        import requests
        names = {"en": "English", "hi": "Hindi", "te": "Telugu", "ta": "Tamil"}
        resp = requests.post(
            "https://api.anthropic.com/v1/messages",
            headers={"x-api-key": key, "anthropic-version": "2023-06-01", "content-type": "application/json"},
            json={
                "model": os.environ.get("ANTHROPIC_MODEL", "claude-sonnet-5-5"),
                "max_tokens": 400,
                "system": (
                    "You are the KisanConnect farming assistant for Indian farmers and buyers. "
                    f"Reply in {names[lang]} in under 120 words, in plain simple language. "
                    "Give practical crop, pest, price and marketplace advice. "
                    "Payment on this platform is Cash on Delivery only. "
                    "For chemical doses, tell the user to confirm with the local KVK or agriculture officer."
                ),
                "messages": [{"role": "user", "content": message}],
            },
            timeout=15,
        )
        resp.raise_for_status()
        return resp.json()["content"][0]["text"].strip()
    except Exception:
        return None


def reply(message, lang="en"):
    message = (message or "").strip()[:500]
    lang = detect_lang(message, lang)
    if not message:
        return {"reply": FALLBACK[lang], "lang": lang, "suggestions": SUGGESTIONS[lang], "source": "offline"}
    text = _llm(message, lang)
    source = "llm"
    if not text:
        text, source = _offline(message, lang), "offline"
    return {"reply": text, "lang": lang, "suggestions": SUGGESTIONS[lang], "source": source}


# ---- Tamil -------------------------------------------------------------
_TA_KB = {'greeting': (['வணக்கம்', 'ஹலோ'], 'வணக்கம்! நான் கிசான்கனெக்ட் உதவியாளர். பயிர் பராமரிப்பு, விலைகள், நோய்கள், ஆர்டர்கள் அல்லது விற்பனை பற்றி கேளுங்கள்.'), 'sell': (['விற்க', 'விற்பனை', 'விற்பது'], 'விற்க: விவசாயி கணக்கில் உள்நுழைந்து Sell > Add produce திறக்கவும், பயிரைத் தேர்ந்தெடுக்கவும், AI தரத்திற்காக புகைப்படம் பதிவேற்றவும், Suggest price அழுத்தி சேமிக்கவும். புதிய விவசாயிகளுக்கு முதலில் நிர்வாகியின் அனுமதி தேவை.'), 'price': (['விலை', 'ரேட்', 'எவ்வளவு'], 'Add produce பக்கத்தில் Suggest price பொத்தானை அழுத்தவும். AI பயிர், மாதம், தரம், இயற்கை நிலை ஆகியவற்றைப் பார்த்து நியாயமான விலை வரம்பைத் தரும். Demand forecast பக்கத்தையும் பாருங்கள்.'), 'disease': (['நோய்', 'புள்ளி', 'மஞ்சள்', 'பூஞ்சை', 'இலை'], 'Crop doctor திறந்து, சாதாரண பின்னணியில் ஒரு இலையின் தெளிவான புகைப்படத்தைப் பதிவேற்றவும். AI சாத்தியமான பிரச்சினையையும் செய்ய வேண்டியதையும் காட்டும். அதிக சேதம் இருந்தால் உள்ளூர் வேளாண் அதிகாரியையும் (KVK) சந்திக்கவும்.'), 'pest': (['பூச்சி', 'புழு'], 'மாலையில் வேப்ப எண்ணெய் (ஒரு லிட்டர் நீருக்கு 5 மி.லி) தெளிக்கவும், வெள்ளை ஈ மற்றும் அசுவினிக்கு மஞ்சள் ஒட்டும் பொறிகள் வைக்கவும், மிகவும் பாதிக்கப்பட்ட செடிகளை அகற்றவும். ரசாயன பூச்சிக்கொல்லிகளை உள்ளூர் KVK ஆலோசனைப்படி மட்டுமே பயன்படுத்தவும்.'), 'fertilizer': (['உரம்', 'யூரியா'], 'முதலில் மண் பரிசோதனை செய்து மண் வள அட்டைப்படி உரமிடுங்கள். விதைப்பதற்கு முன் தொழு உரம் அல்லது மட்கு கலக்கவும், தழைச்சத்தை 2-3 முறையாகப் பிரித்து இடவும், அதிக யூரியா வேண்டாம், அது பூச்சிகளை ஈர்க்கும்.'), 'irrigation': (['நீர்', 'பாசனம்', 'தண்ணீர்'], 'அதிகாலையில் நீர் பாய்ச்சுங்கள், மதியம் வேண்டாம். சொட்டு நீர்ப் பாசனம் 30 முதல் 50 சதவீதம் நீரைச் சேமிக்கும், இலைகள் உலர்ந்திருப்பதால் நோய்கள் குறையும். வைக்கோல் மூடாக்கு ஈரத்தை நீண்ட நேரம் தக்க வைக்கும்.'), 'tomato': (['தக்காளி'], 'தக்காளி குறிப்புகள்: செடிகளுக்கு ஊன்றுகோல் கொடுங்கள், சீராக நீர் பாய்ச்சுங்கள் (சீரற்ற நீரால் காய்கள் வெடிக்கும்), மண்ணைத் தொடும் கீழ் இலைகளை அகற்றுங்கள், நீண்ட நாள் இருக்க பழங்கள் இளஞ்சிவப்பு-சிவப்பு ஆனதும் பறிக்கவும்.'), 'rice': (['நெல்', 'அரிசி'], 'நெல் குறிப்புகள்: தூர் கட்டும் நேரத்தில் 2-5 செ.மீ நீர் நிறுத்துங்கள், சான்றளிக்கப்பட்ட விதை பயன்படுத்துங்கள், அறுவடைக்கு சுமார் 10 நாட்கள் முன் வயலில் நீரை வடியுங்கள். மாற்று ஈரம்-உலர்வு முறை நீரை சேமிக்கும்.'), 'wheat': (['கோதுமை'], 'கோதுமை குறிப்புகள்: நல்ல மகசூலுக்கு நவம்பரில் விதையுங்கள், விதைத்த சுமார் 21 நாட்களில் முதல் நீர்ப்பாசனம் கொடுங்கள், குளிர்ந்த ஈரப்பத வானிலையில் மஞ்சள் துரு நோயைக் கவனியுங்கள்.'), 'organic': (['இயற்கை', 'ஆர்கானிக்'], 'பட்டியலிடும்போது Organic பெட்டியைத் தேர்ந்தெடுக்கவும். இயற்கை விளைபொருளுக்கு பொதுவாக நல்ல விலை கிடைக்கும். மட்கு, வேம்பு, உயிர் உரங்கள் போன்ற பயன்படுத்திய இடுபொருட்களின் பதிவை வைத்திருங்கள், வாங்குபவர்கள் நம்புவார்கள்.'), 'storage': (['சேமிப்பு', 'சேமிக்க', 'இருப்பு'], 'தானியங்களை 12 சதவீதத்திற்கும் குறைவான ஈரப்பதத்தில் சுத்தமான உலர்ந்த சாக்குகளில் சேமிக்கவும். வெங்காயம், உருளைக்கிழங்கை குளிர்ந்த காற்றோட்டமுள்ள இடத்தில் தனித்தனியாக வைக்கவும். கீரைகளை ஒரு நாளில் விற்று, நிழல் அல்லது ஈரத்துணியால் புதிதாக வைக்கவும்.'), 'payment': (['பணம்', 'கட்டணம்', 'கேஷ்'], 'கிசான்கனெக்டில் டெலிவரியில் பணம் (COD) மட்டுமே உள்ளது. ஆர்டர் வந்ததும் வாங்குபவர் விவசாயிக்கு பணம் கொடுப்பார், டெலிவரிக்குப் பின் ஆர்டரில் Payment collected என்று காட்டும்.'), 'order': (['ஆர்டர்', 'டெலிவரி', 'ரத்து'], 'நிலையை அறிய Orders திறக்கவும்: Placed, Confirmed, Packed, Out for delivery, Delivered. ஆர்டர் Placed அல்லது Confirmed நிலையில் இருக்கும் வரை ரத்து செய்யலாம். தயாரிப்பு பக்கத்திலிருந்து விவசாயியுடன் அரட்டையும் செய்யலாம்.'), 'schemes': (['திட்டம்', 'மானியம்', 'காப்பீடு', 'பிஎம் கிசான்'], 'பயனுள்ள திட்டங்கள்: பிஎம்-கிசான் (விவசாயிகளுக்கு வருமான உதவி), ஈ-நாம் (இணையவழி தேசிய வேளாண் சந்தை), அறிவிக்கப்பட்ட பயிர்களுக்கு குறைந்தபட்ச ஆதரவு விலை, பிஎம் பசல் பீமா யோஜனா (பயிர் காப்பீடு). தகுதி மற்றும் தேதிகளை அதிகாரப்பூர்வ இணையதளம் அல்லது அருகிலுள்ள வேளாண் அலுவலகத்தில் சரிபார்க்கவும்.'), 'soil': (['மண்'], 'ஒவ்வொரு 2 முதல் 3 ஆண்டுகளுக்கும் மண்ணின் pH மற்றும் சத்துகளைப் பரிசோதியுங்கள். அமைப்பை மேம்படுத்த மட்கு சேர்க்கவும், பயிர் சுழற்சி செய்யவும் (எ.கா. தானியத்துக்குப் பின் பருப்பு), பருவங்களுக்கு இடையில் நிலத்தை வெறுமையாக விடாதீர்கள்.'), 'quality': (['தரம்', 'கிரேடு'], 'பயிரைச் சேர்க்கும்போது பகல் வெளிச்சத்தில் தெளிவான புகைப்படம் பதிவேற்றவும். AI நிறம், பிரகாசம், தெளிவு, கறைகளை மதிப்பிட்டு தரம் A (உயர்), B (நல்லது) அல்லது C (சாதாரணம்) வழங்கும். தரம் நம்பிக்கையையும் நல்ல விலையையும் தரும்.'), 'register': (['பதிவு', 'கணக்கு', 'அனுமதி'], 'Register அழுத்தி Farmer அல்லது Buyer தேர்ந்தெடுத்து விவரங்களை நிரப்பவும். வாங்குபவர்கள் உடனே வாங்கலாம். சந்தை நம்பகமாக இருக்க விவசாயிகளுக்கு முதலில் நிர்வாகி அனுமதி உண்டு.')}
for _e in KB:
    _keys, _text = _TA_KB[_e["id"]]
    _e["keys"] = _e["keys"] + _keys
    _e["ta"] = _text
FALLBACK["ta"] = "பயிர் பராமரிப்பு, பூச்சிகள், உரம், நீர், விலைகள், தரம், ஆர்டர்கள், திட்டங்கள் பற்றி நான் உதவ முடியும். கீழே உள்ள பரிந்துரைகளில் ஒன்றைத் தேர்ந்தெடுக்கவும்."
SUGGESTIONS["ta"] = ["என் விளைபொருளை எப்படி விற்பது?", "தக்காளி குறிப்புகள்", "பூச்சி கட்டுப்பாடு", "அரசு திட்டங்கள்"]
