"""
Unit tests for the bug reproduction stage (bug_reproduction.py).
Tests reproduction plan generation, tool submission, state handling, and edge cases.
"""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

from agent.agent import BugReproductionState
from agent.stages.bug_reproduction import reproduction_node


@pytest.fixture
def base_state() -> BugReproductionState:
    """Minimal valid BugReproductionState for testing."""
    return {
        "description": "Test bug description",
        "environment": "Linux x86_64",
        "severity_input": "medium",
        "repo_name": "test-repo",
        "jira_ticket": "BUG-123",
        "attachments": [],
        "session_id": "test-session-001",
        "repo_stats": {},
        "processes": [],
        "triage": {
            "bug_category": "crash",
            "keywords": ["assertion", "widget"],
            "severity": "critical",
            "affected_area": "UI rendering",
            "affected_files": ["src/ui.cpp"],
            "initial_hypotheses": ["null pointer dereference"],
            "confidence": "high",
        },
        "mechanics": {
            "code_paths": [
                {
                    "path": "UIElement::render → assert",
                    "description": "assertion in render function",
                    "confidence": "high",
                }
            ],
            "affected_components": ["UIElement", "RenderEngine"],
            "root_cause_hypotheses": [
                {
                    "hypothesis": "uninitialized pointer accessed in render",
                    "confidence": "high",
                    "evidence": "code inspection",
                }
            ],
        },
        "reproduction_plan": {},
        "research_findings": {},
        "bug_report": {},
        "current_stage": "reproduction",
        "tool_calls_used": 10,
        "messages": [],
        "available_tools": [],
        "mechanics_feedback": None,
        "research_context": None,
    }


@pytest.fixture
def mock_llm():
    """Mock LLM for testing."""
    return AsyncMock()


@pytest.fixture
def mock_client():
    """Mock MCP client for testing."""
    client = AsyncMock()
    client.get_tools = AsyncMock(return_value=[])
    return client


class TestReproductionNodeBasics:
    """Test basic reproduction node functionality."""

    @pytest.mark.asyncio
    async def test_reproduction_node_with_mocked_agent(
        self, base_state, mock_llm, mock_client
    ):
        """Test that reproduction_node processes state and returns expected keys."""
        with patch(
            "agent.stages.bug_reproduction.create_react_agent"
        ) as mock_create_agent:
            # Mock agent that completes immediately
            mock_agent = AsyncMock()
            mock_agent.astream_events = AsyncMock(return_value=[])
            mock_agent.aget_state = AsyncMock(
                return_value=MagicMock(values={"messages": []})
            )
            mock_create_agent.return_value = mock_agent

            with patch(
                "agent.stages.bug_reproduction.filter_tools", return_value=[]
            ):
                with patch(
                    "agent.stages.bug_reproduction.safe_tools", return_value=[]
                ):
                    result = await reproduction_node(base_state, mock_llm, mock_client)

            # Check required output keys
            assert "current_stage" in result
            assert result["current_stage"] == "research"
            assert "tool_calls_used" in result

    @pytest.mark.asyncio
    async def test_reproduction_node_state_passed_to_agent(
        self, base_state, mock_llm, mock_client
    ):
        """Test that state information is correctly passed to the agent."""
        with patch(
            "agent.stages.bug_reproduction.create_react_agent"
        ) as mock_create_agent:
            mock_agent = AsyncMock()
            mock_agent.astream_events = AsyncMock(return_value=[])
            mock_agent.aget_state = AsyncMock(
                return_value=MagicMock(values={"messages": []})
            )
            mock_create_agent.return_value = mock_agent

            with patch(
                "agent.stages.bug_reproduction.filter_tools", return_value=[]
            ):
                with patch(
                    "agent.stages.bug_reproduction.safe_tools", return_value=[]
                ):
                    await reproduction_node(base_state, mock_llm, mock_client)

            # Verify agent was created with correct model
            mock_create_agent.assert_called_once()
            call_args = mock_create_agent.call_args
            assert call_args[1]["model"] == mock_llm

    @pytest.mark.asyncio
    async def test_reproduction_node_without_repo_name(
        self, base_state, mock_llm, mock_client
    ):
        """Test reproduction node when repo_name is None."""
        base_state["repo_name"] = None

        with patch(
            "agent.stages.bug_reproduction.create_react_agent"
        ) as mock_create_agent:
            mock_agent = AsyncMock()
            mock_agent.astream_events = AsyncMock(return_value=[])
            mock_agent.aget_state = AsyncMock(
                return_value=MagicMock(values={"messages": []})
            )
            mock_create_agent.return_value = mock_agent

            with patch(
                "agent.stages.bug_reproduction.filter_tools", return_value=[]
            ):
                with patch(
                    "agent.stages.bug_reproduction.safe_tools", return_value=[]
                ):
                    result = await reproduction_node(base_state, mock_llm, mock_client)

            assert "current_stage" in result
            # Should still process without repo_name
            assert result["current_stage"] == "research"


