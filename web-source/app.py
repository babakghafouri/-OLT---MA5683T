#!/usr/bin/env python3
"""
OLT Web Panel
پنل وب برای ثبت ONT روی OLTهای هواوی (سری MA56xx / MA58xx) از طریق SSH یا Telnet.

اجرا:  python app.py     سپس باز کردن  http://127.0.0.1:8080
"""
import json
import os
import re
import secrets
import socket
import threading
import time
from functools import wraps
from pathlib import Path

from flask import Flask, jsonify, request, session

BASE = Path(__file__).parent
app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY") or secrets.token_hex(16)
UI_PASSWORD = os.environ.get("UI_PASSWORD", "")

ANSI = re.compile(r"\x1b\[[0-9;?]*[A-Za-z]")
MORE = re.compile(r"-{2,}\s*More.*?-{2,}", re.I)
PROMPT = re.compile(r"^[\w.\-]+(?:\([\w\-/.]+\))?[>#]\s*$")
ENTER_PROMPT = re.compile(r"\}\s*:\s*$")
ERR = re.compile(
    r"(Failure|Parameter error|Unknown command|Incomplete command|"
    r"Too many parameters|Error:|already exist)",
    re.I,
)

SN_RE = re.compile(r"^[0-9A-Fa-f]{16}$")
DESC_RE = re.compile(r"^[A-Za-z0-9_.\-]{1,64}$")
FSP_RE = re.compile(r"^(\d{1,2})/(\d{1,2})/(\d{1,2})$")
HOST_RE = re.compile(r"^[A-Za-z0-9_.\-:]+$")


class OLTError(Exception):
    pass


def clean(text: str) -> str:
    text = ANSI.sub("", text)
    text = MORE.sub("", text)
    text = text.replace("\r", "")
    # حذف خطوط فقط-فاصله‌ای که از صفحه‌بندی (More) باقی می‌مانند
    lines = [ln.rstrip() for ln in text.split("\n")]
    return "\n".join(lines).strip("\n")


