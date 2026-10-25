"""흐름 정의(flows/*.flow.json) 실행기 — 로컬 검증 전용 Power Automate 에뮬레이터.

구현한 의미론
- 트리거: SharePoint 항목 생성/생성·수정, Outlook 플래그(V4), Teams 선택 메시지, 반복(Recurrence), 수동
- 트리거 조건(모두 true일 때만 실행), 트리거 동시성(1이면 순차·최신 읽기, 제한 없음이면 병렬 배치에서 스냅샷 읽기)
- 액션: Compose, InitializeVariable(최상위만), SetVariable, IncrementVariable, AppendToArrayVariable,
        If, Scope, Foreach, FilterArray, Select, Terminate, Connector
- runAfter(Succeeded/Failed/Skipped/TimedOut) 의존 순서, 건너뜀 전파, Scope 상태 집계, result('범위')
- 재시도: 기본 지수 정책 4회(408·429·5xx), "retry": {"type": "none"} 이면 재시도 없음
- 식 오류는 해당 액션 실패(InvalidTemplate)로 처리
SharePoint 쓰기는 이벤트를 만들고, 그 이벤트가 다시 흐름을 깨우므로 '자기 재실행 루프'를 실제로 재현·검출한다.
"""
from __future__ import annotations

import itertools
import json
from dataclasses import dataclass, field
from pathlib import Path

from fakes import ConnectorError
from wdl import Context, ExprError, evaluate

RETRYABLE = {408, 429, 500, 502, 503, 504}
MAX_RUNS_PER_DRAIN = 200
# 실제 엔진처럼, 안쪽 액션이 실패한 조건·범위·반복은 상세 대신 일반 메시지를 남긴다(상세는 실행 기록 링크로 확인)
ACTION_FAILED = {"code": "ActionFailed", "message": "An action failed. No dependent actions succeeded."}


class Terminate(Exception):
    def __init__(self, status, code, message):
        super().__init__(message)
        self.status, self.code, self.message = status, code, message


class DefinitionError(Exception):
    pass


@dataclass
class Run:
    flow: str
    run_id: str
    trigger: dict
    status: str = "Running"
    actions: dict = field(default_factory=dict)
    terminate: dict | None = None
    error: str = ""

    def action_status(self, name):
        return self.actions.get(name, {}).get("status")


class Flow:
    def __init__(self, path: Path, owner: str, site_map: dict[str, str] | None = None):
        raw = path.read_text(encoding="utf-8")
        for k, v in (site_map or {}).items():
            raw = raw.replace(k, v)
        self.d = json.loads(raw)
        self.name = self.d["name"]
        self.id = self.d["id"]
        self.owner = owner.lower()
        self.trigger = self.d["trigger"]
        self.enabled = True


