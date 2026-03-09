import pytest
import asyncio
from unittest.mock import MagicMock, patch
from dataclasses import dataclass

import veritas.client
from veritas.sinks import BaseSink
from veritas.core import set_default_sink

@dataclass
class UsageObj:
    input_tokens: int
    output_tokens: int

@dataclass
class FakeMessagesResponse:
    usage: UsageObj

class MockSink(BaseSink):
    def __init__(self):
        self.events = []
    
    def emit(self, event):
        self.events.append(event)

class MockSyncClient:
    def __init__(self):
        self.messages = MagicMock()
        self.messages.create.return_value = FakeMessagesResponse(UsageObj(input_tokens=10, output_tokens=20))

class MockAsyncClient:
    def __init__(self):
        self.messages = MagicMock()
        
        async def mock_create(*args, **kwargs):
            return FakeMessagesResponse(UsageObj(input_tokens=50, output_tokens=100))
            
        self.messages.create = mock_create

def test_proxy_sync_success_and_cost_calculation():
    """Verify that the wrapper correctly extracts tokens and intercepts the call on a Sync client."""
    mock_sink = MockSink()
    set_default_sink(mock_sink)
    
    underlying = MockSyncClient()
    proxy = veritas.client.Anthropic(underlying, feature_name="test_sync")
    
    # Run interception
    res = proxy.messages.create(model="claude-3-haiku-20240307", messages=[{"role": "user", "content": "hello"}])
    
    assert res.usage.input_tokens == 10
    
    # Assert background event was logged
    assert len(mock_sink.events) == 1
    event = mock_sink.events[0]
    
    assert event.feature == "test_sync"
    assert event.tokens_in == 10
    assert event.tokens_out == 20
    assert event.model == "claude-3-haiku-20240307"
    assert event.cost_usd > 0.0

@pytest.mark.asyncio
async def test_proxy_async_success():
    """Verify that the wrapper fully supports AsyncAnthropic by preserving the coroutine."""
    mock_sink = MockSink()
    set_default_sink(mock_sink)
    
    underlying = MockAsyncClient()
    proxy = veritas.client.Anthropic(underlying, feature_name="test_async")
    
    # Run interception
    res = await proxy.messages.create(model="claude-3-haiku-20240307", messages=[{"role": "user", "content": "hello async"}])
    
    assert res.usage.input_tokens == 50
    assert len(mock_sink.events) == 1
    assert mock_sink.events[0].feature == "test_async"

def test_proxy_exception_passthrough():
    """CRITICAL: The wrapper must NEVER swallow an error from the underlying SDK."""
    mock_sink = MockSink()
    set_default_sink(mock_sink)
    
    underlying = MockSyncClient()
    # Force the real API call to throw an exception (e.g. 500 error, lack of credits)
    underlying.messages.create.side_effect = ValueError("Anthropic API is down!")
    
    proxy = veritas.client.Anthropic(underlying, feature_name="test_crash")
    
    with pytest.raises(ValueError, match="Anthropic API is down!"):
        proxy.messages.create(model="claude-3-haiku-20240307", messages=[])
        
    # The event is not successfully completed, so we expect nothing. (Or a failed event depending on implementation. In our current client, it skips track_event).
    assert len(mock_sink.events) == 0
