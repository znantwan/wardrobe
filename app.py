import base64
import io
import sys
from pathlib import Path

import streamlit as st
from PIL import Image

sys.path.insert(0, str(Path(__file__).parent))
from src import database as db
from src import claude_client as claude

# ── Page config ───────────────────────────────────────────────────────────────

st.set_page_config(
    page_title="My Wardrobe",
    page_icon="👗",
    layout="wide",
    initial_sidebar_state="expanded",
)

db.init_db()

# ── Sidebar nav ───────────────────────────────────────────────────────────────

PAGES = ["👗 Wardrobe", "✨ Outfit Generator", "📅 Wear Log", "🎨 My Style Profile"]
page = st.sidebar.radio("Navigate", PAGES)

st.sidebar.markdown("---")
st.sidebar.caption("Powered by Claude · Your personal AI stylist")

# ── Helpers ───────────────────────────────────────────────────────────────────

CATEGORY_EMOJI = {
    "top": "👕",
    "bottom": "👖",
    "outerwear": "🧥",
    "shoes": "👟",
    "dress": "👗",
    "accessory": "💍",
    "bag": "👜",
}

COLOR_SWATCHES = {
    "black": "#111111",
    "white": "#f5f5f5",
    "navy blue": "#1a2a5e",
    "navy": "#1a2a5e",
    "blue": "#1e6aad",
    "red": "#cc2200",
    "green": "#2e7d32",
    "olive": "#6b6e2a",
    "grey": "#888888",
    "gray": "#888888",
    "brown": "#795548",
    "beige": "#d4b896",
    "cream": "#fffdd0",
    "pink": "#e91e8c",
    "purple": "#7b1fa2",
    "yellow": "#f9a825",
    "orange": "#e65100",
    "camel": "#c19a6b",
    "tan": "#d2b48c",
    "burgundy": "#800020",
    "khaki": "#c3b091",
}


def img_to_base64(uploaded_file) -> tuple[str, str]:
    img = Image.open(uploaded_file)
    if img.mode in ("RGBA", "P"):
        img = img.convert("RGB")
    buf = io.BytesIO()
    img.save(buf, format="JPEG", quality=85)
    b64 = base64.b64encode(buf.getvalue()).decode()
    return b64, "image/jpeg"


def render_image(b64: str, width: int = 200):
    if b64:
        st.image(f"data:image/jpeg;base64,{b64}", width=width)
    else:
        st.markdown(
            f'<div style="width:{width}px;height:{width}px;background:#f0f0f0;'
            f'display:flex;align-items:center;justify-content:center;border-radius:8px;'
            f'font-size:2rem;">📷</div>',
            unsafe_allow_html=True,
        )


def color_badge(color: str) -> str:
    hex_color = COLOR_SWATCHES.get(color.lower(), "#cccccc")
    text_color = "#fff" if _is_dark(hex_color) else "#333"
    return (
        f'<span style="background:{hex_color};color:{text_color};padding:2px 8px;'
        f'border-radius:12px;font-size:0.75rem;margin-right:4px;">{color}</span>'
    )


def _is_dark(hex_color: str) -> bool:
    h = hex_color.lstrip("#")
    r, g, b = int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16)
    return (0.299 * r + 0.587 * g + 0.114 * b) < 128


# ── Page: Wardrobe ────────────────────────────────────────────────────────────

