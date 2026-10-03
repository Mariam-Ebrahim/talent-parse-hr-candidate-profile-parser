from streamlit.testing.v1 import AppTest


def test_autofill_flow():
    at = AppTest.from_file("../app.py", default_timeout=60).run()
    assert not at.exception
    next(b for b in at.button if b.label == "Auto-fill the form").click().run()
    assert not at.exception
    values = {t.label: t.value for t in at.text_input}
    assert values["Full name"] == "John Smith"
    assert values["Email"] == "john.smith@email.com"
    assert at.multiselect[0].value == ["Python", "Machine Learning", "Data Analysis"]
