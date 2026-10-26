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


def test_af_area_mode_fallback_table_matches_exiftool_codes():
    # Codici autorevoli ExifTool (Canon AFInfo2), quelli verificati sui file
    # della R6 III in evidenza. La riserva serve solo se ExifTool non da' il
    # nome testuale.
    t = af_parser._AF_AREA_MODE_DESCRIPTIONS
    assert t[9] == "Spot AF"
    assert t[13] == "Flexizone Single"
    assert t[19] == "Flexible Zone AF 1"
    assert t[2] == "Single-point AF"
    assert t[22] == "Whole Area AF"


def test_bare_numeric_af_area_mode_uses_the_fallback_table():
    # Se ExifTool restituisce solo il numero (niente descrizione), l'app usa
    # la tabella di riserva.
    raw = {"Canon:AFAreaMode": 9}
    af = af_parser.get_af_data_structured(raw, formatted_metadata={})
    assert af.af_area_mode == "Spot AF"
    assert af.af_area_mode_raw == 9


def test_exiftool_text_description_wins_over_the_fallback_table():
    raw = {"Canon:AFAreaMode": 19}
    fmt = {"Canon:AFAreaMode": "Flexible Zone AF 1"}
    af = af_parser.get_af_data_structured(raw, fmt)
    assert af.af_area_mode == "Flexible Zone AF 1"