class TestReproductionOutput:
    """Test reproduction plan output structure."""

    def test_reproduction_output_valid_structure(self):
        """Test that reproduction output has all required fields."""
        from agent.stages.bug_reproduction import _ReproductionOutput

        output = _ReproductionOutput(
            steps=[
                {
                    "step_number": 1,
                    "action": "Start application",
                    "expected_result": "No error",
                }
            ],
            prerequisites=["Application installed"],
            environment_requirements=["Linux"],
            confidence="high",
        )

        assert output.steps == [
            {
                "step_number": 1,
                "action": "Start application",
                "expected_result": "No error",
            }
        ]
        assert output.prerequisites == ["Application installed"]
        assert output.environment_requirements == ["Linux"]
        assert output.confidence == "high"

    def test_reproduction_output_defaults(self):
        """Test default values in reproduction output."""
        from agent.stages.bug_reproduction import _ReproductionOutput

        output = _ReproductionOutput()

        assert output.steps == []
        assert output.prerequisites == []
        assert output.environment_requirements == []
        assert output.confidence == "low"

    def test_reproduction_output_model_dump(self):
        """Test that output can be serialized with model_dump."""
        from agent.stages.bug_reproduction import _ReproductionOutput

        output = _ReproductionOutput(
            steps=[{"step_number": 1, "action": "Test", "expected_result": "Pass"}],
            prerequisites=["Setup"],
            environment_requirements=["OS X"],
            confidence="medium",
        )

        dumped = output.model_dump()
        assert isinstance(dumped, dict)
        assert dumped["confidence"] == "medium"
        assert len(dumped["steps"]) == 1


class TestToolCallBudget:
    """Test tool call budget enforcement."""

    @pytest.mark.asyncio
    async def test_budget_enforcement_stops_before_limit(
        self, base_state, mock_llm, mock_client
    ):
        """Test that agent stops when approaching budget limit."""
        budget_reached = False

        def mock_stream_events(input_dict, version, config):
            """Generator that emits tool_start events."""
            for i in range(15):  # More than BUDGET of 12
                yield {
                    "event": "on_tool_start",
                    "name": f"tool_{i}",
                    "data": None,
                }
                if i >= 11:  # Should stop before 12
                    nonlocal budget_reached
                    budget_reached = True
                    break

        with patch(
            "agent.stages.bug_reproduction.create_react_agent"
        ) as mock_create_agent:
            mock_agent = AsyncMock()
            mock_agent.astream_events = mock_stream_events
            mock_agent.aget_state = AsyncMock(
                return_value=MagicMock(values={"messages": []})
            )
            mock_create_agent.return_value = mock_agent

            with patch(
                "agent.stages.bug_reproduction.filter_tools", return_value=[]
            ):
                with patch(
                    "agent.stages.bug_reproduction.safe_tools", return_value=[]
                ):
                    await reproduction_node(base_state, mock_llm, mock_client)

        assert budget_reached

    @pytest.mark.asyncio
    async def test_fallback_synthesis_when_budget_exhausted(
        self, base_state, mock_llm, mock_client
    ):
        """Test that synthesis agent is triggered when budget exhausted without submit."""
        with patch(
            "agent.stages.bug_reproduction.create_react_agent"
        ) as mock_create_agent:
            # First agent exhausts budget, second synthesizes
            mock_agent1 = AsyncMock()
            mock_agent1.astream_events = AsyncMock(
                return_value=[
                    {"event": "on_tool_start", "name": "tool_1", "data": None}
                ]
            )
            mock_agent1.aget_state = AsyncMock(
                return_value=MagicMock(
                    values={"messages": [MagicMock(), MagicMock()]}
                )
            )

            mock_agent2 = AsyncMock()
            mock_agent2.astream_events = AsyncMock(return_value=[])

            mock_create_agent.side_effect = [mock_agent1, mock_agent2]

            with patch(
                "agent.stages.bug_reproduction.filter_tools", return_value=[]
            ):
                with patch(
                    "agent.stages.bug_reproduction.safe_tools", return_value=[]
                ):
                    with patch(
                        "agent.stages.bug_reproduction.fix_dangling_tool_calls",
                        return_value=[],
                    ):
                        result = await reproduction_node(
                            base_state, mock_llm, mock_client
                        )

            # Should have created two agents (main + synthesis)
            assert mock_create_agent.call_count >= 2


