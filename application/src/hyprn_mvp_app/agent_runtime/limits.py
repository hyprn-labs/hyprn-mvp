"""The limits every agent session runs under (agents specification section 3.4).

The runtime's admission enforces them for every tool call on every surface; a tool never
enforces its own copy. ``run_refusal`` is the run admission rule as one pure function.
"""

# API calls one delegated runtime session may make.
MAX_API_CALLS_PER_SESSION = 600
# A tool result is about 6,000 tokens at most: 24 KB of JSON text.
RESULT_CAP_BYTES = 24 * 1024
# A tool call's input as canonical JSON.
MAX_INPUT_BYTES = 256 * 1024
# More than this many identical ``invalid_input`` refusals within the window: the next
# identical call is refused until the window has passed.
REPEATED_ERROR_LIMIT = 5
REPEATED_ERROR_WINDOW_SECONDS = 120
# Run submissions: per call, waiting or running per agent actor, and per session.
MAX_RUNS_PER_CALL = 20
MAX_QUEUED_RUNS_PER_ACTOR = 10
MAX_RUNS_PER_SESSION = 60
# Run-list states counted as waiting or running. An uncertain launch may be running, so it
# counts (fail closed); a recorded run and a failed preparation do not.
QUEUED_RUN_STATES = frozenset({'accepted_run', 'prepared', 'dispatching', 'uncertain'})
# Pages of the study's run list read for one admission (100 runs each); a longer list is not
# counted and the submission is refused rather than admitted on a partial count.
MAX_RUN_LIST_PAGES = 50
RUN_LIST_PAGE = 100
# Fresh command ids journaled for one call of a mutating tool: one per run for ``submit``,
# a small fixed set for draft and record tools (a tool issues at most this many commands).
COMMAND_IDS = {'submit': MAX_RUNS_PER_CALL, 'draft': 4, 'record': 4}
# The delegated API session is re-minted when less than this many seconds remain.
API_SESSION_MARGIN_SECONDS = 60
# Bounds of what one journal row keeps.
MAX_RECORDS = 50
MAX_WARNINGS = 20
MAX_API_OPERATIONS = 100


def run_refusal(requested, session_runs, queued_runs):
    """The reason a call requesting ``requested`` runs is refused, or ``None`` to admit it,
    given the runs the session already submitted and the actor's runs waiting or running.
    The per-call cap is checked first, then the session cap, then the queue cap."""
    if requested > MAX_RUNS_PER_CALL:
        return 'run_limit_call'
    if session_runs + requested > MAX_RUNS_PER_SESSION:
        return 'run_limit_session'
    if queued_runs + requested > MAX_QUEUED_RUNS_PER_ACTOR:
        return 'run_limit_queued'
    return None
