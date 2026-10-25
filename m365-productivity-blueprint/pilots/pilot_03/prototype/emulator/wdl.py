"""Power Automate 식(Workflow Definition Language) 부분 구현 — 로컬 검증 전용.

흐름 정의 파일(flows/*.flow.json)에 적힌 식을 '그대로' 평가해, 사용자가 디자이너에 붙여넣을 식이
문법적으로 맞고 의도대로 동작하는지 확인한다.

지원 범위(이 프로토타입 흐름이 쓰는 것만): 아래 FUNCTIONS 표. 표에 없는 함수는 즉시 오류 →
'지원하지 않는 함수가 몰래 통과'하는 일이 없다. 실제 Power Automate와 다를 수 있는 부분은
docs의 '에뮬레이터 한계'에 기록했다.
"""
from __future__ import annotations

import json
import re
import uuid
from datetime import datetime, timedelta, timezone


class ExprError(Exception):
    pass


# ---------------------------------------------------------------- 토크나이저 / 파서
TOKEN = re.compile(r"""
    (?P<ws>\s+)
  | (?P<str>'(?:[^']|'')*')
  | (?P<num>-?\d+(?:\.\d+)?)
  | (?P<ident>[A-Za-z_][A-Za-z0-9_]*)
  | (?P<op>\?\[|\[|\]|\(|\)|,|\.)
""", re.X)


def tokenize(s: str) -> list[tuple[str, str]]:
    pos, out = 0, []
    while pos < len(s):
        m = TOKEN.match(s, pos)
        if not m:
            raise ExprError(f"식 구문 오류(위치 {pos}): {s[pos:pos + 20]!r}")
        kind = m.lastgroup
        if kind != "ws":
            out.append((kind, m.group()))
        pos = m.end()
    return out


class Parser:
    def __init__(self, s: str):
        self.src = s
        self.t = tokenize(s)
        self.i = 0

    def peek(self, k=0):
        return self.t[self.i + k] if self.i + k < len(self.t) else (None, None)

    def take(self, val=None):
        tok = self.peek()
        if tok[0] is None or (val is not None and tok[1] != val):
            raise ExprError(f"'{val}' 이(가) 필요합니다: {self.src!r}")
        self.i += 1
        return tok

    def parse(self):
        node = self.expr()
        if self.i != len(self.t):
            raise ExprError(f"식 끝에 불필요한 토큰: {self.t[self.i][1]!r} in {self.src!r}")
        return node

    def expr(self):
        kind, val = self.peek()
        if kind == "str":
            self.take()
            node = ("lit", val[1:-1].replace("''", "'"))
        elif kind == "num":
            self.take()
            node = ("lit", float(val) if "." in val else int(val))
        elif kind == "ident":
            self.take()
            if val in ("true", "false", "null") and self.peek()[1] != "(":
                node = ("lit", {"true": True, "false": False, "null": None}[val])
            else:
                self.take("(")
                args = []
                if self.peek()[1] != ")":
                    args.append(self.expr())
                    while self.peek()[1] == ",":
                        self.take(",")
                        args.append(self.expr())
                self.take(")")
                node = ("call", val, args)
        else:
            raise ExprError(f"예상치 못한 토큰 {val!r} in {self.src!r}")
        while self.peek()[1] in ("[", "?[", "."):
            op = self.take()[1]
            if op == ".":
                name = self.take()[1]
                node = ("get", node, ("lit", name), False)
            else:
                k = self.expr()
                self.take("]")
                node = ("get", node, k, op == "?[")
        return node


# ---------------------------------------------------------------- 날짜 유틸
TZ = {"UTC": 0, "Korea Standard Time": 9, "(UTC+09:00) Seoul": 9}


def parse_ts(v) -> datetime:
    if isinstance(v, datetime):
        return v
    s = str(v).strip()
    if not s:
        raise ExprError("빈 날짜 문자열")
    s2 = re.sub(r"(\.\d{6})\d+", r"\1", s)
    if s2.endswith("Z"):
        s2 = s2[:-1] + "+00:00"
    try:
        d = datetime.fromisoformat(s2)
    except ValueError:
        raise ExprError(f"날짜 형식 오류: {s!r}")
    if d.tzinfo is None:
        d = d.replace(tzinfo=timezone.utc)
    return d.astimezone(timezone.utc)


