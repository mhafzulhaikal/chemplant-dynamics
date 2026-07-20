# app/components/components.py

"""SVG equipment and pipeline primitives — copied verbatim from V1.1.

This module is pure UI. It must not import the engine, the gateway,
or any service. It only knows how to draw shapes via drawsvg.
"""

from __future__ import annotations

import drawsvg as draw

from app.components.svg_primitives import Equipment, Port, metallic_gradient


# Re-export under the historical private name so the rest of the
# module's long-lived ``_metallic_gradient`` call sites keep working.
def _metallic_gradient(grad_id, x1, y1, x2, y2, colors, units='userSpaceOnUse'):
    return metallic_gradient(grad_id, x1, y1, x2, y2, colors, units)


STEEL_STOPS = [
    (0.00, '#99AEB6'),
    (0.15, '#D2ECF7'),
    (0.25, '#E6F4FA'),
    (0.52, '#B5CED7'),
    (0.69, '#A1B7C0'),
    (0.80, '#98ADB5'),
    (0.92, '#8FA3AB'),
    (1.00, '#A5BBC4'),
]

GREY_BODY_STOPS = [
    (0.00, '#BAC0C1'),
    (0.15, '#F4FAFC'),
    (0.25, '#F8FCFD'),
    (0.44, '#D5DBDD'),
    (0.60, '#BDC3C4'),
    (0.80, '#A0A4A6'),
    (0.97, '#929697'),
    (1.00, '#C2C7C9'),
]

COPPER_STOPS = [
    (0.00, '#BA9A70'),
    (0.22, '#D1AD7F'),
    (0.57, '#EEDCC9'),
    (0.84, '#E5C9A8'),
    (1.00, '#C9A67A'),
]

COLUMN_BODY_STOPS = [
    (0.00, '#5288AF'),
    (0.15, '#7DB8E7'),
    (0.25, '#A1C7EB'),
    (0.44, '#5E9BC8'),
    (0.60, '#538AB2'),
    (0.80, '#457496'),
    (0.97, '#3F6989'),
    (1.00, '#558DB6'),
]

COLUMN_LINE_STOPS = [
    (0.00, '#3475A8'),
    (0.15, '#61A2DE'),
    (0.25, '#7FADE1'),
    (0.44, '#3D86C0'),
    (0.60, '#3577AB'),
    (0.80, '#2B6390'),
    (0.97, '#275A84'),
    (1.00, '#377AAF'),
]

LEG_STOPS = [
    (0.00, '#898D92'),
    (0.03, '#D1D5DA'),
    (0.08, '#B3B8BE'),
    (0.64, '#B0B5BB'),
    (0.95, '#ACB1B7'),
    (1.00, '#7F8387'),
]

PIPE_STOPS = [
    (0.00, '#686E75'),
    (0.22, '#9BA3AD'),
    (0.57, '#E6E8EC'),
    (0.84, '#CAD0D8'),
    (1.00, '#858C95'),
]


