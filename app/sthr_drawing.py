# app/sthr_drawing.py

"""Build the STHR P&ID SVG — copied verbatim from V1.1.

This module is pure UI: no engine, no services. It reads from the local
config module to obtain the initial display values for each instrument.

Layout-symmetric with the biodiesel drawing module:

- ``app/sthr_drawing.py``                      — STHR drawing (this module)
- ``app/biodiesel_drawing.py``                 — biodiesel drawing
- ``app/components/sthr_component.py``         — STHR equipment classes
- ``app/components/biodiesel_component.py``    — biodiesel equipment classes
"""

import drawsvg as draw

from app import config
from app.components.sthr_component import (
    ArrowLine,
    Coil,
    Column,
    Controller,
    ControlValve,
    DashLine,
    DotEndLine,
    FluidLayer,
    LineLine,
    Pump,
    SteamTrap,
    Stirred,
    StreamLabel,
    ValueCard,
)
from app.pid.sthr.ui_config import DISPLAY_MAP, INITIAL_CONDITIONS, PLANT_PARAMS


def _initial_display_value(svg_id: str) -> tuple[float, str]:
    """Get the initial display value and unit for a P&ID element."""
    mapping = DISPLAY_MAP.get(svg_id)
    if not mapping:
        return (0.0, '')

    sig = mapping['signal']
    unit = mapping['unit']

    if sig in INITIAL_CONDITIONS:
        return (INITIAL_CONDITIONS[sig], unit)
    elif sig in PLANT_PARAMS:
        return (PLANT_PARAMS[sig], unit)
    else:
        return (0.0, unit)