def fmt_ts(d: datetime, fmt: str | None, zone_suffix: bool = True) -> str:
    """'o'(기본) 또는 .NET 사용자 지정 형식 일부(yyyy MM dd HH mm ss fff 'literal')"""
    if fmt in (None, "o", "O"):
        base = d.strftime("%Y-%m-%dT%H:%M:%S") + f".{d.microsecond:06d}0"
        return base + ("Z" if zone_suffix else "")
    out, i = [], 0
    while i < len(fmt):
        if fmt[i] == "'":
            j = fmt.index("'", i + 1)
            out.append(fmt[i + 1:j])
            i = j + 1
            continue
        for tok, val in (("yyyy", f"{d.year:04d}"), ("MM", f"{d.month:02d}"), ("dd", f"{d.day:02d}"),
                         ("HH", f"{d.hour:02d}"), ("mm", f"{d.minute:02d}"), ("ss", f"{d.second:02d}"),
                         ("fff", f"{d.microsecond // 1000:03d}")):
            if fmt.startswith(tok, i):
                out.append(val)
                i += len(tok)
                break
        else:
            if fmt[i].isalpha() and fmt[i] not in "T":
                raise ExprError(f"지원하지 않는 날짜 형식 문자 {fmt[i]!r} in {fmt!r}")
            out.append(fmt[i])
            i += 1
    return "".join(out)


def _bool(v) -> bool:
    if not isinstance(v, bool):
        raise ExprError(f"논리값이 필요합니다: {v!r}")
    return v


def _num(v):
    if isinstance(v, bool) or not isinstance(v, (int, float)):
        raise ExprError(f"숫자가 필요합니다: {v!r}")
    return v


def _empty(v) -> bool:
    return v is None or v == "" or v == [] or v == {}


def _int(v):
    if isinstance(v, bool):
        raise ExprError("int(): 논리값 변환 불가")
    try:
        return int(str(v).strip()) if not isinstance(v, (int, float)) else int(v)
    except ValueError:
        raise ExprError(f"int(): 정수 변환 불가 {v!r}")


def _string(v) -> str:
    if v is None:
        return ""
    if isinstance(v, bool):
        return "True" if v else "False"
    if isinstance(v, (dict, list)):
        return json.dumps(v, ensure_ascii=False, separators=(",", ":"))
    if isinstance(v, float) and v.is_integer():
        return str(int(v))
    return str(v)


def _format_number(n, fmt):
    n = _num(n)
    if re.fullmatch(r"0+", fmt):
        return f"{int(round(n)):0{len(fmt)}d}"
    raise ExprError(f"formatNumber 형식 미지원: {fmt!r}")


def _contains(coll, v):
    if coll is None:
        raise ExprError("contains(): 대상이 null")
    if isinstance(coll, str):
        return _string(v) in coll
    if isinstance(coll, dict):
        return v in coll
    return v in coll


def _sub_str(s, start, length=None):
    s = _string(s)
    if start < 0 or start > len(s) or (length is not None and start + length > len(s)):
        raise ExprError("substring(): 범위 초과")
    return s[start:] if length is None else s[start:start + length]


def _length(a):
    if a is None:
        raise ExprError("length(): null")
    return len(a)


def _union(a, b):
    out, seen = [], set()
    for x in list(a) + list(b):
        k = json.dumps(x, sort_keys=True, ensure_ascii=False)
        if k not in seen:
            seen.add(k)
            out.append(x)
    return out


def _cmp(a, b):
    if isinstance(a, str) and isinstance(b, str):
        return (a > b) - (a < b)
    return (_num(a) > _num(b)) - (_num(a) < _num(b))