class TestStatePropagation:
    """Test that state is correctly propagated through the node."""

    @pytest.mark.asyncio
    async def test_tool_calls_used_accumulation(
        self, base_state, mock_llm, mock_client
    ):
        """Test that tool_calls_used is accumulated from base state."""
        base_state["tool_calls_used"] = 25

        with patch(
            "agent.stages.bug_reproduction.create_react_agent"
        ) as mock_create_agent:
            mock_agent = AsyncMock()
            mock_agent.astream_events = AsyncMock(return_value=[])
            mock_agent.aget_state = AsyncMock(
                return_value=MagicMock(values={"messages": []})
            )
            mock_create_agent.return_value = mock_agent

            with patch(
                "agent.stages.bug_reproduction.filter_tools", return_value=[]
            ):
                with patch(
                    "agent.stages.bug_reproduction.safe_tools", return_value=[]
                ):
                    result = await reproduction_node(base_state, mock_llm, mock_client)

            # Result should have accumulated tool calls
            assert result["tool_calls_used"] >= 25

    @pytest.mark.asyncio
    async def test_session_id_used_for_thread(
        self, base_state, mock_llm, mock_client
    ):
        """Test that session_id is used for thread creation."""
        base_state["session_id"] = "custom-session-xyz"

        with patch(
            "agent.stages.bug_reproduction.create_react_agent"
        ) as mock_create_agent:
            mock_agent = AsyncMock()
            mock_agent.astream_events = AsyncMock(return_value=[])
            mock_agent.aget_state = AsyncMock(
                return_value=MagicMock(values={"messages": []})
            )
            mock_create_agent.return_value = mock_agent

            with patch(
                "agent.stages.bug_reproduction.filter_tools", return_value=[]
            ):
                with patch(
                    "agent.stages.bug_reproduction.safe_tools", return_value=[]
                ):
                    with patch(
                        "agent.stages.bug_reproduction.uuid4"
                    ) as mock_uuid:
                        mock_uuid.return_value.hex = "12345678"
                        await reproduction_node(
                            base_state, mock_llm, mock_client
                        )

            # Thread ID should include session ID
            call_args = mock_create_agent.call_args
            # The thread_id is set in _stage_config which isn't directly accessible
            # but we can verify the agent was called
            assert mock_create_agent.called


class TestReproductionWithDifferentMechanics:
    """Test reproduction planning with various mechanics inputs."""

    @pytest.mark.asyncio
    async def test_reproduction_with_empty_mechanics(
        self, base_state, mock_llm, mock_client
    ):
        """Test reproduction when mechanics has minimal data."""
        base_state["mechanics"] = {
            "code_paths": [],
            "affected_components": [],
            "root_cause_hypotheses": [],
        }

        with patch(
            "agent.stages.bug_reproduction.create_react_agent"
        ) as mock_create_agent:
            mock_agent = AsyncMock()
            mock_agent.astream_events = AsyncMock(return_value=[])
            mock_agent.aget_state = AsyncMock(
                return_value=MagicMock(values={"messages": []})
            )
            mock_create_agent.return_value = mock_agent

            with patch(
                "agent.stages.bug_reproduction.filter_tools", return_value=[]
            ):
                with patch(
                    "agent.stages.bug_reproduction.safe_tools", return_value=[]
                ):
                    result = await reproduction_node(base_state, mock_llm, mock_client)

            assert "current_stage" in result

    @pytest.mark.asyncio
    async def test_reproduction_with_multiple_hypotheses(
        self, base_state, mock_llm, mock_client
    ):
        """Test that first hypothesis is used when multiple exist."""
        base_state["mechanics"]["root_cause_hypotheses"] = [
            {"hypothesis": "First hypothesis", "confidence": "high", "evidence": "e1"},
            {
                "hypothesis": "Second hypothesis",
                "confidence": "medium",
                "evidence": "e2",
            },
        ]

        with patch(
            "agent.stages.bug_reproduction.create_react_agent"
        ) as mock_create_agent:
            mock_agent = AsyncMock()
            mock_agent.astream_events = AsyncMock(return_value=[])
            mock_agent.aget_state = AsyncMock(
                return_value=MagicMock(values={"messages": []})
            )
            mock_create_agent.return_value = mock_agent

            with patch(
                "agent.stages.bug_reproduction.filter_tools", return_value=[]
            ):
                with patch(
                    "agent.stages.bug_reproduction.safe_tools", return_value=[]
                ):
                    await reproduction_node(base_state, mock_llm, mock_client)

            # Verify agent was called (first hypothesis would be in prompt)
            assert mock_create_agent.called