class Conn:
    """یک نشست تعاملی با CLI اولتیمیت OLT (SSH یا Telnet)."""

    def __init__(self, host, port, proto, user, password):
        self.host, self.port, self.proto = host, port, proto
        self.user, self.password = user, password
        self.client = None
        self.chan = None
        self.sock = None
        self.prompt = ""

    # ---------- انتقال ----------
    def open(self):
        if self.proto == "ssh":
            import paramiko

            self.client = paramiko.SSHClient()
            self.client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
            self.client.connect(
                self.host,
                port=self.port,
                username=self.user,
                password=self.password,
                timeout=10,
                look_for_keys=False,
                allow_agent=False,
            )
            self.chan = self.client.invoke_shell(width=250, height=500)
            self.chan.settimeout(0.5)
            self._wait_prompt(15)
        else:
            self.sock = socket.create_connection((self.host, self.port), timeout=10)
            self.sock.settimeout(0.5)
            self._login_telnet()  # بعد از ورود، پرامپت را هم دریافت می‌کند
        self.run("enable")
        self.run("config")

    def close(self):
        for obj in (self.chan, self.client, self.sock):
            try:
                if obj:
                    obj.close()
            except Exception:
                pass
        self.chan = self.client = self.sock = None

    def _send(self, text: str):
        data = text.encode()
        if self.chan:
            self.chan.send(data)
        else:
            self.sock.sendall(data)

    def _recv(self) -> str:
        try:
            if self.chan:
                raw = self.chan.recv(4096)
            else:
                raw = self.sock.recv(4096)
        except (socket.timeout, TimeoutError):
            return ""
        except OSError as e:
            raise OLTError(f"ارتباط قطع شد: {e}")
        if raw == b"" or raw is None:  # بسته شدن واقعی اتصال
            raise OLTError("ارتباط با OLT قطع شد")
        data = self._telnet_filter(raw) if self.sock else raw
        return data.decode("utf-8", "ignore")  # ممکن است فقط مذاکرهٔ Telnet باشد و خالی برگردد

    def _telnet_filter(self, data: bytes) -> bytes:
        out = bytearray()
        i = 0
        while i < len(data):
            b = data[i]
            if b == 255 and i + 1 < len(data):
                cmd = data[i + 1]
                if cmd in (251, 253) and i + 2 < len(data):  # WILL / DO
                    reply = 254 if cmd == 251 else 252  # DONT / WONT
                    try:
                        self.sock.sendall(bytes([255, reply, data[i + 2]]))
                    except OSError:
                        pass
                    i += 3
                    continue
                if cmd in (252, 254) and i + 2 < len(data):
                    i += 3
                    continue
                if cmd == 255:
                    out.append(255)
                i += 2
                continue
            out.append(b)
            i += 1
        return bytes(out)

    def _login_telnet(self):
        buf, end = "", time.time() + 20
        sent_user = sent_pw = False
        while time.time() < end:
            buf += self._recv()
            low = ANSI.sub("", buf).lower().rstrip()
            if not sent_user and re.search(r"(user ?name|login)\s*:$", low):
                self._send(self.user + "\n")
                sent_user, buf = True, ""
            elif sent_user and not sent_pw and re.search(r"pass(word)?\s*:$", low):
                self._send(self.password + "\n")
                sent_pw, buf = True, ""
            elif sent_pw:
                last = clean(buf).split("\n")[-1].strip() if buf.strip() else ""
                if PROMPT.match(last):
                    self.prompt = last
                    return
                # شکست ورود فقط وقتی است که OLT دوباره نام کاربری بخواهد
                # (بنر «User fail login information» بعد از ورود موفق هم نمایش داده می‌شود)
                if re.search(r"(user ?name|login)\s*:$", low) or "upper limit" in low:
                    raise OLTError("ورود ناموفق بود (نام کاربری/رمز رد شد یا محدودیت تعداد تلاش). پاسخ OLT: " + repr(clean(buf)[-300:]))
        raise OLTError("زمان ورود (login) به پایان رسید. آخرین خروجی: " + repr(clean(buf)[-300:]))

    def _wait_prompt(self, timeout):
        buf, end = "", time.time() + timeout
        while time.time() < end:
            chunk = self._recv()
            buf += chunk
            last = clean(buf).split("\n")[-1].strip() if buf.strip() else ""
            if not chunk and PROMPT.match(last):
                self.prompt = last
                return
        raise OLTError("پرامپت OLT دریافت نشد. آخرین خروجی دریافتی: " + repr(clean(buf)[-300:]))

    # ---------- اجرای دستور ----------
    def run(self, cmd: str, timeout: int = 30) -> str:
        self._send(cmd + "\n")
        buf = ""
        scan_more = 0
        scan_enter = 0
        end = time.time() + timeout
        while time.time() < end:
            chunk = self._recv()
            if chunk:
                buf += chunk
                if MORE.search(buf[scan_more:]):
                    self._send(" ")
                    scan_more = len(buf)
                elif ENTER_PROMPT.search(ANSI.sub("", buf[scan_enter:]).rstrip()):
                    self._send("\n")
                    scan_enter = len(buf)
                continue
            text = clean(buf)
            last = text.split("\n")[-1].strip() if text else ""
            if PROMPT.match(last):
                self.prompt = last
                lines = text.split("\n")
                if lines and cmd and cmd.strip() in lines[0]:
                    lines = lines[1:]
                return "\n".join(lines[:-1]).strip("\n")
        raise OLTError(f"پاسخ دستور «{cmd}» در زمان مقرر نرسید")

    def reset(self):
        """بازگشت از حالت interface به حالت config بعد از خطا."""
        for _ in range(3):
            if "(config-" not in self.prompt:
                break
            self.run("quit")


# ---------- مدیریت چند OLT و نشست‌های مستقل ----------
from contextvars import ContextVar
import uuid

DEVICE_FILE = Path(os.environ.get("OLT_DEVICE_FILE", str(BASE / "devices.json")))
_ACTIVE_CONN = ContextVar("active_olt_connection", default=None)
_MANAGER_LOCK = threading.RLock()


class ConnectionManager:
    def __init__(self):
        self.connections = {}
        self.locks = {}

    def get(self, device_id):
        with _MANAGER_LOCK:
            return self.connections.get(device_id)

    def add(self, device_id, conn):
        with _MANAGER_LOCK:
            previous = self.connections.get(device_id)
            if previous:
                previous.close()
            self.connections[device_id] = conn
            self.locks.setdefault(device_id, threading.RLock())

    def remove(self, device_id):
        with _MANAGER_LOCK:
            conn = self.connections.pop(device_id, None)
            self.locks.pop(device_id, None)
        if conn:
            conn.close()

    def lock_for(self, device_id):
        with _MANAGER_LOCK:
            return self.locks.setdefault(device_id, threading.RLock())


MANAGER = ConnectionManager()