if page == "👗 Wardrobe":
    st.title("👗 My Wardrobe")

    # Upload section
    with st.expander("➕ Add a clothing item", expanded=False):
        uploaded = st.file_uploader(
            "Upload a photo of the item", type=["jpg", "jpeg", "png", "webp"]
        )

        if uploaded:
            col_img, col_form = st.columns([1, 2])
            with col_img:
                st.image(uploaded, use_container_width=True)

            with col_form:
                if st.button("🤖 Auto-analyze with Claude", type="primary"):
                    with st.spinner("Claude is analyzing your item..."):
                        try:
                            b64, mime = img_to_base64(uploaded)
                            result = claude.analyze_clothing_image(b64, mime)
                            st.session_state["analyzed"] = result
                            st.session_state["analyzed_b64"] = b64
                        except Exception as e:
                            st.error(f"Analysis failed: {e}")

                analyzed = st.session_state.get("analyzed", {})

                with st.form("add_item_form"):
                    name = st.text_input("Name", value=analyzed.get("name", ""))
                    category = st.selectbox(
                        "Category",
                        ["top", "bottom", "outerwear", "shoes", "dress", "accessory", "bag"],
                        index=["top", "bottom", "outerwear", "shoes", "dress", "accessory", "bag"].index(
                            analyzed.get("category", "top")
                        ) if analyzed.get("category") in ["top", "bottom", "outerwear", "shoes", "dress", "accessory", "bag"] else 0,
                    )
                    colors_raw = st.text_input(
                        "Colors (comma-separated)",
                        value=", ".join(analyzed.get("colors", [])),
                    )
                    description = st.text_area("Description", value=analyzed.get("description", ""))
                    tags_raw = st.text_input(
                        "Tags (comma-separated)", value=", ".join(analyzed.get("tags", []))
                    )

                    submitted = st.form_submit_button("Save to Wardrobe")
                    if submitted:
                        b64 = st.session_state.get("analyzed_b64")
                        if not b64:
                            b64, _ = img_to_base64(uploaded)
                        db.add_clothing_item(
                            name=name,
                            category=category,
                            colors=[c.strip() for c in colors_raw.split(",") if c.strip()],
                            description=description,
                            tags=[t.strip() for t in tags_raw.split(",") if t.strip()],
                            image_base64=b64,
                        )
                        st.success(f"✅ '{name}' added to your wardrobe!")
                        st.session_state.pop("analyzed", None)
                        st.session_state.pop("analyzed_b64", None)
                        st.rerun()

    st.markdown("---")

    clothes = db.get_all_clothes()
    recently_worn_ids = db.get_recently_worn_ids(days=3)

    if not clothes:
        st.info("Your wardrobe is empty. Add your first item above!")
    else:
        # Filter controls
        categories = sorted(set(c["category"] for c in clothes))
        col_f1, col_f2 = st.columns([1, 3])
        with col_f1:
            filter_cat = st.selectbox("Filter by category", ["All"] + categories)

        filtered = clothes if filter_cat == "All" else [c for c in clothes if c["category"] == filter_cat]

        st.caption(f"Showing {len(filtered)} of {len(clothes)} items")

        # Grid display
        cols = st.columns(4)
        for i, item in enumerate(filtered):
            with cols[i % 4]:
                with st.container():
                    render_image(item["image_base64"], width=160)
                    worn_badge = " 🔄" if item["id"] in recently_worn_ids else ""
                    st.markdown(
                        f"**{CATEGORY_EMOJI.get(item['category'], '👔')} {item['name']}**{worn_badge}"
                    )
                    colors_html = "".join(color_badge(c) for c in item["colors"])
                    st.markdown(colors_html, unsafe_allow_html=True)
                    st.caption(item.get("description", ""))
                    if st.button("🗑 Remove", key=f"del_{item['id']}"):
                        db.delete_clothing_item(item["id"])
                        st.rerun()
                    st.markdown("<br>", unsafe_allow_html=True)

# ── Page: Outfit Generator ────────────────────────────────────────────────────

elif page == "✨ Outfit Generator":
    st.title("✨ Outfit Generator")

    clothes = db.get_all_clothes()
    if not clothes:
        st.warning("Add some clothes to your wardrobe first!")
        st.stop()

    recently_worn_ids = db.get_recently_worn_ids(days=3)
    style_profile = db.get_full_profile()

    col1, col2 = st.columns([1, 1])
    with col1:
        occasion = st.selectbox(
            "Occasion",
            ["everyday", "work", "date night", "casual weekend", "gym/active", "formal event", "travel"],
        )
    with col2:
        weather = st.text_input("Weather / season (optional)", placeholder="e.g. warm summer day, cold rainy")

    extra_notes = st.text_area(
        "Any special requests?",
        placeholder="e.g. want to wear my new white sneakers, feeling minimal today...",
        height=80,
    )

    if st.button("✨ Generate Outfit", type="primary", use_container_width=True):
        available_count = len([c for c in clothes if c["id"] not in recently_worn_ids])
        if available_count < 2:
            st.warning("Not enough available items (recently worn items are excluded). Try again tomorrow!")
        else:
            with st.spinner("Claude is styling your outfit..."):
                try:
                    result = claude.generate_outfit(
                        wardrobe=clothes,
                        recently_worn_ids=recently_worn_ids,
                        style_profile=style_profile,
                        occasion=occasion,
                        weather=weather,
                        extra_notes=extra_notes,
                    )
                    st.session_state["last_outfit"] = result
                    st.session_state["last_outfit_clothes"] = clothes
                except Exception as e:
                    st.error(f"Outfit generation failed: {e}")

    outfit_result = st.session_state.get("last_outfit")
    if outfit_result:
        st.markdown("---")
        st.subheader("Today's Outfit")

        outfit_ids = outfit_result.get("outfit", [])
        outfit_items = {
            c["id"]: c
            for c in st.session_state.get("last_outfit_clothes", clothes)
            if c["id"] in outfit_ids
        }

        if outfit_items:
            img_cols = st.columns(len(outfit_items))
            for col, item_id in zip(img_cols, outfit_ids):
                item = outfit_items.get(item_id)
                if item:
                    with col:
                        render_image(item["image_base64"], width=150)
                        st.caption(f"**{item['name']}**")
                        colors_html = "".join(color_badge(c) for c in item["colors"])
                        st.markdown(colors_html, unsafe_allow_html=True)

        st.markdown("#### Why this works")
        st.markdown(outfit_result.get("explanation", ""))

        st.markdown("#### Styling Tips")
        for tip in outfit_result.get("styling_tips", []):
            st.markdown(f"- {tip}")

        st.markdown("---")
        col_log, col_regen = st.columns(2)
        with col_log:
            if st.button("✅ I'm wearing this today!", type="primary", use_container_width=True):
                db.log_outfit_worn(
                    cloth_ids=outfit_ids,
                    outfit_description=outfit_result.get("explanation", ""),
                )
                st.success("Logged! These items will be rested for the next 3 days.")
                st.session_state.pop("last_outfit", None)
                st.rerun()
        with col_regen:
            if st.button("🔄 Generate another", use_container_width=True):
                st.session_state.pop("last_outfit", None)
                st.rerun()

