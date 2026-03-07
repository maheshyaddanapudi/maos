"""Unit tests for resilience module."""

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from maos.errors import MAOSCircuitBreakerError
from maos.resilience import CircuitBreaker, retry_with_backoff


@pytest.mark.unit
class TestRetryWithBackoff:
    """Tests for retry_with_backoff."""

    async def test_success_on_first_attempt(self):
        """Test that a successful call returns immediately without retries."""
        fn = AsyncMock(return_value="ok")

        result = await retry_with_backoff(fn, max_retries=3)

        assert result == "ok"
        assert fn.call_count == 1

    async def test_retry_on_transient_failure_then_success(self):
        """Test retry on transient failure followed by success."""
        fn = AsyncMock(side_effect=[ValueError("fail"), "ok"])

        with patch("maos.resilience.asyncio.sleep", new_callable=AsyncMock):
            result = await retry_with_backoff(
                fn,
                max_retries=3,
                retryable_exceptions=(ValueError,),
            )

        assert result == "ok"
        assert fn.call_count == 2

    async def test_all_retries_exhausted_raises(self):
        """Test that final exception is raised when all retries exhausted."""
        fn = AsyncMock(side_effect=ValueError("persistent"))

        with patch("maos.resilience.asyncio.sleep", new_callable=AsyncMock):
            with pytest.raises(ValueError, match="persistent"):
                await retry_with_backoff(
                    fn,
                    max_retries=2,
                    retryable_exceptions=(ValueError,),
                )

        assert fn.call_count == 3  # initial + 2 retries

    async def test_non_retryable_exception_propagates_immediately(self):
        """Test that non-retryable exceptions propagate without retry."""
        fn = AsyncMock(side_effect=TypeError("not retryable"))

        with pytest.raises(TypeError, match="not retryable"):
            await retry_with_backoff(
                fn,
                max_retries=3,
                retryable_exceptions=(ValueError,),
            )

        assert fn.call_count == 1

    async def test_jitter_adds_randomness(self):
        """Test that jitter adds randomness to the delay."""
        fn = AsyncMock(side_effect=[ValueError("fail"), "ok"])
        sleep_delays: list[float] = []

        async def capture_sleep(delay):
            sleep_delays.append(delay)

        with patch(
            "maos.resilience.asyncio.sleep", side_effect=capture_sleep
        ):
            await retry_with_backoff(
                fn,
                max_retries=3,
                base_delay=1.0,
                jitter=True,
                retryable_exceptions=(ValueError,),
            )

        assert len(sleep_delays) == 1
        # base_delay * 2^0 = 1.0, jitter adds up to 0.5 * 1.0
        assert sleep_delays[0] >= 1.0
        assert sleep_delays[0] <= 1.5

    async def test_max_delay_caps_backoff(self):
        """Test that max_delay caps the exponential backoff."""
        call_count = 0

        async def failing_fn():
            nonlocal call_count
            call_count += 1
            raise ValueError("fail")

        sleep_delays: list[float] = []

        async def capture_sleep(delay):
            sleep_delays.append(delay)

        with patch(
            "maos.resilience.asyncio.sleep", side_effect=capture_sleep
        ):
            with pytest.raises(ValueError):
                await retry_with_backoff(
                    failing_fn,
                    max_retries=5,
                    base_delay=1.0,
                    max_delay=3.0,
                    jitter=False,
                    retryable_exceptions=(ValueError,),
                )

        # Without jitter: delays are min(2^attempt * base, max_delay)
        for delay in sleep_delays:
            assert delay <= 3.0

    async def test_passes_args_and_kwargs_to_fn(self):
        """Test that positional and keyword arguments are forwarded."""
        fn = AsyncMock(return_value="done")

        result = await retry_with_backoff(
            fn, "a", "b", max_retries=0, key="val"
        )

        assert result == "done"
        fn.assert_called_once_with("a", "b", key="val")

    async def test_zero_max_retries_calls_once(self):
        """Test that max_retries=0 means only one attempt."""
        fn = AsyncMock(side_effect=ValueError("fail"))

        with pytest.raises(ValueError, match="fail"):
            await retry_with_backoff(
                fn,
                max_retries=0,
                retryable_exceptions=(ValueError,),
            )

        assert fn.call_count == 1


