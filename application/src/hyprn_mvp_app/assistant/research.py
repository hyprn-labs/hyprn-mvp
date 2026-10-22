"""Derived retrieval receipts, never certification of an author's scientific claims.

Only the trusted runtime's successful evidence write can create a receipt. Provider
fetch events establish returned text; exact quotation and citation matching bind it
to the immutable authored version. Human/uploaded/older evidence remains usable.
"""

from datetime import datetime, timezone
from hashlib import sha256
import json
from urllib.parse import urlsplit

from ..contracts import DomainError
from ..evidence_content import read_content
from . import records


def _object(properties):
    return dict(type='object', additionalProperties=False,
                properties=properties, required=list(properties))


_HASH = dict(type='string', pattern='^[0-9a-f]{64}$')
DEFINITIONS = {
    'EvidenceRetrievedExcerpt1': _object(dict(
        source_url=dict(type='string', format='uri', description=(
            'Exact cited URL requested by the paired fetch, not a verified redirect destination.')),
        observed_at=dict(type='string', format='date-time'),
        excerpt_sha256=_HASH,
        retrieved_content_sha256=_HASH,
    )),
    'EvidenceSourceInspection1': _object(dict(
        schema_version=dict(type='string', enum=['1']),
        evidence_version_id=dict(type='string', format='uuid'),
        basis=dict(type='string', enum=['author_supplied', 'retrieved_excerpt']),
        retrieval=dict(anyOf=[{'$ref': '#/components/schemas/EvidenceRetrievedExcerpt1'},
                              {'type': 'null'}]),
    )),
}


def _hash(text):
    return sha256(text.encode('utf-8')).hexdigest()


def _receipt_id(version):
    return 'evidence_source_' + version


def _url(value):
    if not isinstance(value, str):
        return False
    try:
        parsed = urlsplit(value)
        return parsed.scheme in ('http', 'https') and bool(parsed.netloc)
    except ValueError:
        return False


def _texts(event):
    """Read only actual text blocks; URLs, search hits and encoded PDFs are not text."""
    content = event.get('content')
    if not isinstance(content, list):
        return
    for block in content:
        if not isinstance(block, dict):
            continue
        if block.get('type') == 'text' and isinstance(block.get('text'), str):
            yield block['text']
        if block.get('type') == 'document':
            source = block.get('source')
            if (isinstance(source, dict) and source.get('type') == 'text'
                    and source.get('media_type') == 'text/plain'
                    and isinstance(source.get('data'), str)):
                yield source['data']


def _matched_fetch(db, study, before, excerpt, urls):
    # Bound write-time inspection. Reads use the receipt's primary key, not history.
    # Older/unavailable retrievals conservatively remain author-supplied.
    calls = db.execute('SELECT payload,position FROM assistant_events WHERE study_id=? '
        'AND event_type=? AND position<? ORDER BY position DESC LIMIT 256',
        (study, 'agent.tool_use', before)).fetchall()
    for row in calls:
        call = json.loads(row['payload'])
        arguments = call.get('input')
        if (call.get('name') != 'web_fetch' or not isinstance(arguments, dict)
                or not isinstance(arguments.get('url'), str)
                or arguments['url'] not in urls
                or call.get('evaluated_permission') == 'deny'):
            continue
        result_row = db.execute('SELECT payload FROM assistant_events WHERE study_id=? '
            'AND reference_id=? AND event_type=? AND position>? AND position<? '
            'ORDER BY position DESC LIMIT 1',
            (study, call['id'], 'agent.tool_result', row['position'], before)).fetchone()
        if result_row is None:
            continue
        result = json.loads(result_row['payload'])
        # Missing/null error status is not proof of successful retrieval.
        if result.get('is_error') is not False:
            continue
        received = result.get('_received_at')
        if type(received) not in (float, int):
            continue
        for text in _texts(result):
            if excerpt not in text or text.strip() == 'url_not_allowed':
                continue
            try:
                observed = datetime.fromtimestamp(received, timezone.utc).isoformat()
            except (ValueError, OverflowError, OSError):
                continue
            return dict(source_url=arguments['url'], observed_at=observed,
                        excerpt_sha256=_hash(excerpt), retrieved_content_sha256=_hash(text)), {
                            'fetch_event_id': call['id'], 'result_event_id': result['id']}
    return None


def retain_evidence(store, db, actor, study, event_id, content, is_error):
    """Called only after real runtime execution, in the tool-result retention transaction."""
    if is_error:
        return
    result = json.loads(content)
    saved = result.get('content')
    if (result.get('ok') is not True or not isinstance(saved, dict)
            or saved.get('kind') != 'evidence_version' or not isinstance(saved.get('id'), str)):
        return
    original = db.execute('SELECT payload,position FROM assistant_events '
        'WHERE study_id=? AND event_id=?', (study, event_id)).fetchone()
    if original is None:
        return
    call = json.loads(original['payload'])
    if (call.get('type') != 'agent.custom_tool_use'
            or call.get('name') not in ('add_evidence', 'revise_evidence')):
        return
    evidence = store.evidence_record(db, actor, study, saved['id'])
    if evidence is None:
        return
    quote = read_content(evidence['content'])
    if quote is None:
        return
    urls = {value for value in evidence['source_refs'] if _url(value)}
    if _url(quote['source_reference']):
        urls = {quote['source_reference']}
    match = _matched_fetch(db, study, original['position'], quote['excerpt'], urls)
    if match is None:
        return
    retrieval, private = match
    records.save_event(db, study, dict(
        id=_receipt_id(saved['id']), type='hyprn.evidence_source',
        evidence_version_id=saved['id'], evidence_content_sha256=_hash(evidence['content']),
        write_event_id=event_id, retrieval=retrieval, **private))


def read(store, actor, study, evidence_version_id):
    """Authorize the exact evidence version and project only a bound immutable receipt."""
    with store.connection() as db:
        evidence = store.evidence_record(db, actor, study, evidence_version_id)
        if evidence is None:
            raise DomainError('resource_not_found', 404)
        receipt = records.event(db, study, _receipt_id(evidence_version_id))
    result = dict(schema_version='1', evidence_version_id=evidence_version_id,
                  basis='author_supplied', retrieval=None)
    if (receipt is None or receipt.get('type') != 'hyprn.evidence_source'
            or receipt.get('evidence_version_id') != evidence_version_id
            or receipt.get('evidence_content_sha256') != _hash(evidence['content'])):
        return result
    value = receipt['retrieval']
    result.update(basis='retrieved_excerpt', retrieval={
        key: value[key] for key in ('source_url', 'observed_at', 'excerpt_sha256',
                                   'retrieved_content_sha256')})
    return result
