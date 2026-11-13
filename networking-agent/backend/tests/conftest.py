"""Shared test helpers: a scripted chat model that needs no network."""

from collections.abc import Sequence
from typing import Any

import pytest
from langchain_core.callbacks import CallbackManagerForLLMRun
from langchain_core.language_models import BaseChatModel
from langchain_core.messages import AIMessage, BaseMessage
from langchain_core.outputs import ChatGeneration, ChatResult
from langchain_core.runnables import RunnableLambda
from pydantic import BaseModel


class ScriptedChatModel(BaseChatModel):
    """Returns `responses` in order; `structured` is returned by with_structured_output."""

    responses: list[AIMessage] = []
    structured: Any = None
    calls: list[list[BaseMessage]] = []
    structured_calls: list[Any] = []

    @property
    def _llm_type(self) -> str:
        return "scripted"

    def _generate(
        self,
        messages: list[BaseMessage],
        stop: list[str] | None = None,
        run_manager: CallbackManagerForLLMRun | None = None,
        **kwargs: Any,
    ) -> ChatResult:
        self.calls.append(list(messages))
        message = self.responses.pop(0) if self.responses else AIMessage(content="Done.")
        return ChatResult(generations=[ChatGeneration(message=message)])

    def bind_tools(self, tools: Sequence[Any], **kwargs: Any) -> "ScriptedChatModel":
        return self

    def with_structured_output(self, schema: type[BaseModel], **kwargs: Any):
        def run(messages: Any) -> Any:
            self.structured_calls.append({"schema": schema, "kwargs": kwargs, "input": messages})
            return self.structured

        return RunnableLambda(run)


@pytest.fixture
def scripted_model():
    def make(responses: list[AIMessage] | None = None, structured: Any = None):
        return ScriptedChatModel(
            responses=list(responses or []), structured=structured, calls=[], structured_calls=[]
        )

    return make
