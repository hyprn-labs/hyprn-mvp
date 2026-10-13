"""Orient and read: the entry tools of every session (tooling spec section 4.1)."""

from .. import playbook
from ..spec import SURFACES, ToolError, ToolSpec


async def get_playbook(arguments, ctx):
    """One playbook section; an unknown section is refused, never guessed. Static guidance:
    nothing is read from or written to any store."""
    try:
        section = playbook.section(arguments['section'])
    except KeyError:
        raise ToolError(
            'invalid_input',
            'There is no playbook section of that name.',
            fields=({'path': 'section', 'problem': 'must be a playbook section name'},),
            next_step='Call get_playbook with one of: ' + ', '.join(playbook.SECTION_NAMES) + '.',
        ) from None
    return {
        'section': section.name,
        'kind': section.kind,
        'load_when': section.load_when,
        'tools': list(section.tools),
        'text': section.text,
    }


GET_PLAYBOOK = ToolSpec(
    name='get_playbook',
    title='Read a playbook section',
    description=(
        'Returns one section of the HYPRN MVP study playbook: how to carry out the study as '
        'a user of HYPRN MVP, which fields hold which content, and the rules each area '
        'follows. Call it with "workflow" right after get_study_overview, and load an area '
        'section (approach, evidence, model, configuration_and_runs, conclusion) before you '
        'write in that area; style, platform_limits and checklist are cross-cutting. '
        'section: the section name. Each section opens with when to load it and the tools '
        'it governs. Loading a section changes neither your tool list nor what you may do. '
        'Guidance: get_playbook("workflow").'
    ),
    input_schema={
        'type': 'object',
        'additionalProperties': False,
        'required': ['section'],
        'properties': {
            'section': {
                'type': 'string',
                'enum': list(playbook.SECTION_NAMES),
                'description': 'The playbook section to read.',
            }
        },
    },
    effect='read',
    stage='read_only',
    surfaces=SURFACES,
    owners=('agent_tools',),
    outcome='none',
    activity_label='Read: playbook',
    handler=get_playbook,
    client_meta=(('anthropic/alwaysLoad', True),),
)

TOOLS = (GET_PLAYBOOK,)
