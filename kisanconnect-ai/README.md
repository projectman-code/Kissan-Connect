# KisanConnect AI

A direct farmer-to-buyer agriculture marketplace built with Python (Flask) and AI features.
Payment is **Cash on Delivery only**. The interface works in **English, Hindi, Telugu and Tamil**.

## Run it (3 steps)

```bash
# 1. open a terminal in this folder, then (recommended) make a virtual environment
python -m venv venv
venv\Scripts\activate          # Windows
source venv/bin/activate       # macOS / Linux

# 2. install
pip install -r requirements.txt

# 3. start
python app.py
```

Open **http://127.0.0.1:5000**. Demo data is created automatically on the first run.
Python 3.9 or newer is required.

## Demo logins

| Role   | Username   | Password    | Notes                                  |
|--------|------------|-------------|----------------------------------------|
| Admin  | `admin`    | `admin123`  | Sees everything, approves farmers      |
| Farmer | `ramesh`   | `farmer123` | Nashik, has produce and orders         |
| Farmer | `lakshmi`  | `farmer123` | Guntur, Telugu interface               |
| Farmer | `gurpreet` | `farmer123` | Ludhiana, dairy and grains             |
| Farmer | `suresh`   | `farmer123` | Waiting for admin approval             |
| Buyer  | `priya`    | `buyer123`  | Has orders and a chat                  |
| Buyer  | `spicehub` | `buyer123`  | Restaurant with bulk orders            |

The login page has buttons that fill these in. **Before real use**, change the passwords
and delete the "Demo accounts" box in `templates/login.html`.

## One login for everyone

All roles use the same `/login` page. The server checks the username and password, reads the
account's role from the database and redirects:

- Admin goes to `/admin`
- Farmer goes to `/farmer`
- Buyer goes to `/shop`

**Admin can do everything farmers and buyers can do**, plus approve or block users, switch
cash on delivery off for a buyer, manage every listing and order, and create accounts.
Role checks live in one place, the `role_required()` decorator in `app.py`.

## Features

**Marketplace**
- Search, category, grade and organic filters
- Cart, checkout, order tracking (Placed, Confirmed, Packed, Out for delivery, Delivered, Cancelled)
- Orders from different farmers are split automatically
- Reviews after delivery, farmer-buyer chat with live updates
- Farmers manage produce and orders, admin has analytics

**AI**
| Feature | Where | How it works |
|---|---|---|
| Smart price suggestion | Add produce, product page | RandomForest trained on seasonal price patterns (`ai/price.py`) |
| Photo quality grading A/B/C | Add produce | Pillow and NumPy: colour, brightness, sharpness, blemishes (`ai/quality.py`) |
| Crop doctor | Crop doctor page | Leaf colour-pattern analysis with treatment advice in 4 languages (`ai/disease.py`) |
| Demand forecast | Sell > Demand forecast | Seasonal RandomForest blended with real orders (`ai/forecast.py`) |
| Farming assistant | Chat bubble on every page | Offline knowledge base in 4 languages, optional LLM (`ai/chatbot.py`) |

### Be honest about the models
The price, demand and disease models run on built-in seasonal data and colour analysis so the
project works anywhere with no downloads. They are good for demos and a strong base. For a
production launch, replace the training data in `ai/price.py` and `ai/forecast.py` with real
mandi prices, and swap `diagnose()` in `ai/disease.py` for a CNN trained on a dataset such as
PlantVillage. The function signatures stay the same.

### Optional: LLM chatbot
Set an API key and the assistant answers with an LLM, falling back to the offline knowledge
base if the call fails:

```bash
set ANTHROPIC_API_KEY=your_key        # Windows
export ANTHROPIC_API_KEY=your_key     # macOS / Linux
python app.py
```

## Project structure

```
app.py              routes, auth, orders, admin
seed.py             demo data
i18n.py             English / Hindi / Telugu / Tamil interface text
ai/                 price, quality, disease, forecast, chatbot, crop catalog
templates/          pages (admin/, farmer/ sub-folders)
static/css, js      styling and behaviour
instance/kisan.db   SQLite database (created on first run)
static/uploads/     produce photos
```

## Reset the demo data
Stop the app, delete `instance/kisan.db`, start it again.

## Before going live
- Set a strong `SECRET_KEY` environment variable
- Change or remove demo accounts
- Run behind a production server (for example `gunicorn app:app`) with HTTPS
- Replace the AI training data with real data