FUNCTIONS = {
    "concat": lambda *a: "".join(_string(x) for x in a),
    "equals": lambda a, b: a == b,
    "not": lambda a: not _bool(a),
    "empty": _empty,
    "coalesce": lambda *a: next((x for x in a if x is not None), None),
    "length": lambda a: _length(a),
    "first": lambda a: (a[0] if a else None),
    "last": lambda a: (a[-1] if a else None),
    "contains": _contains,
    "greater": lambda a, b: _cmp(a, b) > 0,
    "greaterOrEquals": lambda a, b: _cmp(a, b) >= 0,
    "less": lambda a, b: _cmp(a, b) < 0,
    "lessOrEquals": lambda a, b: _cmp(a, b) <= 0,
    "add": lambda a, b: _num(a) + _num(b),
    "sub": lambda a, b: _num(a) - _num(b),
    "int": _int,
    "string": _string,
    "json": lambda s: s if isinstance(s, (dict, list)) else json.loads(_string(s)),
    "toLower": lambda s: _string(s).lower(),
    "toUpper": lambda s: _string(s).upper(),
    "trim": lambda s: _string(s).strip(),
    "replace": lambda s, a, b: _string(s).replace(a, b),
    "split": lambda s, d: _string(s).split(d),
    "join": lambda arr, d: d.join(_string(x) for x in arr),
    "substring": _sub_str,
    "startsWith": lambda s, p: _string(s).lower().startswith(_string(p).lower()),
    "endsWith": lambda s, p: _string(s).lower().endswith(_string(p).lower()),
    "createArray": lambda *a: list(a),
    "union": lambda a, b: _union(a, b),
    "formatNumber": _format_number,
    "guid": lambda: str(uuid.uuid4()),
    "base64ToBinary": lambda s: {"$binary": _string(s)},
}


class Context:
    """식 평가 환경. runtime이 trigger/action 결과·변수·반복 항목을 채운다."""

    def __init__(self, trigger_outputs=None, clock=None, workflow=None):
        self.trigger_outputs = trigger_outputs or {}
        self.actions: dict[str, dict] = {}
        self.variables: dict[str, object] = {}
        self.loop_items: dict[str, object] = {}
        self.current_item = []  # item() 스택(Filter array·Select·Foreach)
        self.clock = clock or (lambda: datetime.now(timezone.utc))
        self.workflow = workflow or {}
        self.scope_results: dict[str, list] = {}


def evaluate_node(node, ctx: Context):
    kind = node[0]
    if kind == "lit":
        return node[1]
    if kind == "get":
        base = evaluate_node(node[1], ctx)
        k = evaluate_node(node[2], ctx)
        safe = node[3]
        if base is None:
            if safe:
                return None
            raise ExprError(f"null 값에서 속성 '{k}' 를 읽을 수 없습니다(?[ ] 사용 검토)")
        if isinstance(base, list):
            if not isinstance(k, int):
                raise ExprError(f"배열 인덱스는 정수여야 합니다: {k!r}")
            if 0 <= k < len(base):
                return base[k]
            if safe:
                return None
            raise ExprError(f"배열 인덱스 범위 초과: {k}")
        if isinstance(base, dict):
            if k in base:
                return base[k]
            if isinstance(k, str) and "/" in k:
                # 디자이너가 생성하는 경로형 키: triggerOutputs()?['body/Status/Value']
                cur = base
                for part in k.split("/"):
                    if isinstance(cur, dict) and part in cur:
                        cur = cur[part]
                    elif safe:
                        return None
                    else:
                        raise ExprError(f"경로 '{k}' 의 '{part}' 가 없습니다")
                return cur
            if safe:
                return None
            raise ExprError(f"속성 '{k}' 가 없습니다")
        raise ExprError(f"속성 접근 불가 타입: {type(base).__name__}")
    _, name, args = node
    # 지연 평가가 필요한 함수
    if name == "if":
        if len(args) != 3:
            raise ExprError("if()는 인수 3개")
        return evaluate_node(args[1] if _bool(evaluate_node(args[0], ctx)) else args[2], ctx)
    if name == "and":
        return all(_bool(evaluate_node(a, ctx)) for a in args)
    if name == "or":
        return any(_bool(evaluate_node(a, ctx)) for a in args)
    vals = [evaluate_node(a, ctx) for a in args]
    if name == "triggerOutputs":
        return ctx.trigger_outputs
    if name == "triggerBody":
        return ctx.trigger_outputs.get("body")
    if name in ("body", "outputs"):
        if vals[0] not in ctx.actions:
            raise ExprError(f"{name}('{vals[0]}'): 실행되지 않았거나 없는 액션")
        a = ctx.actions[vals[0]]
        return a.get("body") if name == "body" else a.get("outputs")
    if name == "actions":
        if vals[0] not in ctx.actions:
            raise ExprError(f"actions('{vals[0]}'): 없는 액션")
        return ctx.actions[vals[0]]
    if name == "variables":
        if vals[0] not in ctx.variables:
            raise ExprError(f"variables('{vals[0]}'): 초기화되지 않은 변수")
        return ctx.variables[vals[0]]
    if name == "items":
        if vals[0] not in ctx.loop_items:
            raise ExprError(f"items('{vals[0]}'): 해당 반복 밖에서 사용")
        return ctx.loop_items[vals[0]]
    if name == "item":
        if not ctx.current_item:
            raise ExprError("item(): 반복·필터 밖에서 사용")
        return ctx.current_item[-1]
    if name == "result":
        if vals[0] not in ctx.scope_results:
            raise ExprError(f"result('{vals[0]}'): 범위(Scope) 결과 없음")
        return ctx.scope_results[vals[0]]
    if name == "workflow":
        return ctx.workflow
    if name == "utcNow":
        return fmt_ts(ctx.clock(), vals[0] if vals else None)
    if name in ("addDays", "addHours", "addMinutes"):
        d = parse_ts(vals[0])
        unit = {"addDays": "days", "addHours": "hours", "addMinutes": "minutes"}[name]
        return fmt_ts(d + timedelta(**{unit: _num(vals[1])}), vals[2] if len(vals) > 2 else None)
    if name == "formatDateTime":
        return fmt_ts(parse_ts(vals[0]), vals[1] if len(vals) > 1 else None)
    if name == "convertFromUtc":
        if vals[1] not in TZ:
            raise ExprError(f"시간대 미지원: {vals[1]!r}")
        d = parse_ts(vals[0]) + timedelta(hours=TZ[vals[1]])
        return fmt_ts(d, vals[2] if len(vals) > 2 else None, zone_suffix=False)
    if name == "convertToUtc":
        if vals[1] not in TZ:
            raise ExprError(f"시간대 미지원: {vals[1]!r}")
        d = parse_ts(vals[0]).replace(tzinfo=timezone.utc) - timedelta(hours=TZ[vals[1]])
        return fmt_ts(d, vals[2] if len(vals) > 2 else None)
    if name == "dayOfWeek":
        return (parse_ts(vals[0]).weekday() + 1) % 7
    if name not in FUNCTIONS:
        raise ExprError(f"지원하지 않는 함수: {name}()")
    try:
        return FUNCTIONS[name](*vals)
    except TypeError as e:
        raise ExprError(f"{name}() 인수 오류: {e}")


