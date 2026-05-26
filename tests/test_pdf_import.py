from pathlib import Path

from logic.pdf_import import extract_soil_from_pdf


def test_format_c_dojo_shohosen():
    pdf = Path("sample/dojo_shohosen.pdf").read_bytes()
    result = extract_soil_from_pdf(pdf)
    assert result.template_id == "format_c"
    soil = result.as_soil_inputs()
    assert soil["P"] == 30.0
    assert soil["K"] == 70.0
    assert soil["Ca"] == 150.0
    assert soil["Mg"] == 50.0