# COIL
class Coil(Equipment):
    """Copper coil with 12 front turns, back turns, and end caps."""

    def __init__(self, id: str, x: float = 0, y: float = 0, status: str = 'normal'):
        super().__init__(
            id=id,
            x=x,
            y=y,
            status=status,
            ports={
                'in': Port(0, 0),
                'out': Port(0, 125),
            },
        )

    def _add_defs(self, g: draw.Group):
        """Register all gradient definitions."""
        # Front turn gradients (12)
        front_y_starts = [
            111.017,
            102.005,
            93.005,
            84.002,
            75.003,
            66.002,
            57.211,
            48.199,
            39.199,
            30.196,
            21.197,
            12.196,
        ]
        front_y_ends = [
            114.888,
            105.875,
            96.875,
            87.873,
            78.873,
            69.872,
            61.082,
            52.069,
            43.069,
            34.067,
            25.067,
            16.066,
        ]
        for i in range(12):
            n = 12 - i
            g.append(
                _metallic_gradient(
                    f'gradient-coil-front-turn-{n}',
                    11.925,
                    front_y_starts[i],
                    11.232,
                    front_y_ends[i],
                    COPPER_STOPS,
                )
            )

        # Back turn gradients (upper 1-7)
        back_upper_y1 = [60.387, 51.300, 42.449, 33.704, 24.324, 15.519, 15.519]
        back_upper_y2 = [56.465, 47.379, 38.528, 29.782, 20.402, 11.597, 11.597]
        for i in range(7):
            n = 7 - i
            g.append(
                _metallic_gradient(
                    f'gradient-coil-back-turn-{n}',
                    12.111,
                    back_upper_y1[i],
                    11.792,
                    back_upper_y2[i],
                    COPPER_STOPS,
                )
            )

        # Back turn gradients (lower 8-13)
        back_lower_y1 = [114.300, 105.213, 96.362, 87.617, 78.237, 69.432]
        back_lower_y2 = [110.378, 101.292, 92.441, 83.695, 74.315, 65.510]
        for i in range(6):
            n = 13 - i
            g.append(
                _metallic_gradient(
                    f'gradient-coil-back-turn-{n}',
                    11.674,
                    back_lower_y1[i],
                    11.355,
                    back_lower_y2[i],
                    COPPER_STOPS,
                )
            )

        # Top cap
        g.append(
            _metallic_gradient('gradient-coil-top-cap', 5.406, 0.899, 4.667, 4.761, COPPER_STOPS)
        )

        # Bottom cap
        g.append(
            _metallic_gradient(
                'gradient-coil-bottom-cap', 5.603, 120.591, 5.773, 124.523, COPPER_STOPS
            )
        )

    def render(self) -> draw.Group:
        g = draw.Group(
            id=self.id,
            class_=f'equipment coil status-{self.status}',
            transform=f'translate({self.x},{self.y})',
        )
        self._add_defs(g)

        # ── Front turns (12, bottom to top) ──
        front_paths = [
            'M7.44484 112.565L7.52716 111.971C7.66436 110.981 8.53163 110.401 9.39926 110.528L53.3593 116.953C54.3233 117.094 54.9985 117.899 54.8613 118.889L54.779 119.483C54.6418 120.473 53.7608 121.153 52.7967 121.012L8.83674 114.587C7.9691 114.46 7.30764 113.555 7.44484 112.565Z',
            'M7.44484 103.552L7.52716 102.958C7.66436 101.968 8.53163 101.388 9.39926 101.515L53.3593 107.94C54.3233 108.081 54.9985 108.887 54.8613 109.877L54.779 110.471C54.6418 111.461 53.7608 112.14 52.7967 111.999L8.83674 105.574C7.9691 105.447 7.30764 104.542 7.44484 103.552Z',
            'M7.44484 94.5525L7.52716 93.9585C7.66436 92.9685 8.53163 92.3882 9.39926 92.515L53.3593 98.9401C54.3233 99.081 54.9985 99.8867 54.8613 100.877L54.779 101.471C54.6418 102.461 53.7608 103.14 52.7967 102.999L8.83674 96.5741C7.9691 96.4473 7.30764 95.5425 7.44484 94.5525Z',
            'M7.44484 85.55L7.52716 84.956C7.66436 83.9659 8.53163 83.3857 9.39926 83.5125L53.3593 89.9376C54.3233 90.0785 54.9985 90.8842 54.8613 91.8742L54.779 92.4682C54.6418 93.4583 53.7608 94.1376 52.7967 93.9966L8.83674 87.5716C7.9691 87.4448 7.30764 86.54 7.44484 85.55Z',
            'M7.44484 76.5501L7.52716 75.9561C7.66436 74.9661 8.53163 74.3858 9.39926 74.5126L53.3593 80.9377C54.3233 81.0786 54.9985 81.8843 54.8613 82.8743L54.779 83.4683C54.6418 84.4584 53.7608 85.1377 52.7967 84.9968L8.83674 78.5717C7.9691 78.4449 7.30764 77.5401 7.44484 76.5501Z',
            'M7.44484 67.5495L7.52716 66.9555C7.66436 65.9655 8.53163 65.3852 9.39926 65.512L53.3593 71.9371C54.3233 72.078 54.9985 72.8837 54.8613 73.8737L54.779 74.4677C54.6418 75.4578 53.7608 76.1371 52.7967 75.9962L8.83674 69.5711C7.9691 69.4443 7.30764 68.5395 7.44484 67.5495Z',
            'M7.44484 58.759L7.52716 58.165C7.66436 57.175 8.53163 56.5947 9.39926 56.7215L53.3593 63.1466C54.3233 63.2875 54.9985 64.0932 54.8613 65.0833L54.779 65.6773C54.6418 66.6673 53.7608 67.3466 52.7967 67.2057L8.83674 60.7806C7.9691 60.6538 7.30764 59.7491 7.44484 58.759Z',
            'M7.44484 49.7464L7.52716 49.1524C7.66436 48.1623 8.53163 47.582 9.39926 47.7088L53.3593 54.1339C54.3233 54.2748 54.9985 55.0806 54.8613 56.0706L54.779 56.6646C54.6418 57.6546 53.7608 58.3339 52.7967 58.193L8.83674 51.7679C7.9691 51.6411 7.30764 50.7364 7.44484 49.7464Z',
            'M7.44484 40.7465L7.52716 40.1524C7.66436 39.1624 8.53163 38.5821 9.39926 38.7089L53.3593 45.134C54.3233 45.2749 54.9985 46.0807 54.8613 47.0707L54.779 47.6647C54.6418 48.6547 53.7608 49.334 52.7967 49.1931L8.83674 42.768C7.9691 42.6412 7.30764 41.7365 7.44484 40.7465Z',
            'M7.44484 31.744L7.52716 31.1499C7.66436 30.1599 8.53163 29.5796 9.39926 29.7064L53.3593 36.1315C54.3233 36.2724 54.9985 37.0782 54.8613 38.0682L54.779 38.6622C54.6418 39.6522 53.7608 40.3315 52.7967 40.1906L8.83674 33.7655C7.9691 33.6387 7.30764 32.734 7.44484 31.744Z',
            'M7.44484 22.7441L7.52716 22.1501C7.66436 21.16 8.53163 20.5797 9.39926 20.7066L53.3593 27.1316C54.3233 27.2725 54.9985 28.0783 54.8613 29.0683L54.779 29.6623C54.6418 30.6523 53.7608 31.3316 52.7967 31.1907L8.83674 24.7657C7.9691 24.6388 7.30764 23.7341 7.44484 22.7441Z',
            'M7.44484 13.7435L7.52716 13.1495C7.66436 12.1594 8.53163 11.5791 9.39926 11.7059L53.3593 18.131C54.3233 18.2719 54.9985 19.0777 54.8613 20.0677L54.779 20.6617C54.6418 21.6517 53.7608 22.331 52.7967 22.1901L8.83674 15.765C7.9691 15.6382 7.30764 14.7335 7.44484 13.7435Z',
        ]
        for i, d in enumerate(front_paths):
            n = 12 - i
            g.append(
                draw.Path(
                    d=d, id=f'coil-front-turn-{n}', fill=f'url(#gradient-coil-front-turn-{n})'
                )
            )

        # ── Back turns (upper, 7 → 1) ──
        back_upper_paths = [
            'M7.85719 58.3103L7.88922 59.0095C7.93497 60.0084 8.74512 60.6698 9.62052 60.6273L53.2931 58.5067C54.1685 58.4642 54.9146 57.7272 54.8688 56.7283L54.8368 56.0291C54.7956 55.1301 53.9809 54.3688 53.1055 54.4113L9.43295 56.5319C8.55755 56.5744 7.81602 57.4113 7.85719 58.3103Z',
            'M7.85719 49.2234L7.88922 49.9226C7.93497 50.9215 8.74512 51.5829 9.62052 51.5404L53.2931 49.4198C54.1685 49.3773 54.9146 48.6403 54.8688 47.6414L54.8368 46.9422C54.7956 46.0432 53.9809 45.2818 53.1055 45.3243L9.43295 47.4449C8.55755 47.4875 7.81602 48.3244 7.85719 49.2234Z',
            'M7.85719 40.3724L7.88922 41.0716C7.93497 42.0705 8.74512 42.7319 9.62052 42.6894L53.2931 40.5688C54.1685 40.5263 54.9146 39.7893 54.8688 38.7904L54.8368 38.0912C54.7956 37.1922 53.9809 36.4308 53.1055 36.4733L9.43295 38.594C8.55755 38.6365 7.81602 39.4734 7.85719 40.3724Z',
            'M7.85719 31.6273L7.88922 32.3265C7.93497 33.3254 8.74512 33.9868 9.62052 33.9443L53.2931 31.8237C54.1685 31.7812 54.9146 31.0442 54.8688 30.0453L54.8368 29.3461C54.7956 28.4471 53.9809 27.6857 53.1055 27.7282L9.43295 29.8488C8.55755 29.8914 7.81602 30.7283 7.85719 31.6273Z',
            'M7.85719 22.2473L7.88922 22.9465C7.93497 23.9454 8.74512 24.6068 9.62052 24.5643L53.2931 22.4437C54.1685 22.4012 54.9146 21.6642 54.8688 20.6653L54.8368 19.9661C54.7956 19.0671 18.3057 18.3057 53.1055 18.3482L9.43295 20.4688C8.55755 20.5113 7.81602 21.3482 7.85719 22.2473Z',
            'M7.85719 13.4421L7.88922 14.1413C7.93497 15.1402 8.74512 15.8016 9.62052 15.7591L53.2931 13.6385C54.1685 13.596 54.9146 12.859 54.8688 11.8601L54.8368 11.1609C54.7956 10.2619 53.9809 9.50056 53.1055 9.54307L9.43295 11.6637C8.55755 11.7062 7.81602 12.5431 7.85719 13.4421Z',
        ]
        for i, d in enumerate(back_upper_paths):
            n = 7 - i
            g.append(
                draw.Path(d=d, id=f'coil-back-turn-{n}', fill=f'url(#gradient-coil-back-turn-{n})')
            )

        # ── Top cap ──
        g.append(
            draw.Path(
                d='M0.274189 2.27169L0.365586 1.67908C0.517913 0.691391 1.49013 0.1408 2.54806 0.312877L53.0405 8.52566C54.0984 8.69774 54.8574 9.52991 54.7051 10.5176L54.6137 11.1102C54.4613 12.0979 53.4739 12.7473 52.4159 12.5752L1.92352 4.3624C0.865584 4.19032 0.121862 3.25938 0.274189 2.27169Z',
                id='coil-top-cap',
                fill='url(#gradient-coil-top-cap)',
            )
        )

        # ── Bottom cap ──
        g.append(
            draw.Path(
                d='M1.00652 123.107L0.965765 122.509C0.89784 121.511 1.72453 120.75 2.69591 120.68L52.7218 117.088C53.6932 117.018 54.615 117.654 54.6829 118.651L54.7237 119.25C54.7916 120.247 53.9717 121.108 53.0003 121.178L2.9744 124.77C2.00302 124.84 1.07444 124.105 1.00652 123.107Z',
                id='coil-bottom-cap',
                fill='url(#gradient-coil-bottom-cap)',
            )
        )

        # ── Back turns (lower, 13 → 8) ──
        back_lower_paths = [
            'M7.42 112.223L7.45202 112.923C7.49777 113.921 8.30793 114.583 9.18332 114.54L52.8559 112.42C53.7313 112.377 54.4774 111.64 54.4316 110.641L54.3996 109.942C54.3584 109.043 53.5437 108.282 52.6683 108.324L8.99575 110.445C8.12035 110.487 7.37882 111.324 7.42 112.223Z',
            'M7.42 103.136L7.45202 103.836C7.49777 104.835 8.30793 105.496 9.18332 105.453L52.8559 103.333C53.7313 103.29 54.4774 102.553 54.4316 101.554L54.3996 100.855C54.3584 99.9562 53.5437 99.1949 52.6683 99.2374L8.99575 101.358C8.12035 101.4 7.37882 102.237 7.42 103.136Z',
            'M7.42 94.2854L7.45202 94.9846C7.49777 95.9835 8.30793 96.645 9.18332 96.6024L52.8559 94.4818C53.7313 94.4393 54.4774 93.7023 54.4316 92.7034L54.3996 92.0042C54.3584 91.1052 53.5437 90.3439 52.6683 90.3864L8.99575 92.507C8.12035 92.5495 7.37882 93.3864 7.42 94.2854Z',
            'M7.42 85.5403L7.45202 86.2395C7.49777 87.2384 8.30793 87.8999 9.18332 87.8573L52.8559 85.7367C53.7313 85.6942 54.4774 84.9572 54.4316 83.9583L54.3996 83.2591C54.3584 82.3601 53.5437 81.5988 52.6683 81.6413L8.99575 83.7619C8.12035 83.8044 7.37882 84.6413 7.42 85.5403Z',
            'M7.42 76.1603L7.45202 76.8595C7.49777 77.8584 8.30793 78.5198 9.18332 78.4773L52.8559 76.3567C53.7313 76.3142 54.4774 75.5772 54.4316 74.5783L54.3996 73.8791C54.3584 72.9801 53.5437 72.2188 52.6683 72.2613L8.99575 74.3819C8.12035 74.4244 7.37882 75.2613 7.42 76.1603Z',
            'M7.42 67.3551L7.45202 68.0543C7.49777 69.0532 8.30793 69.7147 9.18332 69.6721L52.8559 67.5515C53.7313 67.509 54.4774 66.772 54.4316 65.7731L54.3996 65.0739C54.3584 64.1749 53.5437 63.4136 52.6683 63.4561L8.99575 65.5767C8.12035 65.6192 7.37882 66.4561 7.42 67.3551Z',
        ]
        for i, d in enumerate(back_lower_paths):
            n = 13 - i
            g.append(
                draw.Path(d=d, id=f'coil-back-turn-{n}', fill=f'url(#gradient-coil-back-turn-{n})')
            )

        # Back turn 1 (duplicate at bottom)
        g.append(
            draw.Path(
                d='M7.85719 13.4421L7.88922 14.1413C7.93497 15.1402 8.74512 15.8016 9.62052 15.7591L53.2931 13.6385C54.1685 13.596 54.9146 12.859 54.8688 11.8601L54.8368 11.1609C54.7956 10.2619 53.9809 9.50056 53.1055 9.54307L9.43295 11.6637C8.55755 11.7062 7.81602 12.5431 7.85719 13.4421Z',
                id='coil-back-turn-1-dup',
                fill='url(#gradient-coil-back-turn-1)',
            )
        )

        return g