_cache: dict[str, tuple] = {}


def compile_expr(src: str):
    if src not in _cache:
        _cache[src] = Parser(src).parse()
    return _cache[src]


def evaluate_string(s: str, ctx: Context):
    """'@식' → 식의 값(형식 유지), '...@{식}...' → 문자열 보간, '@@' → '@' 리터럴."""
    if s.startswith("@@"):
        return s[1:]
    if s.startswith("@") and not s.startswith("@{"):
        return evaluate_node(compile_expr(s[1:]), ctx)
    if "@{" not in s:
        return s
    out, i = [], 0
    while i < len(s):
        j = s.find("@{", i)
        if j < 0:
            out.append(s[i:])
            break
        out.append(s[i:j])
        k, depth, q = j + 2, 1, False
        while k < len(s) and depth:
            ch = s[k]
            if ch == "'":
                q = not q
            elif not q and ch == "{":
                depth += 1
            elif not q and ch == "}":
                depth -= 1
            k += 1
        if depth:
            raise ExprError(f"닫히지 않은 @{{ }}: {s!r}")
        out.append(_string(evaluate_node(compile_expr(s[j + 2:k - 1]), ctx)))
        i = k
    return "".join(out)


def evaluate(value, ctx: Context):
    if isinstance(value, str):
        return evaluate_string(value, ctx)
    if isinstance(value, list):
        return [evaluate(v, ctx) for v in value]
    if isinstance(value, dict):
        return {k: evaluate(v, ctx) for k, v in value.items()}
    return value


def iter_expressions(value):
    """정의 안의 모든 식 원문을 순회(lint용)."""
    if isinstance(value, str):
        if value.startswith("@@"):
            return
        if value.startswith("@") and not value.startswith("@{"):
            yield value[1:]
        for m in re.finditer(r"@\{((?:[^{}']|'(?:[^']|'')*')*)\}", value):
            yield m.group(1)
    elif isinstance(value, list):
        for v in value:
            yield from iter_expressions(v)
    elif isinstance(value, dict):
        for v in value.values():
            yield from iter_expressions(v)
