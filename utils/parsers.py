# utils/parsers.py
import re

def maybe_parse_tick(line: str):
    """
    Try to extract MSPT (milliseconds per tick) from a variety of sources:
      - 'Average tick time: 0.502 ms'
      - 'mean tick time: 10.3 ms'
      - 'tick time: 7.1 ms' / 'tick duration: 7.1 ms'
      - 'MSPT: 12.7'
      - Spark-ish lines containing 'spark' and a '... ms' value
    Returns float(ms) or None if not found.
    """
    s = line.strip()
    low = s.lower()

    # 1) Explicit MSPT label (may not include 'ms' unit)
    m = re.search(r"\bmspt\b[^\d]*([0-9]+(?:\.[0-9]+)?)", low)
    if m:
        try:
            return float(m.group(1))
        except ValueError:
            return None

    # 2) Average/mean tick time ... ms
    m = re.search(r"(?:average|mean)\s+tick\s+time[^\d]*([0-9]+(?:\.[0-9]+)?)\s*ms", low)
    if m:
        try:
            return float(m.group(1))
        except ValueError:
            return None

    # 3) Tick time/duration ... ms
    m = re.search(r"tick\s+(?:duration|time|times?)[^\d]*([0-9]+(?:\.[0-9]+)?)\s*ms", low)
    if m:
        try:
            return float(m.group(1))
        except ValueError:
            return None

    # 4) Spark-style: any line containing 'spark' and a '... ms' number
    if "spark" in low:
        m = re.search(r"([0-9]+(?:\.[0-9]+)?)\s*ms", low)
        if m:
            try:
                return float(m.group(1))
            except ValueError:
                return None

    # 5) Legacy exact string (kept for completeness)
    m = re.search(r"Average tick time:\s*([0-9.]+)\s*ms", s, flags=re.IGNORECASE)
    if m:
        try:
            return float(m.group(1))
        except ValueError:
            return None

    return None


def parse_online_counts(line: str):
    """
    Parse lines like:
      'There are X of a max of Y players online: ...'
      'There are 0 of a max of Y players online'
    Returns (current, max) as ints, or None if no match.
    """
    m = re.search(
        r"There are\s+(\d+)\s+of a max of\s+(\d+)\s+players online",
        line,
        flags=re.IGNORECASE,
    )
    if m:
        return int(m.group(1)), int(m.group(2))
    return None


def maybe_parse_players(line: str, current_players: set[str]) -> set[str] | None:
    """
    Update players set from:
      - '[INFO]: There are X of a max of Y players online: name1, name2'
      - '[INFO]: There are 0 of a max of Y players online'
      - '] <Player> joined the game' / '] <Player> left the game'
    Returns a NEW set if changed, else None.
    """
    updated = False
    players = set(current_players)
    low = line.lower()

    if "players online" in low:
        try:
            marker = low.rfind("players online:")
            if marker != -1:
                names_segment = line[marker + len("players online:"):].strip()
            else:
                names_segment = ""  # case with 0 players, no trailing colon
            names = [n.strip() for n in names_segment.split(",") if n.strip()]
            new_set = set(names)
            if new_set != players:
                players = new_set
                updated = True
        except Exception:
            pass

    m = re.search(r"]:\s*([A-Za-z0-9_]{1,16})\s+(joined|left) the game", line)
    if m:
        pname, action = m.group(1), m.group(2)
        if action == "joined" and pname not in players:
            players.add(pname); updated = True
        if action == "left" and pname in players:
            players.discard(pname); updated = True

    return players if updated else None
