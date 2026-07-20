# app/biodiesel_drawing.py

from __future__ import annotations

import drawsvg as draw

from app.components.biodiesel_component import (
    PROCESS_LINE_COLORS,
    ArrowLine,
    Controller,
    DashLine,
    DotEndLine,
    InputOutputArrow,
    LineLine,
    ManualValve,
    Pump,
    ReactorBody,
    ReactorFluidLayer,
    ReactorJacket,
    ReactorJacketFluidLayer,
    Stirred,
    Text,
    ValueCard,
    Valve,
)


# MAIN FUNCTION TO BUILD BIODIESEL REACTOR DRAWING
def build_biodiesel_drawing() -> str:
    d = draw.Drawing(1500, 700)
    d.set_render_size('100%', '100%')
    d.append(draw.Rectangle(0, 0, '100%', '100%', fill='none'))

    # EQUIPMENT INSTANCES
    reactor_body = ReactorBody(id='reactor-body', x=799.34, y=317.36)

    reactor_jacket = ReactorJacket(id='reactor-jacket', x=789.17, y=355.16)

    reactor_jacket_fluid = ReactorJacketFluidLayer(
        id='reactor-jacket-fluid', jacket=reactor_jacket, fluid_opacity=1.0
    )

    reactor_fluid = ReactorFluidLayer(
        id='reactor-fluid', body=reactor_body, fluid_level=0.5, fluid_opacity=0.7
    )

    reactor_stirred = Stirred(id='reactor-stirred', x=833.49, y=238.6, status='normal')

    oil_valve = Valve(
        id='valve-oil',
        x=381,
        y=429,
        status='open',
        vp_tag='fv-100',
    )

    meoh_valve = Valve(
        id='valve-meoh',
        x=384,
        y=229,
        status='open',
        vp_tag='fv-101',
    )

    naoh_valve = Valve(
        id='valve-naoh',
        x=536,
        y=86,
        status='open',
        vp_tag='fv-102',
    )

    coolant_valve = Valve(
        id='valve-coolant',
        x=579,
        y=588,
        status='open',
        vp_tag='tv-100',
    )

    product_valve = Valve(
        id='valve-product',
        x=1123,
        y=615,
        status='open',
        vp_tag='lv-100',
    )

    vent_valve = ManualValve(id='manual-valve', x=1198, y=200, status='closed')

    oil_pump = Pump(id='pump-oil', x=193, y=451, status='normal')

    meoh_pump = Pump(id='pump-meoh', x=193, y=252, status='normal')

    naoh_pump = Pump(id='pump-naoh', x=193, y=109, status='normal')

    product_pump = Pump(id='pump-product', x=961, y=638, status='normal')

    coolant_pump = Pump(id='pump-coolant', x=193, y=610, status='normal')

    oil_input = InputOutputArrow(
        id='input-oil',
        x=0,
        y=463,
        color_scheme='yellow',
    )

    meoh_input = InputOutputArrow(
        id='input-meoh',
        x=0,
        y=264,
        color_scheme='gray',
    )

    naoh_input = InputOutputArrow(
        id='input-naoh',
        x=0,
        y=119,
        color_scheme='gray',
    )

    coolant_input = InputOutputArrow(
        id='input-coolant',
        x=0,
        y=621,
        color_scheme='blue',
    )

    product_output = InputOutputArrow(
        id='output-product',
        x=1387,
        y=634,
        color_scheme='yellow',
    )

    coolant_output = InputOutputArrow(
        id='output-coolant',
        x=1387,
        y=371,
        color_scheme='red',
    )

    vent_output = InputOutputArrow(
        id='output-vent',
        x=1387,
        y=206,
        color_scheme='gray',
    )

    # CONTROLLERS & INDICATORS
    TIC_100_controller = Controller(
        id='tic-100',
        x=542,
        y=484,
        tag='TIC-100',
        value="{{ snapshot['tic-100'] }}",
        unit='',
        value_color='normal',
        sp_tag='tic_sp',
    )

    LIC_100_controller = Controller(
        id='lic-100',
        x=975,
        y=464,
        tag='LIC-100',
        value="{{ snapshot['lic-100'] }}",
        unit='',
        value_color='normal',
        sp_tag='lic_sp',
    )

    FIC_100_controller = Controller(
        id='fic-100',
        x=342,
        y=352,
        tag='FIC-100',
        value="{{ snapshot['fic-100'] }}",
        unit='',
        value_color='normal',
        sp_tag='fic100_sp',
    )

    FIC_101_controller = Controller(
        id='fic-101',
        x=345,
        y=148,
        tag='FIC-101',
        value="{{ snapshot['fic-101'] }}",
        unit='',
        value_color='normal',
        sp_tag='fic101_sp',
    )

    FIC_102_controller = Controller(
        id='fic-102',
        x=497,
        y=0,
        tag='FIC-102',
        value="{{ snapshot['fic-102'] }}",
        unit='',
        value_color='normal',
        sp_tag='fic102_sp',
    )

    TI_100_indicator = Controller(
        id='ti-100',
        x=602,
        y=349,
        tag='TI-100',
        value="{{ snapshot['ti-100'] }}",
        unit='',
        value_color='normal',
    )

    TI_101_indicator = Controller(
        id='ti-101',
        x=559,
        y=192,
        tag='TI-101',
        value="{{ snapshot['ti-101'] }}",
        unit='',
        value_color='normal',
    )

    TI_102_indicator = Controller(
        id='ti-102',
        x=845,
        y=127,
        tag='TI-102',
        value="{{ snapshot['ti-102'] }}",
        unit='',
        value_color='normal',
    )

    TI_103_indicator = Controller(
        id='ti-103',
        x=389,
        y=553,
        tag='TI-103',
        value="{{ snapshot['ti-103'] }}",
        unit='',
        value_color='normal',
    )

    TI_104_indicator = Controller(
        id='ti-104',
        x=1140,
        y=321,
        tag='TI-104',
        value="{{ snapshot['ti-104'] }}",
        unit='',
        value_color='normal',
    )

    FI_100_indicator = Controller(
        id='fi-100',
        x=284,
        y=638,
        tag='FI-100',
        value="{{ snapshot['fi-100'] }}",
        unit='',
        value_color='normal',
    )

    FI_101_indicator = Controller(
        id='fi-101',
        x=1210,
        y=580,
        tag='FI-101',
        value="{{ snapshot['fi-101'] }}",
        unit='',
        value_color='normal',
    )

    PI_100_indicator = Controller(
        id='pi-100',
        x=1006,
        y=152,
        tag='PI-100',
        value="{{ snapshot['pi-100'] }}",
        unit='',
        value_color='normal',
    )

    # ── Valve position % cards (mirrors STHR VP-100 ValueCard) ──
    FV_100_vp = ValueCard(
        id='fv-100',
        x=367,
        y=477,
        value="{{ snapshot['fv-100'] }}",
        unit='',
    )
    FV_101_vp = ValueCard(
        id='fv-101',
        x=370,
        y=280,
        value="{{ snapshot['fv-101'] }}",
        unit='',
    )
    FV_102_vp = ValueCard(
        id='fv-102',
        x=523,
        y=141,
        value="{{ snapshot['fv-102'] }}",
        unit='',
    )
    TV_100_vp = ValueCard(
        id='tv-100',
        x=565,
        y=642,
        value="{{ snapshot['tv-100'] }}",
        unit='',
    )
    LV_100_vp = ValueCard(
        id='lv-100',
        x=1110,
        y=668,
        value="{{ snapshot['lv-100'] }}",
        unit='',
    )

    # REACTOR BODY
    reactor_feed1 = reactor_body.port_abs('inlet-1')
    reactor_feed2 = reactor_body.port_abs('inlet-2')
    reactor_outlet = reactor_body.port_abs('outlet')
    reactor_vent = reactor_body.port_abs('vent')

    # INPUT PORTS
    oil_in = oil_input.port_abs('right')
    meoh_in = meoh_input.port_abs('right')
    naoh_in = naoh_input.port_abs('right')
    coolant_in = coolant_input.port_abs('right')

    # PUMP PORTS
    oil_pump_in = oil_pump.port_abs('inlet')
    oil_pump_out = oil_pump.port_abs('outlet')
    meoh_pump_in = meoh_pump.port_abs('inlet')
    meoh_pump_out = meoh_pump.port_abs('outlet')
    naoh_pump_in = naoh_pump.port_abs('inlet')
    naoh_pump_out = naoh_pump.port_abs('outlet')
    coolant_pump_in = coolant_pump.port_abs('inlet')
    coolant_pump_out = coolant_pump.port_abs('outlet')
    product_pump_in = product_pump.port_abs('inlet')
    product_pump_out = product_pump.port_abs('outlet')

    # VALVE PORTS
    oil_valve_in = oil_valve.port_abs('left')
    oil_valve_out = oil_valve.port_abs('right')
    oil_valve_top = oil_valve.port_abs('top')
    meoh_valve_in = meoh_valve.port_abs('left')
    meoh_valve_out = meoh_valve.port_abs('right')
    meoh_valve_top = meoh_valve.port_abs('top')
    naoh_valve_in = naoh_valve.port_abs('left')
    naoh_valve_out = naoh_valve.port_abs('right')
    naoh_valve_top = naoh_valve.port_abs('top')
    coolant_valve_in = coolant_valve.port_abs('left')
    coolant_valve_out = coolant_valve.port_abs('right')
    coolant_valve_top = coolant_valve.port_abs('top')
    vent_valve_in = vent_valve.port_abs('left')
    vent_valve_out = vent_valve.port_abs('right')
    product_valve_in = product_valve.port_abs('left')
    product_valve_out = product_valve.port_abs('right')
    product_valve_top = product_valve.port_abs('top')

    # JACKET PORTS
    jacket_in = reactor_jacket.port_abs('inlet')
    jacket_out = reactor_jacket.port_abs('outlet')

    # OUTPUT PORTS
    product_out = product_output.port_abs('left')
    coolant_out = coolant_output.port_abs('left')
    vent_out = vent_output.port_abs('left')

    # CONTROLLER PORTS
    TIC_100_right = TIC_100_controller.port_abs('right')
    TIC_100_bottom = TIC_100_controller.port_abs('bottom')
    LIC_100_right = LIC_100_controller.port_abs('right')
    LIC_100_left = LIC_100_controller.port_abs('left')
    FIC_100_left = FIC_100_controller.port_abs('left')
    FIC_100_bottom = FIC_100_controller.port_abs('bottom')
    FIC_101_left = FIC_101_controller.port_abs('left')
    FIC_101_bottom = FIC_101_controller.port_abs('bottom')
    FIC_102_left = FIC_102_controller.port_abs('left')
    FIC_102_bottom = FIC_102_controller.port_abs('bottom')
    TI_100_right = TI_100_indicator.port_abs('right')
    TI_101_bottom = TI_101_indicator.port_abs('bottom')
    TI_102_left = TI_102_indicator.port_abs('left')
    TI_103_bottom = TI_103_indicator.port_abs('bottom')
    TI_104_bottom = TI_104_indicator.port_abs('bottom')
    FI_100_top = FI_100_indicator.port_abs('top')
    FI_101_bottom = FI_101_indicator.port_abs('bottom')
    PI_100_bottom = PI_100_indicator.port_abs('bottom')

    oil_input_to_oil_pump = ArrowLine(
        id='line-oil-input-to-oil-pump',
        waypoints=[(oil_in.x, oil_in.y), (oil_pump_in.x, oil_pump_in.y)],
        color=PROCESS_LINE_COLORS['oil'],
        width=4,
        mode='straight',
    )

    oil_pump_to_oil_valve = LineLine(
        id='line-oil-pump-to-oil-valve',
        waypoints=[(oil_pump_out.x, oil_pump_out.y), (oil_valve_in.x, oil_valve_in.y)],
        color=PROCESS_LINE_COLORS['oil'],
        width=4,
        mode='straight',
    )

    meoh_input_to_meoh_pump = ArrowLine(
        id='line-meoh-input-to-meoh-pump',
        waypoints=[(meoh_in.x, meoh_in.y), (meoh_pump_in.x, meoh_pump_in.y)],
        color=PROCESS_LINE_COLORS['meoh'],
        width=4,
        mode='straight',
    )

    meoh_pump_to_meoh_valve = LineLine(
        id='line-meoh-pump-to-meoh-valve',
        waypoints=[(meoh_pump_out.x, meoh_pump_out.y), (meoh_valve_in.x, meoh_valve_in.y)],
        color=PROCESS_LINE_COLORS['meoh'],
        width=4,
        mode='straight',
    )

    naoh_input_to_naoh_pump = ArrowLine(
        id='line-naoh-input-to-naoh-pump',
        waypoints=[(naoh_in.x, naoh_in.y), (naoh_pump_in.x, naoh_pump_in.y)],
        color=PROCESS_LINE_COLORS['naoh'],
        width=4,
        mode='straight',
    )

    naoh_pump_to_naoh_valve = LineLine(
        id='line-naoh-pump-to-naoh-valve',
        waypoints=[(naoh_pump_out.x, naoh_pump_out.y), (naoh_valve_in.x, naoh_valve_in.y)],
        color=PROCESS_LINE_COLORS['naoh'],
        width=4,
        mode='straight',
    )

    coolant_input_to_coolant_pump = ArrowLine(
        id='line-coolant-input-to-coolant-pump',
        waypoints=[(coolant_in.x, coolant_in.y), (coolant_pump_in.x, coolant_pump_in.y)],
        color=PROCESS_LINE_COLORS['cooling'],
        width=4,
        mode='straight',
    )

    coolant_pump_to_coolant_valve = LineLine(
        id='line-coolant-pump-to-coolant-valve',
        waypoints=[
            (coolant_pump_out.x, coolant_pump_out.y),
            (coolant_valve_in.x, coolant_valve_in.y),
        ],
        color=PROCESS_LINE_COLORS['cooling'],
        width=4,
        mode='straight',
    )

    jacket_to_coolant_out = LineLine(
        id='line-jacket-to-coolant-output',
        waypoints=[(jacket_out.x, jacket_out.y), (coolant_out.x, coolant_out.y)],
        color=PROCESS_LINE_COLORS['red'],
        width=4,
        mode='straight',
    )

    vent_valve_to_vent_out = LineLine(
        id='line-vent-valve-to-vent-output',
        waypoints=[(vent_valve_out.x, vent_valve_out.y), (vent_out.x, vent_out.y)],
        color=PROCESS_LINE_COLORS['white'],
        width=4,
        mode='straight',
    )

    oil_valve_to_reactor = ArrowLine(
        id='line-oil-valve-to-reactor',
        waypoints=[
            (oil_valve_out.x, oil_valve_out.y),
            (reactor_jacket.x - 33, oil_valve_out.y),
            (reactor_jacket.x - 33, oil_valve_out.y - 160),
            (reactor_body.x + 9.66, oil_valve_out.y - 160),
            (reactor_body.x + 9.66, reactor_feed1.y),
        ],
        color=PROCESS_LINE_COLORS['oil'],
        width=4,
        mode='elbow',
        elbow_radius=15,
    )

    coolant_valve_to_reactor_jacket = ArrowLine(
        id='line-coolant-valve-to-reactor-jacket',
        waypoints=[
            (coolant_valve_out.x, coolant_valve_out.y),
            (reactor_jacket.x - 33.17, coolant_valve_out.y),
            (reactor_jacket.x - 33.17, jacket_in.y),
            (jacket_in.x, jacket_in.y),
        ],
        color=PROCESS_LINE_COLORS['cooling'],
        width=4,
        mode='elbow',
        elbow_radius=10,
    )

    naoh_valve_to_reactor = ArrowLine(
        id='line-naoh-valve-to-reactor',
        waypoints=[
            (naoh_valve_out.x, naoh_valve_out.y),
            (reactor_feed2.x, naoh_valve_out.y),
            (reactor_feed2.x, reactor_feed2.y),
        ],
        color=PROCESS_LINE_COLORS['naoh'],
        width=4,
        mode='elbow',
        elbow_radius=15,
    )

    meoh_valve_to_naoh_line = ArrowLine(
        id='line-meoh-valve-to-naoh-line',
        waypoints=[
            (meoh_valve_out.x, meoh_valve_out.y),
            (reactor_feed2.x, meoh_valve_out.y),
        ],
        color=PROCESS_LINE_COLORS['meoh'],
        width=4,
        mode='elbow',
        elbow_radius=15,
    )

    reactor_outlet_to_product_pump = ArrowLine(
        id='line-reactor-outlet-to-product-pump',
        waypoints=[
            (reactor_outlet.x, reactor_outlet.y),
            (reactor_outlet.x, product_pump_in.y),
            (product_pump_in.x, product_pump_in.y),
        ],
        color=PROCESS_LINE_COLORS['product'],
        width=4,
        mode='elbow',
        elbow_radius=15,
    )

    product_pump_to_product_valve = LineLine(
        id='line-product-pump-to-product-valve',
        waypoints=[
            (product_pump_out.x, product_pump_out.y),
            (product_valve_in.x, product_valve_in.y),
        ],
        color=PROCESS_LINE_COLORS['product'],
        width=4,
        mode='straight',
    )

    product_valve_to_product_out = LineLine(
        id='line-product-valve-to-product-output',
        waypoints=[
            (product_valve_out.x, product_valve_out.y),
            (product_out.x, product_out.y),
        ],
        color=PROCESS_LINE_COLORS['product'],
        width=4,
        mode='straight',
    )

    reactor_vent_to_vent_valve = LineLine(
        id='line-reactor-vent-to-vent-valve',
        waypoints=[
            (reactor_vent.x, reactor_vent.y),
            (reactor_vent.x, vent_valve_in.y),
            (vent_valve_in.x, vent_valve_in.y),
        ],
        color=PROCESS_LINE_COLORS['white'],
        width=4,
        mode='elbow',
        elbow_radius=15,
    )

    level_sensor_to_LIC_100 = LineLine(
        id='signal-level-sensor-to-LIC-100',
        waypoints=[
            (jacket_out.x, LIC_100_left.y - 13.5),
            (LIC_100_left.x, LIC_100_left.y),
            (jacket_out.x, LIC_100_left.y + 13.5),
        ],
        color=PROCESS_LINE_COLORS['signal'],
        width=2,
        mode='elbow',
        elbow_radius=5,
    )

    LIC_100_to_product_valve = DashLine(
        id='signal-LIC-100-to-product-valve',
        waypoints=[
            (LIC_100_right.x, LIC_100_right.y),
            (product_valve_top.x, LIC_100_right.y),
            (product_valve_top.x, product_valve_top.y),
        ],
        color=PROCESS_LINE_COLORS['signal'],
        width=2,
        mode='elbow',
        elbow_radius=5,
        dash='4 4',
    )

    flow_sensor_to_FIC_100 = LineLine(
        id='signal-flow-sensor-to-FIC-100',
        waypoints=[
            (oil_pump_out.x + 33, oil_pump_out.y),
            (oil_pump_out.x + 33, FIC_100_left.y),
            (FIC_100_left.x, FIC_100_left.y),
        ],
        color=PROCESS_LINE_COLORS['signal'],
        width=2,
        mode='elbow',
        elbow_radius=5,
    )

    FIC_100_to_oil_valve = DashLine(
        id='signal-FIC-100-to-oil-valve',
        waypoints=[
            (FIC_100_bottom.x, FIC_100_bottom.y),
            (oil_valve_top.x, oil_valve_top.y),
        ],
        color=PROCESS_LINE_COLORS['signal'],
        width=2,
        mode='straight',
        dash='4 4',
    )

    flow_sensor_to_FIC_101 = LineLine(
        id='signal-flow-sensor-to-FIC-101',
        waypoints=[
            (meoh_pump_out.x + 33, meoh_pump_out.y),
            (meoh_pump_out.x + 33, FIC_101_left.y),
            (FIC_101_left.x, FIC_101_left.y),
        ],
        color=PROCESS_LINE_COLORS['signal'],
        width=2,
        mode='elbow',
        elbow_radius=5,
    )

    FIC_101_to_meoh_valve = DashLine(
        id='signal-FIC-101-to-meoh-valve',
        waypoints=[
            (FIC_101_bottom.x, FIC_101_bottom.y),
            (meoh_valve_top.x, meoh_valve_top.y),
        ],
        color=PROCESS_LINE_COLORS['signal'],
        width=2,
        mode='straight',
        dash='4 4',
    )

    flow_sensor_to_FIC_102 = LineLine(
        id='signal-flow-sensor-to-FIC-102',
        waypoints=[
            (naoh_pump_out.x + 145, naoh_pump_out.y),
            (naoh_pump_out.x + 145, FIC_102_left.y),
            (FIC_102_left.x, FIC_102_left.y),
        ],
        color=PROCESS_LINE_COLORS['signal'],
        width=2,
        mode='elbow',
        elbow_radius=5,
    )

    FIC_102_to_naoh_valve = DashLine(
        id='signal-FIC-102-to-naoh-valve',
        waypoints=[
            (FIC_102_bottom.x, FIC_102_bottom.y),
            (naoh_valve_top.x, naoh_valve_top.y),
        ],
        color=PROCESS_LINE_COLORS['signal'],
        width=2,
        mode='straight',
        dash='4 4',
    )

    temp_sensor_to_TIC_100 = DotEndLine(
        id='signal-temp-sensor-to-TIC-100',
        waypoints=[
            (TIC_100_right.x, TIC_100_right.y),
            (reactor_body.x + 22, TIC_100_right.y),
        ],
        color=PROCESS_LINE_COLORS['signal'],
        width=2,
        mode='straight',
    )

    TIC_100_to_coolant_valve = DashLine(
        id='signal-TIC-100-to-coolant-valve',
        waypoints=[
            (TIC_100_bottom.x, TIC_100_bottom.y),
            (coolant_valve_top.x, coolant_valve_top.y),
        ],
        color=PROCESS_LINE_COLORS['signal'],
        width=2,
        mode='straight',
        dash='4 4',
    )

    temp_sensor_to_TI_100 = LineLine(
        id='signal-temp-sensor-to-TI-100',
        waypoints=[
            (reactor_jacket.x - 33, TI_100_right.y - 13.5),
            (TI_100_right.x, TI_100_right.y),
            (reactor_jacket.x - 33, TI_100_right.y + 13.5),
        ],
        color=PROCESS_LINE_COLORS['signal'],
        width=2,
        mode='elbow',
        elbow_radius=5,
    )

    temp_sensor_to_TI_101 = LineLine(
        id='signal-temp-sensor-to-TI-101',
        waypoints=[
            (TI_101_bottom.x - 13.5, meoh_valve_out.y),
            (TI_101_bottom.x, TI_101_bottom.y),
            (TI_101_bottom.x + 13.5, meoh_valve_out.y),
        ],
        color=PROCESS_LINE_COLORS['signal'],
        width=2,
        mode='elbow',
        elbow_radius=5,
    )

    temp_sensor_to_TI_102 = LineLine(
        id='signal-temp-sensor-to-TI-102',
        waypoints=[
            (reactor_feed2.x, TI_102_left.y - 13.5),
            (TI_102_left.x, TI_102_left.y),
            (reactor_feed2.x, TI_102_left.y + 13.5),
        ],
        color=PROCESS_LINE_COLORS['signal'],
        width=2,
        mode='elbow',
        elbow_radius=5,
    )

    temp_sensor_to_TI_103 = LineLine(
        id='signal-temp-sensor-to-TI-103',
        waypoints=[
            (TI_103_bottom.x - 13.5, coolant_pump_out.y),
            (TI_103_bottom.x, TI_103_bottom.y),
            (TI_103_bottom.x + 13.5, coolant_pump_out.y),
        ],
        color=PROCESS_LINE_COLORS['signal'],
        width=2,
        mode='elbow',
        elbow_radius=5,
    )

    temp_sensor_to_TI_104 = LineLine(
        id='signal-temp-sensor-to-TI-104',
        waypoints=[
            (TI_104_bottom.x - 13.5, jacket_out.y),
            (TI_104_bottom.x, TI_104_bottom.y),
            (TI_104_bottom.x + 13.5, jacket_out.y),
        ],
        color=PROCESS_LINE_COLORS['signal'],
        width=2,
        mode='elbow',
        elbow_radius=5,
    )

    flow_sensor_to_FI_100 = LineLine(
        id='signal-flow-sensor-to-FI-100',
        waypoints=[
            (FI_100_top.x - 13.5, coolant_pump_out.y),
            (FI_100_top.x, FI_100_top.y),
            (FI_100_top.x + 13.5, coolant_pump_out.y),
        ],
        color=PROCESS_LINE_COLORS['signal'],
        width=2,
        mode='elbow',
        elbow_radius=5,
    )

    flow_sensor_to_FI_101 = LineLine(
        id='signal-flow-sensor-to-FI-101',
        waypoints=[
            (FI_101_bottom.x - 13.5, product_pump_out.y),
            (FI_101_bottom.x, FI_101_bottom.y),
            (FI_101_bottom.x + 13.5, product_pump_out.y),
        ],
        color=PROCESS_LINE_COLORS['signal'],
        width=2,
        mode='elbow',
        elbow_radius=5,
    )

    press_sensor_to_PI_100 = LineLine(
        id='signal-pressure-sensor-to-PI-100',
        waypoints=[
            (PI_100_bottom.x - 13.5, vent_valve_in.y),
            (PI_100_bottom.x, PI_100_bottom.y),
            (PI_100_bottom.x + 13.5, vent_valve_in.y),
        ],
        color=PROCESS_LINE_COLORS['signal'],
        width=2,
        mode='elbow',
        elbow_radius=5,
    )

    # Text for arrows
    text_oil_in = Text(
        'text-oil-in',
        x=56.5,
        y=478,
        text='OIL',
        font_weight='bold',
        color='#000000',
        font_family='JetBrains Mono, monospace',
    )
    text_oil_above = Text(
        'text-oil-above',
        x=5,
        y=448,
        text='FEED - Palm Oil (RBDPO)',
        font_size=16,
        color=PROCESS_LINE_COLORS['oil'],
        font_family='JetBrains Mono, monospace',
        text_anchor='start',
    )

    text_meoh_in = Text(
        'text-meoh-in',
        x=56.5,
        y=279,
        text='METHANOL',
        font_weight='bold',
        color='#000000',
        font_family='JetBrains Mono, monospace',
    )
    text_meoh_above = Text(
        'text-meoh-above',
        x=5,
        y=249,
        text='FEED - Methanol (MeOH)',
        font_size=16,
        color=PROCESS_LINE_COLORS['meoh'],
        font_family='JetBrains Mono, monospace',
        text_anchor='start',
    )

    text_naoh_in = Text(
        'text-naoh-in',
        x=56.5,
        y=134,
        text='CATALYST',
        font_weight='bold',
        color='#000000',
        font_family='JetBrains Mono, monospace',
    )
    text_naoh_above = Text(
        'text-naoh-above',
        x=5,
        y=104,
        text='FEED - Sodium Hydroxide (NaOH)',
        font_size=16,
        color=PROCESS_LINE_COLORS['naoh'],
        font_family='JetBrains Mono, monospace',
        text_anchor='start',
    )

    text_coolant_in = Text(
        'text-coolant-in',
        x=56.5,
        y=636,
        text='COOLANT',
        font_weight='bold',
        color='#000000',
        font_family='JetBrains Mono, monospace',
    )
    text_coolant_above = Text(
        'text-coolant-above',
        x=5,
        y=606,
        text='INLET - Cooling Water (CW)',
        font_size=16,
        color=PROCESS_LINE_COLORS['cooling'],
        font_family='JetBrains Mono, monospace',
        text_anchor='start',
    )

    text_product_out = Text(
        'text-product-out',
        x=1443.5,
        y=649,
        text='PRODUCT',
        font_weight='bold',
        color='#000000',
        font_family='JetBrains Mono, monospace',
    )
    text_product_below = Text(
        'text-product-below',
        x=1495,
        y=679,
        text='PRODUCT - Fatty Acid Methyl Ester (FAME)',
        font_size=16,
        color=PROCESS_LINE_COLORS['product'],
        font_family='JetBrains Mono, monospace',
        text_anchor='end',
    )

    text_coolant_out = Text(
        'text-coolant-out',
        x=1443.5,
        y=386,
        text='COOLANT',
        font_weight='bold',
        color='#000000',
        font_family='JetBrains Mono, monospace',
    )
    text_coolant_out_above = Text(
        'text-coolant-out-above',
        x=1495,
        y=356,
        text='OUTLET - Cooling Water (CW)',
        font_size=16,
        color=PROCESS_LINE_COLORS['red'],
        font_family='JetBrains Mono, monospace',
        text_anchor='end',
    )

    text_vent_out = Text(
        'text-vent-out',
        x=1443.5,
        y=221,
        text='VENT',
        font_weight='bold',
        color='#000000',
        font_family='JetBrains Mono, monospace',
    )
    text_vent_above = Text(
        'text-vent-above',
        x=1495,
        y=191,
        text='EXHAUST',
        font_size=16,
        color=PROCESS_LINE_COLORS['white'],
        font_family='JetBrains Mono, monospace',
        text_anchor='end',
    )

    # Append in logical layering order
    d.append(reactor_jacket.render())
    d.append(reactor_jacket_fluid.render())
    d.append(reactor_body.render())
    d.append(reactor_stirred.render())
    d.append(reactor_fluid.render())
    d.append(oil_valve.render())
    d.append(meoh_valve.render())
    d.append(naoh_valve.render())
    d.append(coolant_valve.render())
    d.append(product_valve.render())
    d.append(vent_valve.render())
    d.append(oil_pump.render())
    d.append(meoh_pump.render())
    d.append(naoh_pump.render())
    d.append(product_pump.render())
    d.append(coolant_pump.render())
    d.append(oil_input.render())
    d.append(meoh_input.render())
    d.append(naoh_input.render())
    d.append(coolant_input.render())
    d.append(product_output.render())
    d.append(coolant_output.render())
    d.append(vent_output.render())
    d.append(text_oil_in.render())
    d.append(text_oil_above.render())
    d.append(text_meoh_in.render())
    d.append(text_meoh_above.render())
    d.append(text_naoh_in.render())
    d.append(text_naoh_above.render())
    d.append(text_coolant_in.render())
    d.append(text_coolant_above.render())
    d.append(text_product_out.render())
    d.append(text_product_below.render())
    d.append(text_coolant_out.render())
    d.append(text_coolant_out_above.render())
    d.append(text_vent_out.render())
    d.append(text_vent_above.render())
    d.append(TIC_100_controller.render())
    d.append(LIC_100_controller.render())
    d.append(FIC_100_controller.render())
    d.append(FIC_101_controller.render())
    d.append(FIC_102_controller.render())
    d.append(TI_100_indicator.render())
    d.append(TI_101_indicator.render())
    d.append(TI_102_indicator.render())
    d.append(TI_103_indicator.render())
    d.append(TI_104_indicator.render())
    d.append(FI_100_indicator.render())
    d.append(FI_101_indicator.render())
    d.append(PI_100_indicator.render())
    d.append(FV_100_vp.render())
    d.append(FV_101_vp.render())
    d.append(FV_102_vp.render())
    d.append(TV_100_vp.render())
    d.append(LV_100_vp.render())
    d.append(oil_input_to_oil_pump.render())
    d.append(oil_pump_to_oil_valve.render())
    d.append(meoh_input_to_meoh_pump.render())
    d.append(meoh_pump_to_meoh_valve.render())
    d.append(naoh_input_to_naoh_pump.render())
    d.append(naoh_pump_to_naoh_valve.render())
    d.append(coolant_input_to_coolant_pump.render())
    d.append(coolant_pump_to_coolant_valve.render())
    d.append(jacket_to_coolant_out.render())
    d.append(vent_valve_to_vent_out.render())
    d.append(oil_valve_to_reactor.render())
    d.append(coolant_valve_to_reactor_jacket.render())
    d.append(naoh_valve_to_reactor.render())
    d.append(meoh_valve_to_naoh_line.render())
    d.append(reactor_outlet_to_product_pump.render())
    d.append(product_pump_to_product_valve.render())
    d.append(product_valve_to_product_out.render())
    d.append(reactor_vent_to_vent_valve.render())
    d.append(level_sensor_to_LIC_100.render())
    d.append(LIC_100_to_product_valve.render())
    d.append(flow_sensor_to_FIC_100.render())
    d.append(FIC_100_to_oil_valve.render())
    d.append(flow_sensor_to_FIC_101.render())
    d.append(FIC_101_to_meoh_valve.render())
    d.append(flow_sensor_to_FIC_102.render())
    d.append(FIC_102_to_naoh_valve.render())
    d.append(temp_sensor_to_TIC_100.render())
    d.append(TIC_100_to_coolant_valve.render())
    d.append(temp_sensor_to_TI_100.render())
    d.append(temp_sensor_to_TI_101.render())
    d.append(temp_sensor_to_TI_102.render())
    d.append(temp_sensor_to_TI_103.render())
    d.append(temp_sensor_to_TI_104.render())
    d.append(flow_sensor_to_FI_100.render())
    d.append(flow_sensor_to_FI_101.render())
    d.append(press_sensor_to_PI_100.render())

    DEBUG_GRID = False

    if DEBUG_GRID:
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
            reactor_body,
            reactor_jacket,
            reactor_jacket_fluid,
            reactor_fluid,
            oil_valve,
            meoh_valve,
            naoh_valve,
            coolant_valve,
            product_valve,
            vent_valve,
            oil_pump,
            meoh_pump,
            naoh_pump,
            product_pump,
            coolant_pump,
            oil_input,
            meoh_input,
            naoh_input,
            coolant_input,
            product_output,
            coolant_output,
            vent_output,
            TIC_100_controller,
            LIC_100_controller,
            FIC_100_controller,
            FIC_101_controller,
            FIC_102_controller,
            TI_100_indicator,
            TI_101_indicator,
            TI_102_indicator,
            TI_103_indicator,
            TI_104_indicator,
            FI_100_indicator,
            FI_101_indicator,
            PI_100_indicator,
        ]

        for eq in all_equipment:
            # Mengambil ports secara aman. Jika tidak ada atribut 'ports' atau
            # bernilai None, kembalikan dict kosong
            ports = getattr(eq, 'ports', None)
            if not ports:
                continue  # Lewati jika tidak ada port

            for name in ports:
                p = eq.port_abs(name)

                # Jaga-jaga jika method port_abs mengembalikan None
                if p is None:
                    continue

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
    assert svg_str is not None
    if svg_str.startswith('<?xml'):
        svg_str = svg_str.split('?>', 1)[-1].strip()
    return svg_str
