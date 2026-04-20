def test_settings_loaded(settings):
    assert settings.SECRET_KEY is not None