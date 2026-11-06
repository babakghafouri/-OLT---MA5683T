"""Conservative parsing of read-only Huawei ONT detail output.

Only fields explicitly present in CLI key/value output are returned. Unknown
firmware-specific fields remain available in the raw CLI response.
"""
import re


def _key(value):
    return re.sub(r"[^a-z0-9]", "", str(value).lower())


def parse_cli_properties(raw):
    """Extract simple 'Label : Value' lines without interpreting table rows."""
    result = []
    if not isinstance(raw, str):
        return result
    for line in raw.splitlines():
        if ":" not in line:
            continue
        label, value = line.split(":", 1)
        label, value = label.strip(), value.strip()
        if not label or not value or len(label) > 72:
            continue
        key = _key(label)
        if key in {"command", "error", "failure"} or "password" in key:
            continue
        result.append({"key": key, "label": label, "value": value})
    return result


ALIASES = {
    "serial_number": ("ontsn", "serialnumber", "sn"),
    "model": ("ontequipmentid", "equipmentid", "ontmodel", "model"),
    "description": ("description", "desc"),
    "distance_m": ("ontdistancem", "distancem", "ontdistance", "distance"),
    "last_up_time": ("lastuptime", "lastup"),
    "last_down_time": ("lastdowntime", "lastdown"),
    "last_down_cause": ("lastdowncause", "downcause"),
    "online_duration": ("ontonlineduration", "onlineduration", "onlineworkingtime"),
    "line_profile_id": ("ontlineprofileid", "lineprofileid"),
    "service_profile_id": ("ontsrvprofileid", "ontserviceprofileid", "serviceprofileid"),
    "control_state": ("controlflag", "controlstate"),
    "run_state": ("runstate",),
    "config_state": ("configstate",),
    "match_state": ("matchstate",),
    "rx_power_dbm": ("rxopticalpowerdbm", "ontrxopticalpowerdbm", "rxpowerdbm"),
    "tx_power_dbm": ("txopticalpowerdbm", "onttxopticalpowerdbm", "txpowerdbm"),
    "olt_rx_power_dbm": ("oltrxontopticalpowerdbm", "oltrxopticalpowerdbm", "oltrxpowerdbm"),
    "olt_tx_power_dbm": ("olttxontopticalpowerdbm", "olttxopticalpowerdbm", "olttxpowerdbm"),
    "temperature_c": ("temperaturec", "onttemperaturec"),
    "voltage_v": ("voltagev",),
    "bias_current_ma": ("biascurrentma",),
}


def parse_ont_details(info_raw, optical_raw):
    """Return normalized fields plus safe generic properties from OLT output."""
    info = parse_cli_properties(info_raw)
    optical = parse_cli_properties(optical_raw)
    info_map = {item["key"]: item["value"] for item in info}
    optical_map = {item["key"]: item["value"] for item in optical}

    fields = {}
    for name, aliases in ALIASES.items():
        sources = (optical_map, info_map) if name.endswith("_power_dbm") or name in {
            "temperature_c", "voltage_v", "bias_current_ma"
        } else (info_map, optical_map)
        value = next((source[key] for source in sources for key in aliases if source.get(key)), None)
        fields[name] = value

    return {
        **fields,
        "info_properties": info,
        "optical_properties": optical,
    }
