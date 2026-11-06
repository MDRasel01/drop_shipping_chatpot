import uuid
import pytest
from app.modules.saas.service import saas_service
from app.modules.saas.schemas import TenantRegisterRequest
from app.modules.knowledge.service import knowledge_service
from app.modules.knowledge.schemas import InstructionCreateRequest
from app.modules.support.service import support_service


class InMemoryMockAsyncSession:
    """Mock database session managing in-memory entity tables for end-to-end workflow verification."""

    def __init__(self):
        self.tables = {
            "tenants": {},
            "users": {},
            "settings": {},
            "subscriptions": {},
            "usage": {},
            "instructions": {},
            "chunks": {},
            "questions": {},
            "answers": {},
            "widgets": {},
            "agents": {},
            "conversations": {},
            "messages": {}
        }

    def add(self, item):
        name = item.__class__.__name__
        if "TenantSetting" in name:
            self.tables["settings"][item.tenant_id] = item
        elif "Tenant" in name:
            self.tables["tenants"][item.id] = item
        elif "User" in name:
            self.tables["users"][item.id] = item
        elif "Subscription" in name:
            self.tables["subscriptions"][item.tenant_id] = item
        elif "UsageCounter" in name:
            self.tables["usage"][item.tenant_id] = item
        elif "Instruction" in name:
            self.tables["instructions"][item.id] = item
        elif "KnowledgeChunk" in name:
            self.tables["chunks"][item.id] = item
        elif "CustomQuestion" in name:
            self.tables["questions"][item.id] = item
        elif "ApprovedAnswer" in name:
            self.tables["answers"][item.id] = item
        elif "WidgetInstallation" in name:
            self.tables["widgets"][item.public_key] = item
        elif "AIAgent" in name:
            self.tables["agents"][item.id] = item
        elif "Conversation" in name:
            self.tables["conversations"][item.id] = item
        elif "Message" in name:
            self.tables["messages"][item.id] = item

    async def flush(self):
        pass

    async def execute(self, stmt):
        class MockResult:
            def __init__(self, data):
                self._data = data

            def scalar_one_or_none(self):
                return self._data[0] if self._data else None

            def scalar_one(self):
                return self._data[0]

            def scalars(self):
                class MockScalars:
                    def __init__(self, items):
                        self.items = items

                    def all(self):
                        return self.items

                    def first(self):
                        return self.items[0] if self.items else None
                return MockScalars(self._data)

        sql_str = str(stmt).lower()
        if "from users" in sql_str:
            return MockResult(list(self.tables["users"].values()))
        if "from tenants" in sql_str:
            return MockResult(list(self.tables["tenants"].values()))
        if "from usage_counters" in sql_str:
            return MockResult(list(self.tables["usage"].values()))
        if "from widget_installations" in sql_str:
            return MockResult(list(self.tables["widgets"].values()))
        if "from ai_agents" in sql_str:
            return MockResult(list(self.tables["agents"].values()))
        if "from instructions" in sql_str:
            return MockResult(list(self.tables["instructions"].values()))
        if "from knowledge_chunks" in sql_str:
            return MockResult(list(self.tables["chunks"].values()))
        if "from custom_questions" in sql_str:
            return MockResult(list(self.tables["questions"].values()))

        return MockResult([])


@pytest.mark.asyncio
async def test_full_mvp_12_step_workflow():
    db = InMemoryMockAsyncSession()

    # Step 1: Company Registration
    reg_req = TenantRegisterRequest(
        company_name="Apex Global Logistics",
        admin_name="Sarah Connor",
        email="sarah@apex-logistics.com",
        password="SafePassword123!"
    )
    tenant, user, token = await saas_service.register_company(db, reg_req)

    assert tenant.name == "Apex Global Logistics"
    assert user.role == "Company Admin"
    assert token is not None

    # Step 2: Validate Initial Usage Quota
    quota = await saas_service.validate_quota(db, tenant.id)
    assert quota.allowed is True
    assert quota.current_used == 0
    assert quota.max_limit == 10000

    # Step 3: Create Company Instruction
    inst_req = InstructionCreateRequest(
        title="Delivery and Return Policy",
        content="Standard deliveries arrive within 3-5 business days.\n\nReturns are accepted within 30 days of delivery with original receipt."
    )
    instruction = await knowledge_service.create_instruction(db, tenant.id, inst_req)
    assert instruction.status == "draft"

    # Step 4: Publish Instruction (Chunking + 768d Vector Embeddings)
    pub_inst = await knowledge_service.publish_instruction(db, tenant.id, instruction.id)
    assert pub_inst.status == "published"
    assert len(db.tables["chunks"]) == 2  # Two paragraphs chunked

    # Step 5: Configure AI Agent and Widget Installation
    widget = await support_service.get_or_create_widget(db, tenant.id)
    assert widget.public_key.startswith("pk_live_")

    agent = await support_service.get_or_create_default_agent(db, tenant.id)
    assert agent.status == "online"

    # Step 6: Customer Website Visitor Initiates Chat Session
    session_res = await support_service.initialize_visitor_session(
        db=db,
        public_key=widget.public_key,
        origin="https://apex-logistics.com",
        visitor_fingerprint="visitor_browser_001"
    )
    assert session_res.session_token is not None
    assert session_res.tenant_id == tenant.id

    # Step 7 & 8 & 9: Customer Asks Grounded Question (RAG Retrieval + AI Response + Usage increment)
    chat_turn1 = await support_service.process_chat_message(
        db=db,
        tenant_id=tenant.id,
        conversation_id=session_res.session_id,
        message_text="How many days do I have for returns?"
    )
    assert chat_turn1.is_escalated is False
    assert "30 days" in chat_turn1.content
    assert chat_turn1.tokens_consumed > 0

    # Step 10: Customer Asks Unknown Question (< 0.65 similarity -> Escalation to custom_questions)
    chat_turn2 = await support_service.process_chat_message(
        db=db,
        tenant_id=tenant.id,
        conversation_id=session_res.session_id,
        message_text="Do you provide refrigerated storage for frozen seafood?"
    )
    assert chat_turn2.is_escalated is True
    assert "I do not have enough verified information" in chat_turn2.content
    assert len(db.tables["questions"]) == 1

    # Step 11: Admin Reviews and Submits Approved Answer (Auto-vectorized into KnowledgeBase)
    unanswered_q = list(db.tables["questions"].values())[0]
    assert unanswered_q.status == "UNANSWERED"

    approved_ans = await knowledge_service.approve_answer(
        db=db,
        tenant_id=tenant.id,
        question_id=unanswered_q.id,
        answer_text="Yes, we operate temperature-controlled refrigerated facilities for frozen seafood at -18°C.",
        approved_by="Sarah Connor"
    )
    assert unanswered_q.status == "ANSWERED"
    assert approved_ans.answer_text.startswith("Yes, we operate temperature-controlled")
    assert len(db.tables["chunks"]) == 3  # New approved answer chunk added to vector knowledge!

    # Step 12: Subsequent Customer Query Now Matches Newly Approved Knowledge!
    chat_turn3 = await support_service.process_chat_message(
        db=db,
        tenant_id=tenant.id,
        conversation_id=session_res.session_id,
        message_text="Can you store frozen seafood in refrigerated warehouses?"
    )
    assert chat_turn3.is_escalated is False
    assert "frozen seafood" in chat_turn3.content

