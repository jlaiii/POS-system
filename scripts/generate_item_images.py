#!/usr/bin/env python3
"""Generate SVG placeholder images for all menu items."""
import os
import json

ITEMS_FILE = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'items.json')
OUTPUT_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'static', 'images')

# Item configurations: emoji, gradient colors, description, dietary tags
ITEM_CONFIG = {
    "Foods": {
        "Hamburger - Normal": {
            "emoji": "🍔", "gradient": ("#c0392b", "#e74c3c"),
            "description": "Juicy quarter-pound beef patty with crisp lettuce, ripe tomato, and fresh onion on a toasted sesame seed bun.",
            "dietary_tags": []
        },
        "Hamburger - All the Fixings": {
            "emoji": "🍔", "gradient": ("#a93226", "#e74c3c"),
            "description": "Fully loaded quarter-pound burger with melted cheddar, crispy bacon, lettuce, tomato, pickles, and grilled onions.",
            "dietary_tags": []
        },
        "Hotdog - Loaded": {
            "emoji": "🌭", "gradient": ("#d35400", "#e67e22"),
            "description": "All-beef frankfurter piled high with spicy chili, shredded cheddar cheese, diced onions, and pickled jalapeños.",
            "dietary_tags": ["spicy"]
        },
        "Hotdog - Plain": {
            "emoji": "🌭", "gradient": ("#e67e22", "#f39c12"),
            "description": "Classic all-beef frankfurter served in a warm, steamed poppy seed bun. Simple and satisfying.",
            "dietary_tags": []
        },
        "Taco - Beef & Cheese": {
            "emoji": "🌮", "gradient": ("#b03a2e", "#d35400"),
            "description": "Crispy corn shell filled with seasoned ground beef, melted cheddar, shredded lettuce, and diced tomatoes.",
            "dietary_tags": ["gluten_free"]
        },
        "Taco - Chicken with Salsa": {
            "emoji": "🌮", "gradient": ("#ba4a00", "#e67e22"),
            "description": "Soft flour tortilla loaded with seasoned shredded chicken, fresh pico de gallo, sour cream, and sliced avocado.",
            "dietary_tags": []
        }
    },
    "Drinks": {
        "Lemonade": {
            "emoji": "🍋", "gradient": ("#f1c40f", "#f39c12"),
            "description": "Refreshing freshly squeezed lemonade made with real lemons and a touch of cane sugar. Served over ice.",
            "dietary_tags": ["vegan", "gluten_free", "vegetarian"]
        },
        "Coke": {
            "emoji": "🥤", "gradient": ("#c0392b", "#e74c3c"),
            "description": "Ice-cold Coca-Cola served in a chilled fountain cup or classic glass bottle. The real thing.",
            "dietary_tags": ["vegan", "gluten_free"]
        },
        "Water Bottle": {
            "emoji": "💧", "gradient": ("#2980b9", "#3498db"),
            "description": "Pure natural spring water sourced from mountain aquifers. 16 oz bottle, perfectly chilled.",
            "dietary_tags": ["vegan", "gluten_free", "vegetarian", "low_carb", "sugar_free"]
        }
    },
    "Snacks": {
        "Raspia (Fruit Slush)": {
            "emoji": "🍧", "gradient": ("#8e44ad", "#9b59b6"),
            "description": "Refreshing frozen fruit slushie blended with real raspberry, mango, and passionfruit purée. A customer favorite!",
            "dietary_tags": ["vegan", "gluten_free", "vegetarian"]
        },
        "Chips (Large Bag)": {
            "emoji": "🥔", "gradient": ("#f39c12", "#f1c40f"),
            "description": "Generous share-size bag of golden, crispy potato chips. Lightly salted and cooked to perfection.",
            "dietary_tags": ["vegan", "gluten_free", "vegetarian"]
        },
        "Chocolate Bar": {
            "emoji": "🍫", "gradient": ("#5d4037", "#795548"),
            "description": "Rich and creamy milk chocolate bar made with premium Belgian cocoa. The perfect sweet treat.",
            "dietary_tags": ["vegetarian"]
        },
        "Mixed Nuts (Small Pack)": {
            "emoji": "🥜", "gradient": ("#a1887f", "#8d6e63"),
            "description": "Roasted and salted premium mixed nuts: almonds, cashews, pecans, and peanuts. Protein-packed snack.",
            "dietary_tags": ["vegan", "gluten_free", "vegetarian", "low_carb"]
        },
        "Granola Bar": {
            "emoji": "🌾", "gradient": ("#f57f17", "#fbc02d"),
            "description": "Hearty oats-and-honey granola bar with dried cranberries and pumpkin seeds. Great for a quick energy boost.",
            "dietary_tags": ["vegetarian"]
        }
    }
}

