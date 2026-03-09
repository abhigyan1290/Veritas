import time
import inspect
from datetime import datetime, timezone
import os

from veritas.core import CostEvent
from veritas.pricing import compute_cost

class Anthropic:
    """
    Veritas Proxy for the Anthropic Python SDK.
    
    Wraps an initialized `anthropic.Anthropic` or `anthropic.AsyncAnthropic` client.
    Intercepts exactly one thing: `messages.create`.
    Calculates cost, metrics, and emits an event in the background silently.
    Passes all exceptions perfectly through to the calling application.
    """
    def __init__(self, client, feature_name: str = "default_feature"):
        self._client = client
        self._feature_name = feature_name
        
        # We must mirror the `messages` attribute so `client.messages.create` works.
        self.messages = _MessagesProxy(self._client.messages, self._feature_name)

    def __getattr__(self, name):
        # Forward any other attribute access (like .models, .completions) directly to the underlying client.
        return getattr(self._client, name)

class _MessagesProxy:
    def __init__(self, original_messages, feature_name: str):
        self._original_messages = original_messages
        self._feature_name = feature_name

    def create(self, *args, **kwargs):
        """Intercept the messages.create call to capture metrics."""
        from veritas.utils import get_current_commit_hash
        
        start_time = time.time()
        
        # If the underlying client is AsyncAnthropic, `create` is a coroutine.
        if inspect.iscoroutinefunction(self._original_messages.create):
            return self._async_create(start_time, *args, **kwargs)
        else:
            return self._sync_create(start_time, *args, **kwargs)

    def _sync_create(self, start_time: float, *args, **kwargs):
        from veritas.utils import get_current_commit_hash
        
        try:
            response = self._original_messages.create(*args, **kwargs)
            latency_ms = (time.time() - start_time) * 1000
            
            # Fire and forget background event tracking
            self._track_event(response, kwargs.get("model", "unknown"), latency_ms, get_current_commit_hash())
            return response
        except Exception as e:
            # We never swallow errors from the real API call.
            raise e

    async def _async_create(self, start_time: float, *args, **kwargs):
        from veritas.utils import get_current_commit_hash
        
        try:
            response = await self._original_messages.create(*args, **kwargs)
            latency_ms = (time.time() - start_time) * 1000
            
            # Fire and forget background event tracking
            self._track_event(response, kwargs.get("model", "unknown"), latency_ms, get_current_commit_hash())
            return response
        except Exception as e:
            # We never swallow errors from the real API call.
            raise e

    def _track_event(self, response, model: str, latency_ms: float, commit_hash: str):
        try:
            # Safely extract token usage
            usage = getattr(response, "usage", None)
            if not usage:
                return
                
            tokens_in = getattr(usage, "input_tokens", 0)
            tokens_out = getattr(usage, "output_tokens", 0)
            cache_creation = getattr(usage, "cache_creation_input_tokens", 0) or 0
            cache_read = getattr(usage, "cache_read_input_tokens", 0) or 0
            
            # Compute Cost using Veritas Engine
            calculated_cost_tuple = compute_cost(
                model=model,
                tokens_in=tokens_in,
                tokens_out=tokens_out,
                cache_creation_tokens=cache_creation,
                cache_read_tokens=cache_read
            )
            cost = calculated_cost_tuple[0]
            
            event = CostEvent(
                feature=self._feature_name,
                model=model,
                code_version=commit_hash,
                tokens_in=tokens_in,
                tokens_out=tokens_out,
                cache_creation_tokens=cache_creation,
                cache_read_tokens=cache_read,
                latency_ms=latency_ms,
                cost_usd=cost,
                timestamp=datetime.now(timezone.utc).isoformat()
            )
            
            from veritas.core import get_default_sink
            sink = get_default_sink()
            if sink:
                sink.emit(event)
                
        except Exception as e:
            # If our internal metric parsing fails for ANY reason, we swallow it silently.
            # Veritas must never crash the host application.
            pass
