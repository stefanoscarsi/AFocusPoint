from core import af_parser


def test_white_balance_shows_kelvin_when_color_temperature_present():
    raw = {"Canon:ColorTemperature": 5200}
    formatted = {"Canon:WhiteBalance": "Manual Temperature (Kelvin)"}
    data = af_parser.get_shooting_data(raw, formatted)
    assert data.white_balance == "5200 K"


def test_white_balance_shows_kelvin_for_auto_mode_too():
    """ColorTemperature reflects whatever temperature the camera actually
    used, whether set manually or determined by Auto WB -- unlike the mode
    name, which would just say "Auto" and not the actual value."""
    raw = {"Canon:ColorTemperature": 4500}
    formatted = {"Canon:WhiteBalance": "Auto"}
    data = af_parser.get_shooting_data(raw, formatted)
    assert data.white_balance == "4500 K"


def test_white_balance_falls_back_to_mode_name_when_no_color_temperature():
    raw = {}
    formatted = {"Canon:WhiteBalance": "Daylight"}
    data = af_parser.get_shooting_data(raw, formatted)
    assert data.white_balance == "Daylight"


def test_white_balance_none_when_nothing_available():
    data = af_parser.get_shooting_data({}, {})
    assert data.white_balance is None
