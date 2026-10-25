"""가짜 M365 커넥터 — 로컬 검증 전용(실제 서비스·데이터에 접속하지 않음).

SharePoint(목록·권한·필수 열·선택지 검증·OData 필터·이벤트), Outlook(일정·메일), Teams(카드 게시),
Excel Online(Office Scripts 실행: 실제 스크립트를 node 로 실행), Office 365 Users 를 흉내 낸다.
장애 주입(faults)으로 429 조절·401 연결 만료·403 권한 부족을 재현한다.
"""
from __future__ import annotations

import json
import re
import subprocess
from datetime import datetime, timezone
from pathlib import Path

BRIDGE = Path(__file__).resolve().parent / "run_office_script.js"


class ConnectorError(Exception):
    def __init__(self, status: int, code: str, message: str):
        super().__init__(f"{status} {code}: {message}")
        self.status, self.code, self.message = status, code, message


def iso(d: datetime) -> str:
    return d.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


class Faults:
    """('SharePoint', 'Create item', 'ActionItems') 같은 키에 [상태코드,...] 큐를 걸어 순서대로 실패시킨다."""

    def __init__(self):
        self.rules: dict[tuple, list[int]] = {}

    def add(self, connector: str, operation: str, target: str | None, statuses: list[int]):
        self.rules[(connector, operation, target)] = list(statuses)

    def check(self, connector: str, operation: str, target: str | None):
        for key in ((connector, operation, target), (connector, operation, None), (connector, "*", None)):
            q = self.rules.get(key)
            if q:
                st = q.pop(0)
                raise ConnectorError(st, {429: "TooManyRequests", 401: "Unauthorized", 403: "Forbidden",
                                          500: "InternalServerError", 502: "BadGateway"}.get(st, "Error"),
                                     f"주입된 장애 {st}")


# ------------------------------------------------------------------ OData 필터
ODATA = re.compile(r"\s*(?:(?P<lp>\()|(?P<rp>\))|(?P<str>'(?:[^']|'')*')|(?P<num>-?\d+(?:\.\d+)?)|"
                   r"(?P<word>[A-Za-z_][A-Za-z0-9_/]*))")


def _odata_tokens(s: str):
    pos, out = 0, []
    while pos < len(s):
        if s[pos:].strip() == "":
            break
        m = ODATA.match(s, pos)
        if not m:
            raise ConnectorError(400, "InvalidFilter", f"필터 구문 오류: {s[pos:pos + 20]!r}")
        out.append((m.lastgroup, m.group(m.lastgroup)))
        pos = m.end()
    return out


class _ODataParser:
    def __init__(self, s):
        self.t, self.i, self.src = _odata_tokens(s), 0, s

    def peek(self):
        return self.t[self.i] if self.i < len(self.t) else (None, None)

    def take(self):
        tok = self.peek()
        self.i += 1
        return tok

    def parse(self):
        n = self.or_()
        if self.i != len(self.t):
            raise ConnectorError(400, "InvalidFilter", f"필터 끝 오류: {self.src!r}")
        return n

    def or_(self):
        n = self.and_()
        while self.peek() == ("word", "or"):
            self.take()
            n = ("or", n, self.and_())
        return n

    def and_(self):
        n = self.atom()
        while self.peek() == ("word", "and"):
            self.take()
            n = ("and", n, self.atom())
        return n

    def atom(self):
        k, v = self.take()
        if k == "lp":
            n = self.or_()
            if self.take()[0] != "rp":
                raise ConnectorError(400, "InvalidFilter", "괄호 불일치")
            return n
        if k != "word":
            raise ConnectorError(400, "InvalidFilter", f"필드 이름 필요: {v!r}")
        field = v
        op = self.take()[1]
        if op not in ("eq", "ne", "lt", "le", "gt", "ge"):
            raise ConnectorError(400, "InvalidFilter", f"연산자 미지원: {op!r}")
        vk, vv = self.take()
        if vk == "str":
            val = vv[1:-1].replace("''", "'")
        elif vk == "num":
            val = float(vv) if "." in vv else int(vv)
        elif vk == "word" and vv == "null":
            val = None
        elif vk == "word" and vv in ("true", "false"):
            val = vv == "true"
        else:
            raise ConnectorError(400, "InvalidFilter", f"값 형식 오류: {vv!r}")
        return ("cmp", field, op, val)


