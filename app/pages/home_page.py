# app/pages/home_page.py

"""Home page — mirrors engine_root home exactly.

Includes intro section, developer area (with team & supervisors hover
card), and collapsible simulation case selector with both STHR and
Biodiesel Reactor case cards.
"""

from __future__ import annotations

from dataclasses import dataclass

from nicegui import ui

from app.layouts.shell import home_shell

# ============================================================
# STATIC ASSETS
# ============================================================

LOGO_UNRI = '/static/assets/logos/logo_unri.png'

GITHUB_ICON = '/static/assets/icons/GitHub_Lockup_White_Clearspace.svg'
DOCS_ICON = '/static/assets/icons/logo-light.svg'
LINKEDIN_ICON = '/static/assets/icons/linkedin.png'


# ============================================================
# EXTERNAL LINKS
# ============================================================

GITHUB_URL = 'https://github.com/mhafzulhaikal'
DOCS_URL = 'https://github.com/mhafzulhaikal/chemplant-dynamics'
LINKEDIN_URL = 'https://www.linkedin.com/in/mhafzulhaikal'


# ============================================================
# INTERNAL ROUTES
# ============================================================

STHR_URL = '/control-panel/sthr'
REACTOR_URL = '/control-panel/biodiesel'


# ============================================================
# DATA MODELS
# ============================================================


@dataclass(frozen=True)
class Person:
    name: str
    email: str


@dataclass(frozen=True)
class ResourceLink:
    icon: str
    image_classes: str
    tooltip: str
    url: str


@dataclass(frozen=True)
class SimulationCase:
    title: str
    description: str
    tags: tuple[str, ...]
    url: str
    new_tab: bool = True


# ============================================================
# PAGE DATA
# ============================================================

TEAM_MEMBERS: tuple[Person, ...] = (
    Person(
        name='Muhammad Hafzul Haikal',
        email='muhammad.hafzul4355@student.unri.ac.id',
    ),
    Person(
        name='Nurmansyah Aditya',
        email='nurmansyah.aditya@student.unri.ac.id',
    ),
)

SUPERVISORS: tuple[Person, ...] = (
    Person(
        name='Hari Rionaldo, S.T., M.T.',
        email='hari.rionaldo@lecture.unri.ac.id',
    ),
    Person(
        name='Zulfansyah, S.T., M.T.',
        email='zulfansyah@lecture.unri.ac.id',
    ),
)

RESOURCE_LINKS: tuple[ResourceLink, ...] = (
    ResourceLink(
        icon=GITHUB_ICON,
        image_classes='resource-icon github-resource-icon',
        tooltip='GitHub',
        url=GITHUB_URL,
    ),
    ResourceLink(
        icon=DOCS_ICON,
        image_classes='resource-icon docs-resource-icon',
        tooltip='Documentation',
        url=DOCS_URL,
    ),
    ResourceLink(
        icon=LINKEDIN_ICON,
        image_classes='resource-icon linkedin-resource-icon',
        tooltip='LinkedIn',
        url=LINKEDIN_URL,
    ),
)

SIMULATION_CASES: tuple[SimulationCase, ...] = (
    SimulationCase(
        title='Stirred Tank Heater (STHR)',
        description=(
            'Dynamic simulation and control of a stirred tank heater. '
            'This simulation is based on Example 6.2 from Principles and '
            'Practice of Automatic Process Control, Third Edition '
            '(Smith & Corripio, 2006).'
        ),
        tags=(
            'Temperature Control',
            'PID Control',
            'Dynamic Response',
        ),
        url=STHR_URL,
    ),
    SimulationCase(
        title='Biodiesel Reactor (R-100)',
        description=(
            'Dynamic simulation and control of a biodiesel reactor'
            ' from palm oil '
            'using a continuous stirred tank reactor model.'
            ' The simulation is '
            'developed based on selected literature, Aspen Plus'
            ' biodiesel example '
            'case studies, and process control model development'
            ' by the ChE_21 '
            'Process Control Research Team.'
        ),
        tags=(
            'Temperature Control',
            'Level Control',
            'Flow Control',
            'CSTR',
        ),
        url=REACTOR_URL,
    ),
)


# ============================================================
# SHARED COMPONENTS
# ============================================================


def render_asset_image(
    src: str,
    css_classes: str,
    *,
    tooltip: str | None = None,
) -> ui.image:
    image = ui.image(src).classes(css_classes).props('fit=contain no-spinner')
    if tooltip:
        image.tooltip(tooltip)
    return image