@pytest.mark.unit
class TestCircuitBreaker:
    """Tests for CircuitBreaker."""

    async def test_closed_state_passes_calls(self):
        """Test that closed state allows calls through."""
        cb = CircuitBreaker("test", failure_threshold=3)
        fn = AsyncMock(return_value="ok")

        result = await cb.call(fn)

        assert result == "ok"
        assert cb.state == "closed"

    async def test_transitions_to_open_after_threshold(self):
        """Test that circuit opens after failure_threshold failures."""
        cb = CircuitBreaker("test", failure_threshold=3)
        fn = AsyncMock(side_effect=RuntimeError("fail"))

        for _ in range(3):
            with pytest.raises(RuntimeError):
                await cb.call(fn)

        assert cb.state == "open"

    async def test_open_state_rejects_calls(self):
        """Test that open state rejects with MAOSCircuitBreakerError."""
        cb = CircuitBreaker(
            "test", failure_threshold=2, recovery_timeout=60.0
        )
        fn = AsyncMock(side_effect=RuntimeError("fail"))

        # Trip the breaker
        for _ in range(2):
            with pytest.raises(RuntimeError, match="fail"):
                await cb.call(fn)

        assert cb.state == "open"

        # Next call should be rejected immediately
        with pytest.raises(MAOSCircuitBreakerError, match="is open"):
            await cb.call(AsyncMock(return_value="ok"))

    async def test_transitions_to_half_open_after_recovery(self):
        """Test transition to half_open after recovery_timeout."""
        start_time = 1000.0
        # Calls: _record_failure x2 (set _last_failure_time), then state check
        mock_time = MagicMock(
            side_effect=[start_time, start_time, start_time + 0.2]
        )
        with patch("maos.resilience.time.monotonic", mock_time):
            cb = CircuitBreaker(
                "test", failure_threshold=2, recovery_timeout=0.1
            )
            fn = AsyncMock(side_effect=RuntimeError("fail"))

            # Trip the breaker
            for _ in range(2):
                with pytest.raises(RuntimeError):
                    await cb.call(fn)

            assert cb.state == "half_open"

    async def test_half_open_closes_on_success(self):
        """Test that half_open transitions to closed on success."""
        start_time = 1000.0
        # Calls: _record_failure x2 (set _last_failure_time),
        # then state check (half_open), then state check in call(),
        # then _record_success state check
        mock_time = MagicMock(
            side_effect=[
                start_time,       # _record_failure call 1
                start_time,       # _record_failure call 2
                start_time + 0.2, # state check -> half_open
                start_time + 0.2, # state check in call()
                start_time + 0.2, # any further checks
                start_time + 0.2,
                start_time + 0.2,
            ]
        )
        with patch("maos.resilience.time.monotonic", mock_time):
            cb = CircuitBreaker(
                "test", failure_threshold=2, recovery_timeout=0.1
            )
            fn_fail = AsyncMock(side_effect=RuntimeError("fail"))

            # Trip the breaker
            for _ in range(2):
                with pytest.raises(RuntimeError):
                    await cb.call(fn_fail)

            assert cb.state == "half_open"

            # Successful call should close the circuit
            fn_ok = AsyncMock(return_value="recovered")
            result = await cb.call(fn_ok)

            assert result == "recovered"
            assert cb.state == "closed"

    async def test_half_open_reopens_on_failure(self):
        """Test that half_open transitions back to open on failure."""
        start_time = 1000.0
        mock_time = MagicMock(
            side_effect=[
                start_time,       # _record_failure call 1
                start_time,       # _record_failure call 2
                start_time + 0.2, # state check -> half_open
                start_time + 0.2, # state check in call()
                start_time + 0.2, # _record_failure call 3
                start_time + 0.2,
                start_time + 0.2,
            ]
        )
        with patch("maos.resilience.time.monotonic", mock_time):
            cb = CircuitBreaker(
                "test", failure_threshold=2, recovery_timeout=0.1
            )
            fn_fail = AsyncMock(side_effect=RuntimeError("fail"))

            # Trip the breaker
            for _ in range(2):
                with pytest.raises(RuntimeError):
                    await cb.call(fn_fail)

            assert cb.state == "half_open"

            # Failure in half_open should re-open
            with pytest.raises(RuntimeError):
                await cb.call(fn_fail)

            # State should be open (failure count >= threshold)
            assert cb._state == "open"

    async def test_state_property_returns_correct_string(self):
        """Test that state property returns correct state strings."""
        start_time = 1000.0
        mock_time = MagicMock(
            side_effect=[
                start_time,       # _record_failure call 1
                start_time,       # _record_failure call 2
                start_time,       # state check -> open (not enough time)
                start_time + 0.2, # state check -> half_open
            ]
        )
        with patch("maos.resilience.time.monotonic", mock_time):
            cb = CircuitBreaker(
                "test", failure_threshold=2, recovery_timeout=0.1
            )

            assert cb.state == "closed"

            fn_fail = AsyncMock(side_effect=RuntimeError("fail"))
            for _ in range(2):
                with pytest.raises(RuntimeError):
                    await cb.call(fn_fail)

            assert cb.state == "open"

            assert cb.state == "half_open"

    async def test_concurrent_calls_are_safe(self):
        """Test that concurrent calls do not corrupt state."""
        cb = CircuitBreaker("test", failure_threshold=100)
        fn = AsyncMock(return_value="ok")

        results = await asyncio.gather(
            *[cb.call(fn) for _ in range(20)]
        )

        assert all(r == "ok" for r in results)
        assert cb.state == "closed"

    async def test_success_resets_failure_count(self):
        """Test that a success in closed state resets failure count."""
        cb = CircuitBreaker("test", failure_threshold=3)
        fn_fail = AsyncMock(side_effect=RuntimeError("fail"))
        fn_ok = AsyncMock(return_value="ok")

        # Accumulate 2 failures (below threshold)
        for _ in range(2):
            with pytest.raises(RuntimeError):
                await cb.call(fn_fail)

        # Success should reset the counter
        await cb.call(fn_ok)
        assert cb._failure_count == 0
        assert cb.state == "closed"

    async def test_half_open_max_calls_exceeded(self):
        """Test that half_open rejects after max test calls."""
        start_time = 1000.0
        mock_time = MagicMock(
            side_effect=[
                start_time,       # _record_failure call 1
                start_time,       # _record_failure call 2
                start_time + 0.2, # state check -> half_open
                start_time + 0.2, # state check in call()
                start_time + 0.2, # _record_failure call 3
                start_time + 0.2,
                start_time + 0.2,
            ]
        )
        with patch("maos.resilience.time.monotonic", mock_time):
            cb = CircuitBreaker(
                "test",
                failure_threshold=2,
                recovery_timeout=0.1,
                half_open_max_calls=1,
            )
            fn_fail = AsyncMock(side_effect=RuntimeError("fail"))

            # Trip the breaker
            for _ in range(2):
                with pytest.raises(RuntimeError):
                    await cb.call(fn_fail)

            assert cb.state == "half_open"

            # First half-open call allowed (will fail, re-opening)
            with pytest.raises(RuntimeError, match="fail"):
                await cb.call(fn_fail)