class Runtime:
    def __init__(self, sp, outlook, teams, excel, users, clock):
        self.sp, self.outlook, self.teams, self.excel, self.users, self.clock = sp, outlook, teams, excel, users, clock
        self.flows: list[Flow] = []
        self.runs: list[Run] = []
        self._ids = itertools.count(1)
        self.connector_calls: list[tuple] = []

    def register(self, flow: Flow):
        self.flows.append(flow)

    # ---------------------------------------------------------------- 트리거
    def _matches(self, flow: Flow, event: dict) -> bool:
        t = flow.trigger
        kind = t["kind"]
        if event["source"] == "SharePoint":
            if kind not in ("SharePoint.WhenAnItemIsCreated", "SharePoint.WhenAnItemIsCreatedOrModified"):
                return False
            if kind == "SharePoint.WhenAnItemIsCreated" and event["kind"] != "created":
                return False
            return (t["inputs"]["site"].lower() == event["site"].lower() and t["inputs"]["list"] == event["list"])
        return kind == event.get("trigger_kind")

    def _conditions_pass(self, flow: Flow, outputs: dict) -> bool:
        ctx = Context(trigger_outputs=outputs, clock=self.clock)
        for cond in flow.trigger.get("conditions", []):
            v = evaluate(cond, ctx)
            if v is not True:
                return False
        return True

    def drain(self):
        """SharePoint 이벤트 큐가 빌 때까지 흐름 실행(순차). 무한 루프면 예외."""
        count = 0
        while self.sp.events:
            ev = self.sp.events.pop(0)
            for flow in self.flows:
                if flow.enabled and self._matches(flow, ev):
                    outputs = {"body": ev["item"], "headers": {}}
                    if self._conditions_pass(flow, outputs):
                        self.run(flow, outputs)
                        count += 1
                        if count > MAX_RUNS_PER_DRAIN:
                            raise RuntimeError("흐름이 끝없이 다시 실행됩니다(자기 트리거 루프)")
        return count

    def fire(self, trigger_kind: str, outputs: dict, flow_id: str | None = None, read_seq=None) -> list[Run]:
        runs = []
        for flow in self.flows:
            folder = flow.trigger.get("inputs", {}).get("folder")
            if folder and outputs.get("_folder") not in (None, folder):
                continue
            if flow.enabled and flow.trigger["kind"] == trigger_kind and (flow_id is None or flow.id == flow_id):
                if self._conditions_pass(flow, outputs):
                    runs.append(self.run(flow, outputs, read_seq=read_seq))
        return runs

    def fire_parallel(self, trigger_kind: str, outputs_list: list[dict], flow_id: str):
        """같은 트리거가 동시에 여러 번 발생. 동시성 제한 없는 흐름은 모든 실행이 같은 시점의 데이터를 읽는다."""
        flow = next(f for f in self.flows if f.id == flow_id)
        serial = flow.trigger.get("concurrency") == 1
        snapshot = self.sp.seq
        return [self.fire(trigger_kind, o, flow_id, read_seq=None if serial else snapshot)[0] for o in outputs_list]

    # ---------------------------------------------------------------- 실행
    def run(self, flow: Flow, outputs: dict, read_seq=None) -> Run:
        rid = f"08585{next(self._ids):06d}"
        run = Run(flow.id, rid, outputs)
        ctx = Context(trigger_outputs=outputs, clock=self.clock,
                      workflow={"name": flow.id, "run": {"name": rid}, "tags": {"environmentName": "Default-emulator",
                                                                               "flowDisplayName": flow.name}})
        ctx.read_seq = read_seq
        ctx.owner = flow.owner
        ctx.run = run
        try:
            status = self._run_scope(flow.d["actions"], ctx, top=True)
            run.status = "Failed" if status == "Failed" else "Succeeded"
        except Terminate as t:
            run.status = t.status
            run.terminate = {"status": t.status, "code": t.code, "message": t.message}
        except DefinitionError as e:
            run.status = "Failed"
            run.error = f"정의 오류: {e}"
        self.runs.append(run)
        return run

    def _run_scope(self, actions: dict, ctx: Context, top=False) -> str:
        pending = list(actions.items())
        done: dict[str, str] = {}
        worst = "Succeeded"
        while pending:
            progressed = False
            for name, a in list(pending):
                ra = a.get("runAfter", {})
                missing = [d for d in ra if d not in actions]
                if missing:
                    raise DefinitionError(f"{name}: runAfter 대상 없음 {missing}")
                if all(dep in done for dep in ra):
                    if all(done[dep] in sts for dep, sts in ra.items()):
                        if a["type"] == "InitializeVariable" and not top:
                            raise DefinitionError(f"{name}: 변수 초기화는 최상위에서만 가능")
                        st = self._exec(name, a, ctx)
                    else:
                        st = "Skipped"
                        ctx.actions[name] = {"status": "Skipped"}
                        ctx.run.actions[name] = {"status": "Skipped"}
                    done[name] = st
                    if st in ("Failed", "TimedOut"):
                        worst = "Failed"
                    pending.remove((name, a))
                    progressed = True
            if not progressed:
                raise DefinitionError("runAfter 순환 참조")
        # 실패 액션 뒤에 '실패 시 실행' 처리기가 성공했다면 그 범위 결과는 처리된 것으로 본다
        handled = any(set(a.get("runAfter", {}).get(dep, [])) & {"Failed", "TimedOut"} and done.get(n) == "Succeeded"
                      for n, a in actions.items() for dep in a.get("runAfter", {}))
        return "Succeeded" if handled and top else worst

    def _record(self, ctx, name, status, body=None, outputs=None, error=None):
        rec = {"status": status, "body": body, "outputs": outputs if outputs is not None else body}
        if error:
            rec["error"] = error
        ctx.actions[name] = rec
        ctx.run.actions[name] = {"status": status, **({"error": error} if error else {})}
        return status

    def _exec(self, name, a, ctx: Context) -> str:
        t = a["type"]
        try:
            if t == "Compose":
                v = evaluate(a["inputs"], ctx)
                return self._record(ctx, name, "Succeeded", v, v)
            if t == "InitializeVariable":
                i = a["inputs"]
                ctx.variables[i["name"]] = evaluate(i.get("value"), ctx)
                return self._record(ctx, name, "Succeeded")
            if t == "SetVariable":
                i = a["inputs"]
                if i["name"] not in ctx.variables:
                    raise ExprError(f"초기화되지 않은 변수 {i['name']}")
                ctx.variables[i["name"]] = evaluate(i["value"], ctx)
                return self._record(ctx, name, "Succeeded")
            if t == "IncrementVariable":
                i = a["inputs"]
                ctx.variables[i["name"]] += evaluate(i.get("value", 1), ctx)
                return self._record(ctx, name, "Succeeded")
            if t == "AppendToArrayVariable":
                i = a["inputs"]
                ctx.variables[i["name"]].append(evaluate(i["value"], ctx))
                return self._record(ctx, name, "Succeeded")
            if t == "Terminate":
                i = evaluate(a["inputs"], ctx)
                self._record(ctx, name, "Succeeded")
                raise Terminate(i["runStatus"], i.get("runError", {}).get("code", ""), i.get("runError", {}).get("message", i.get("message", "")))
            if t == "If":
                cond = evaluate(a["expression"], ctx)
                if not isinstance(cond, bool):
                    raise ExprError(f"조건 식 결과가 논리값이 아님: {cond!r}")
                branch = a.get("actions", {}) if cond else a.get("else", {}).get("actions", {})
                st = self._run_scope(branch, ctx)
                return self._record(ctx, name, st, error=ACTION_FAILED if st == "Failed" else None)
            if t == "Scope":
                st = self._run_scope(a["actions"], ctx)
                ctx.scope_results[name] = [{"name": n, "status": ctx.actions.get(n, {}).get("status"),
                                            "error": ctx.actions.get(n, {}).get("error")} for n in a["actions"]]
                return self._record(ctx, name, st, error=ACTION_FAILED if st == "Failed" else None)
            if t == "Foreach":
                arr = evaluate(a["foreach"], ctx)
                if not isinstance(arr, list):
                    raise ExprError(f"Apply to each 입력이 배열이 아님: {type(arr).__name__}")
                worst = "Succeeded"
                for it in arr:
                    ctx.loop_items[name] = it
                    ctx.current_item.append(it)
                    try:
                        if self._run_scope(a["actions"], ctx) == "Failed":
                            worst = "Failed"
                    finally:
                        ctx.current_item.pop()
                ctx.loop_items.pop(name, None)
                return self._record(ctx, name, worst, error=ACTION_FAILED if worst == "Failed" else None)
            if t in ("FilterArray", "Select"):
                arr = evaluate(a["inputs"]["from"], ctx)
                if not isinstance(arr, list):
                    raise ExprError(f"{t} 입력이 배열이 아님")
                out = []
                for it in arr:
                    ctx.current_item.append(it)
                    try:
                        if t == "FilterArray":
                            keep = evaluate(a["inputs"]["where"], ctx)
                            if not isinstance(keep, bool):
                                raise ExprError("필터 조건이 논리값이 아님")
                            if keep:
                                out.append(it)
                        else:
                            out.append(evaluate(a["inputs"]["select"], ctx))
                    finally:
                        ctx.current_item.pop()
                return self._record(ctx, name, "Succeeded", out, out)
            if t == "Connector":
                return self._connector(name, a, ctx)
            raise DefinitionError(f"{name}: 지원하지 않는 액션 형식 {t}")
        except ExprError as e:
            return self._record(ctx, name, "Failed", error={"code": "InvalidTemplate", "message": str(e)})

    def _connector(self, name, a, ctx):
        inputs = evaluate(a["inputs"], ctx)
        policy = a.get("retry", {"type": "exponential", "count": 4})
        attempts = 1 + (policy.get("count", 4) if policy.get("type") != "none" else 0)
        last = None
        for attempt in range(attempts):
            try:
                body = self._call(a["connector"], a["operation"], inputs, ctx)
                self.connector_calls.append((ctx.run.flow, name, a["operation"], "ok", attempt))
                return self._record(ctx, name, "Succeeded", body, {"body": body, "statusCode": 200})
            except ConnectorError as e:
                last = e
                self.connector_calls.append((ctx.run.flow, name, a["operation"], e.status, attempt))
                if e.status not in RETRYABLE:
                    break
        return self._record(ctx, name, "Failed", {"error": {"code": last.code, "message": last.message}},
                            {"statusCode": last.status},
                            error={"code": last.code, "status": last.status, "message": last.message})

    def _call(self, connector, op, i, ctx):
        user = ctx.owner
        if connector == "SharePoint":
            self.sp.faults.check("SharePoint", op, i.get("list"))
            if op == "Get items":
                return {"value": self.sp.get_items(user, i["site"], i["list"], i.get("filter") or None, i.get("top"),
                                                   read_seq=getattr(ctx, "read_seq", None))}
            if op == "Get item":
                rows = self.sp.get_items(user, i["site"], i["list"], f"ID eq {int(i['id'])}")
                if not rows:
                    raise ConnectorError(404, "ItemNotFound", f"항목 {i['id']} 없음")
                return rows[0]
            if op == "Create item":
                return self.sp.create(user, i["site"], i["list"], i["item"])
            if op == "Update item":
                return self.sp.update(user, i["site"], i["list"], i["id"], i["item"])
        if connector == "Office 365 Outlook":
            if op == "Get calendar view of events (V3)":
                return {"value": self.outlook.calendar_view(user, i["startTime"], i["endTime"])}
            if op == "Send an email (V2)":
                return self.outlook.send_email(user, i["to"], i["subject"], i["body"])
        if connector == "Microsoft Teams":
            if op == "Post card in a chat or channel":
                return self.teams.post_card(user, i["poster"], i["location"], i["recipient"], i["card"])
            if op == "Post message in a chat or channel":
                return self.teams.post_message(user, i["poster"], i["recipient"], i["message"])
        if connector == "Excel Online (Business)" and op == "Run script from SharePoint library":
            return self.excel.run_script(user, i["workbook"], i["script"], i["parameters"])
        if connector == "Office 365 Users" and op == "Get user profile (V2)":
            return self.users.profile(user, i["user"])
        raise DefinitionError(f"지원하지 않는 커넥터 작업: {connector} / {op}")
