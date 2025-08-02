def is_markdown(text: str) -> bool:
    # Returns True if text contains 4+ markdown patterns at line beginnings
    if not text: return False
    patterns = ['#', '##', '###', '- ', '* ', '> ', '```', '`', '---', '***']
    score = 0
    for line in text.split('\n'):
        s = line.strip()
        if not s: continue
        if any(s.startswith(p) for p in patterns) or (s[0].isdigit() and '. ' in s[:3]):
            score += 1
            if score >= 4: return True
    return score >= 4