def build_sthr_drawing() -> str:
    d = draw.Drawing(1001, 540.225)
    d.set_render_size('100%', '100%')
    d.append(draw.Rectangle(0, 0, '100%', '100%', fill='none'))

    # ── Initial display values from real config ──
    _, fi100_unit = _initial_display_value('fi-100')
    _, fi101_unit = _initial_display_value('fi-101')
    _, tic100_unit = _initial_display_value('tic-100')
    _, ti100_unit = _initial_display_value('ti-100')
    _, li100_unit = _initial_display_value('li-100')
    _, fi102_unit = _initial_display_value('fi-102')
    _, vp100_unit = _initial_display_value('vp-100')

    # ── Equipment ──
    column = Column('column', x=455, y=80)
    coil = Coil('coil', x=457, y=198)
    control_valve = ControlValve('control_valve', x=274, y=150)
    pump = Pump('pump', x=672, y=463)
    stirred = Stirred('stirred', x=482, y=0)
    steam_trap = SteamTrap('steam_trap', x=318, y=411)
    fluid = FluidLayer(
        'column-fluid',
        column,
        fluid_level=0.95,
        fluid_color='#5FABF7FF',
        fluid_opacity=0.1,
    )

    # ── Controllers (driven by real initial values) ──
    # NOTE: `round()` raises TypeError on str; coerce to float defensively
    # so a stray string in config (e.g. "150" from a YAML/JSON read) never
    # crashes first render with "type str doesn't define __round__ method".
    fi100_ctrl = Controller(
        'fi-100',
        x=59,
        y=106,
        width=121,
        height=55,
        tag='FI-100',
        value="{{ snapshot['fi-100'] }}",
        unit=fi100_unit,
        value_color='green',
    )
    fi101_ctrl = Controller(
        'fi-101',
        x=0,
        y=260,
        width=125,
        height=55,
        tag='FI-101',
        value="{{ snapshot['fi-101'] }}",
        unit=fi101_unit,
        value_color='green',
        sp_tag='feed_flow',
    )
    tic100_ctrl = Controller(
        'tic-100',
        x=262,
        y=22,
        width=88,
        height=55,
        tag='TIC-100',
        value="{{ snapshot['tic-100'] }}",
        unit=tic100_unit,
        value_color='green',
        sp_tag='sp',
    )
    ti100_ctrl = Controller(
        'ti-100',
        x=167,
        y=260,
        width=88,
        height=55,
        tag='TI-100',
        value="{{ snapshot['ti-100'] }}",
        unit=ti100_unit,
        value_color='green',
    )
    li100_ctrl = Controller(
        'li-100',
        x=609,
        y=230,
        width=110,
        height=55,
        tag='LI-100',
        value="{{ snapshot['li-100'] }}",
        unit=li100_unit,
        value_color='green',
    )
    fi102_ctrl = Controller(
        'fi-102',
        x=814,
        y=387,
        width=125,
        height=55,
        tag='FI-102',
        value="{{ snapshot['fi-102'] }}",
        unit=fi102_unit,
        value_color='green',
    )
    vp100 = ValueCard(
        'vp-100',
        x=control_valve.x + (64 - 70) / 2,
        y=control_valve.y + 65,
        value="{{ snapshot['vp-100'] }}",
        unit='%',
        value_color='green',
    )

    # ── Ports ──
    cv_in = control_valve.port_abs('in')
    cv_top = control_valve.port_abs('top')
    col_in = column.port_abs('in')
    st_out = steam_trap.port_abs('out')
    pump_out = pump.port_abs('out')
    col_rt = column.port_abs('right-top')
    col_rb = column.port_abs('right-bottom')

    fi100_ctrl_bot = fi100_ctrl.port_abs('bottom')
    fi101_ctrl_bot = fi101_ctrl.port_abs('bottom')
    ti100_ctrl_bot = ti100_ctrl.port_abs('bottom')
    fi102_ctrl_bot = fi102_ctrl.port_abs('bottom')
    tic100_ctrl_bot = tic100_ctrl.port_abs('bottom')
    tic100_ctrl_right = tic100_ctrl.port_abs('right')
    li100_ctrl_left = li100_ctrl.port_abs('left')

    # ── Pipelines ──
    steam_to_cv = LineLine(
        id='steam_feed',
        waypoints=[(0, cv_in.y), (cv_in.x, cv_in.y)],
        width=4,
        color='#ffffff',
    )
    cv_to_coil = ArrowLine.from_ports(
        'col_feed', control_valve, 'out', coil, 'in', width=4, color='#ffffff'
    )
    coil_to_st = LineLine.from_ports(
        'coil_feed',
        coil,
        'out',
        steam_trap,
        'in',
        mid_points=[(338, 323)],
        width=4,
        color='#ffffff',
    )
    st_to_out = ArrowLine(
        id='st_out',
        waypoints=[(st_out.x, st_out.y), (st_out.x, 500)],
        width=4,
        color='#ffffff',
    )
    feed_to_col = ArrowLine(
        id='feed_to_col',
        waypoints=[(0, col_in.y), (col_in.x, col_in.y)],
        width=4,
        color='#ffffff',
    )
    col_to_pump = ArrowLine.from_ports(
        'col_to_pump',
        column,
        'out',
        pump,
        'in',
        mid_points=[(524, 499)],
        width=4,
        color='#ffffff',
    )
    pump_to_out = ArrowLine(
        id='pump_to_out',
        waypoints=[(pump_out.x, pump_out.y), (1001, pump_out.y)],
        width=4,
        color='#ffffff',
    )

    # ── Instrument signal lines ──
    fi100_s_to_ctrl = DashLine(
        id='fi100_s_to_ctrl',
        waypoints=[
            (fi100_ctrl_bot.x, fi100_ctrl_bot.y),
            (fi100_ctrl_bot.x, cv_in.y),
        ],
        width=2,
        color='yellow',
        dash='5,5',
    )
    fi101_s_to_ctrl = DashLine(
        id='fi101_s_to_ctrl',
        waypoints=[
            (fi101_ctrl_bot.x, fi101_ctrl_bot.y),
            (fi101_ctrl_bot.x, col_in.y),
        ],
        width=2,
        color='yellow',
        dash='5,5',
    )
    ti100_s_to_ctrl = DashLine(
        id='ti100_s_to_ctrl',
        waypoints=[
            (ti100_ctrl_bot.x, ti100_ctrl_bot.y),
            (ti100_ctrl_bot.x, col_in.y),
        ],
        width=2,
        color='yellow',
        dash='5,5',
    )
    fi102_s_to_ctrl = DashLine(
        id='fi102_s_to_ctrl',
        waypoints=[
            (fi102_ctrl_bot.x, fi102_ctrl_bot.y),
            (fi102_ctrl_bot.x, pump_out.y),
        ],
        width=2,
        color='yellow',
        dash='5,5',
    )
    tic100_act_to_ctrl = LineLine(
        id='tic100_act_to_ctrl',
        waypoints=[
            (tic100_ctrl_bot.x, tic100_ctrl_bot.y),
            (cv_top.x, cv_top.y),
        ],
        width=2,
        color='yellow',
    )
    tic100_s_to_ctrl = DotEndLine(
        id='tic100_s_to_ctrl',
        waypoints=[
            (tic100_ctrl_right.x, tic100_ctrl_right.y),
            (475, tic100_ctrl_right.y),
            (475, 170),
        ],
        width=2,
        color='yellow',
        dash='5,5',
    )
    li100_s_to_ctrl = LineLine(
        id='li100_s_to_ctrl',
        waypoints=[
            (col_rt.x, col_rt.y),
            (li100_ctrl_left.x, li100_ctrl_left.y),
            (col_rb.x, col_rb.y),
        ],
        width=2,
        color='yellow',
    )

    # ── Stream Labels ──
    lbl_steam = StreamLabel('lbl-steam', x=0, y=215, text='STEAM', color='#ffffff', font_size=16)
    lbl_feed = StreamLabel('lbl-feed', x=0, y=387, text='FEED', color='#ffffff', font_size=16)
    lbl_condensate = StreamLabel(
        'lbl-condensate',
        x=286,
        y=520,
        text='CONDENSATE',
        color='#ffffff',
        font_size=16,
    )
    lbl_product = StreamLabel(
        'lbl-product',
        x=900,
        y=497,
        text='PRODUCT',
        color='#ffffff',
        font_size=16,
    )

    # ── Render order ──
    render_order = [
        column,
        coil,
        stirred,
        tic100_s_to_ctrl,
        fluid,
        control_valve,
        pump,
        steam_trap,
        fi100_ctrl,
        steam_to_cv,
        cv_to_coil,
        coil_to_st,
        st_to_out,
        feed_to_col,
        col_to_pump,
        pump_to_out,
        fi101_ctrl,
        tic100_ctrl,
        ti100_ctrl,
        li100_ctrl,
        fi102_ctrl,
        vp100,
        fi100_s_to_ctrl,
        fi101_s_to_ctrl,
        ti100_s_to_ctrl,
        fi102_s_to_ctrl,
        tic100_act_to_ctrl,
        tic100_s_to_ctrl,
        li100_s_to_ctrl,
        lbl_steam,
        lbl_feed,
        lbl_condensate,
        lbl_product,
    ]
    for eq in render_order:
        d.append(eq.render())

    # ── Debug grid ──
    if config.DEBUG_GRID:
        for x in range(0, int(d.width) + 1, 50):
            d.append(draw.Line(x, 0, x, d.height, stroke='#444', stroke_width=0.5))
            d.append(
                draw.Text(
                    str(x), 8, x + 2, 10, fill='#444', font_family='JetBrains Mono, monospace'
                )
            )
        for y in range(0, int(d.height) + 1, 50):
            d.append(draw.Line(0, y, d.width, y, stroke='#444', stroke_width=0.5))
            d.append(
                draw.Text(str(y), 8, 2, y - 2, fill='#444', font_family='JetBrains Mono, monospace')
            )
        all_equipment = [
            column,
            coil,
            control_valve,
            pump,
            steam_trap,
            stirred,
            fi100_ctrl,
            fi101_ctrl,
            tic100_ctrl,
            ti100_ctrl,
            li100_ctrl,
            fi102_ctrl,
        ]
        for eq in all_equipment:
            for name in eq.ports:
                p = eq.port_abs(name)
                d.append(draw.Circle(p.x, p.y, 4, fill='red', fill_opacity=0.8))
                d.append(
                    draw.Text(
                        f'{eq.id}.{name}',
                        7,
                        p.x + 6,
                        p.y - 4,
                        fill='yellow',
                        font_family='JetBrains Mono, monospace',
                    )
                )

    svg_str = d.as_svg()
    # drawsvg's stub types this as optional, but it always returns str
    assert svg_str is not None
    if svg_str.startswith('<?xml'):
        svg_str = svg_str.split('?>', 1)[-1].strip()
    return svg_str