# COLUMN
class Column(Equipment):
    def __init__(self, id: str, x: float = 0, y: float = 0, status: str = 'normal'):
        super().__init__(
            id=id,
            x=x,
            y=y,
            status=status,
            ports={
                'in': Port(3, 290),
                'out': Port(69, 354),
                'right-top': Port(136, 162),
                'right-bottom': Port(136, 192),
            },
        )

    def render(self) -> draw.Group:
        g = draw.Group(
            id=self.id,
            class_=f'equipment column status-{self.status}',
            transform=f'translate({self.x},{self.y})',
        )

        # Gradients
        g.append(
            _metallic_gradient('gradient-column-cylinder', 136, 177.3, 3, 177.3, COLUMN_BODY_STOPS)
        )
        g.append(
            _metallic_gradient('gradient-column-top-line', 139, 43.5, 1, 43.5, COLUMN_LINE_STOPS)
        )
        g.append(
            _metallic_gradient(
                'gradient-column-bottom-line', 138, 304.5, 0, 304.5, COLUMN_LINE_STOPS
            )
        )

        # Cylinder body
        path = draw.Path(
            d='M2.59634 48.3C2.59634 48.3 2.59634 0 68.7139 0C134.832 0 136 48.3 136 48.3'
            'V306.6C136 306.6 133.955 354.2 69.006 354.2C4.05696 354.2 2.59634 306.6 '
            '2.59634 306.6V48.3Z',
            id='column-cylinder',
            fill='url(#gradient-column-cylinder)',
        )
        path.args[':fill'] = "snapshot['reactor_cylinder_fill'] || 'url(#gradient-column-cylinder)'"
        g.append(path)

        # Top line
        g.append(
            draw.Line(
                136.5,
                46.5,
                3.5,
                46.5,
                id='column-top-line',
                stroke='url(#gradient-column-top-line)',
                stroke_width=5,
                stroke_linecap='round',
            )
        )

        # Bottom line
        g.append(
            draw.Line(
                135.5,
                307.5,
                2.5,
                307.5,
                id='column-bottom-line',
                stroke='url(#gradient-column-bottom-line)',
                stroke_width=5,
                stroke_linecap='round',
            )
        )

        return g


# CONTROL VALVE
class ControlValve(Equipment):
    """Control valve with diaphragm actuator."""

    def __init__(self, id: str, x: float = 0, y: float = 0, status: str = 'normal'):
        super().__init__(
            id=id,
            x=x,
            y=y,
            status=status,
            ports={
                'in': Port(0, 48),
                'out': Port(64, 48),
                'top': Port(32, 0),
            },
        )

    def render(self) -> draw.Group:
        g = draw.Group(
            id=self.id,
            class_=f'equipment control-valve status-{self.status}',
            transform=f'translate({self.x},{self.y})',
        )

        # Gradients
        g.append(_metallic_gradient('gradient-control-valve-stem', 35, 33, 29, 33, STEEL_STOPS))
        g.append(
            _metallic_gradient('gradient-control-valve-body-right', 64, 36, 64, 60, STEEL_STOPS)
        )
        g.append(_metallic_gradient('gradient-control-valve-body-left', 0, 36, 0, 60, STEEL_STOPS))
        g.append(_metallic_gradient('gradient-control-valve-actuator', 55, 23, 9, 23, STEEL_STOPS))

        # Stem
        g.append(
            draw.Rectangle(
                29.0963,
                17.9607,
                5.5,
                30.1,
                id='control-valve-stem',
                fill='url(#gradient-control-valve-stem)',
            )
        )

        # Body right
        g.append(
            draw.Path(
                d='M63.7303 36.1573V59.8573L31.9303 48.0573L63.7303 36.1573Z',
                id='control-valve-body-right',
                fill='url(#gradient-control-valve-body-right)',
            )
        )

        # Body left
        g.append(
            draw.Path(
                d='M0 36.1573V59.8573L31.8 48.0573L0 36.1573Z',
                id='control-valve-body-left',
                fill='url(#gradient-control-valve-body-left)',
            )
        )

        # Actuator (half-circle dome)
        g.append(
            draw.Path(
                d='M8.9491 22.8C8.9491 10.2 19.1491 0 31.8491 0C44.5491 0 54.7491 10.2 54.7491 22.8H8.9491Z',
                id='control-valve-actuator',
                fill='url(#gradient-control-valve-actuator)',
            )
        )

        return g


