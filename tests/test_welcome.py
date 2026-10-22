from bot.welcome import DESCRIPTION, WELCOME


def test_description_fits_telegram_limit():
    assert len(DESCRIPTION) <= 255


def test_welcome_fits_and_has_disclaimer():
    assert len(WELCOME) <= 4096
    assert "nije zvanični izvor" in WELCOME.lower()
    assert "eksperimentalan" in WELCOME