class ActiveConnectionProxy:
    def _conn_or_none(self):
        conn = _ACTIVE_CONN.get()
        if conn is not None:
            return conn
        device_id = session.get("active_olt_id")
        return MANAGER.get(device_id) if device_id else None

    def _conn(self):
        conn = self._conn_or_none()
        if conn is None:
            raise OLTError("ابتدا به یک OLT متصل شوید")
        return conn

    def __bool__(self):
        return self._conn_or_none() is not None

    def __getattr__(self, name):
        return getattr(self._conn(), name)


CONN = ActiveConnectionProxy()


def load_devices():
    if not DEVICE_FILE.exists():
        return []
    try:
        data = json.loads(DEVICE_FILE.read_text("utf-8"))
        return data if isinstance(data, list) else []
    except (OSError, ValueError):
        return []


def save_devices(items):
    DEVICE_FILE.parent.mkdir(parents=True, exist_ok=True)
    tmp = DEVICE_FILE.with_suffix(".tmp")
    tmp.write_text(json.dumps(items, ensure_ascii=False, indent=2), "utf-8")
    os.chmod(tmp, 0o600)
    tmp.replace(DEVICE_FILE)
    os.chmod(DEVICE_FILE, 0o600)


def public_device(item):
    return {k: item.get(k) for k in ("id", "name", "host", "port", "proto", "credential_mode", "notes")}


def need_conn(fn):
    @wraps(fn)
    def wrapper(*a, **k):
        device_id = session.get("active_olt_id")
        conn = MANAGER.get(device_id) if device_id else None
        if conn is None:
            return jsonify(error="ابتدا به یک OLT متصل شوید"), 400
        with MANAGER.lock_for(device_id):
            token = _ACTIVE_CONN.set(conn)
            try:
                return fn(*a, **k)
            finally:
                _ACTIVE_CONN.reset(token)
    return wrapper


@app.errorhandler(Exception)
def on_error(e):
    from werkzeug.exceptions import HTTPException
    if isinstance(e, HTTPException):
        return e
    print(f"[ERROR] {request.path}: {e.__class__.__name__}: {e}", flush=True)
    device_id = session.get("active_olt_id")
    conn = MANAGER.get(device_id) if device_id else None
    if isinstance(e, OLTError) and conn is not None and "قطع" in str(e):
        MANAGER.remove(device_id)
    code = 400 if isinstance(e, (OLTError, ValueError)) else 500
    return jsonify(error=str(e) or e.__class__.__name__), code


@app.before_request
def guard():
    if not UI_PASSWORD:
        return None
    if request.path in ("/", "/api/login"):
        return None
    if not session.get("auth"):
        return jsonify(error="auth"), 401
    return None


# ---------- پارس خروجی‌ها ----------
def parse_autofind(text: str):
    items = []
    for blk in re.split(r"-{20,}", text):
        fsp = re.search(r"F/S/P\s*:\s*(\d+)/(\d+)/(\d+)", blk)
        sn = re.search(r"Ont SN\s*:\s*([0-9A-Fa-f]{16})", blk)
        if not (fsp and sn):
            continue
        model = re.search(r"Ont EquipmentID\s*:\s*(\S+)", blk)
        when = re.search(r"Ont autofind time\s*:\s*(.+)", blk)
        items.append(
            {
                "fsp": "/".join(fsp.groups()),
                "sn": sn.group(1).upper(),
                "model": model.group(1) if model else "",
                "time": when.group(1).strip() if when else "",
            }
        )
    return items


ONT_ROW = re.compile(
    r"^\s*(\d+)/\s*(\d+)/\s*(\d+)\s+(\d+)\s+([0-9A-Fa-f]{16})\s+(\S+)\s+(\S+)\s+(\S+)\s+(\S+)",
    re.M,
)


def parse_onts(text: str):
    rows = []
    for m in ONT_ROW.finditer(text):
        rows.append(
            {
                "id": int(m.group(4)),
                "sn": m.group(5).upper(),
                "control": m.group(6),
                "run": m.group(7),
                "config": m.group(8),
                "match": m.group(9),
            }
        )
    return rows


def parse_fsp(value: str):
    m = FSP_RE.match(str(value).strip())
    if not m:
        raise ValueError("فرمت F/S/P نادرست است (مثال: 0/0/2)")
    return tuple(int(x) for x in m.groups())


def load_services():
    return json.loads((BASE / "services.json").read_text("utf-8"))


