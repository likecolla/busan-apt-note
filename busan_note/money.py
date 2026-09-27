"""금액 표기: 1,080,000,000원 (10억 8,000만)"""


def korean_unit(won):
    """원 → '10억 8,000만' 형식(만 원 미만은 반올림)."""
    man = (int(won) + 5000) // 10000  # 사사오입
    eok, rest = divmod(man, 10000)
    parts = []
    if eok:
        parts.append(f"{eok:,}억")
    if rest:
        parts.append(f"{rest:,}만")
    return " ".join(parts) if parts else "0"


def format_won(won):
    if won is None:
        return "-"
    won = int(round(won))
    return f"{won:,}원 ({korean_unit(won)})"