def _norm_cmp(v):
    if isinstance(v, str) and re.match(r"^\d{4}-\d{2}-\d{2}", v):
        return v[:10] if len(v) == 10 else v[:19].replace("T", " ")
    return v


def _match(node, item: dict) -> bool:
    kind = node[0]
    if kind == "and":
        return _match(node[1], item) and _match(node[2], item)
    if kind == "or":
        return _match(node[1], item) or _match(node[2], item)
    _, field, op, val = node
    parts = field.split("/")
    cur = item
    for p in parts:
        if isinstance(cur, dict):
            key = next((k for k in cur if k.lower() == p.lower()), None)
            cur = cur.get(key) if key else None
        else:
            cur = None
    if isinstance(cur, dict) and "Value" in cur:
        cur = cur["Value"]
    if isinstance(cur, dict) and "Email" in cur:
        cur = cur["Email"]
    if op == "eq":
        return (cur.lower() == val.lower()) if isinstance(cur, str) and isinstance(val, str) and "/" in field else cur == val
    if op == "ne":
        return cur != val
    if cur is None or val is None:
        return False
    a, b = _norm_cmp(cur), _norm_cmp(val)
    if isinstance(a, str) and isinstance(b, str) and len(a) != len(b):
        a, b = a[:10], b[:10]
    return {"lt": a < b, "le": a <= b, "gt": a > b, "ge": a >= b}[op]


