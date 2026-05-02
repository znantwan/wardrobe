import base64
import json
import os
import anthropic

_client = None


def _get_client() -> anthropic.Anthropic:
    global _client
    if _client is None:
        _client = anthropic.Anthropic(api_key=os.environ.get("ANTHROPIC_API_KEY"))
    return _client


MODEL = "claude-sonnet-4-6"


def analyze_clothing_image(image_base64: str, mime_type: str = "image/jpeg") -> dict:
    """
    Send a clothing image to Claude and get back structured metadata.
    Returns dict with: name, category, colors, description, tags
    """
    client = _get_client()

    prompt = """Analyze this clothing item and return a JSON object with these fields:
- name: a short descriptive name (e.g. "White Linen Button-Down", "Navy Slim Chinos")
- category: one of [top, bottom, outerwear, shoes, dress, accessory, bag]
- colors: list of colors present (be specific, e.g. ["navy blue", "white"])
- description: 1-2 sentences describing style, fit, fabric if visible, and formality level
- tags: list of style tags (e.g. ["casual", "summer", "classic", "streetwear", "business"])

Return ONLY valid JSON, no markdown fences."""

    response = client.messages.create(
        model=MODEL,
        max_tokens=512,
        messages=[
            {
                "role": "user",
                "content": [
                    {
                        "type": "image",
                        "source": {
                            "type": "base64",
                            "media_type": mime_type,
                            "data": image_base64,
                        },
                    },
                    {"type": "text", "text": prompt},
                ],
            }
        ],
    )

    raw = response.content[0].text.strip()
    if raw.startswith("```"):
        raw = raw.split("```")[1]
        if raw.startswith("json"):
            raw = raw[4:]
    return json.loads(raw.strip())


def generate_outfit(
    wardrobe: list[dict],
    recently_worn_ids: set[int],
    style_profile: dict,
    occasion: str = "everyday",
    weather: str = "",
    extra_notes: str = "",
) -> dict:
    """
    Ask Claude to build an outfit from the wardrobe.
    Returns dict with: outfit (list of item ids), explanation, styling_tips
    """
    client = _get_client()

    profile_text = _build_profile_text(style_profile)

    available = [item for item in wardrobe if item["id"] not in recently_worn_ids]
    recently_worn = [item for item in wardrobe if item["id"] in recently_worn_ids]

    wardrobe_lines = []
    for item in available:
        wardrobe_lines.append(
            f"ID {item['id']} | {item['category'].upper()} | {item['name']} | "
            f"Colors: {', '.join(item['colors'])} | {item['description']} | Tags: {', '.join(item['tags'])}"
        )

    recently_worn_lines = [f"ID {item['id']} | {item['name']}" for item in recently_worn]

    user_prompt = f"""Build an outfit for: {occasion}{(' in ' + weather) if weather else ''}.
{('Extra notes: ' + extra_notes) if extra_notes else ''}

AVAILABLE WARDROBE (do not use recently worn items):
{chr(10).join(wardrobe_lines) if wardrobe_lines else 'No available items.'}

RECENTLY WORN (avoid these — worn in last 3 days):
{chr(10).join(recently_worn_lines) if recently_worn_lines else 'None.'}

Return a JSON object with:
- outfit: list of item IDs that make the outfit (integers)
- explanation: why this combination works for the occasion and the user's coloring/style
- styling_tips: 2-3 practical tips on how to wear it (e.g. tuck/untuck, roll sleeves, accessorize)

Return ONLY valid JSON, no markdown fences."""

    response = client.messages.create(
        model=MODEL,
        max_tokens=1024,
        system=[
            {
                "type": "text",
                "text": profile_text,
                "cache_control": {"type": "ephemeral"},
            }
        ],
        messages=[{"role": "user", "content": user_prompt}],
    )

    raw = response.content[0].text.strip()
    if raw.startswith("```"):
        raw = raw.split("```")[1]
        if raw.startswith("json"):
            raw = raw[4:]
    return json.loads(raw.strip())


def _build_profile_text(profile: dict) -> str:
    if not profile:
        return (
            "You are a personal stylist AI. Help the user build stylish outfits from their wardrobe. "
            "Apply color theory and general style principles."
        )

    parts = [
        "You are a personal stylist AI with deep knowledge of this specific user's style profile.\n"
    ]

    if profile.get("color_season"):
        parts.append(f"Color Season: {profile['color_season']}")
    if profile.get("skin_tone"):
        parts.append(f"Skin Tone: {profile['skin_tone']}")
    if profile.get("best_colors"):
        parts.append(f"Best Colors for Them: {profile['best_colors']}")
    if profile.get("avoid_colors"):
        parts.append(f"Colors to Avoid: {profile['avoid_colors']}")
    if profile.get("style_vibe"):
        parts.append(f"Style Vibe: {profile['style_vibe']}")
    if profile.get("fit_preference"):
        parts.append(f"Fit Preference: {profile['fit_preference']}")
    if profile.get("lifestyle"):
        parts.append(f"Lifestyle / Occasions: {profile['lifestyle']}")
    if profile.get("notes"):
        parts.append(f"Additional Notes: {profile['notes']}")

    parts.append(
        "\nUse this profile to tailor every outfit suggestion. Prioritize colors that complement "
        "the user's coloring, respect their style vibe, and avoid colors/styles they dislike."
    )
    return "\n".join(parts)
