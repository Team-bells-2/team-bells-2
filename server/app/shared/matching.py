def match_key(text: str) -> str:
    """How item and unit names are compared (FR-S25, decision D6): case, extra spaces and a
    plural ending on the last word are ignored, so "Rices" = "rice", "bags" = "bag",
    "tomatoes" = "tomato". Different names ("palm oil" vs "oil") are left to the ledger's model match
    against the trader's inventory (LedgerOrchestrator._match_item)."""
    words = text.casefold().split()
    if not words:
        return ""
    last = words[-1]
    if last.endswith("oes") and len(last) > 4:
        last = last[:-2]
    elif last.endswith("s") and not last.endswith("ss") and len(last) > 3:
        last = last[:-1]
    return " ".join([*words[:-1], last])
