"""Read-only MA5683T chassis inventory parsing.

Never infer installed boards from the chassis profile or a sample screenshot.
Unknown and unparsed slots are explicitly reported as unknown.
"""
import re

SLOT_COUNT = 13
BOARD_LINE = re.compile(r"^\s*(\d{1,2})\s+(H\d{3}[A-Z0-9-]+)\s+(\S+)", re.I)
EMPTY_WORDS = {"empty", "absent", "none", "offline", "not-installed"}

def parse_chassis_inventory(raw):
    """Parse 'display board 0' into a conservative slot map.

    Returns 13 slots, with unknown state until a recognizable live row exists.
    Unrecognized lines are retained for diagnostics; they never imply a board.
    """
    slots = [{"slot": i, "board": None, "state": "unknown", "status": None}
             for i in range(SLOT_COUNT)]
    if not isinstance(raw, str):
        return {"slots": slots, "recognized": 0, "unparsed": []}
    unparsed = []
    recognized = 0
    for line in raw.splitlines():
        m = BOARD_LINE.match(line)
        if m:
            number = int(m.group(1))
            if 0 <= number < SLOT_COUNT:
                slots[number] = {"slot": number, "board": m.group(2).upper(),
                                 "state": "installed", "status": m.group(3)}
                recognized += 1
            else:
                unparsed.append(line)
            continue
        # Explicit empty rows only; don't infer emptiness from missing rows.
        empty = re.match(r"^\s*(\d{1,2})(?:\s+(?:empty|absent|none|not-installed))?\s*$", line, re.I)
        if empty and int(empty.group(1)) < SLOT_COUNT:
            n = int(empty.group(1))
            slots[n]["state"] = "empty"
            recognized += 1
        elif re.match(r"^\s*\d{1,2}\s+", line):
            unparsed.append(line)
    return {"slots": slots, "recognized": recognized, "unparsed": unparsed}

def parse_board_ports(raw, slot):
    """Extract only explicit F/S/P port identifiers for a specific frame/slot."""
    if not isinstance(raw, str):
        return []
    prefix = f"0/{int(slot)}/"
    found = set()
    for match in re.finditer(r"(?<![\d/])0/(\d{1,2})/(\d{1,2})(?![\d/])", raw):
        if int(match.group(1)) == int(slot):
            found.add(prefix + match.group(2))
    return sorted(found, key=lambda value: int(value.rsplit("/", 1)[1]))