def build_plan(d: dict):
    f, s, p = parse_fsp(d.get("fsp", ""))
    try:
        ont_id = int(d.get("ont_id"))
        lp = int(d.get("lineprofile", 12))
        sp = int(d.get("srvprofile", 12))
    except (TypeError, ValueError):
        raise ValueError("ONT-ID و شماره پروفایل‌ها باید عدد باشند")
    if not 0 <= ont_id <= 127:
        raise ValueError("ONT-ID باید بین 0 تا 127 باشد")
    sn = str(d.get("sn", "")).strip()
    if not SN_RE.match(sn):
        raise ValueError("Serial Number باید 16 رقم هگز باشد")
    desc = str(d.get("desc", "")).strip()
    if not DESC_RE.match(desc):
        raise ValueError("توضیح (desc) فقط حروف انگلیسی، عدد و _ . - مجاز است")

    catalog = {x["name"]: x for x in load_services()}
    chosen = d.get("services") or []
    unknown = [n for n in chosen if n not in catalog]
    if unknown:
        raise ValueError(f"سرویس ناشناخته: {unknown[0]}")
    if not chosen:
        raise ValueError("حداقل یک سرویس انتخاب کنید")

    cmds = [
        f"interface gpon {f}/{s}",
        f'ont add {p} {ont_id} sn-auth "{sn.upper()}" omci '
        f"ont-lineprofile-id {lp} ont-srvprofile-id {sp} desc \"{desc}\"",
        "quit",
    ]
    for name in chosen:
        sv = catalog[name]
        v, g = int(sv["vlan"]), int(sv["gemport"])
        cmds.append(
            f"service-port vlan {v} gpon {f}/{s}/{p} ont {ont_id} gemport {g} "
            f"multi-service user-vlan {v} tag-transform translate"
        )
    if d.get("save", True):
        cmds.append("save")
    return {"commands": cmds, "fsp": (f, s, p), "ont_id": ont_id}


def do_verify(f, s, p, ont_id):
    info = CONN.run(f"display ont info {f} {s} {p} {ont_id}")
    sps = CONN.run(f"display service-port port {f}/{s}/{p} ont {ont_id}")
    CONN.run(f"interface gpon {f}/{s}")
    try:
        optical = CONN.run(f"display ont optical-info {p} {ont_id}")
    finally:
        CONN.run("quit")

    def pick(rx):
        m = re.search(rx, info, re.I)
        return m.group(1) if m else ""

    return {
        "run_state": pick(r"Run state\s*:\s*(\S+)"),
        "config_state": pick(r"Config state\s*:\s*(\S+)"),
        "match_state": pick(r"Match state\s*:\s*(\S+)"),
        "rx_power": (re.search(r"Rx optical power\(dBm\)\s*:\s*(\S+)", optical) or [None, ""])[1],
        "info": info,
        "service_ports": sps,
        "optical": optical,
    }


# ---------- API ----------
@app.get("/")
def index():
    return (BASE / "index.html").read_text("utf-8")


@app.post("/api/login")
def api_login():
    pw = str((request.get_json(force=True) or {}).get("password", ""))
    if UI_PASSWORD and secrets.compare_digest(pw, UI_PASSWORD):
        session["auth"] = True
        return jsonify(ok=True)
    return jsonify(error="رمز اشتباه است"), 401


@app.get("/api/devices")
def api_devices():
    connected = set(MANAGER.connections)
    return jsonify(devices=[{**public_device(x), "connected": x.get("id") in connected}
                            for x in load_devices()])


@app.post("/api/devices")
def api_add_device():
    d = request.get_json(force=True) or {}
    name, host = str(d.get("name", "")).strip(), str(d.get("host", "")).strip()
    proto = str(d.get("proto", "ssh")).lower()
    if not name:
        raise ValueError("نام دستگاه الزامی است")
    if not HOST_RE.match(host):
        raise ValueError("آدرس OLT نامعتبر است")
    if proto not in ("ssh", "telnet"):
        raise ValueError("پروتکل نامعتبر است")
    port = int(d.get("port") or (22 if proto == "ssh" else 23))
    if not 1 <= port <= 65535:
        raise ValueError("پورت نامعتبر است")
    mode = d.get("credential_mode", "session")
    if mode not in ("session", "encrypted"):
        raise ValueError("حالت نگهداری رمز نامعتبر است")
    item = {"id": uuid.uuid4().hex, "name": name, "host": host, "port": port,
            "proto": proto, "credential_mode": mode, "notes": str(d.get("notes", ""))[:500]}
    if mode == "encrypted":
        key = os.environ.get("OLT_CREDENTIALS_KEY", "")
        if not key:
            raise ValueError("برای ذخیره رمز، OLT_CREDENTIALS_KEY را در محیط سرویس تنظیم کنید")
        from cryptography.fernet import Fernet
        password = str(d.get("password", ""))
        if not password:
            raise ValueError("برای ذخیره رمز، رمز عبور الزامی است")
        item["password_enc"] = Fernet(key.encode()).encrypt(password.encode()).decode()
        item["username"] = str(d.get("user", "")).strip()
    items = load_devices()
    items.append(item)
    save_devices(items)
    return jsonify(ok=True, device=public_device(item))


