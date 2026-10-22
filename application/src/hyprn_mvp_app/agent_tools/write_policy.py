"""The closed classification of human-only API routes (ADR-0003).

Deleting saved records, archive and restore (unarchive) of studies and documents, access
management, and backup restore and import are human-only on every surface and stage. One
classification serves the registry build rule (no tool may declare such a route), the agent
route allowlist (refused before anything else, whatever a registry declares) and the journal's
reason mapping.

``route_category(method, path)`` accepts a route template (``/api/1/studies/{study_id}/...``)
or a concrete request path: a template placeholder and a concrete segment both match one path
segment, so the same rule classifies the contract's operations and the requests an agent
session sends. A route that is in no category is not human-only; it is still refused for an
agent session unless a registered tool declares it.

Pure data and one function; imports nothing.
"""

import re

SAVED_RECORD_DELETION = 'saved_record_deletion'
LIFECYCLE = 'lifecycle'
ACCESS_MANAGEMENT = 'access_management'
BACKUP_AND_IMPORT = 'backup_and_import'
WORKING_MATERIAL = 'working_material_deletion'
HUMAN_ONLY = frozenset({SAVED_RECORD_DELETION, LIFECYCLE, ACCESS_MANAGEMENT, BACKUP_AND_IMPORT})

S = '/api/1/studies/{study_id}'
# Working material an agent may delete under revision checks (the draft rule). It is not
# refused by this classification, and it stays off the agent allowlist until a registered
# tool declares it.
WORKING_MATERIAL_DELETION = frozenset(
    {('DELETE', S + '/document-versions/{version_id}/annotations/{annotation_id}')}
)
LIFECYCLE_ROUTES = frozenset(
    {
        ('POST', S + '/archive'),
        ('POST', S + '/restore'),
        ('POST', S + '/documents/{document_id}/archive'),
        ('POST', S + '/documents/{document_id}/unarchive'),
    }
)
# Saved-record deletion named explicitly besides "every DELETE route".
DELETION_ROUTES = frozenset({('DELETE', S + '/document-collections/{collection_id}')})
# Path segments of access-management routes: memberships, invitations, grants, delegations and
# tool tokens.
ACCESS_SEGMENTS = frozenset({'memberships', 'invitations', 'grants', 'delegations', 'tokens'})
# Route families, each with every route below it, for every method.
ACCESS_FAMILIES = (
    '/api/1/session',
    S + '/assistant',
    S + '/agent',
    '/api/1/agent/attribution',
    '/api/1/agent/sessions',
)
BACKUP_AND_IMPORT_FAMILIES = (S + '/document-restores', S + '/document-imports')
DELETION_FAMILIES = (S + '/document-deletions',)

_PLACEHOLDER = re.compile(r'\{[a-z_]+\}')


def _pattern(template, family=False):
    parts = _PLACEHOLDER.split(template)
    body = '[^/]+'.join(re.escape(p) for p in parts)
    return re.compile(body + ('(?:/.*)?' if family else ''))


def _routes(pairs):
    return tuple((method, _pattern(template)) for method, template in sorted(pairs))


def _families(templates):
    return tuple(_pattern(template, family=True) for template in templates)


_WORKING = _routes(WORKING_MATERIAL_DELETION)
_LIFECYCLE = _routes(LIFECYCLE_ROUTES)
_DELETION = _routes(DELETION_ROUTES)
_ACCESS = _families(ACCESS_FAMILIES)
_BACKUP = _families(BACKUP_AND_IMPORT_FAMILIES)
_DELETION_FAMILIES = _families(DELETION_FAMILIES)


def route_category(method, path):
    """The category of ``method path``: one of the four human-only categories,
    ``working_material_deletion``, or ``None`` for a route in no category."""
    if not isinstance(method, str) or not isinstance(path, str):
        raise TypeError('method and path must be text')
    method = method.upper()

    def named(routes):
        return any(m == method and p.fullmatch(path) for m, p in routes)

    def family(patterns):
        return any(p.fullmatch(path) for p in patterns)

    if named(_WORKING):
        return WORKING_MATERIAL
    if named(_LIFECYCLE):
        return LIFECYCLE
    if family(_ACCESS) or ACCESS_SEGMENTS.intersection(path.split('/')):
        return ACCESS_MANAGEMENT
    if family(_BACKUP):
        return BACKUP_AND_IMPORT
    if method == 'DELETE' or named(_DELETION) or family(_DELETION_FAMILIES):
        return SAVED_RECORD_DELETION
    return None


def is_human_only(method, path):
    """Whether ``method path`` is human-only: refused for every agent session and never
    declared by a tool."""
    return route_category(method, path) in HUMAN_ONLY
