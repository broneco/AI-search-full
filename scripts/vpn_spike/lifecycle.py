"""Pure state transitions shared by the helper and isolated unit tests."""
from dataclasses import dataclass
from typing import Literal


State = Literal['disabled', 'connecting', 'ready', 'degraded', 'auth_failed']


@dataclass
class Lifecycle:
    state: State = 'disabled'
    code: str | None = None
    attempts: int = 0
    generation: int = 0
    max_attempts: int = 3

    def connecting(self) -> None:
        if self.attempts >= self.max_attempts:
            raise ValueError('retry_budget_exhausted')
        self.attempts += 1
        self.state, self.code = 'connecting', None

    def ready(self) -> None:
        self.state, self.code = 'ready', None
        self.generation += 1

    def failed(self, code: str) -> float | None:
        self.state = 'auth_failed' if code == 'vpn_auth_failed' else 'degraded'
        self.code = code
        if code in {'vpn_auth_failed', 'vpn_certificate_failed', 'vpn_options_failed', 'vpn_profile_invalid'}:
            return None
        if self.attempts >= self.max_attempts:
            return None
        return (2.0, 5.0)[self.attempts - 1]

    def public(self) -> dict:
        return dict(state=self.state, code=self.code, attempts=self.attempts, generation=self.generation)


@dataclass
class ForwardHealth:
    """Withdraw readiness immediately; tolerate two transient probe failures."""
    initialized: bool = False
    failures: int = 0

    def observe(self, lifecycle: Lifecycle, healthy: bool) -> bool:
        if healthy:
            self.failures = 0
            if not self.initialized:
                lifecycle.ready()
                self.initialized = True
            else:
                lifecycle.state, lifecycle.code = 'ready', None
        else:
            self.failures += 1
            lifecycle.state, lifecycle.code = 'degraded', 'vpn_upstream_unavailable'
        return self.failures >= 3
