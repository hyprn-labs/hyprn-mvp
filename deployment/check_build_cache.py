"""Budget only build-cache records attributable to HYPRN, never global Docker prune."""
import json
import re
import subprocess

PROJECT = re.compile(r'hyprn|whatsopt|modeling_policy\.rb|modeling_contract\.rb|'
                     r'modeling\.schema\.json|build_engine\.py|origin-instrument\.rb|'
                     r'upstream/engine-packaging|COPY application /app/application|'
                     r'COPY contracts /app/contracts|COPY ui-dist /app/ui', re.I)


def size(value):
    if isinstance(value, int) and value >= 0:
        return value
    match = re.fullmatch(r'([\d.]+)\s*(B|kB|MB|GB|TB)', value)
    if not match:
        raise ValueError('Unrecognized Docker cache size: ' + str(value))
    return int(float(match[1]) * {'B': 1, 'kB': 10**3, 'MB': 10**6, 'GB': 10**9, 'TB': 10**12}[match[2]])


def attributed(records):
    by_id = {r['ID']: r for r in records}
    related = {r['ID'] for r in records if PROJECT.search(r.get('Description', ''))}
    while True:
        extra = {r['ID'] for r in records if any(p in related for p in r.get('Parents') or [])}
        if extra <= related:
            break
        related.update(extra)
    # Ancestors are shared dependencies; do not expand their unrelated descendants.
    while True:
        extra = {p for i in related for p in by_id[i].get('Parents') or [] if p in by_id}
        if extra <= related:
            break
        related.update(extra)
    return [r for r in records if r['ID'] in related]


def inventory():
    result = subprocess.run(['docker', 'buildx', 'du', '--format=json'],
                            capture_output=True, text=True, timeout=60, check=True)
    return attributed([json.loads(line) for line in result.stdout.splitlines() if line.strip()])


def enforce(budget):
    before = inventory()
    used = sum(size(r['Size']) for r in before)
    if used <= budget:
        return dict(before=used, after=used, budget=budget)
    eligible = [r['ID'] for r in before if r.get('Reclaimable') and not r.get('Shared')]
    if eligible:
        # Zero reserved space is intentional: the daemon's default reserve must not
        # silently override the developer's smaller budget. Exact IDs bound the scope.
        selector = 'id~=^(' + '|'.join(re.escape(i) for i in sorted(eligible)) + ')$'
        subprocess.run(['docker', 'buildx', 'prune', '--force', '--all',
                        '--reserved-space', '0', '--max-used-space', str(budget),
                        '--filter', selector], capture_output=True, text=True, timeout=180, check=True)
    after = sum(size(r['Size']) for r in inventory())
    print(json.dumps(dict(build_cache_before=used, build_cache_after=after, budget=budget)), flush=True)
    if after > budget:
        raise ValueError(f'HYPRN build cache remains over budget ({after} > {budget} bytes). '
                         'Active/shared image layers were preserved; release unused images or set '
                         'HYPRN_MVP_TEST_BUILD_CACHE_BYTES explicitly.')
    return dict(before=used, after=after, budget=budget)