# PUMP
class Pump(Equipment):
    """Centrifugal pump with legs, body, blades, and pipe connector."""

    def __init__(self, id: str, x: float = 0, y: float = 0, status: str = 'normal'):
        super().__init__(
            id=id,
            x=x,
            y=y,
            status=status,
            ports={
                'in': Port(0, 36),
                'out': Port(83, 16),
            },
        )

    def render(self) -> draw.Group:
        g = draw.Group(
            id=self.id,
            class_=f'equipment industrial-pump status-{self.status}',
            transform=f'translate({self.x},{self.y})',
        )

        # ── Gradients ──
        g.append(_metallic_gradient('gradient-right-leg', 57.769, 59.556, 58.125, 73, LEG_STOPS))
        g.append(_metallic_gradient('gradient-right-foot', 61.125, 73, 61.125, 77.5, LEG_STOPS))
        g.append(_metallic_gradient('gradient-left-leg', 14.125, 60, 8.625, 73, LEG_STOPS))
        g.append(_metallic_gradient('gradient-left-foot', 5.125, 73, 5.125, 77, LEG_STOPS))
        g.append(_metallic_gradient('gradient-pipe', 78.94, 30.178, 78.94, -2869.82, PIPE_STOPS))
        g.append(
            _metallic_gradient(
                'gradient-pipe-connector',
                82.932,
                31.8,
                82.932,
                -3148.2,
                [(0, '#8F969D'), (0.64, '#D3D8DE'), (1, '#9AA0A8')],
            )
        )
        g.append(
            _metallic_gradient(
                'gradient-pipe-connector-back',
                80.212,
                31.667,
                80.212,
                -3118.33,
                [(0, '#626974'), (0.66, '#CCD0D5'), (1, '#5E6670')],
            )
        )

        # Radial gradient for body (approximate as linear)
        body_grad = draw.RadialGradient(
            33.719, 36.163, 48.9, id='gradient-body', gradientUnits='userSpaceOnUse'
        )
        body_grad.add_stop(0, '#B0B6BD')
        body_grad.add_stop(0.54, '#BCC2C9')
        body_grad.add_stop(0.74, '#D8DCE1')
        body_grad.add_stop(0.91, '#B0B6BD')
        g.append(body_grad)

        # ── Right leg ──
        g.append(
            draw.Path(
                d='M52.705 59.5559H40.241L45.2071 72.9559H57.7685L52.705 59.5559Z',
                id='pump-right-leg',
                fill='url(#gradient-right-leg)',
            )
        )

        # Right foot
        g.append(
            draw.Path(
                d='M60.3666 72.9252H42.6444C42.4496 72.9252 42.1575 73.1252 42.1575 73.4252'
                'V76.7252C42.1575 77.0252 42.4496 77.2252 42.6444 77.2252H60.3666'
                'C60.6587 77.2252 60.8535 77.0252 60.8535 76.7252V73.4252'
                'C60.8535 73.1252 60.6587 72.9252 60.3666 72.9252Z',
                id='pump-right-foot',
                fill='url(#gradient-right-foot)',
            )
        )

        # Left leg
        g.append(
            draw.Path(
                d='M13.415 59.5559H25.879L20.9129 72.9559H8.35154L13.415 59.5559Z',
                id='pump-left-leg',
                fill='url(#gradient-left-leg)',
            )
        )

        # Left foot
        g.append(
            draw.Path(
                d='M5.75346 72.9252H23.4757C23.6705 72.9252 23.9626 73.1252 23.9626 73.4252'
                'V76.7252C23.9626 77.0252 23.6705 77.2252 23.4757 77.2252H5.75346'
                'C5.46134 77.2252 5.26659 77.0252 5.26659 76.7252V73.4252'
                'C5.26659 73.1252 5.46134 72.9252 5.75346 72.9252Z',
                id='pump-left-foot',
                fill='url(#gradient-left-foot)',
            )
        )

        # Discharge pipe
        g.append(
            draw.Rectangle(33.9529, 1.1775, 44.987, 29, id='pump-pipe', fill='url(#gradient-pipe)')
        )

        # Body (outer circle)
        g.append(
            draw.Path(
                d='M34.0115 70.1632C52.6101 70.1632 67.8006 54.7632 67.8006 35.6632'
                'C67.8006 16.6632 52.6101 1.16319 34.0115 1.16319'
                'C15.3155 1.16319 0.125 16.6632 0.125 35.6632'
                'C0.125 54.7632 15.3155 70.1632 34.0115 70.1632Z',
                id='pump-body-outer',
                fill='url(#gradient-body)',
                stroke='#D4D6DB',
                stroke_width=0.25,
            )
        )

        # Pipe connector
        g.append(
            draw.Path(
                d='M82.9319 30.8V1.1C82.9319 0.5 82.0555 0 80.9844 0'
                'C79.8159 0 78.9395 0.5 78.9395 1.1V30.8'
                'C78.9395 31.3 79.8159 31.8 80.9844 31.8'
                'C82.0555 31.8 82.9319 31.3 82.9319 30.8Z',
                id='pump-pipe-connector',
                fill='url(#gradient-pipe-connector)',
            )
        )

        # Pipe connector back highlight
        g.append(
            draw.Path(
                d='M80.2115 0.166485C79.5298 0.266485 78.9456 0.666485 78.9456 1.16648'
                'V30.6665C78.9456 31.1665 79.5298 31.5665 80.2115 31.6665V0.166485Z',
                id='pump-pipe-connector-back',
                fill='url(#gradient-pipe-connector-back)',
            )
        )

        # Pipe connector front highlight
        g.append(
            draw.Path(
                d='M82.7055 30.7941V1.09408C82.7055 0.794079 82.5107 0.594078 82.316 0.594078'
                'C82.1212 0.594078 81.9265 0.794079 81.9265 1.09408V30.7941'
                'C81.9265 31.0941 82.1212 31.2941 82.316 31.2941'
                'C82.5107 31.2941 82.7055 31.0941 82.7055 30.7941Z',
                id='pump-pipe-connector-front',
                fill='white',
                fill_opacity=0.75,
            )
        )

        # Body inner circle
        g.append(
            draw.Path(
                d='M64.5596 35.675C64.5596 52.875 50.8297 66.875 33.9838 66.875'
                'C17.0406 66.875 3.4081 52.875 3.4081 35.675'
                'C3.4081 18.475 17.0406 4.47498 33.9838 4.47498'
                'C50.8297 18.475 64.5596 35.675 64.5596 35.675Z',
                id='pump-body-inner',
                fill='white',
                fill_opacity=0.25,
            )
        )

        # Blade circle outer
        g.append(
            draw.Path(
                d='M49.1471 35.6685C49.1471 44.2685 42.3309 51.1685 33.9567 51.1685'
                'C25.5824 51.1685 18.7662 44.2685 18.7662 35.6685'
                'C18.7662 27.1685 25.5824 20.2685 33.9567 20.2685'
                'C42.3309 20.2685 49.1471 27.1685 49.1471 35.6685Z',
                id='pump-blade-circle-outer',
                fill='#A4ABB3',
                stroke='#787F87',
            )
        )

        # Blade circle inner
        g.append(
            draw.Path(
                d='M47.5855 35.6772C47.5855 43.3772 41.4509 49.5772 33.9531 49.5772'
                'C26.4552 49.5772 20.3206 43.3772 20.3206 35.6772'
                'C20.3206 28.0772 26.4552 21.7772 33.9531 21.7772'
                'C41.4509 21.7772 47.5855 28.0772 47.5855 35.6772Z',
                id='pump-blade-circle-inner',
                fill='#8E959E',
            )
        )

        # ── Blades group (animated) ──
        blades = draw.Group(class_='pump-blades')

        # Blade vertical
        blades.append(
            draw.Path(
                d='M33.6118 22H34.0013C34.2934 22 34.4882 22.2 34.4882 22.5'
                'C34.4882 33.0051 34.4882 38.8949 34.4882 49.4'
                'C34.4882 49.6 34.2934 49.9 34.0013 49.9H33.6118'
                'C33.3197 49.9 33.1249 49.6 33.1249 49.4V35.95V22.5'
                'C33.1249 22.2 33.3197 22 33.6118 22Z',
                id='pump-blade-vertical',
                fill='#FF0004',
            )
        )

        # Blade diagonal right
        blades.append(
            draw.Path(
                d='M45.9805 28.433L46.1753 28.7794C46.3213 29.0392 46.2501 29.3124 '
                '45.9971 29.4624L23.2282 42.9624C22.9752 43.1124 22.7092 43.0392 '
                '22.5631 42.7794L22.3684 42.433C22.2223 42.1732 22.2936 41.9 '
                '22.5466 41.75L45.3155 28.25C45.5684 28.1 45.8345 28.1732 45.9805 28.433Z',
                id='pump-blade-diagonal-right',
                fill='#FF0004',
            )
        )

        # Blade diagonal left
        blades.append(
            draw.Path(
                d='M22.5631 28.433L22.3684 28.7794C22.2223 29.0392 22.2936 29.3124 '
                '22.5466 29.4624C31.4384 34.7345 36.4237 37.6903 45.3155 42.9624'
                'C45.5684 43.1124 45.8345 43.0392 45.9805 42.7794L46.1753 42.433'
                'C46.3214 42.1732 46.2501 41.9 45.9971 41.75L23.2282 28.25'
                'C22.9752 28.1 22.7092 28.1732 22.5631 28.433Z',
                id='pump-blade-diagonal-left',
                fill='#FF0004',
            )
        )

        # Center hub
        blades.append(draw.Circle(34.125, 36, 3, id='pump-blade-center', fill='#D9D9D9'))
        blades.append(draw.Circle(34.125, 36, 2, id='pump-blade-center-hole', fill='#5C646F'))

        g.append(blades)

        return g