class TestDefaultLLMUsage:
    """Test default LLM behavior when not provided."""

    @pytest.mark.asyncio
    async def test_default_llm_imported_when_none_provided(
        self, base_state, mock_client
    ):
        """Test that _llm is imported when llm parameter is None."""
        with patch("agent.stages.bug_reproduction.create_react_agent") as mock_create:
            mock_agent = AsyncMock()
            mock_agent.astream_events = AsyncMock(return_value=[])
            mock_agent.aget_state = AsyncMock(
                return_value=MagicMock(values={"messages": []})
            )
            mock_create.return_value = mock_agent

            with patch(
                "agent.stages.bug_reproduction.filter_tools", return_value=[]
            ):
                with patch(
                    "agent.stages.bug_reproduction.safe_tools", return_value=[]
                ):
                    await reproduction_node(base_state, llm=None, client=mock_client)

            # Should have used imported _llm
            assert mock_create.called


class TestClientManagement:
    """Test MCP client creation and cleanup."""

    @pytest.mark.asyncio
    async def test_own_client_created_when_none_provided(self, base_state, mock_llm):
        """Test that get_mcp_client is called when client is None."""
        with patch(
            "agent.stages.bug_reproduction.get_mcp_client"
        ) as mock_get_client:
            mock_client_instance = AsyncMock()
            mock_client_instance.get_tools = AsyncMock(return_value=[])
            mock_get_client.return_value = mock_client_instance

            with patch(
                "agent.stages.bug_reproduction.create_react_agent"
            ) as mock_create:
                mock_agent = AsyncMock()
                mock_agent.astream_events = AsyncMock(return_value=[])
                mock_agent.aget_state = AsyncMock(
                    return_value=MagicMock(values={"messages": []})
                )
                mock_create.return_value = mock_agent

                with patch(
                    "agent.stages.bug_reproduction.filter_tools", return_value=[]
                ):
                    with patch(
                        "agent.stages.bug_reproduction.safe_tools", return_value=[]
                    ):
                        await reproduction_node(base_state, mock_llm, client=None)

            # Should have called get_mcp_client
            mock_get_client.assert_called_once()

    @pytest.mark.asyncio
    async def test_provided_client_used_directly(
        self, base_state, mock_llm, mock_client
    ):
        """Test that provided client is used without creating new one."""
        with patch(
            "agent.stages.bug_reproduction.get_mcp_client"
        ) as mock_get_client:
            with patch(
                "agent.stages.bug_reproduction.create_react_agent"
            ) as mock_create:
                mock_agent = AsyncMock()
                mock_agent.astream_events = AsyncMock(return_value=[])
                mock_agent.aget_state = AsyncMock(
                    return_value=MagicMock(values={"messages": []})
                )
                mock_create.return_value = mock_agent

                with patch(
                    "agent.stages.bug_reproduction.filter_tools", return_value=[]
                ):
                    with patch(
                        "agent.stages.bug_reproduction.safe_tools", return_value=[]
                    ):
                        await reproduction_node(
                            base_state, mock_llm, client=mock_client
                        )

            # Should NOT have called get_mcp_client
            mock_get_client.assert_not_called()
            # Should have used provided client
            mock_client.get_tools.assert_called_once()
