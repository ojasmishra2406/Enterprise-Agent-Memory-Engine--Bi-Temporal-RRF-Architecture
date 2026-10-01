import pytest
from app.services.llm_service import llm_service
from app.schemas import ExtractedFact

# ==============================================================================
# FAST LOCAL ITERATION FIXTURE
# ==============================================================================
# Use this fixture when Docker-to-Windows networking for Ollama is down, or 
# when you want to run the test suite instantly without waiting for local LLM 
# inference (which takes ~4+ minutes on a laptop).
#
# IMPORTANT: This is NOT an autouse=True fixture. 
# To use it, you must explicitly import it or pass it to your test function, 
# or temporarily add it to your conftest.py's pytest_plugins.
#
# Usage:
#   def test_my_function(mock_llm_network):
#       ...
# ==============================================================================

@pytest.fixture
def mock_llm_network(mocker):
    async def mock_extract(messages):
        content = messages[-1].content
        return [ExtractedFact(
            content=content, 
            memory_type="SEMANTIC", 
            importance=0.8, 
            confidence=0.9, 
            reasoning="mock"
        )]
        
    async def mock_embed(text):
        return [0.1] * 1024
        
    async def mock_eval(fact, candidate_list):
        from app.schemas import ContradictionDecision, ResolutionAction
        # If it's the exact same, we already handled it. If not, just mock an UPDATE for testing lineage.
        return ContradictionDecision(
            action=ResolutionAction.UPDATE,
            target_memory_ids=[str(candidate_list[0].id)],
            reason="mock eval",
            updated_content=fact.content
        )
        
    mocker.patch.object(llm_service, "extract_salient_facts", side_effect=mock_extract)
    mocker.patch.object(llm_service, "generate_embedding", side_effect=mock_embed)
    mocker.patch.object(llm_service, "evaluate_contradiction", side_effect=mock_eval)