# STEAM TRAP
class SteamTrap(Equipment):
    """Simple steam trap with 'T' marking."""

    def __init__(self, id: str, x: float = 0, y: float = 0, status: str = 'normal'):
        super().__init__(
            id=id,
            x=x,
            y=y,
            status=status,
            ports={
                'in': Port(20, 0),
                'out': Port(20, 32),
            },
        )

    def render(self) -> draw.Group:
        g = draw.Group(
            id=self.id,
            class_=f'equipment steam-trap status-{self.status}',
            transform=f'translate({self.x},{self.y})',
        )

        # Body
        g.append(
            draw.Rectangle(0.5, 0.5, 39, 31, id='steam-trap-body', fill='#D9D9D9', stroke='black')
        )

        # 'T' letter (using the original SVG path for exact serif font)
        g.append(
            draw.Path(
                d='M25.8281 11.3359L25.2109 14.1641H24.2109C24.2057 13.5859 24.1719 '
                '13.1823 24.1094 12.9531C24.0469 12.7188 23.9453 12.5443 23.8047 '
                '12.4297C23.6693 12.3099 23.4766 12.25 23.2266 12.25H22.5312L20.8516 '
                '19.8906C20.8203 20.0312 20.7995 20.1406 20.7891 20.2188C20.7786 '
                '20.2917 20.7682 20.375 20.7578 20.4688C20.7526 20.5573 20.75 20.6693 '
                '20.75 20.8047C20.75 21.0443 20.8099 21.2135 20.9297 21.3125C21.0547 '
                '21.4115 21.2474 21.4688 21.5078 21.4844L21.3984 22H17.25L17.3594 '
                '21.4844C17.5885 21.4531 17.7708 21.3854 17.9062 21.2812C18.0417 '
                '21.1771 18.1536 21.0234 18.2422 20.8203C18.3359 20.612 18.4297 '
                '20.3021 18.5234 19.8906L20.2031 12.25H19.5781C19.375 12.25 19.2083 '
                '12.2682 19.0781 12.3047C18.9531 12.3411 18.8438 12.3932 18.75 '
                '12.4609C18.6562 12.5234 18.5547 12.6146 18.4453 12.7344C18.3359 '
                '12.849 18.2135 13.0078 18.0781 13.2109C17.9479 13.4089 17.8073 '
                '13.6719 17.6562 14H16.6328L17.2188 11.3359H25.8281Z',
                id='steam-trap-letter',
                fill='black',
            )
        )

        return g


# STIRRED
class Stirred(Equipment):
    """Stirred with motor, shaft, coupling, and impeller blades."""

    def __init__(self, id: str, x: float = 0, y: float = 0, status: str = 'normal'):
        super().__init__(id=id, x=x, y=y, status=status)

    def _add_gradients(self, g: draw.Group):
        pairs = [
            ('gradient-stirred-motor-base', 64, 66, 21.622, 65.901, GREY_BODY_STOPS),
            ('gradient-stirred-motor-body', 64, 11, 21.622, 11.461, GREY_BODY_STOPS),
            ('gradient-stirred-motor-top', 58, 0, 27.933, 0, GREY_BODY_STOPS),
            ('gradient-stirred-shaft-coupling', 53, 73, 32.465, 73.157, GREY_BODY_STOPS),
            ('gradient-stirred-motor-flange', 68, 72, 18, 72, GREY_BODY_STOPS),
            ('gradient-stirred-shaft', 51.229, 119.301, 35.001, 118.971, GREY_BODY_STOPS),
        ]
        for gid, x1, y1, x2, y2, stops in pairs:
            g.append(_metallic_gradient(gid, x1, y1, x2, y2, stops))

        # Blade gradients
        blade_defs = [
            ('gradient-stirred-upper-blade-right', 82, 194.083, 56, 164.083),
            ('gradient-stirred-upper-blade-left', 35, 184.298, 5, 167.798),
            ('gradient-stirred-lower-blade-right', 82, 356.083, 56, 326.083),
            ('gradient-stirred-lower-blade-left', 23.329, 357.083, 12.329, 326.083),
        ]
        for gid, x1, y1, x2, y2 in blade_defs:
            g.append(_metallic_gradient(gid, x1, y1, x2, y2, GREY_BODY_STOPS))

    def render(self) -> draw.Group:
        g = draw.Group(
            id=self.id,
            class_=f'equipment stirred-reactor status-{self.status}',
            transform=f'translate({self.x},{self.y})',
        )
        self._add_gradients(g)

        # Motor base
        g.append(
            draw.Rectangle(
                21.622,
                65.901,
                42.6,
                9.1,
                id='stirred-motor-base',
                fill='url(#gradient-stirred-motor-base)',
            )
        )

        # Motor body
        g.append(
            draw.Rectangle(
                21.622,
                11.461,
                42.6,
                61.2,
                id='stirred-motor-body',
                fill='url(#gradient-stirred-motor-body)',
            )
        )

        # Motor top
        g.append(
            draw.Rectangle(
                27.933,
                0,
                29.9,
                11.5,
                id='stirred-motor-top',
                fill='url(#gradient-stirred-motor-top)',
            )
        )

        # Shaft coupling
        g.append(
            draw.Rectangle(
                32.465,
                73.157,
                20.9,
                45.8,
                id='stirred-shaft-coupling',
                fill='url(#gradient-stirred-shaft-coupling)',
            )
        )

        # Motor flange
        g.append(
            draw.Path(
                d='M19.8637 71.6429H65.8637C66.7637 71.6429 67.5637 72.5429 67.5637 73.7429'
                'V78.7429C67.5637 79.9429 66.7637 80.9429 65.8637 80.9429H19.8637'
                'C18.8637 80.9429 18.1637 79.9429 18.1637 78.7429V73.7429'
                'C18.1637 72.5429 18.8637 71.6429 19.8637 71.6429Z',
                id='stirred-motor-flange',
                fill='url(#gradient-stirred-motor-flange)',
            )
        )

        # Shaft (rendered first, behind blades)
        g.append(
            draw.Rectangle(
                35, 119, 16, 235, id='stirred-shaft', fill='url(#gradient-stirred-shaft)'
            )
        )

        # ── Upper blades group (animated) ──
        upper_blades = draw.Group(class_='stirred-upper-blades')

        upper_blades.append(
            draw.Path(
                d='M51 171.983C51 171.983 58.2 173.183 72.5 168.683'
                'C85.9 164.383 93.9 181.483 75.8 189.483'
                'C75.8 189.483 60.2 193.683 51 184.883V171.983Z',
                id='stirred-upper-blade-right',
                fill='url(#gradient-stirred-upper-blade-right)',
            )
        )

        upper_blades.append(
            draw.Path(
                d='M35.3288 171.983C35.3288 171.983 28.1288 173.183 13.8288 168.683'
                'C0.42878 164.383 -7.57122 181.483 10.5288 189.483'
                'C10.5288 189.483 26.1288 193.683 35.3288 184.883V171.983Z',
                id='stirred-upper-blade-left',
                fill='url(#gradient-stirred-upper-blade-left)',
            )
        )

        g.append(upper_blades)

        # ── Lower blades group (animated) ──
        lower_blades = draw.Group(class_='stirred-lower-blades')

        lower_blades.append(
            draw.Path(
                d='M51 333.983C51 333.983 58.2 335.183 72.5 330.683'
                'C85.9 326.383 93.9 343.483 75.8 351.483'
                'C75.8 351.483 60.2 355.683 51 346.883V333.983Z',
                id='stirred-lower-blade-right',
                fill='url(#gradient-stirred-lower-blade-right)',
            )
        )

        lower_blades.append(
            draw.Path(
                d='M35.3288 333.983C35.3288 333.983 28.1288 335.183 13.8288 330.683'
                'C0.42878 326.383 -7.57122 343.483 10.5288 351.483'
                'C10.5288 351.483 26.1288 355.683 35.3288 346.883V333.983Z',
                id='stirred-lower-blade-left',
                fill='url(#gradient-stirred-lower-blade-left)',
            )
        )

        g.append(lower_blades)

        return g