# ── Page: Wear Log ────────────────────────────────────────────────────────────

elif page == "📅 Wear Log":
    st.title("📅 Wear Log")

    logs = db.get_all_wear_log()
    clothes_map = {c["id"]: c for c in db.get_all_clothes()}

    if not logs:
        st.info("No outfits logged yet. Generate an outfit and mark it worn!")
    else:
        for log in logs:
            worn_date = log["worn_at"][:10]
            outfit_items = [clothes_map[cid] for cid in log["cloth_ids"] if cid in clothes_map]

            with st.expander(f"📅 {worn_date} — {', '.join(i['name'] for i in outfit_items)}", expanded=False):
                if outfit_items:
                    img_cols = st.columns(min(len(outfit_items), 4))
                    for col, item in zip(img_cols, outfit_items):
                        with col:
                            render_image(item["image_base64"], width=120)
                            st.caption(item["name"])

                if log.get("outfit_description"):
                    st.markdown("**Stylist notes:**")
                    st.caption(log["outfit_description"])

                if log.get("notes"):
                    st.markdown(f"**Your notes:** {log['notes']}")

# ── Page: Style Profile ───────────────────────────────────────────────────────

elif page == "🎨 My Style Profile":
    st.title("🎨 My Style Profile")
    st.markdown(
        "Fill in your color theory and style info so Claude can give you perfectly tailored suggestions. "
        "The more you share, the better the outfit recommendations."
    )

    profile = db.get_full_profile()

    with st.form("style_profile_form"):
        st.subheader("Color Theory")
        color_season = st.selectbox(
            "Color Season",
            ["", "Spring (Warm/Light)", "Summer (Cool/Light)", "Autumn (Warm/Deep)", "Winter (Cool/Deep)"],
            index=["", "Spring (Warm/Light)", "Summer (Cool/Light)", "Autumn (Warm/Deep)", "Winter (Cool/Deep)"].index(
                profile.get("color_season", "")
            ) if profile.get("color_season", "") in ["", "Spring (Warm/Light)", "Summer (Cool/Light)", "Autumn (Warm/Deep)", "Winter (Cool/Deep)"] else 0,
        )
        skin_tone = st.text_input(
            "Skin Tone (describe freely)",
            value=profile.get("skin_tone", ""),
            placeholder="e.g. warm medium brown, cool fair with pink undertones",
        )
        best_colors = st.text_area(
            "Colors that look great on you",
            value=profile.get("best_colors", ""),
            placeholder="e.g. earthy tones, rust, olive, warm whites, camel",
            height=80,
        )
        avoid_colors = st.text_area(
            "Colors to avoid",
            value=profile.get("avoid_colors", ""),
            placeholder="e.g. cool greys, pastels, neon",
            height=80,
        )

        st.subheader("Style Preferences")
        style_vibe = st.text_area(
            "Your style vibe",
            value=profile.get("style_vibe", ""),
            placeholder="e.g. clean minimalist with street edge, classic with modern fits",
            height=80,
        )
        fit_preference = st.text_input(
            "Fit preference",
            value=profile.get("fit_preference", ""),
            placeholder="e.g. relaxed tops, slim bottoms, oversized outerwear",
        )
        lifestyle = st.text_area(
            "Lifestyle & typical occasions",
            value=profile.get("lifestyle", ""),
            placeholder="e.g. creative office job, lots of weekend brunches, occasional formal events",
            height=80,
        )
        notes = st.text_area(
            "Anything else Claude should know",
            value=profile.get("notes", ""),
            placeholder="e.g. I run hot so prefer breathable fabrics, I'm 5'9 with athletic build",
            height=80,
        )

        if st.form_submit_button("💾 Save Profile", type="primary", use_container_width=True):
            fields = {
                "color_season": color_season,
                "skin_tone": skin_tone,
                "best_colors": best_colors,
                "avoid_colors": avoid_colors,
                "style_vibe": style_vibe,
                "fit_preference": fit_preference,
                "lifestyle": lifestyle,
                "notes": notes,
            }
            for k, v in fields.items():
                if v:
                    db.set_profile_value(k, v)
            st.success("✅ Style profile saved! Claude will use this for all outfit suggestions.")
            st.rerun()

    if profile:
        st.markdown("---")
        st.subheader("Current Profile")
        labels = {
            "color_season": "Color Season",
            "skin_tone": "Skin Tone",
            "best_colors": "Best Colors",
            "avoid_colors": "Colors to Avoid",
            "style_vibe": "Style Vibe",
            "fit_preference": "Fit Preference",
            "lifestyle": "Lifestyle",
            "notes": "Notes",
        }
        for key, label in labels.items():
            if val := profile.get(key):
                st.markdown(f"**{label}:** {val}")
