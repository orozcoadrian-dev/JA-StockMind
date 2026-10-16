from __future__ import annotations


class ConversationMemory:
    def __init__(self, max_messages: int = 20):
        self.max_messages = max_messages
        self._messages: list[dict] = []
        self._summary = ""

    def add(self, role: str, content: str, **extra) -> None:
        self._messages.append({"role": role, "content": content, **extra})
        self._compact()

    def _compact(self) -> None:
        if len(self._messages) <= self.max_messages:
            return
        removed = self._messages[:-self.max_messages]
        self._summary = " | ".join(f"{item['role']}: {str(item.get('content', ''))[:160]}" for item in removed[-6:])
        self._messages = self._messages[-self.max_messages:]

    def messages(self) -> list[dict]:
        if not self._summary:
            return list(self._messages)
        return [{"role": "system", "content": f"Resumen de conversación anterior: {self._summary}"}, *self._messages]


class MemoryStore:
    def __init__(self, max_messages: int = 20):
        self.max_messages = max_messages
        self._sessions: dict[str, ConversationMemory] = {}

    def get(self, session_id: str) -> ConversationMemory:
        if session_id not in self._sessions:
            self._sessions[session_id] = ConversationMemory(self.max_messages)
        return self._sessions[session_id]