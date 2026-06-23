#!/usr/bin/env python3
"""
Optimize form inputs for tablet use.

Adds `inputmode` and `pattern` attributes to <input type="number"> elements
that don't already have `inputmode`. Handles multi-line tags and JS strings.
"""
import re

# ---- Classification helpers ----
DECIMAL_IDS = [
    'price', 'Price', 'PayRate', 'payRate', 'taxItem', 'Tip', 'TipAmount',
    'tipAmount', 'cash', 'Cash', 'amount', 'Amount', 'comboPrice',
    'discountValue', 'discountMinOrder', 'pricingDiscount', 'scPercentage',
    'catRate', 'price_mod', 'OpeningBalance', 'CashTendered', 'checkoutTip',
    'customTip', 'kioskCustomTip', 'globalTaxRate', 'taxItemRate',
]
INTEGER_IDS = [
    'tableNum', 'UsageLimit', 'wasteQuantity', 'emailPort', 'adDuration',
    'adRotation', 'scThreshold', 'comboChildQty', 'lateFlag', 'loyaltyAdj',
    'tsConfig', 'DailyOT', 'WeeklyOT', 'LateGrace', 'invStock', 'invThresh',
]


def classify_input(tag_text):
    """Return 'decimal' or 'numeric' for the given input tag content."""
    # Normalize quotes for JS escaped strings
    text = tag_text.replace('\\"', '"')
    # Check integer patterns
    for kw in INTEGER_IDS:
        if f'id="{kw}' in text or f'id= \\"{kw}' in text:
            return 'numeric'
    # Check decimal patterns
    for kw in DECIMAL_IDS:
        if f'id="{kw}' in text or f'id= \\"{kw}' in text:
            return 'decimal'
    # step="0." → decimal
    if 'step="0.' in text:
        return 'decimal'
    # placeholder hints
    if re.search(r'placeholder="[^"]*[\$%]', text):
        return 'decimal'
    return 'numeric'


def add_attr(tag, attrs):
    """Insert attrs before the closing > of a tag (multi-line safe)."""
    # Handle self-closing tags: insert before />
    stripped = tag.rstrip()
    if stripped.endswith('/>'):
        idx = len(tag) - len(stripped) + stripped.rindex('/>')
        return tag[:idx] + ' ' + attrs + ' ' + tag[idx:]
    # Regular tag: insert before >
    last_gt = stripped.rindex('>')
    return tag[:last_gt] + ' ' + attrs + ' ' + tag[last_gt:]


def main():
    path = '/root/pos-system-work/index.html'
    with open(path, 'r', encoding='utf-8') as f:
        content = f.read()

    # ----- Static HTML: <input ... type="number" ... > -----
    # Match an <input tag that contains type="number".
    # Use [^>]*? would NOT match newlines, so we use [\s\S]*? for within-attribute.
    # Actually, we need to match from <input to the closing >.
    # The simplest approach: match <input ... type="number" ... >
    # We can use re.DOTALL and a pattern that matches the full tag.
    pattern = re.compile(
        r'(<input\s[\s\S]*?type="number"[\s\S]*?>)',
        re.IGNORECASE
    )

    def repl_html(m):
        tag = m.group(1)
        if 'inputmode' in tag:
            return tag
        mode = classify_input(tag)
        return add_attr(tag, f'inputmode="{mode}" pattern="[0-9]*"')

    content = pattern.sub(repl_html, content)

    # ----- Dynamic JS: <input ... type=\"number\" ... > -----
    pattern_js = re.compile(
        r'(<input\s[\s\S]*?type=\\"number\\"[\s\S]*?>)',
        re.IGNORECASE
    )

    def repl_js(m):
        tag = m.group(1)
        if 'inputmode' in tag:
            return tag
        mode = classify_input(tag)
        return add_attr(tag, f'inputmode=\\"{mode}\\" pattern=\\"[0-9]*\\"')

    content = pattern_js.sub(repl_js, content)

    # ----- addUserId PIN input - add autocomplete="off" -----
    content = re.sub(
        r'(<input[\s\S]*?id="addUserId"[\s\S]*?)(\s*>)',
        lambda m: m.group(1) + ' autocomplete="off"' + m.group(2) if 'autocomplete' not in m.group(1) else m.group(0),
        content
    )

    # Write changes
    with open(path, 'w', encoding='utf-8') as f:
        f.write(content)

    print(f"Done. Written to {path}")

if __name__ == '__main__':
    main()