def render_external_image_link(resource: ResourceLink) -> None:
    with ui.link(target=resource.url, new_tab=True).classes(
        'resource-link clickable-resource-icon'
    ):
        render_asset_image(
            resource.icon,
            resource.image_classes,
            tooltip=resource.tooltip,
        )


# ============================================================
# DEVELOPER SECTION
# ============================================================


def render_person_block(person: Person) -> None:
    with ui.column().classes('developer-person-block gap-0'):
        ui.label(person.name).classes('developer-person')
        ui.label(person.email).classes('developer-email')


def render_people_column(title: str, people: tuple[Person, ...]) -> None:
    with ui.column().classes('developer-column gap-2'):
        ui.label(title).classes('developer-section-title')
        for person in people:
            render_person_block(person)


def render_developer_card() -> None:
    with ui.card().classes('developer-floating-card'):
        with ui.row().classes('developer-row-layout no-wrap'):
            render_people_column('Team Members', TEAM_MEMBERS)
            render_people_column('Supervisors', SUPERVISORS)


def render_developer_resource_links() -> None:
    with ui.row().classes('developer-icon-row items-center no-wrap'):
        for resource in RESOURCE_LINKS:
            render_external_image_link(resource)


def render_developer_area() -> None:
    with ui.column().classes('developer-area items-center gap-2'):
        with ui.row().classes('developer-top-row items-center justify-center'):
            render_developer_resource_links()
            ui.label('Developed with 💚 by Process Control Research Team').classes(
                'developer-team-title developer-hover-trigger'
            )
        render_developer_card()


# ============================================================
# INTRO SECTION
# ============================================================


def render_intro_logo() -> None:
    render_asset_image(LOGO_UNRI, 'intro-logo', tooltip='University of Riau')


def render_intro_text() -> None:
    with ui.column().classes('intro-text-block items-center gap-2'):
        ui.label('ChemPlant Dynamics').classes('intro-title')
        ui.label(
            'Dynamic Process Simulation Platform for Chemical Plant'
            ' Operation, '
            'Process Control, and Plantwide System Understanding.'
        ).classes('intro-subtitle')
        ui.label(
            'ChemPlant Dynamics is a web-based dynamic process'
            ' simulation platform '
            'designed to support learning, analysis, and'
            ' visualization of chemical '
            'plant behavior. The application provides interactive'
            ' process simulation '
            'cases, piping and instrumentation diagram navigation,'
            ' dynamic response observation, '
            'and process control studies including PID control,'
            ' set-point tracking, '
            'disturbance rejection, and operating condition'
            ' analysis.'
        ).classes('intro-description')


def render_intro_section() -> None:
    with ui.element('section').classes('intro-section'):
        with ui.column().classes('intro-section-inner items-center gap-3'):
            render_intro_logo()
            render_intro_text()
            render_developer_area()


# ============================================================
# SIMULATION SECTION
# ============================================================


def render_case_tags(tags: tuple[str, ...]) -> None:
    with ui.row().classes('case-tags items-center'):
        for tag in tags:
            ui.label(tag).classes('case-tag')


def render_simulation_case_content(case: SimulationCase) -> None:
    with ui.column().classes('simulation-case-content gap-2'):
        ui.label(case.title).classes('case-title')
        ui.label(case.description).classes('case-description')
        render_case_tags(case.tags)


def render_simulation_case_card(case: SimulationCase) -> None:
    with ui.link(target=case.url, new_tab=case.new_tab).classes('simulation-case-link'):
        with ui.card().classes('simulation-case-card clickable-card'):
            render_simulation_case_content(case)


def render_simulation_case_grid() -> None:
    with ui.column().classes('simulation-card-grid'):
        for case in SIMULATION_CASES:
            render_simulation_case_card(case)


def render_simulation_section() -> None:
    with ui.element('section').classes('simulation-section'):
        with ui.column().classes('simulation-section-inner w-full'):
            with (
                ui.expansion('Select Plant Simulation Case', value=False)
                .classes('simulation-expansion')
                .props('dense')
            ):
                with ui.card().classes('simulation-wrapper-card'):
                    render_simulation_case_grid()


# ============================================================
# HOME PAGE CONTENT
# ============================================================


def render_home_content() -> None:
    with ui.column().classes('home-content-root'):
        render_intro_section()
        render_simulation_section()


# ============================================================
# PAGE ENTRY
# ============================================================


@ui.page('/')
def build_home_page() -> None:
    home_shell(render_home_content)