def generate_svg(name, emoji, color1, color2):
    """Generate an attractive SVG placeholder image."""
    # Clean name for filename
    clean = name.lower().replace(" - ", "-").replace(" ", "-").replace("(", "").replace(")", "").replace("'", "")
    # Slugify
    return f'''<svg xmlns="http://www.w3.org/2000/svg" width="400" height="300" viewBox="0 0 400 300">
  <defs>
    <linearGradient id="bg" x1="0%" y1="0%" x2="100%" y2="100%">
      <stop offset="0%" style="stop-color:{color1};stop-opacity:1" />
      <stop offset="100%" style="stop-color:{color2};stop-opacity:1" />
    </linearGradient>
    <filter id="shadow" x="-10%" y="-10%" width="120%" height="120%">
      <feDropShadow dx="0" dy="2" stdDeviation="4" flood-opacity="0.3"/>
    </filter>
  </defs>
  <rect width="400" height="300" rx="16" fill="url(#bg)"/>
  <text x="200" y="80" text-anchor="middle" font-size="80" filter="url(#shadow)">{emoji}</text>
  <text x="200" y="170" text-anchor="middle" font-family="system-ui, sans-serif" font-size="20" font-weight="bold" fill="white" letter-spacing="0.5">{name}</text>
  <line x1="120" y1="195" x2="280" y2="195" stroke="rgba(255,255,255,0.3)" stroke-width="1"/>
  <text x="200" y="230" text-anchor="middle" font-family="system-ui, sans-serif" font-size="14" fill="rgba(255,255,255,0.7)">Tap to view details</text>
  <rect x="140" y="252" width="120" height="30" rx="15" fill="rgba(255,255,255,0.2)"/>
  <text x="200" y="272" text-anchor="middle" font-family="system-ui, sans-serif" font-size="12" font-weight="bold" fill="white">🍽️ Menu Item</text>
</svg>'''

def main():
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    
    # Load current items.json
    with open(ITEMS_FILE, 'r') as f:
        data = json.load(f)
    
    # Generate SVGs and update data
    slug_map = {}
    for category, items in ITEM_CONFIG.items():
        for name, cfg in items.items():
            clean = name.lower().replace(" - ", "-").replace(" ", "-").replace("(", "").replace(")", "").replace("'", "")
            filename = f"{clean}.svg"
            svg_content = generate_svg(name, cfg["emoji"], cfg["gradient"][0], cfg["gradient"][1])
            
            filepath = os.path.join(OUTPUT_DIR, filename)
            with open(filepath, 'w') as f:
                f.write(svg_content)
            print(f"Created {filepath}")
            
            slug_map[name] = f"static/images/{filename}"
    
    # Update items.json
    for category, cat_items in data.items():
        if category in ITEM_CONFIG:
            for item in cat_items:
                name = item["name"]
                if name in ITEM_CONFIG.get(category, {}):
                    cfg = ITEM_CONFIG[category][name]
                    item["description"] = cfg["description"]
                    item["image_url"] = slug_map[name]
                    item["dietary_tags"] = cfg["dietary_tags"]
                else:
                    # Items not in our config get empty defaults
                    if "description" not in item:
                        item["description"] = ""
                    if "image_url" not in item:
                        item["image_url"] = ""
                    if "dietary_tags" not in item:
                        item["dietary_tags"] = []
    
    # Write back
    with open(ITEMS_FILE, 'w') as f:
        json.dump(data, f, indent=4)
    
    print(f"\nUpdated {ITEMS_FILE} with {len(slug_map)} items.")

if __name__ == '__main__':
    main()
