"""Integração real: todas as mutações de teste são revertidas por rollback."""
from contextlib import contextmanager
from copy import deepcopy
import os
import uuid

import pytest
from sqlalchemy import text

from configuracao import BASE_DIR, criar_engine, destinos
from planilha import ler_planilha
from repositorio import ler_estado, substituir, transacao

pytestmark = pytest.mark.skipif(os.getenv("SAGA_TEST_MYSQL") != "1", reason="Requer MySQL Saga local configurado.")


@pytest.fixture
def eng():
    nome, cfg = destinos("local")[0]
    assert cfg["host"] in ("localhost", "127.0.0.1")
    assert cfg["database"] == "dashboard_saga"
    engine = criar_engine(cfg)
    yield engine
    engine.dispose()


class ReverterTeste(Exception):
    pass


def test_substituicao_idempotencia_exclusao_e_rollback(eng):
    base = ler_planilha(BASE_DIR / "BASE GRUPO SAGA.xlsx")
    with eng.connect() as conn:
        antes = ler_estado(conn)
        eventos_antes = conn.execute(text("SELECT COUNT(*) FROM lancamentos_historico")).scalar()
    with pytest.raises(ReverterTeste):
        with transacao(eng) as conn:
            assert substituir(conn, base, str(uuid.uuid4())) == 0
            nova = deepcopy(base)
            nova.tabelas["lancamentos"] = nova.tabelas["lancamentos"][:-1]
            assert substituir(conn, nova, str(uuid.uuid4())) == 1
            ultimo = conn.execute(text("SELECT * FROM vw_lancamentos_historico ORDER BY id DESC LIMIT 1")).mappings().one()
            assert ultimo["tipo"] == "exclusao"
            assert ultimo["refil_diant_periodo"] == -35
            assert ultimo["total_periodo"] == -375
            assert conn.execute(text("SELECT SUM(total_geral) FROM vw_base_tidy")).scalar() == 1900
            substituir(conn, base, str(uuid.uuid4()))
            assert conn.execute(text("SELECT SUM(total_periodo) FROM vw_lancamentos_historico")).scalar() == 2275
            raise ReverterTeste()
    with eng.connect() as conn:
        assert ler_estado(conn) == antes
        assert conn.execute(text("SELECT COUNT(*) FROM lancamentos_historico")).scalar() == eventos_antes


def test_falha_no_meio_da_carga_reverte_todas_as_tabelas(eng, monkeypatch):
    import repositorio
    base = ler_planilha(BASE_DIR / "BASE GRUPO SAGA.xlsx")
    with eng.connect() as conn:
        antes = ler_estado(conn)
    def falhar(*args):
        raise ValueError("Falha simulada após substituição")
    monkeypatch.setattr(repositorio, "conferir_carga", falhar)
    with pytest.raises(ValueError, match="simulada"):
        with transacao(eng) as conn:
            substituir(conn, base, str(uuid.uuid4()))
    with eng.connect() as conn:
        assert ler_estado(conn) == antes


def test_lancamento_manual_preserva_precos_e_audita_exclusao(eng, monkeypatch):
    import db
    with pytest.raises(ReverterTeste):
        with transacao(eng) as conn:
            @contextmanager
            def mesma_transacao(_):
                yield conn
            monkeypatch.setattr(db, "transacao", mesma_transacao)
            monkeypatch.setattr(db, "get_engine", lambda: eng)
            f = dict(conn.execute(text("SELECT * FROM lancamentos LIMIT 1")).mappings().one())
            conn.execute(text("UPDATE unidades SET preco_diant=99 WHERE id=:id"), {"id": f["unidade_id"]})
            db.salvar_lancamento(f["consultor_id"], f["mes"], f["unidade_id"], 100, 20, 10)
            atual = conn.execute(text("SELECT * FROM lancamentos WHERE consultor_id=:cid AND unidade_id=:uid AND mes=:mes"),
                                 dict(cid=f["consultor_id"], uid=f["unidade_id"], mes=f["mes"])).mappings().one()
            assert atual["preco_diant"] == f["preco_diant"]
            assert atual["refil_diant"] == 20
            db.excluir_lancamento(f["consultor_id"], f["mes"], f["unidade_id"])
            ultimo = conn.execute(text("SELECT * FROM vw_lancamentos_historico ORDER BY id DESC LIMIT 1")).mappings().one()
            assert ultimo["origem"] == "app"
            assert ultimo["refil_diant_periodo"] == -20
            raise ReverterTeste()
