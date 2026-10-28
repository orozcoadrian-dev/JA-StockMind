from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

import httpx
from dotenv import load_dotenv
from sqlalchemy import select

from Backend.Agent.memory import MemoryStore
from Backend.Agent.prompts import build_system_prompt
from Backend.Agent.tools import TOOL_SCHEMAS, execute_tool
from app.db.session import SessionLocal
from app.models import AgentAction

load_dotenv(Path(__file__).resolve().parents[1] / ".env", override=False)


class GeminiClient:
    def __init__(self):
        self.api_key = os.getenv("GEMINI_API_KEY") or os.getenv("LLM_API_KEY", "")
        self.base_url = os.getenv(
            "GEMINI_API_URL",
            "https://generativelanguage.googleapis.com/v1beta/openai/chat/completions",
        )
        self.model = os.getenv("GEMINI_MODEL", "gemini-3.5-flash-lite")

    def complete(self, messages: list[dict], tools: dict) -> dict:
        if not self.api_key or self.api_key.startswith("dev-") or self.api_key.startswith("test-"):
            raise RuntimeError("El agente Gemini no está configurado. Define GEMINI_API_KEY en Backend/.env antes de usar /api/agent/chat.")
        response = httpx.post(self.base_url, headers={"Authorization": f"Bearer {self.api_key}"}, json={"model": self.model, "messages": messages, "tools": [{"type": "function", "function": schema} for schema in tools.values()]}, timeout=60)
        response.raise_for_status()
        message = response.json()["choices"][0]["message"]
        calls = []
        for call in message.get("tool_calls", []):
            calls.append({
                "id": call["id"],
                "name": call["function"]["name"],
                "arguments": json.loads(call["function"].get("arguments") or "{}"),
                "extra_content": call.get("extra_content"),
            })
        return {"content": message.get("content"), "tool_calls": calls}


class AgentCore:
    def __init__(self, llm_client=None, db_factory=SessionLocal, max_iterations: int = 8):
        self.llm_client = llm_client or GeminiClient()
        self.db_factory = db_factory
        self.max_iterations = max_iterations
        self.memory = MemoryStore()

    def run(self, message: str, session_id: str = "default") -> dict:
        db = self.db_factory()
        memory = self.memory.get(session_id)
        memory_snapshot = memory.snapshot()
        memory.add("user", message)
        messages = [{"role": "system", "content": build_system_prompt(db)}, *memory.messages()]
        used_tools = []
        pending = []
        response = None
        try:
            for _ in range(self.max_iterations):
                response = self.llm_client.complete(messages, TOOL_SCHEMAS)
                calls = response.get("tool_calls", [])
                if not calls:
                    content = response.get("content") or "No recibí una respuesta final del modelo."
                    memory.add("assistant", content)
                    return {"response": content, "tools_used": used_tools, "pending_confirmations": pending}
                assistant_calls = []
                tool_results = []
                for call in calls:
                    name = call["name"]
                    arguments = call.get("arguments", {})
                    result = execute_tool(name, arguments, db=db)
                    used_tools.append(name)
                    action = AgentAction(
                        session_id=session_id,
                        tool=name,
                        input_params=arguments,
                        result=result,
                        required_confirmation=bool(result.get("confirmation_required")),
                    )
                    db.add(action)
                    db.flush()
                    if result.get("confirmation_required"):
                        pending.append({"action_id": action.id, "tool_name": name, "data": result.get("data", {})})
                    assistant_call = {
                        "id": call.get("id", name),
                        "type": "function",
                        "function": {"name": name, "arguments": json.dumps(arguments)},
                    }
                    if call.get("extra_content"):
                        assistant_call["extra_content"] = call["extra_content"]
                    assistant_calls.append(assistant_call)
                    tool_results.append({
                        "role": "tool",
                        "tool_call_id": call.get("id", name),
                        "content": json.dumps(result, ensure_ascii=False),
                    })
                messages.append({"role": "assistant", "tool_calls": assistant_calls})
                messages.extend(tool_results)
            content = "Alcancé el límite de pasos del agente; dejé las acciones pendientes sin ejecutar automáticamente."
            memory.add("assistant", content)
            return {"response": content, "tools_used": used_tools, "pending_confirmations": pending}
        except Exception:
            memory.restore(memory_snapshot)
            raise
        finally:
            db.commit()
            db.close()

    def confirm_action(self, action_id: int, approved: bool) -> dict:
        db = self.db_factory()
        try:
            action = db.get(AgentAction, action_id)
            if action is None:
                raise ValueError("La acción pendiente no existe.")
            if not action.required_confirmation or action.approved is not None:
                raise ValueError("La acción ya fue resuelta o no requiere confirmación.")
            action.approved = approved
            if not approved:
                action.result = {"summary": "La acción fue rechazada por el usuario."}
                db.commit()
                return action.result
            arguments = dict(action.input_params or {})
            result = execute_tool(action.tool, arguments, db=db, confirmed=True)
            action.result = result
            db.commit()
            return result
        finally:
            db.close()


agent_core = AgentCore()