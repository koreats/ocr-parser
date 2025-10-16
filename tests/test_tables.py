from src.table_normalize import pp_table_to_html_csv
import os

def test_table_export_basic(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    t = {"cells":[{"row":0,"col":0,"text":"A"},{"row":0,"col":1,"text":"B"}]}
    out = pp_table_to_html_csv([t], base_name="sample")
    assert out and out[0]["csv_path"].endswith(".csv")
    assert os.path.exists(out[0]["csv_path"])