@app.delete("/api/devices/<device_id>")
def api_delete_device(device_id):
    items = load_devices()
    kept = [x for x in items if x.get("id") != device_id]
    if len(kept) == len(items):
        return jsonify(error="دستگاه پیدا نشد"), 404
    save_devices(kept)
    MANAGER.remove(device_id)
    if session.get("active_olt_id") == device_id:
        session.pop("active_olt_id", None)
    return jsonify(ok=True)


@app.get("/api/status")
def api_status():
    device_id = session.get("active_olt_id")
    conn = MANAGER.get(device_id) if device_id else None
    return jsonify(connected=conn is not None,
                   **({"host": conn.host, "proto": conn.proto, "prompt": conn.prompt, "device_id": device_id} if conn else {}),
                   devices=[public_device(x) for x in load_devices()])


@app.get("/api/services")
def api_services():
    return jsonify(services=load_services())


@app.post("/api/connect")
def api_connect():
    d = request.get_json(force=True) or {}
    device_id = str(d.get("device_id", "")).strip()
    saved = next((x for x in load_devices() if x.get("id") == device_id), None) if device_id else None
    if saved:
        host, proto, port = saved["host"], saved["proto"], int(saved["port"])
        user = str(d.get("user") or saved.get("username") or "").strip()
        password = str(d.get("password", ""))
        if saved.get("credential_mode") == "encrypted" and not password:
            key = os.environ.get("OLT_CREDENTIALS_KEY", "")
            if not key:
                raise ValueError("کلید رمزنگاری تنظیم نشده است")
            from cryptography.fernet import Fernet
            password = Fernet(key.encode()).decrypt(saved["password_enc"].encode()).decode()
    else:
        host, proto = str(d.get("host", "")).strip(), str(d.get("proto", "ssh")).lower()
        port = int(d.get("port") or (22 if proto == "ssh" else 23))
        user, password = str(d.get("user", "")).strip(), str(d.get("password", ""))
    if proto not in ("ssh", "telnet") or not HOST_RE.match(host) or not 1 <= port <= 65535:
        raise ValueError("مشخصات اتصال OLT نامعتبر است")
    c = Conn(host, port, proto, user, password)
    try:
        c.open()
    except Exception:
        c.close()
        raise
    if not device_id:
        device_id = "temporary-" + uuid.uuid4().hex
    MANAGER.add(device_id, c)
    session["active_olt_id"] = device_id
    return jsonify(ok=True, prompt=c.prompt, device_id=device_id)


@app.post("/api/disconnect")
def api_disconnect():
    device_id = session.get("active_olt_id")
    if device_id:
        MANAGER.remove(device_id)
    session.pop("active_olt_id", None)
    return jsonify(ok=True)


@app.get("/api/autofind")
@need_conn
def api_autofind():
    out = CONN.run("display ont autofind all", timeout=60)
    return jsonify(items=parse_autofind(out), raw=out)


@app.get("/api/port")
@need_conn
def api_port():
    f, s, p = parse_fsp(request.args.get("fsp", ""))
    out = CONN.run(f"display ont info {f} {s} {p} all", timeout=60)
    onts = parse_onts(out)
    used = {o["id"] for o in onts}
    free = next((i for i in range(128) if i not in used), None)
    return jsonify(onts=onts, next_free=free, raw=out)


@app.post("/api/plan")
def api_plan():
    plan = build_plan(request.get_json(force=True) or {})
    return jsonify(commands=plan["commands"])


@app.post("/api/apply")
@need_conn
def api_apply():
    d = request.get_json(force=True) or {}
    plan = build_plan(d)
    log, ok = [], True
    for cmd in plan["commands"]:
        out = CONN.run(cmd, timeout=60)
        bad = bool(ERR.search(out))
        log.append({"cmd": cmd, "out": out, "ok": not bad})
        if bad:
            ok = False
            CONN.reset()
            break
    result = {"ok": ok, "log": log}
    if ok:
        f, s, p = plan["fsp"]
        result["verify"] = do_verify(f, s, p, plan["ont_id"])
    return jsonify(result)


