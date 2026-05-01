# Wardrobe — AI Personal Stylist

Upload photos of your clothes, build your style profile, and let GPT-4o generate outfits tailored to your color theory and taste. The app tracks what you wear so it never repeats an outfit too soon.

## Features

- **Wardrobe** — Upload clothing photos; GPT-4o auto-analyzes each item (name, category, colors, style tags)
- **Outfit Generator** — AI builds outfits from available items, skipping anything worn in the last 3 days
- **Wear Log** — Mark outfits as worn; view history
- **Style Profile** — Store your color season, skin tone, best/avoid colors, style vibe, and fit preferences so every suggestion is personalized

## Setup

```bash
# 1. Clone
git clone https://github.com/znantwan/wardrobe.git
cd wardrobe

# 2. Install dependencies
pip install -r requirements.txt

# 3. Set your OpenAI API key
export OPENAI_API_KEY=sk-...       # Mac/Linux
set OPENAI_API_KEY=sk-...          # Windows

# 4. Run
streamlit run app.py
```

The SQLite database is created automatically at `data/wardrobe.db` on first run.

## How it works

1. Upload a photo → GPT-4o vision identifies the item and pre-fills all metadata
2. Fill in your **Style Profile** once (color season, what colors look good on you, etc.)
3. Hit **Generate Outfit** — the AI reads your full wardrobe + profile + recent wear history and picks a combination that flatters your coloring and suits the occasion
4. Tap **"I'm wearing this today"** to log it — those items are rested for 3 days automatically
