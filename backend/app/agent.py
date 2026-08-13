from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from time import perf_counter
from typing import Any, Callable

from .models import ChatRequest, ChatResponse, MissingPersonRequest, ToolStep
from .tools import AgentTools


class EvacuationAgent:
    """One deterministic orchestrator with exactly seven callable tools."""

    def __init__(self, tools: AgentTools | None = None) -> None:
        self.tools = tools or AgentTools()

    @staticmethod
    def _call(name: str, func: Callable, payload: dict[str, Any], origin: str = "deterministic") -> ToolStep:
        started = perf_counter()
        try:
            output = func(**payload)
            status = "warning" if (
                isinstance(output, dict) and (output.get("status") == "blocked" or output.get("cleared") is False)
            ) else "ok"
        except Exception as exc:  # Defensive boundary: one data source must not crash the turn.
            output = {"error": str(exc), "fallback": "Tool failed; no safety conclusion was inferred."}
            status = "blocked"
        return ToolStep(
            tool=name,
            status=status,
            origin=origin,
            input={key: value.model_dump() if hasattr(value, "model_dump") else value for key, value in payload.items()},
            output=output,
            elapsed_ms=round((perf_counter() - started) * 1000),
        )

    def chat(self, request: ChatRequest) -> ChatResponse:
        ctx = request.context
        evac_step = self._call("get_evacuation_status", self.tools.get_evacuation_status, {
            "address": ctx.address, "lat": ctx.lat, "lon": ctx.lon, "at": ctx.at,
        })
        evac = evac_step.output if isinstance(evac_step.output, dict) else {}

        jobs = [
            ("get_active_incidents", self.tools.get_active_incidents, {
                "lat": ctx.lat, "lon": ctx.lon, "radius_km": 35.0, "at": ctx.at,
            }),
            ("find_shelters", self.tools.find_shelters, {
                "lat": ctx.lat, "lon": ctx.lon, "needs": ctx.needs, "at": ctx.at,
            }),
            ("check_hazmat_clearance", self.tools.check_hazmat_clearance, {
                "address": ctx.address, "zone_name": evac.get("zone_name"), "at": ctx.at,
            }),
        ]
        with ThreadPoolExecutor(max_workers=3) as executor:
            futures = [executor.submit(self._call, name, func, payload) for name, func, payload in jobs]
            parallel_steps = [future.result() for future in futures]

        steps = [evac_step, *parallel_steps]
        incidents = parallel_steps[0].output if isinstance(parallel_steps[0].output, list) else []
        shelters = parallel_steps[1].output if isinstance(parallel_steps[1].output, list) else []
        hazmat = parallel_steps[2].output if isinstance(parallel_steps[2].output, dict) else {}
        level = evac.get("level")
        notices = [
            "Decision-support demo only. Follow 911 and official incident-command instructions.",
            "Shelter capabilities and personal records are synthetic for the hackathon demo.",
        ]
        if evac.get("conflicts"):
            notices.append("Conflicting evacuation records were detected; the official, more conservative level was selected.")
        if evac.get("provenance", {}).get("stale"):
            notices.append("Evacuation data is stale. The agent will not infer an all-clear.")

        notification_step = None
        if level == 3:
            notification_step = self._call("send_notification", self.tools.send_notification, {
                "session_id": request.session_id,
                "contact": ctx.contact,
                "message": f"Level 3 evacuation for {ctx.address}: leave now and follow official directions.",
            })
            notification_step.input["contact"] = "masked"
            steps.append(notification_step)

        answer, severity = self._compose(level, evac, incidents, shelters, hazmat, ctx.needs.model_dump())
        map_state = {
            "center": [ctx.lat, ctx.lon],
            "user": {"lat": ctx.lat, "lon": ctx.lon, "address": ctx.address},
            "evacuation": evac,
            "incidents": incidents,
            "shelters": shelters,
            "selected_shelter": shelters[0] if shelters else None,
        }
        return ChatResponse(
            session_id=request.session_id,
            intent="evacuation_plan",
            answer=answer,
            severity=severity,
            steps=steps,
            map_state=map_state,
            notices=notices,
            orchestration={"provider": "deterministic", "model": None, "model_tool_calls": 0, "guard_tool_calls": len(steps)},
        )

    @staticmethod
    def _compose(level: int | None, evac: dict, incidents: list, shelters: list, hazmat: dict, needs: dict) -> tuple[str, str]:
        closest = incidents[0] if incidents else None
        shelter = shelters[0] if shelters else None
        need_labels = [label for label, enabled in needs.items() if enabled]
        if level == 3:
            opening = "Level 3（GO）：立即撤离。不要等待进一步通知。"
            severity = "danger"
        elif level == 2:
            opening = "Level 2（SET）：保持随时撤离状态，不要把降级理解为可以返家。"
            severity = "warning"
        elif level == 1:
            opening = "Level 1（READY）：保持警觉并准备撤离；当前记录不是明确的 All Clear。"
            severity = "warning"
        else:
            opening = "没有匹配到有效撤离多边形；这不代表安全或已经解除警报。"
            severity = "warning"

        details = []
        if closest:
            details.append(
                f"最近事件为 {closest['name']}，约 {closest['distance_km']} km；展示数据带有独立观测时间。"
            )
        if shelter:
            requirements = "、".join(need_labels) if need_labels else "一般需求"
            details.append(
                f"首选避难所：{shelter['name']}（约 {shelter['distance_km']} km），满足 {requirements}；"
                f"路线状态：{shelter['route_status']}。出发前请通过官方渠道再次确认。"
            )
        else:
            details.append("没有找到满足全部硬性需求且状态开放的避难所，请联系 911/当地应急部门人工协调。")
        if not hazmat.get("cleared", False):
            details.append("危险品/返家状态没有明确放行，因此系统不会建议返家。")
        return "\n\n".join([opening, *details]), severity

    def missing_person(self, request: MissingPersonRequest) -> ChatResponse:
        ctx = request.context
        file_step = self._call("file_missing_person", self.tools.file_missing_person, {
            "session_id": request.session_id,
            "name": request.name,
            "last_known_location": request.last_known_location,
            "contact": request.contact,
            "consent": request.consent,
        })
        file_step.input["contact"] = "masked"
        steps = [file_step]
        if isinstance(file_step.output, dict) and file_step.output.get("status") == "blocked":
            return ChatResponse(
                session_id=request.session_id,
                intent="reunification",
                answer="没有获得明确授权，因此未创建或搜索任何人员记录。",
                severity="warning",
                steps=steps,
                map_state={"center": [ctx.lat, ctx.lon]},
                notices=["This demo never sends personal data to authorities."],
            )
        search_step = self._call("search_missing_reports", self.tools.search_missing_reports, {
            "session_id": request.session_id, "name": request.name, "consent": request.consent,
        })
        steps.append(search_step)
        matches = search_step.output if isinstance(search_step.output, list) else []
        if matches:
            notification_step = self._call("send_notification", self.tools.send_notification, {
                "session_id": request.session_id,
                "contact": request.contact,
                "message": f"Synthetic demo match found for {request.name}. Verify through official channels.",
            })
            notification_step.input["contact"] = "masked"
            steps.append(notification_step)
            answer = f"合成演示记录中找到一个匹配：{matches[0]['shelter']}。这不是真实人员信息，请通过官方渠道核实。"
        else:
            answer = "合成演示记录中没有找到匹配。报告仅保存在本次内存会话中，没有提交给政府机构。"
        return ChatResponse(
            session_id=request.session_id,
            intent="reunification",
            answer=answer,
            severity="info",
            steps=steps,
            map_state={"center": [ctx.lat, ctx.lon]},
            notices=["All people and check-in records in this flow are synthetic."],
            orchestration={"provider": "deterministic", "model": None, "model_tool_calls": 0, "guard_tool_calls": len(steps)},
        )
