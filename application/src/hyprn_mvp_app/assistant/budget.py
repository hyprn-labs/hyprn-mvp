"""Read-only administrative spending snapshots; never an admission decision.

A cached list-cost read is never an invoice or an admission decision.
Cache only for this process; an unavailable provider after restart yields unknown spend.
"""

import asyncio
import time

from .claude import ProviderError


class Budget:
    def __init__(self, store):
        self.store = store
        self._lock = asyncio.Lock()
        self._costs = {}
        self._attempted = {}

    async def read(self, provider, settings, study=None):
        rows = [dict(r) for r in self.store.assistant_accounts()]
        current = next((r for r in rows if r['study_id'] == study), None)
        reserved = 0  # Populated only from known observational usage below.
        async with self._lock:
            now = time.time()
            semaphore = asyncio.Semaphore(4)

            async def refresh(row):
                sid = row['provider_id']
                if not sid or now - self._attempted.get(sid, 0) < 60:
                    return
                self._attempted[sid] = now
                async with semaphore:
                    try:
                        cost = await asyncio.wait_for(provider.spending(sid), timeout=5)
                        self._costs[sid] = (cost, time.time())
                    except (ProviderError, TimeoutError):
                        # Preserve the last observed cost with its original timestamp.
                        pass

            if provider and settings:
                await asyncio.gather(*(refresh(row) for row in rows))
            costs = dict(self._costs)
        # Not-yet-provisioned reservations cannot be reported as confirmed zero spending:
        # creation may have reached the provider even if its acknowledgement was lost.
        snapshots = [costs.get(r['provider_id']) for r in rows]
        known = all(item is not None for item in snapshots)
        reserved = sum(max(0, r['reserved_cents'] - costs[r['provider_id']][0])
                       for r in rows if r.get('active_turn') and r['provider_id'] in costs)
        prior = settings.prior_cents if settings else 0
        spent = prior + sum(item[0] for item in snapshots) if known else None
        checked = min((item[1] for item in snapshots if item), default=None)
        fresh = known and all(time.time() - item[1] < 60 for item in snapshots)
        own = costs.get(current['provider_id']) if current else None
        limit = settings.total_cents if settings else None
        own_limit = current['reserved_cents'] if current else None
        return dict(
            configured=bool(settings), currency='USD', limit_cents=limit,
            reserved_cents=reserved, prior_cents=prior,
            unallocated_cents=max(0, limit - spent - reserved)
            if limit is not None and spent is not None else None,
            spent_cents=spent if settings else None,
            remaining_cents=max(0, limit - spent)
            if limit is not None and spent is not None else None,
            new_study_limit_cents=max(0, limit - spent)
            if limit is not None and spent is not None else None,
            study_limit_cents=own_limit, study_spent_cents=own[0] if own else None,
            study_remaining_cents=max(0, limit - spent)
            if current and limit is not None and spent is not None else None,
            checked_at=checked, usage_current=bool(settings and fresh),
            approved=dict(minor=settings.approved_minor, currency=settings.approved_currency,
                          conversion_date=settings.conversion_date)
            if settings and settings.approved_minor is not None else None,
        )
