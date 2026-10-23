# Staging storage lifecycle maintenance

User authorizes cleanup of old HYPRN staging exports and unused build volumes/cache,
plus automatic staging-workflow retention. Preserve code, running work and whole
experiments changed within 24 hours. One inline maintenance batch continues the
existing storage maintenance amendment; unrelated hosted/UI work is excluded.

1. Discover build/payload manifests beneath explicitly configured parent folders.
   Delete only generated OCI/native exports from known artifact destinations.
   Preserve source trees, source archives, records, links and recent/active roots.
2. Reconcile exact labelled build volumes against all container references, build
   root activity, creation time and read-only content age. Prune only project cache
   IDs unused for 24 hours. No image deletion or global Docker/volume prune.
3. Invoke collection/admission around staging build commands and before checks.
   Newly created manifest-bearing folders beneath enrolled parents need no enrollment.
   Apply staging files, owned volumes, cache and free-space admission budgets.
4. Verify isolated behavioral tests and real host cleanup. Record before/after
   filesystem allocation, actual actions, preserved work and qualification limits.