# ------------------------------------------------------------------ SharePoint
class FakeSharePoint:
    def __init__(self, clock, faults: Faults, directory: dict[str, str]):
        self.clock, self.faults, self.directory = clock, faults, directory
        self.lists: dict[tuple, dict] = {}
        self.seq = 0
        self.events: list[dict] = []
        self.calls: list[tuple] = []

    def add_list(self, site: str, name: str, columns: list[dict], acl: dict[str, str]):
        self.lists[(site.lower(), name)] = {"columns": {c["internalName"]: c for c in columns}, "items": {},
                                            "next_id": 1, "acl": {k.lower(): v for k, v in acl.items()},
                                            "site": site, "name": name}

    def _list(self, site, name):
        lst = self.lists.get((str(site).lower(), name))
        if not lst:
            raise ConnectorError(404, "ListNotFound", f"목록 없음: {site} / {name}")
        return lst

    def _require(self, lst, user, need):
        role = lst["acl"].get(user.lower())
        if role is None or (need == "edit" and role != "edit"):
            raise ConnectorError(403, "Forbidden", f"{user} 에게 '{lst['name']}' {need} 권한 없음")

    def _shape(self, lst, rec):
        out = {"ID": rec["ID"], "Created": rec["Created"], "Modified": rec["Modified"],
               "Author": self._person(rec["Author"]), "Editor": self._person(rec["Editor"]),
               "{Link}": f"{lst['site']}/Lists/{lst['name']}/DispForm.aspx?ID={rec['ID']}"}
        for name, col in lst["columns"].items():
            v = rec.get(name)
            if col["type"] == "Choice":
                out[name] = {"Value": v} if v is not None else None
            elif col["type"] == "User":
                out[name] = self._person(v) if v else None
            else:
                out[name] = v
        return out

    def _person(self, email):
        return {"Email": email, "Claims": f"i:0#.f|membership|{email}",
                "DisplayName": self.directory.get(email.lower(), email)}

    def _apply(self, lst, rec, fields: dict, creating: bool):
        cols = lst["columns"]
        for raw_key, v in fields.items():
            key = raw_key.split("/")[0]
            if key not in cols:
                raise ConnectorError(400, "InvalidField", f"열 '{key}' 이(가) 목록에 없습니다")
            col = cols[key]
            if v == "" and col["type"] != "Text" and col["type"] != "Note":
                v = None
            if v is not None:
                if col["type"] == "Choice" and v not in col.get("choices", []):
                    raise ConnectorError(400, "InvalidChoice", f"'{key}' 선택지에 없는 값: {v!r}")
                if col["type"] == "User":
                    email = str(v).split("|")[-1]
                    if email.lower() not in self.directory:
                        raise ConnectorError(400, "UserNotFound", f"사용자 확인 불가: {v!r}")
                    v = email.lower()
                if col["type"] == "Number":
                    try:
                        v = float(v) if "." in str(v) else int(v)
                    except ValueError:
                        raise ConnectorError(400, "InvalidNumber", f"'{key}' 숫자 아님: {v!r}")
                if col["type"] == "DateTime":
                    s = str(v)
                    if not re.match(r"^\d{4}-\d{2}-\d{2}", s):
                        raise ConnectorError(400, "InvalidDate", f"'{key}' 날짜 아님: {v!r}")
                    v = s[:10] if col.get("dateOnly") else s
                if col["type"] in ("Text",) and len(str(v)) > 255:
                    raise ConnectorError(400, "TooLong", f"'{key}' 255자 초과")
                if col["type"] == "Note" and len(str(v)) > 63999:
                    raise ConnectorError(400, "TooLong", f"'{key}' 여러 줄 텍스트 한도(63,999자) 초과")
            rec[key] = v
        if creating:
            for name, col in cols.items():
                if name not in rec and "default" in col:
                    rec[name] = col["default"]
        missing = [n for n, c in cols.items() if c.get("required") and rec.get(n) in (None, "")]
        if missing:
            raise ConnectorError(400, "RequiredFieldMissing", f"필수 열 누락: {', '.join(missing)}")

    def _emit(self, lst, rec, kind):
        self.events.append({"source": "SharePoint", "site": lst["site"], "list": lst["name"], "kind": kind,
                            "item": self._shape(lst, rec)})

    # --- 사람(UI)이 직접 하는 입력도 같은 경로를 탄다(권한·필수열 검증·이벤트 동일)
    def create(self, user, site, name, fields: dict):
        lst = self._list(site, name)
        self._require(lst, user, "edit")
        now = iso(self.clock())
        self.seq += 1
        rec = {"ID": lst["next_id"], "Created": now, "Modified": now, "Author": user.lower(),
               "Editor": user.lower(), "_seq": self.seq, "_created_seq": self.seq}
        self._apply(lst, rec, fields, creating=True)
        lst["items"][rec["ID"]] = rec
        lst["next_id"] += 1
        self._emit(lst, rec, "created")
        return self._shape(lst, rec)

    def update(self, user, site, name, item_id, fields: dict, ui: bool = False):
        lst = self._list(site, name)
        self._require(lst, user, "edit")
        rec = lst["items"].get(int(item_id))
        if not rec:
            raise ConnectorError(404, "ItemNotFound", f"항목 {item_id} 없음")
        if not ui:
            # 실제 Power Automate 'Update item'은 목록의 필수 열을 모두 입력해야 저장된다
            given = {k.split("/")[0] for k in fields}
            need = [n for n, c in lst["columns"].items() if c.get("required") and n not in given]
            if need:
                raise ConnectorError(400, "RequiredInputMissing", f"Update item 필수 입력 누락: {', '.join(need)}")
        trial = dict(rec)
        self._apply(lst, trial, fields, creating=False)
        trial["Modified"], trial["Editor"] = iso(self.clock()), user.lower()
        self.seq += 1
        trial["_seq"] = self.seq
        lst["items"][rec["ID"]] = trial
        self._emit(lst, trial, "modified")
        return self._shape(lst, trial)

    def get_items(self, user, site, name, filter_query=None, top=None, read_seq=None):
        lst = self._list(site, name)
        self._require(lst, user, "read")
        node = _ODataParser(filter_query).parse() if filter_query else None
        rows = []
        for rec in sorted(lst["items"].values(), key=lambda r: r["ID"]):
            if read_seq is not None and rec["_created_seq"] > read_seq:
                continue  # 병렬 실행 시 다른 실행이 아직 커밋하지 않은 항목(경합 재현용)
            shaped = self._shape(lst, rec)
            if node is None or _match(node, shaped):
                rows.append(shaped)
        return rows[: int(top)] if top else rows

    def items(self, site, name):
        lst = self._list(site, name)
        return [self._shape(lst, r) for r in sorted(lst["items"].values(), key=lambda r: r["ID"])]


