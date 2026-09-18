import os

import pytest
from streamlit.testing.v1 import AppTest

from configuracao import BASE_DIR, ler_config

pytestmark = pytest.mark.skipif(os.getenv("SAGA_TEST_MYSQL") != "1", reason="Requer dados Saga locais.")


def sem_erros(app):
    assert not app.exception, [e.message for e in app.exception]
    assert not app.error, [e.value for e in app.error]


def test_telas_filtros_e_area_restrita():
    app = AppTest.from_file(str(BASE_DIR / "app.py"), default_timeout=30).run()
    sem_erros(app)
    assert any(m.value == "R$ 2.275,00" for m in app.metric)
    assert len(app.get("download_button")) >= 1
    menu = app.sidebar.radio[0]
    assert len(menu.options) == 4
    app.sidebar.multiselect[1].set_value(["Volkswagen · Loja 1"]).run()
    sem_erros(app)
    assert any(m.value == "R$ 935,00" for m in app.metric)
    for pagina in ("Relatório Por Gerente", "Relatório Por Consultor", "Verbas"):
        app.sidebar.radio[0].set_value(pagina).run()
        sem_erros(app)
        if pagina == "Verbas":
            assert any("não contém verbas" in m.value for m in app.info)
        else:
            assert len(app.get("download_button")) >= 1
            assert any("Não configurada" in df.value.to_string() for df in app.dataframe)
    app.button(key="btn_cadeado").click().run()
    app.text_input[0].set_value(ler_config()["acesso"]["senha_lancamento"])
    next(b for b in app.button if b.label == "Entrar").click().run()
    sem_erros(app)
    assert len(app.sidebar.radio[0].options) == 6
    assert app.sidebar.radio[0].value == "📝 Lançamento"
    assert any(m.value == "R$ 205,00" for m in app.metric)
    app.sidebar.radio[0].set_value("🗂️ Histórico").run()
    sem_erros(app)
    assert any(m.value == "6" and m.label == "Lançamentos" for m in app.metric)
    assert len(app.get("download_button")) >= 1
    app.button(key="btn_cadeado").click().run()
    assert len(app.sidebar.radio[0].options) == 4