class Controller(Equipment):
    """Instrument display with tag label (top) and live value with unit (bottom)."""

    DEFAULT_WIDTH = 121
    DEFAULT_HEIGHT = 55
    CORNER_R = 2.5

    def __init__(
        self,
        id: str,
        x: float = 0,
        y: float = 0,
        width: float = DEFAULT_WIDTH,
        height: float = DEFAULT_HEIGHT,
        tag: str = 'FI-100',
        value: float | str = 42.20,
        unit: str = 'lb/min',
        value_color: str = 'green',
        status: str = 'normal',
        sp_tag: str | None = None,
    ):
        self.width = width
        self.height = height
        super().__init__(
            id=id,
            x=x,
            y=y,
            status=status,
            ports={
                'left': Port(0, self.height / 2),
                'right': Port(self.width, self.height / 2),
                'top': Port(self.width / 2, 0),
                'bottom': Port(self.width / 2, self.height),
            },
        )
        self.tag = tag
        self.value = value
        self.unit = unit
        self.value_color = value_color
        self.sp_tag = sp_tag

    def _centered_text(
        self,
        text: str,
        font_size: float,
        x: float,
        y: float,
        fill: str,
        font_weight: str = 'normal',
        text_id: str | None = None,
        vue_fill: str | None = None,
    ) -> draw.Raw:
        """Create a centered <text> element using raw SVG for reliable centering.

        Uses text-anchor="middle" for horizontal centering and
        dominant-baseline="central" for vertical centering.
        No dy offset — dominant-baseline="central" handles it correctly.

        ``text_id``, when provided, sets the SVG ``id`` attribute on the
        <text> element so the engine-driven UI can update its content
        in place via ``el.textContent = ...`` from JavaScript.
        """
        escaped_text = text.replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;')
        id_attr = f' id="{text_id}"' if text_id else ''
        if vue_fill:
            fill_attr = f' :fill="{vue_fill}"'
        else:
            fill_attr = f' fill="{fill}"'

        return draw.Raw(f"""
                    <text{id_attr} x="{x}" y="{y}"
                        {fill_attr}
                        font-size="{font_size}"
                        font-family="JetBrains Mono, monospace"
                        font-weight="{font_weight}"
                        text-anchor="middle"
                        line-height="1.2"
                        dominant-baseline="central">{escaped_text}</text>
                """)

    def render(self) -> draw.Group:
        g = draw.Group(
            id=self.id,
            class_=f'equipment controller status-{self.status}',
            transform=f'translate({self.x},{self.y})',
        )

        w = self.width
        h = self.height
        r = self.CORNER_R
        mid_y = h / 2

        # ── Top half: rounded top corners, flat bottom ──
        top = draw.Path(fill='black', stroke='white', stroke_width=1)
        top.M(0.5, mid_y)
        top.V(r + 0.5)
        top.A(r, r, 0, 0, 1, r + 0.5, 0.5)
        top.H(w - r - 0.5)
        top.A(r, r, 0, 0, 1, w - 0.5, r + 0.5)
        top.V(mid_y)
        top.Z()
        g.append(top)

        # ── Bottom half: flat top, rounded bottom corners ──
        bot = draw.Path(fill='black', stroke='white', stroke_width=1)
        bot.M(0.5, mid_y)
        bot.H(w - 0.5)
        bot.V(h - r - 0.5)
        bot.A(r, r, 0, 0, 1, w - r - 0.5, h - 0.5)
        bot.H(r + 0.5)
        bot.A(r, r, 0, 0, 1, 0.5, h - r - 0.5)
        bot.Z()
        g.append(bot)

        # ── Tag label (centered in top half) ──
        g.append(
            self._centered_text(
                self.tag,
                font_size=16,
                x=w / 2,
                y=mid_y / 2,
                fill='white',
                font_weight='bold',
            )
        )

        # ── Value + unit (centered in bottom half) ──
        vue_fill = None
        if self.sp_tag:
            normal_color = self.value_color
            pv_key = self.id
            sp_key = self.sp_tag
            vue_fill = f"getPvColor('{pv_key}', '{sp_key}', '{normal_color}')"

        text = (
            f'{self.value} {self.unit}'
            if self.unit and not str(self.value).startswith('{{')
            else str(self.value)
        )
        g.append(
            self._centered_text(
                text,
                font_size=16,
                x=w / 2,
                y=mid_y + ((h - mid_y) / 2),
                fill=self.value_color,
                font_weight='bold',
                text_id=f'{self.id}-value',
                vue_fill=vue_fill,
            )
        )

        return g


# PIPELINE LINES
class LineLine:
    """Polyline between waypoints with optional elbow radius or smooth curve."""

    def __init__(
        self,
        id: str,
        waypoints: list[tuple[float, float]],
        color: str = '#686E75',
        width: float = 4,
        mode: str = 'straight',
        elbow_radius: float = 10,
        status: str = 'normal',
    ):
        self.id = id
        self.waypoints = waypoints
        self.color = color
        self.width = width
        self.mode = mode
        self.elbow_radius = elbow_radius
        self.status = status

    @staticmethod
    def from_ports(
        id: str,
        source: Equipment,
        source_port: str,
        target: Equipment,
        target_port: str,
        mid_points: list[tuple[float, float]] | None = None,
        **kwargs,
    ) -> LineLine:
        sp = source.port_abs(source_port)
        tp = target.port_abs(target_port)
        pts: list[tuple[float, float]] = [(sp.x, sp.y)]
        if mid_points:
            pts.extend(mid_points)
        pts.append((tp.x, tp.y))
        return LineLine(id=id, waypoints=pts, **kwargs)

    def _build_path(self) -> draw.Path:
        p = draw.Path(
            fill='none',
            stroke=self.color,
            stroke_width=self.width,
            stroke_linecap='round',
            stroke_linejoin='round',
        )
        pts = self.waypoints
        if len(pts) < 2:
            return p

        if self.mode == 'curve':
            self._build_curve(p, pts)
        elif self.mode == 'elbow':
            self._build_elbow(p, pts)
        else:
            self._build_straight(p, pts)
        return p

    def _build_straight(self, p: draw.Path, pts: list[tuple[float, float]]):
        p.M(*pts[0])
        for pt in pts[1:]:
            p.L(*pt)

    def _build_elbow(self, p: draw.Path, pts: list[tuple[float, float]]):
        """Orthogonal segments with rounded corners at bends."""
        r = self.elbow_radius
        p.M(*pts[0])

        for i in range(1, len(pts) - 1):
            prev = pts[i - 1]
            curr = pts[i]
            nxt = pts[i + 1]

            dx_in = curr[0] - prev[0]
            dy_in = curr[1] - prev[1]
            dx_out = nxt[0] - curr[0]
            dy_out = nxt[1] - curr[1]

            len_in = (dx_in**2 + dy_in**2) ** 0.5
            len_out = (dx_out**2 + dy_out**2) ** 0.5

            if len_in == 0 or len_out == 0:
                p.L(*curr)
                continue

            actual_r = min(r, len_in / 2, len_out / 2)

            arc_sx = curr[0] - actual_r * dx_in / len_in
            arc_sy = curr[1] - actual_r * dy_in / len_in

            arc_ex = curr[0] + actual_r * dx_out / len_out
            arc_ey = curr[1] + actual_r * dy_out / len_out

            cross = dx_in * dy_out - dy_in * dx_out
            sweep = 1 if cross > 0 else 0

            p.L(arc_sx, arc_sy)
            p.A(actual_r, actual_r, 0, 0, sweep, arc_ex, arc_ey)

        p.L(*pts[-1])

    def _build_curve(self, p: draw.Path, pts: list[tuple[float, float]]):
        """Smooth cubic bezier using Catmull-Rom → Bezier conversion."""
        p.M(*pts[0])

        if len(pts) == 2:
            p.L(*pts[1])
            return

        padded = [pts[0]] + list(pts) + [pts[-1]]

        for i in range(1, len(padded) - 2):
            p0 = padded[i - 1]
            p1 = padded[i]
            p2 = padded[i + 1]
            p3 = padded[i + 2]

            cp1x = p1[0] + (p2[0] - p0[0]) / 6
            cp1y = p1[1] + (p2[1] - p0[1]) / 6
            cp2x = p2[0] - (p3[0] - p1[0]) / 6
            cp2y = p2[1] - (p3[1] - p1[1]) / 6

            p.C(cp1x, cp1y, cp2x, cp2y, p2[0], p2[1])

    def render(self) -> draw.Group:
        g = draw.Group(id=self.id, class_=f'pipeline status-{self.status}')
        g.append(self._build_path())
        return g


