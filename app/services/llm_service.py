import httpx
from app.config import settings
from app.schemas import FactExtractionOutput, ExtractedFact, MessageTurn, ContradictionDecision
from app.models import Memory

class LLMService:
    def __init__(self):
        self.http_client = httpx.AsyncClient(base_url=settings.OLLAMA_BASE_URL, timeout=settings.LLM_TIMEOUT_SECONDS)

    async def generate_embedding(self, text: str) -> list[float]:
        res = await self.http_client.post("/api/embed", json={
            "model": settings.EMBEDDING_MODEL,
            "input": text
        })
        res.raise_for_status()
        emb_data = res.json().get("embeddings", [])
        if not emb_data or len(emb_data[0]) != settings.EMBEDDING_DIMENSIONS:
            raise ValueError(f"Embedding length mismatch. Expected {settings.EMBEDDING_DIMENSIONS}")
        return emb_data[0]

    async def extract_salient_facts(self, messages: list[MessageTurn]) -> list[ExtractedFact]:
        system_prompt = """Extract salient, persistent facts, user preferences, episodic events, procedures, or tasks.
You must resolve coreferences and pronouns strictly to explicit entity names.
Classify each fact strictly into one MemoryType:
- SEMANTIC: General knowledge or persistent facts.
- PREFERENCE: User likes, dislikes, and constraints.
- EPISODIC: Specific events or experiences tied to time/context.
- PROCEDURAL: Step-by-step instructions or methods.
- TASK: Actionable goals or statuses.
Score importance (0.0 to 1.0, where 0.0=trivial chatter, 1.0=critical constraint/identity) and confidence (0.0 to 1.0, where 0.0=speculative/implied, 1.0=explicitly stated)."""

        user_content = "\n".join([f"{m.role}: {m.content}" for m in messages])
        
        res = await self.http_client.post("/api/chat", json={
            "model": settings.EXTRACTION_MODEL,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_content}
            ],
            "stream": False,
            "options": {"temperature": 0.0},
            "format": FactExtractionOutput.model_json_schema()
        })
        res.raise_for_status()
        out_content = res.json()["message"]["content"]
        return FactExtractionOutput.model_validate_json(out_content).facts

    async def evaluate_contradiction(self, new_fact: ExtractedFact, candidates: list[Memory]) -> ContradictionDecision:
        system_prompt = """Evaluate if the new fact contradicts or updates any candidate memories.
Decision Criteria (Action):
- ADD: The new fact introduces completely new, orthogonal information not covered by any candidate.
- UPDATE: The new fact directly contradicts, corrects, or updates the temporal state of one or more candidates. You MUST copy the exact candidate UUIDs into target_memory_ids.
- NONE: The new fact is redundant or a duplicate of an existing candidate. You MUST copy the exact matched candidate UUID into target_memory_ids.
CRITICAL: Never fabricate UUIDs. Use ONLY the exact UUIDs provided in the Candidates list."""

        c_lines = [f"ID: {c.id} | Content: {c.content} | Type: {c.memory_type} | Valid From: {c.valid_from}" for c in candidates]
        cand_str = "\n".join(c_lines)
        user_content = f"New Fact: {new_fact.content}\nCandidates:\n{cand_str}"
        
        res = await self.http_client.post("/api/chat", json={
            "model": settings.EXTRACTION_MODEL,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_content}
            ],
            "stream": False,
            "options": {"temperature": 0.0},
            "format": ContradictionDecision.model_json_schema()
        })
        res.raise_for_status()
        out_content = res.json()["message"]["content"]
        return ContradictionDecision.model_validate_json(out_content)

llm_service = LLMService()
