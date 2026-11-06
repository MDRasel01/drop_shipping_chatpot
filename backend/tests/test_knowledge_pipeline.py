import pytest
from app.modules.knowledge.service import KnowledgeService
from app.modules.knowledge.schemas import InstructionCreateRequest


def test_embedding_generation_dimension_and_range():
    svc = KnowledgeService()
    vector = svc._generate_mock_embedding("Company return policy: 30 days money-back guarantee.")

    assert len(vector) == 768
    assert all(isinstance(v, float) for v in vector)
    assert all(0.0 <= v <= 1.0 for v in vector)


def test_embedding_determinism():
    svc = KnowledgeService()
    text = "Identical text should yield identical vector."
    v1 = svc._generate_mock_embedding(text)
    v2 = svc._generate_mock_embedding(text)

    assert v1 == v2


def test_instruction_schema_validation():
    req = InstructionCreateRequest(
        title="Refund Guidelines",
        content="Items returned within 30 days are eligible for a 100% full refund with original receipt."
    )
    assert req.title == "Refund Guidelines"
    assert len(req.content) > 10