@app.get("/api/verify")
@need_conn
def api_verify():
    f, s, p = parse_fsp(request.args.get("fsp", ""))
    ont_id = int(request.args.get("ont_id", "-1"))
    if not 0 <= ont_id <= 127:
        raise ValueError("ONT-ID نامعتبر")
    return jsonify(do_verify(f, s, p, ont_id))



# ---------- Read-only operator dashboard ----------
# Supported commands differ by Huawei model and software release. Each section
# reports its raw CLI result as well as conservatively parsed fields.
OVERVIEW_COMMANDS = {
    "system": [("version", "display version"), ("uptime", "display sysuptime"), ("time", "display time")],
    "inventory": [("boards", "display board 0"), ("device", "display device")],
    "resource": [("cpu", "display resource occupancy cpu"),
                 ("memory", "display resource occupancy mem"),
                 ("message", "display resource occupancy message"),
                 ("cpu_board", "__ACTIVE_CPU__"),
                 ("temperature", "__ACTIVE_TEMP__"),
                 ("fan", "display emu")],
    "alarms": [("active", "display alarm active all")],
    "uplinks": [("slot_8", "display board 0/8"), ("slot_9", "display board 0/9")],
}

OVERVIEW_ERROR = re.compile(
    r"(?im)^\s*(?:Error:|Failure:|Unknown command|Incomplete command|"
    r"Parameter error|Unrecognized command|Too many parameters|"
    r"%\s*(?:Unknown|Incomplete|Unrecognized|Invalid|Ambiguous)\s+command)"
)

def extract_properties(raw):
    # Do not infer numeric thresholds/capacity from arbitrary CLI output.
    data = {}
    for line in raw.splitlines():
        match = re.match(r"^\s*([\w /().%+-]{3,45}?)\s*:\s*(.{1,160}?)\s*$", line)
        if match:
            key = match.group(1).strip()
            if key.lower() not in ("command", "error", "failure"):
                data[key] = match.group(2).strip()
    return data

# Static MA5683T chassis facts; board population is always live/unknown, not assumed.
MA5683T_PROFILE = {
    "model": "Huawei SmartAX MA5683T", "service_slots": 6,
    "control_slots": 2, "upstream_slots": 2,
    "power_slots": 2, "universal_slots": 1,
    "max_gpon_ports": 96,
    "note": "Maximum chassis potential, not installed equipment or actual subscriber capacity."
}

@app.get("/api/chassis-profile")
def api_chassis_profile():
    return jsonify(MA5683T_PROFILE)

@app.get("/api/overview")
@need_conn
def api_overview():
    section = request.args.get("section", "system")
    if section not in OVERVIEW_COMMANDS:
        raise ValueError("بخش درخواست‌شده نامعتبر است")
    results = []
    active_slot = None
    if section == "resource":
        # Discover the active SCUN instead of assuming slot 7 remains active after switchover.
        board_output = CONN.run("display board 0", timeout=18)
        for line in board_output.splitlines():
            match = re.match(r"^\s*(\d+)\s+H\w*SCU\w*\s+Active_normal\b", line, re.I)
            if match:
                active_slot = int(match.group(1))
                break
    for name, template in OVERVIEW_COMMANDS[section]:
        command = (f"display cpu 0/{active_slot}" if template == "__ACTIVE_CPU__" and active_slot is not None else
                   f"display temperature 0/{active_slot}" if template == "__ACTIVE_TEMP__" and active_slot is not None else template)
        if command in ("__ACTIVE_CPU__", "__ACTIVE_TEMP__"):
            results.append({"key": name, "command": "display " + ("cpu" if name == "cpu_board" else "temperature") + " 0/<active-slot>",
                            "supported": False, "error": "اسلات کنترل فعال مشخص نشد", "raw": "", "properties": {}})
            continue
        try:
            output = CONN.run(command, timeout=18)
            unsupported = bool(OVERVIEW_ERROR.search(output))
            results.append({"key": name, "command": command,
                            "supported": not unsupported,
                            "raw": output[:50000],
                            "properties": extract_properties(output) if not unsupported else {}})
        except OLTError as exc:
            # A timeout may leave the interactive CLI unsynchronized: stop here.
            results.append({"key": name, "command": command,
                            "supported": False, "error": str(exc), "raw": "", "properties": {}})
            break
    return jsonify(section=section, results=results, collected_at=int(time.time()),
                   host=CONN.host)


