"""User-scoped observational spending; fresh admission remains in allowance."""
import time
from . import allowance
from .claude import ProviderError


class Budget:
    def __init__(self, store):
        self.store = store

    async def read(self, provider, settings, actor):
        spent = checked = None
        if provider and settings:
            try:
                spent, _ = await allowance.account(self.store, provider, actor)
                checked = time.time()
            except ProviderError:
                pass
        ceiling = allowance.limit(actor, settings)
        return dict(configured=bool(settings), currency='USD',
                    limit_cents=ceiling, spent_cents=spent,
                    remaining_cents=max(0, ceiling-spent)
                    if spent is not None else None, checked_at=checked,
                    scope='user', period='cumulative', resets_at=None)