# ARROW LINE
class ArrowLine(LineLine):
    """Line with a triangular arrowhead at the end."""

    def __init__(
        self,
        id: str,
        waypoints: list[tuple[float, float]],
        color: str = '#686E75',
        width: float = 4,
        arrow_size: float = 5,
        mode: str = 'straight',
        elbow_radius: float = 10,
        status: str = 'normal',
    ):
        super().__init__(
            id=id,
            waypoints=waypoints,
            color=color,
            width=width,
            mode=mode,
            elbow_radius=elbow_radius,
            status=status,
        )
        self.arrow_size = arrow_size

    @staticmethod
    def from_ports(
        id: str,
        source: Equipment,
        source_port: str,
        target: Equipment,
        target_port: str,
        mid_points: list[tuple[float, float]] | None = None,
        **kwargs,
    ) -> ArrowLine:
        sp = source.port_abs(source_port)
        tp = target.port_abs(target_port)
        pts: list[tuple[float, float]] = [(sp.x, sp.y)]
        if mid_points:
            pts.extend(mid_points)
        pts.append((tp.x, tp.y))
        return ArrowLine(id=id, waypoints=pts, **kwargs)

    def render(self) -> draw.Group:
        g = draw.Group(id=self.id, class_=f'pipeline arrow-line status-{self.status}')
        s = self.arrow_size
        marker_id = f'marker-arrow-{self.id}'
        m = draw.Marker(
            0,
            0,
            s,
            s,
            id=marker_id,
            markerWidth=s,
            markerHeight=s,
            refX=s,
            refY=s / 2,
            orient='auto-start-reverse',
        )
        m.append(draw.Path(d=f'M0,0 L{s},{s / 2} L0,{s} Z', fill=self.color))
        g.append(m)

        path = self._build_path()
        path.args['marker-end'] = f'url(#{marker_id})'
        g.append(path)
        return g


# DASH LINE
class DashLine(LineLine):
    """Dashed line."""

    def __init__(
        self,
        id: str,
        waypoints: list[tuple[float, float]],
        color: str = '#686E75',
        width: float = 4,
        dash: str = '12 6',
        mode: str = 'straight',
        elbow_radius: float = 10,
        status: str = 'normal',
    ):
        super().__init__(
            id=id,
            waypoints=waypoints,
            color=color,
            width=width,
            mode=mode,
            elbow_radius=elbow_radius,
            status=status,
        )
        self.dash = dash

    @staticmethod
    def from_ports(
        id: str,
        source: Equipment,
        source_port: str,
        target: Equipment,
        target_port: str,
        mid_points: list[tuple[float, float]] | None = None,
        **kwargs,
    ) -> DashLine:
        sp = source.port_abs(source_port)
        tp = target.port_abs(target_port)
        pts: list[tuple[float, float]] = [(sp.x, sp.y)]
        if mid_points:
            pts.extend(mid_points)
        pts.append((tp.x, tp.y))
        return DashLine(id=id, waypoints=pts, **kwargs)

    def render(self) -> draw.Group:
        g = draw.Group(id=self.id, class_=f'pipeline dash-line status-{self.status}')
        path = self._build_path()
        path.args['stroke-dasharray'] = self.dash
        g.append(path)
        return g


# DOT END LINE
class DotEndLine(LineLine):
    """Line with a circular dot at the endpoint and a dashed stroke."""

    def __init__(
        self,
        id: str,
        waypoints: list[tuple[float, float]],
        color: str = '#686E75',
        width: float = 4,
        dot_radius: float = 2,
        dash: str = '12 6',
        mode: str = 'straight',
        elbow_radius: float = 10,
        status: str = 'normal',
    ):
        super().__init__(
            id=id,
            waypoints=waypoints,
            color=color,
            width=width,
            mode=mode,
            elbow_radius=elbow_radius,
            status=status,
        )
        self.dot_radius = dot_radius
        self.dash = dash

    @staticmethod
    def from_ports(
        id: str,
        source: Equipment,
        source_port: str,
        target: Equipment,
        target_port: str,
        mid_points: list[tuple[float, float]] | None = None,
        **kwargs,
    ) -> DotEndLine:
        sp = source.port_abs(source_port)
        tp = target.port_abs(target_port)
        pts: list[tuple[float, float]] = [(sp.x, sp.y)]
        if mid_points:
            pts.extend(mid_points)
        pts.append((tp.x, tp.y))
        return DotEndLine(id=id, waypoints=pts, **kwargs)

    def render(self) -> draw.Group:
        g = draw.Group(id=self.id, class_=f'pipeline dot-end-line status-{self.status}')
        r = self.dot_radius
        d = r * 2
        marker_id = f'marker-dot-{self.id}'
        m = draw.Marker(
            0, 0, d, d, id=marker_id, markerWidth=d, markerHeight=d, refX=r, refY=r, orient='auto'
        )
        m.append(draw.Circle(r, r, r, fill=self.color))
        g.append(m)

        path = self._build_path()
        path.args['stroke-dasharray'] = self.dash
        path.args['marker-end'] = f'url(#{marker_id})'
        g.append(path)
        return g


