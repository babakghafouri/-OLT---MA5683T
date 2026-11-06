"""Read-only parsing of Huawei MA5683T ONT CLI output.

The parser preserves reported values, flags suspicious epoch-like connection
timestamps, and never treats unavailable firmware fields as measured values.
"""
import re
from datetime import datetime


def _key(value):
    return re.sub(r"[^a-z0-9]", "", str(value).lower())


def parse_cli_properties(raw):
    """Extract simple 'Label : Value' rows; keep source labels and values."""
    result = []
    if not isinstance(raw, str):
        return result
    for line in raw.splitlines():
        if ":" not in line:
            continue
        label, value = line.split(":", 1)
        label, value = label.strip(), value.strip()
        if not label or not value or len(label) > 96:
            continue
        key = _key(label)
        if key in {"command", "error", "failure"} or "password" in key or "secret" in key:
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
    "line_profile_name": ("ontlineprofilename", "lineprofilename"),
    "service_profile_id": ("ontsrvprofileid", "ontserviceprofileid", "serviceprofileid"),
    "service_profile_name": ("ontsrvprofilename", "ontserviceprofilename", "serviceprofilename"),
    "control_state": ("controlflag", "controlstate"),
    "run_state": ("runstate",),
    "config_state": ("configstate",),
    "match_state": ("matchstate",),
    "dba_type": ("dbatype",),
    "memory_occupation": ("memoryoccupation",),
    "cpu_occupation": ("cpuoccupation",),
    "temperature_c": ("temperaturec", "onttemperaturec", "temperature"),
    "authentic_type": ("authentictype", "authenticationtype"),
    "management_mode": ("managementmode",),
    "software_work_mode": ("softwareworkmode",),
    "isolation_state": ("isolationstate",),
    "ont_ip": ("ontip0addressmask", "ontipaddressmask"),
    "rx_power_dbm": ("rxopticalpowerdbm", "ontrxopticalpowerdbm", "rxpowerdbm"),
    "tx_power_dbm": ("txopticalpowerdbm", "onttxopticalpowerdbm", "txpowerdbm"),
    "olt_rx_power_dbm": ("oltrxontopticalpowerdbm", "oltrxopticalpowerdbm", "oltrxpowerdbm"),
    "olt_tx_power_dbm": ("olttxontopticalpowerdbm", "olttxopticalpowerdbm", "olttxpowerdbm"),
    "catv_rx_power_dbm": ("catvrxopticalpowerdbm",),
    "module_type": ("moduletype",),
    "module_subtype": ("modulesubtype",),
    "used_type": ("usedtype",),
    "encapsulation_type": ("encapsulationtype",),
    "vendor_name": ("vendorname",),
    "vendor_rev": ("vendorrev",),
    "vendor_pn": ("vendorpn",),
    "vendor_sn": ("vendorsn",),
    "date_code": ("datecode",),
    "optical_power_precision_dbm": ("opticalpowerprecisiondbm",),
    "rx_warning_threshold_dbm": ("rxpowercurrentwarningthresholddbm",),
    "rx_alarm_threshold_dbm": ("rxpowercurrentalarmthresholddbm",),
    "tx_warning_threshold_dbm": ("txpowercurrentwarningthresholddbm",),
    "tx_alarm_threshold_dbm": ("txpowercurrentalarmthresholddbm",),
    "laser_bias_current_ma": ("laserbiascurrentma", "biascurrentma"),
    "temperature_warning_threshold_c": ("temperaturewarningthresholdc",),
    "temperature_alarm_threshold_c": ("temperaturealarmthresholdc",),
    "voltage_v": ("voltagev",),
    "voltage_warning_threshold_v": ("supplyvoltagewarningthresholdv",),
    "voltage_alarm_threshold_v": ("supplyvoltagealarmthresholdv",),
    "olt_rx_warning_threshold_dbm": ("oltrxpowerwarningthresholddbm",),
    "olt_rx_alarm_threshold_dbm": ("oltrxpoweralarmthresholddbm",),
}


def parse_service_ports(raw):
    """Parse Huawei Switch-Oriented Flow List rows without guessing columns."""
    rows = []
    if not isinstance(raw, str):
        return rows
    pattern = re.compile(
        r"^\s*(\d+)\s+(\d+)\s+(\S+)\s+(gpon|epon)\s+"
        r"(\d+)\s*/\s*(\d+)\s*/\s*(\d+)\s+"
        r"(\d+)\s+(\d+)\s+(\S+)\s+(\S+)\s+(\S+)\s+(\S+)\s+(\S+)\s*$",
        re.I,
    )
    for line in raw.splitlines():
        match = pattern.match(line)
        if not match:
            continue
        (index, vlan_id, vlan_attr, port_type, frame, slot, port,
         vpi, vci, flow_type, flow_para, rx, tx, state) = match.groups()
        rows.append({
            "index": index, "vlan_id": vlan_id, "vlan_attr": vlan_attr,
            "port_type": port_type.upper(),
            "fsp": f"{frame}/{slot}/{port}", "ont_id": vpi, "gem_id": vci,
            "flow_type": flow_type, "flow_parameter": flow_para,
            "rx": rx, "tx": tx, "state": state,
        })
    return rows


def _connection_time_is_reliable(last_up_time, online_duration):
    """Reject known epoch-like timestamps and implausibly long ONT sessions."""
    if not last_up_time:
        return False
    try:
        stamp = datetime.fromisoformat(last_up_time.replace("Z", "+00:00"))
    except (TypeError, ValueError):
        return False
    if stamp.year < 2010:
        return False
    if online_duration:
        match = re.search(r"(\d+)\s*day", online_duration, re.I)
        if match and int(match.group(1)) > 3650:
            return False
    return True


def parse_ont_details(info_raw, optical_raw, service_ports_raw=""):
    """Return normalized fields plus source-labelled CLI properties."""
    info = parse_cli_properties(info_raw)
    optical = parse_cli_properties(optical_raw)
    info_map = {item["key"]: item["value"] for item in info}
    optical_map = {item["key"]: item["value"] for item in optical}

    fields = {}
    for name, aliases in ALIASES.items():
        optical_first = (
            name.endswith("_power_dbm")
            or name.endswith("_threshold_dbm")
            or name.endswith("_threshold_c")
            or name.endswith("_threshold_v")
            or name in {
                "module_type", "module_subtype", "used_type", "encapsulation_type",
                "vendor_name", "vendor_rev", "vendor_pn", "vendor_sn", "date_code",
                "optical_power_precision_dbm", "laser_bias_current_ma", "voltage_v",
            }
        )
        sources = (optical_map, info_map) if optical_first else (info_map, optical_map)
        value = next((source[key] for source in sources for key in aliases if source.get(key)), None)
        fields[name] = value

    reliable = _connection_time_is_reliable(fields["last_up_time"], fields["online_duration"])
    service_rows = parse_service_ports(service_ports_raw)
    return {
        **fields,
        "connection_timing_valid": reliable,
        "connection_timing_note": (
            "زمان اتصال در خروجی OLT معتبر به نظر می‌رسد."
            if reliable else
            "زمان اتصال قابل اتکا نیست؛ Last Up با سال 2000 گزارش شده یا مقدار زمانی معتبر وجود ندارد."
        ),
        "service_port_rows": service_rows,
        "service_port_count": len(service_rows),
        "info_properties": info,
        "optical_properties": optical,
    }
