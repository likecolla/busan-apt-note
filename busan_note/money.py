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


def pyeong_type(area):
    """전용면적 ㎡ → 흔히 부르는 평형(공급면적 기준). 59·84㎡는 관례값, 나머지는 전용률 약 75%로 어림."""
    if area is None:
        return ""
    if 57 <= area < 61:
        return "25평형"
    if 83 <= area < 86:
        return "34평형"
    return f"약 {round(area * 1.33 / 3.3058)}평형"
