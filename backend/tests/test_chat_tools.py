"""Tests for the chat tool registry — guards schema↔handler drift.

The individual tool functions are thin wrappers over services covered
elsewhere; these tests verify the contract handed to Claude is well-formed and
every advertised tool has a callable handler.
"""
import inspect

from app.services import chat_tools


class TestToolRegistry:
    def test_every_tool_has_a_handler(self):
        for tool in chat_tools.TOOLS:
            assert tool["name"] in chat_tools.HANDLERS, tool["name"]

    def test_no_orphan_handlers(self):
        tool_names = {t["name"] for t in chat_tools.TOOLS}
        assert set(chat_tools.HANDLERS) == tool_names

    def test_schemas_are_well_formed(self):
        for tool in chat_tools.TOOLS:
            assert tool["name"]
            assert tool["description"]
            schema = tool["input_schema"]
            assert schema["type"] == "object"
            assert "properties" in schema

    def test_handlers_are_async_and_accept_db(self):
        for name, handler in chat_tools.HANDLERS.items():
            assert inspect.iscoroutinefunction(handler), name
            params = inspect.signature(handler).parameters
            assert "db" in params, name

    def test_required_args_exist_as_handler_params(self):
        for tool in chat_tools.TOOLS:
            handler = chat_tools.HANDLERS[tool["name"]]
            params = inspect.signature(handler).parameters
            for req in tool["input_schema"].get("required", []):
                assert req in params, f"{tool['name']}.{req}"

    def test_schema_properties_are_known_handler_params(self):
        # Every property the model can pass must map to a real handler argument.
        for tool in chat_tools.TOOLS:
            handler = chat_tools.HANDLERS[tool["name"]]
            params = set(inspect.signature(handler).parameters)
            for prop in tool["input_schema"]["properties"]:
                assert prop in params, f"{tool['name']}.{prop}"