# ---------- Live interface traffic (read-only) ----------
# The MA5683T H801GICF uplink boards are queried in GIU view. The OLT reports
# the current upstream/downstream rate directly in kbps; the panel polls it.
TRAFFIC_INTERFACES = {
    "0/8/0": {"slot": 8, "port": 0, "board": "H801GICF"},
    "0/8/1": {"slot": 8, "port": 1, "board": "H801GICF"},
    "0/9/0": {"slot": 9, "port": 0, "board": "H801GICF"},
    "0/9/1": {"slot": 9, "port": 1, "board": "H801GICF"},
}


def parse_traffic_rates(raw: str):
    """Return (upstream_kbps, downstream_kbps) from supported Huawei CLI formats.

    On the MA5683T uplink GE interface, transmitted traffic is traffic sent
    from the OLT toward the upstream network (subscriber upstream), while
    received traffic is traffic arriving from the upstream network (subscriber
    downstream). Keep RX/TX fields explicitly named in the raw CLI output.
    """
    def find(patterns):
        for pattern in patterns:
            m = re.search(pattern, raw, re.I | re.M)
            if m:
                try:
                    return float(m.group(1).replace(',', ''))
                except (ValueError, TypeError):
                    pass
        return None

    # Native MA5683T output, e.g.:
    # The transmitted traffic of this port(kbits/s) =104325.6
    # The received traffic of this port(kbits/s) =9172.7
    transmitted = find([
        r"transmitted\s+traffic\s+of\s+this\s+port\s*\(\s*kbits?/s\s*\)\s*=\s*([\d,]+(?:\.\d+)?)",
        r"transmitted\s+traffic.*?\(\s*kbps\s*\)\s*[:=]\s*([\d,]+(?:\.\d+)?)",
    ])
    received = find([
        r"received\s+traffic\s+of\s+this\s+port\s*\(\s*kbits?/s\s*\)\s*=\s*([\d,]+(?:\.\d+)?)",
        r"received\s+traffic.*?\(\s*kbps\s*\)\s*[:=]\s*([\d,]+(?:\.\d+)?)",
    ])

    # Generic output formats retained for firmware variants that label the
    # rates directly as Up/Down rather than Received/Transmitted.
    up = find([
        r"Up\s+traffic\s*\(\s*kbps\s*\)\s*[:=]\s*([\d,]+(?:\.\d+)?)",
        r"Upstream\s+(?:traffic|rate)\s*\(?\s*k(?:bit|b)/s\s*\)?\s*[:=]\s*([\d,]+(?:\.\d+)?)",
    ])
    down = find([
        r"Down\s+traffic\s*\(\s*kbps\s*\)\s*[:=]\s*([\d,]+(?:\.\d+)?)",
        r"Downstream\s+(?:traffic|rate)\s*\(?\s*k(?:bit|b)/s\s*\)?\s*[:=]\s*([\d,]+(?:\.\d+)?)",
    ])

    if transmitted is not None and received is not None:
        return transmitted, received
    return up, down


@app.get("/api/traffic")
@need_conn
def api_traffic():
    requested = [x.strip() for x in request.args.get("interfaces", "0/8/0,0/8/1,0/9/0,0/9/1").split(',') if x.strip()]
    if not requested:
        raise ValueError("حداقل یک Interface انتخاب کنید")
    invalid = [x for x in requested if x not in TRAFFIC_INTERFACES]
    if invalid:
        raise ValueError("Interface نامعتبر است: " + invalid[0])
    requested = list(dict.fromkeys(requested))
    results = {name: {"interface": name, **TRAFFIC_INTERFACES[name], "supported": False,
                      "up_kbps": None, "down_kbps": None, "raw": "", "error": ""}
               for name in requested}

    # Query once per GIU slot, then read the selected ports in that slot.
    for slot in sorted({TRAFFIC_INTERFACES[name]["slot"] for name in requested}):
        slot_names = [name for name in requested if TRAFFIC_INTERFACES[name]["slot"] == slot]
        try:
            entered = CONN.run(f"interface giu 0/{slot}", timeout=15)
            if OVERVIEW_ERROR.search(entered) or not re.search(r"\(config-if-giu-0/" + str(slot) + r"\)", CONN.prompt, re.I):
                detail = (entered.strip() or "دستگاه وارد نمای GIU نشد")[-1200:]
                for name in slot_names:
                    results[name]["error"] = detail
                    results[name]["raw"] = entered[:5000]
                continue

            for name in slot_names:
                port = TRAFFIC_INTERFACES[name]["port"]
                command = f"display port traffic {port}"
                try:
                    output = CONN.run(command, timeout=15)
                    up, down = parse_traffic_rates(output)
                    unsupported = bool(OVERVIEW_ERROR.search(output)) or (up is None and down is None)
                    results[name].update({
                        "command": f"interface giu 0/{slot} ; {command}",
                        "supported": not unsupported,
                        "up_kbps": up,
                        "down_kbps": down,
                        "raw": output[:10000],
                        "error": ((output.strip()[-1200:] or "نرخ ترافیک در خروجی CLI قابل تشخیص نیست") if unsupported else ""),
                    })
                except OLTError as exc:
                    results[name]["error"] = str(exc)
                    break
        except OLTError as exc:
            for name in slot_names:
                results[name]["error"] = str(exc)
        finally:
            # Return to config view if the interface command succeeded.
            try:
                if CONN is not None and "(config-if-" in CONN.prompt:
                    CONN.run("quit", timeout=8)
            except Exception:
                pass

    return jsonify(interfaces=[results[name] for name in requested],
                   sampled_at=time.time(), poll_mode="CLI polling", host=CONN.host)