# ------------------------------------------------------------------ Outlook / Teams / Users / Excel
class FakeOutlook:
    def __init__(self, faults: Faults):
        self.faults = faults
        self.calendar: dict[str, list[dict]] = {}
        self.sent: list[dict] = []

    def calendar_view(self, user, start, end):
        self.faults.check("Office 365 Outlook", "Get calendar view of events (V3)", None)
        evs = self.calendar.get(user.lower(), [])
        return [e for e in evs if e["start"] < end and e["end"] > start]

    def send_email(self, user, to, subject, body):
        self.faults.check("Office 365 Outlook", "Send an email (V2)", None)
        if to.lower() != user.lower():
            # 프로토타입 안전 규칙: 본인 외 발송 금지(승인 전)
            raise ConnectorError(403, "PrototypeGuard", "프로토타입은 본인에게만 메일을 보낼 수 있습니다")
        self.sent.append({"from": user, "to": to, "subject": subject, "body": body})
        return {"status": "sent"}


class FakeTeams:
    CARD_LIMIT = 28 * 1024

    def __init__(self, faults: Faults, directory):
        self.faults, self.directory = faults, directory
        self.workflows_app_allowed = True
        self.posts: list[dict] = []

    def post_card(self, user, poster, location, recipient, card):
        self.faults.check("Microsoft Teams", "Post card in a chat or channel", None)
        if poster == "Flow bot" and not self.workflows_app_allowed:
            raise ConnectorError(403, "WorkflowsAppBlocked", "Teams 관리 센터에서 Workflows 앱이 차단됨")
        if recipient.lower() not in self.directory:
            raise ConnectorError(404, "RecipientNotFound", f"수신자 없음: {recipient}")
        raw = card if isinstance(card, str) else json.dumps(card, ensure_ascii=False)
        try:
            parsed = json.loads(raw)
        except json.JSONDecodeError:
            raise ConnectorError(400, "InvalidCard", "Adaptive Card JSON 형식 오류")
        if parsed.get("type") != "AdaptiveCard":
            raise ConnectorError(400, "InvalidCard", "type=AdaptiveCard 필요")
        if len(raw.encode("utf-8")) > self.CARD_LIMIT:
            raise ConnectorError(413, "MessageTooLarge", "카드 28KB 초과")
        self.posts.append({"from": user, "recipient": recipient.lower(), "card": parsed, "location": location})
        return {"messageId": f"msg-{len(self.posts)}"}

    def post_message(self, user, poster, recipient, message):
        self.faults.check("Microsoft Teams", "Post message in a chat or channel", None)
        if poster == "Flow bot" and not self.workflows_app_allowed:
            raise ConnectorError(403, "WorkflowsAppBlocked", "Workflows 앱 차단")
        self.posts.append({"from": user, "recipient": recipient.lower(), "message": message})
        return {"messageId": f"msg-{len(self.posts)}"}


class FakeUsers:
    def __init__(self, faults: Faults, directory):
        self.faults, self.directory = faults, directory

    def profile(self, user, upn):
        self.faults.check("Office 365 Users", "Get user profile (V2)", None)
        if not upn or upn.lower() not in self.directory:
            raise ConnectorError(404, "UserNotFound", f"사용자 없음: {upn!r}")
        return {"mail": upn.lower(), "displayName": self.directory[upn.lower()]}


class FakeExcel:
    def __init__(self, faults: Faults):
        self.faults = faults
        self.files: dict[str, set[str]] = {}  # 파일 경로 → 접근 가능 사용자
        self.calls_today = 0
        self.daily_limit = 1600

    def add_file(self, path, users):
        self.files[path] = {u.lower() for u in users}

    def run_script(self, user, workbook, script, params):
        self.faults.check("Excel Online (Business)", "Run script from SharePoint library", None)
        for p in (workbook, script):
            if p not in self.files:
                raise ConnectorError(404, "FileNotFound", f"파일 없음: {p}")
            if user.lower() not in self.files[p]:
                raise ConnectorError(403, "Forbidden", f"{user} 에게 {p} 접근 권한 없음")
        self.calls_today += 1
        if self.calls_today > self.daily_limit:
            raise ConnectorError(429, "DailyLimit", "Run script 일일 한도(1,600회) 초과")
        name = Path(script).stem
        proc = subprocess.run(["node", str(BRIDGE)], input=json.dumps({"script": name, "params": params}),
                              capture_output=True, text=True, timeout=120)
        if proc.returncode != 0:
            raise ConnectorError(502, "BadGateway", proc.stderr[-300:])
        out = json.loads(proc.stdout)
        if not out["ok"]:
            raise ConnectorError(400, "ScriptError", out["error"])
        return {"result": out["result"], "logs": []}