# FLUID LAYER
class FluidLayer:
    """Standalone animated fluid layer rendered at absolute coordinates.

    Sits on top of coil / stirred so it visually covers them,
    while being clipped to the column silhouette with a visible wall inset.
    """

    WALL_INSET = 2  # px gap antara fluida dan dinding tangki

    def __init__(
        self,
        id: str,
        column: Column,
        fluid_level: float = 0.75,
        fluid_color: str = '#1976D2',
        fluid_opacity: float = 0.72,
    ):
        self.id = id
        self.col = column
        self.fluid_level = fluid_level
        self.fluid_color = fluid_color
        self.fluid_opacity = fluid_opacity

    # ── absolute geometry (sudah di-inset) ──
    @property
    def _body_left(self):
        return self.col.x + 2.6 + self.WALL_INSET

    @property
    def _body_right(self):
        return self.col.x + 136.0 - self.WALL_INSET

    @property
    def _body_top(self):
        return self.col.y + 48.3

    @property
    def _body_bottom(self):
        return self.col.y + 306.6

    @property
    def _dome_bottom(self):
        return self.col.y + 354.2 - self.WALL_INSET

    @property
    def _cx(self):
        return (self._body_left + self._body_right) / 2

    @property
    def _body_width(self):
        return self._body_right - self._body_left

    def _tank_clip(self) -> draw.ClipPath:
        """Clip path inset dari dinding tangki — menyisakan dinding terlihat."""
        clip = draw.ClipPath(id=f'{self.id}-clip')
        p = draw.Path()
        p.M(self._body_left, self._body_top)
        p.V(self._body_bottom)

        # Curve left-to-center
        cp1_x = self._body_left
        cp1_y = self._body_bottom
        cp2_x = self.col.x + 4.05696 + self.WALL_INSET
        cp2_y = self._dome_bottom
        cx = self.col.x + 69.006
        cy = self._dome_bottom
        p.C(cp1_x, cp1_y, cp2_x, cp2_y, cx, cy)

        # Curve center-to-right
        cp3_x = self.col.x + 133.955 - self.WALL_INSET
        cp3_y = self._dome_bottom
        cp4_x = self._body_right
        cp4_y = self._body_bottom
        p.C(cp3_x, cp3_y, cp4_x, cp4_y, self._body_right, self._body_bottom)

        p.V(self._body_top)
        p.Z()
        clip.append(p)
        return clip

    def _wave_path(
        self,
        start_x: float,
        surface_y: float,
        total_w: float,
        wave_len: float,
        amp: float,
        bottom_y: float,
    ) -> draw.Path:
        p = draw.Path()
        p.M(start_x, surface_y)
        cx = start_x
        for _ in range(int(total_w / wave_len) + 2):
            half = wave_len / 2
            p.C(
                cx + half * 0.3,
                surface_y - amp,
                cx + half * 0.7,
                surface_y - amp,
                cx + half,
                surface_y,
            )
            cx += half
            p.C(
                cx + half * 0.3,
                surface_y + amp,
                cx + half * 0.7,
                surface_y + amp,
                cx + half,
                surface_y,
            )
            cx += half
        p.L(cx, bottom_y)
        p.L(start_x, bottom_y)
        p.Z()
        return p

    def render(self) -> draw.Group:
        g = draw.Group(id=self.id, class_='fluid-layer')

        g.append(self._tank_clip())

        fluid = draw.Group(clip_path=f'url(#{self.id}-clip)', class_='fluid-body')

        total_h = self._dome_bottom - self._body_top
        surface_y = self._dome_bottom - total_h * self.fluid_level
        bottom_y = self._dome_bottom + 10

        fluid.append(
            draw.Rectangle(
                self._body_left,
                surface_y + 4,
                self._body_width,
                bottom_y - surface_y + 20,
                fill=self.fluid_color,
                fill_opacity=self.fluid_opacity,
            )
        )

        dg_id = f'{self.id}-depth'
        dg = draw.LinearGradient(
            0, surface_y, 0, self._dome_bottom, id=dg_id, gradientUnits='userSpaceOnUse'
        )
        dg.add_stop(0.0, self.fluid_color, opacity=0.0)
        dg.add_stop(0.3, self.fluid_color, opacity=0.15)
        dg.add_stop(1.0, '#0D47A1', opacity=0.45)
        g.append(dg)
        fluid.append(
            draw.Rectangle(
                self._body_left,
                surface_y,
                self._body_width,
                bottom_y - surface_y + 20,
                fill=f'url(#{dg_id})',
            )
        )

        sg_id = f'{self.id}-spec'
        sg = draw.LinearGradient(
            self._body_left, 0, self._body_right, 0, id=sg_id, gradientUnits='userSpaceOnUse'
        )
        sg.add_stop(0.0, 'white', opacity=0.0)
        sg.add_stop(0.15, 'white', opacity=0.12)
        sg.add_stop(0.30, 'white', opacity=0.0)
        sg.add_stop(0.70, 'white', opacity=0.0)
        sg.add_stop(0.85, 'white', opacity=0.08)
        sg.add_stop(1.0, 'white', opacity=0.0)
        g.append(sg)
        fluid.append(
            draw.Rectangle(
                self._body_left,
                surface_y,
                self._body_width,
                bottom_y - surface_y,
                fill=f'url(#{sg_id})',
            )
        )

        ext = 250
        w_start = self._body_left - ext
        w_total = self._body_width + ext * 2

        w1 = self._wave_path(w_start, surface_y, w_total, 100, 5, bottom_y)
        w1.args['fill'] = self.fluid_color
        w1.args['fill-opacity'] = self.fluid_opacity
        w1.args['class'] = 'fluid-wave-1'
        fluid.append(w1)

        w2 = self._wave_path(w_start, surface_y + 2, w_total, 70, 3.5, bottom_y)
        w2.args['fill'] = '#42A5F5'
        w2.args['fill-opacity'] = self.fluid_opacity * 0.5
        w2.args['class'] = 'fluid-wave-2'
        fluid.append(w2)

        w3 = self._wave_path(w_start, surface_y - 1, w_total, 150, 2, surface_y + 15)
        w3.args['fill'] = '#BBDEFB'
        w3.args['fill-opacity'] = 0.25
        w3.args['class'] = 'fluid-wave-3'
        fluid.append(w3)

        mn = self._wave_path(w_start, surface_y, w_total, 100, 5, surface_y + 8)
        mn.args['fill'] = 'white'
        mn.args['fill-opacity'] = 0.18
        mn.args['class'] = 'fluid-wave-1'
        fluid.append(mn)

        g.append(fluid)
        return g


# STREAM LABELS
class StreamLabel:
    """Text label placed on or near a pipeline to identify the stream."""

    def __init__(
        self,
        id: str,
        x: float,
        y: float,
        text: str,
        font_size: float = 12,
        color: str = '#ffffff',
        rotation: float = 0,
        bg: bool = True,
        bg_color: str = '#00000000',
        bg_opacity: float = 0.7,
        bg_padding: float = 3,
    ):
        self.id = id
        self.x = x
        self.y = y
        self.text = text
        self.font_size = font_size
        self.color = color
        self.rotation = rotation
        self.bg = bg
        self.bg_color = bg_color
        self.bg_opacity = bg_opacity
        self.bg_padding = bg_padding

    def render(self) -> draw.Group:
        g = draw.Group(id=self.id, class_='stream-label', transform=f'translate({self.x},{self.y})')

        if self.rotation:
            g.args['transform'] += f' rotate({self.rotation})'

        approx_w = len(self.text) * self.font_size * 0.6
        pad = self.bg_padding

        if self.bg:
            g.append(
                draw.Rectangle(
                    -pad,
                    -self.font_size * 0.8 - pad,
                    approx_w + pad * 2,
                    self.font_size + pad * 2,
                    fill=self.bg_color,
                    fill_opacity=self.bg_opacity,
                    rx=2,
                    ry=2,
                )
            )

        escaped = self.text.replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;')

        g.append(
            draw.Raw(
                f'<text x="0" y="0" fill="{self.color}" '
                f'font-size="{self.font_size}" '
                f'font-family="JetBrains Mono, monospace" '
                f'font-weight="bold">{escaped}</text>'
            )
        )

        return g


# VALUE CARD
class ValueCard:
    """Simple rectangular card showing only a value + unit (no tag label)."""

    def __init__(
        self,
        id: str,
        x: float,
        y: float,
        width: float = 70,
        height: float = 30,
        value: float | str = 50.0,
        unit: str = '%',
        font_size: float = 16,
        value_color: str = 'green',
        bg_color: str = 'black',
        border_color: str = 'white',
        border_width: float = 1,
        corner_r: float = 3,
    ):
        self.id = id
        self.x = x
        self.y = y
        self.width = width
        self.height = height
        self.value = value
        self.unit = unit
        self.font_size = font_size
        self.value_color = value_color
        self.bg_color = bg_color
        self.border_color = border_color
        self.border_width = border_width
        self.corner_r = corner_r

    def render(self) -> draw.Group:
        g = draw.Group(
            id=self.id,
            class_='value-card',
            transform=f'translate({self.x},{self.y})',
        )

        g.append(
            draw.Rectangle(
                0,
                0,
                self.width,
                self.height,
                fill=self.bg_color,
                stroke=self.border_color,
                stroke_width=self.border_width,
                rx=self.corner_r,
                ry=self.corner_r,
            )
        )

        text = (
            f'{self.value} {self.unit}'
            if self.unit and not str(self.value).startswith('{{')
            else str(self.value)
        )
        escaped = text.replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;')

        g.append(
            draw.Raw(
                f'<text id="{self.id}-value" x="{self.width / 2}" y="{self.height / 2}" '
                f'fill="{self.value_color}" '
                f'font-size="{self.font_size}" '
                f'font-family="JetBrains Mono, monospace" '
                f'font-weight="bold" '
                f'text-anchor="middle" '
                f'dominant-baseline="central">{escaped}</text>'
            )
        )

        return g