if __name__ == "__main__":
    host = os.environ.get("HOST", "127.0.0.1")
    port = int(os.environ.get("PORT", "8080"))
    if host != "127.0.0.1" and not UI_PASSWORD:
        print("!! هشدار: بدون UI_PASSWORD روی شبکه در دسترس است. حتماً UI_PASSWORD تنظیم کنید.")
    app.run(host=host, port=port, threaded=True)


# ---------- MA5683T live chassis map (read-only) ----------
from chassis_inventory import parse_chassis_inventory, parse_board_ports, gpon_port_count

@app.get("/api/chassis-inventory")
@need_conn
def api_chassis_inventory():
    """Return slot population read from the currently selected OLT, never a sample."""
    raw = CONN.run("display board 0", timeout=25)
    if OVERVIEW_ERROR.search(raw):
        raise OLTError("دریافت اطلاعات کارت‌های شاسی ناموفق بود")
    inventory = parse_chassis_inventory(raw)
    return jsonify(model="MA5683T", device_id=session.get("active_olt_id"),
                   slots=inventory["slots"], recognized=inventory["recognized"],
                   unparsed=inventory["unparsed"], sampled_at=int(time.time()))

@app.get("/api/board/<int:slot>")
@need_conn
def api_board_detail(slot):
    """Read-only detail for an installed chassis board and its reported PON ports."""
    if not 0 <= slot <= 12:
        raise ValueError("شماره اسلات نامعتبر است")
    inventory_raw = CONN.run("display board 0", timeout=25)
    inventory = parse_chassis_inventory(inventory_raw)
    board = inventory["slots"][slot]
    if board["state"] != "installed":
        raise ValueError("در این اسلات کارت نصب‌شده‌ای از خروجی زنده OLT شناسایی نشد")
    detail = CONN.run(f"display board 0/{slot}", timeout=25)
    port_state = ""
    port_info = []
    port_error = ""
    entered_gpon = False
    try:
        # MA56xx GPON service-port commands run in GPON interface context.
        interface_out = CONN.run(f"interface gpon 0/{slot}", timeout=25)
        if ERR.search(interface_out):
            port_error = interface_out.strip() or "دستگاه ورود به رابط GPON را نپذیرفت"
        else:
            entered_gpon = True
            port_state = CONN.run("display port state", timeout=25)
            if ERR.search(port_state):
                port_error = port_state.strip()
            else:
                port_count = gpon_port_count(board["board"])
                if port_count is None:
                    port_error = f"تعداد پورت برای مدل {board['board']} در جدول سازگاری تعریف نشده است"
                else:
                    for port_id in range(port_count):
                        output = CONN.run(f"display port info {port_id}", timeout=25)
                        port_info.append({"port_id": port_id, "raw": output})
    except OLTError as exc:
        port_error = str(exc)
    finally:
        if entered_gpon:
            try:
                CONN.run("quit", timeout=15)
            except OLTError as exc:
                port_error = (port_error + "; " if port_error else "") + f"بازگشت از GPON interface ناموفق: {exc}"
    info_raw = "\\n".join(item["raw"] for item in port_info)
    ports = parse_board_ports(info_raw, slot)
    return jsonify(slot=slot, board=board, detail=detail[:30000],
                   port_state=port_state[:30000], port_info=port_info,
                   ports=ports, port_error=port_error,
                   sampled_at=int(time.time()))
