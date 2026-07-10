from datetime import datetime, date

AGING_LABELS = {
    '0-3': '0–3 Days',
    '4-7': '4–7 Days',
    '8-15': '8–15 Days',
    '15plus': '15+ Days',
}


def parse_aging_filter(args):
    """Read the ?aging= query param. Returns (aging_filter, aging_label) or (None, "")."""
    aging_filter = args.get('aging')
    if aging_filter in AGING_LABELS:
        return aging_filter, AGING_LABELS[aging_filter]
    return None, ""


def filter_by_aging(items, aging_filter, date_key):
    """Keep only items whose date_key falls in the given aging bucket (days since today)."""
    if not aging_filter:
        return items

    today = date.today()
    filtered = []
    for item in items:
        raw = item.get(date_key)
        if not raw:
            continue
        try:
            item_date = datetime.strptime(str(raw)[:19], "%Y-%m-%d %H:%M:%S").date()
        except Exception:
            try:
                item_date = datetime.strptime(str(raw)[:10], "%Y-%m-%d").date()
            except Exception:
                continue

        diff_days = (today - item_date).days
        if aging_filter == '0-3' and diff_days <= 3:
            filtered.append(item)
        elif aging_filter == '4-7' and 4 <= diff_days <= 7:
            filtered.append(item)
        elif aging_filter == '8-15' and 8 <= diff_days <= 15:
            filtered.append(item)
        elif aging_filter == '15plus' and diff_days > 15:
            filtered.append(item)
    return filtered
