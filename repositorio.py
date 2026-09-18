"""Persistência MySQL transacional, usada por importações e lançamentos."""
from contextlib import contextmanager
import datetime as dt
from decimal import Decimal
import json
from pathlib import Path

from sqlalchemy import inspect, text

from configuracao import BASE_DIR, criar_engine
from planilha import TABELAS

CHAVE = ("consultor_id", "unidade_id", "mes")


def conferir_projeto(conn):
    if conn.execute(text("SELECT valor FROM saga_metadata WHERE chave='projeto'")).scalar() != "dashboard_saga_v1":
        raise ValueError("O banco não está identificado como Dashboard Saga.")


def inicializar(cfg, *, online=False):
    if cfg.get("criar_banco", False):
        eng = criar_engine(cfg, sem_banco=True, online=online)
        try:
            with eng.begin() as conn:
                conn.execute(text(f"CREATE DATABASE IF NOT EXISTS `{cfg['database']}` CHARACTER SET utf8mb4 COLLATE utf8mb4_bin"))
        finally:
            eng.dispose()
    eng = criar_engine(cfg, online=online)
    try:
        with eng.connect() as conn:
            existentes = set(inspect(conn).get_table_names())
            if "saga_metadata" in existentes:
                conferir_projeto(conn)
            elif existentes:
                raise ValueError("O banco selecionado já contém tabelas de outro projeto. Escolha um banco vazio exclusivo da Saga.")
            sql = (BASE_DIR / "schema.sql").read_text(encoding="utf-8")
            sql = "\n".join(l for l in sql.splitlines() if not l.lstrip().startswith("--"))
            for comando in sql.split(";"):
                if comando.strip():
                    conn.execute(text(comando))
            conn.commit()
        return eng
    except Exception:
        eng.dispose()
        raise


@contextmanager
def transacao(eng):
    """Serializa importador/app no mesmo banco; libera o lock mesmo em rollback."""
    with eng.connect() as conn:
        banco = conn.execute(text("SELECT DATABASE()")).scalar()
        lock = f"saga:{banco}"[:64]
        adquirido = conn.execute(text("SELECT GET_LOCK(:nome, 10)"), {"nome": lock}).scalar()
        conn.commit()
        if adquirido != 1:
            raise ValueError("Outra atualização está em andamento. Tente novamente em alguns segundos.")
        try:
            with conn.begin():
                conferir_projeto(conn)
                yield conn
        finally:
            conn.execute(text("SELECT RELEASE_LOCK(:nome)"), {"nome": lock})
            conn.commit()


def ler_estado(conn):
    return {t: [dict(r) for r in conn.execute(text(f"SELECT * FROM {t}")).mappings()]
            for t in TABELAS}


def inserir(conn, tabela, linhas):
    permitidas = set(TABELAS) | {"lancamentos_historico", "importacoes"}
    if tabela not in permitidas:
        raise ValueError("Tabela não permitida.")
    if not linhas:
        return
    colunas = list(linhas[0])
    if any(not c.replace("_", "").isalnum() for c in colunas):
        raise ValueError("Coluna inválida.")
    sql = text(f"INSERT INTO {tabela} ({', '.join(colunas)}) VALUES ({', '.join(':'+c for c in colunas)})")
    for inicio in range(0, len(linhas), 1000):
        conn.execute(sql, linhas[inicio:inicio+1000])


def evento(fato, unidades, consultores, origem, lote, *, excluido=False):
    r = dict(fato)
    u, c = unidades[r["unidade_id"]], consultores[r["consultor_id"]]
    if excluido:
        r.update(passagens=0, refil_diant=0, refil_tras=0)
    r.update(consultor=c["nome"], unidade=u["nome_exibicao"], marca=u["marca"],
             tipo="exclusao" if excluido else "lancamento", origem=origem, lote=lote)
    return r


def substituir(conn, base, lote):
    """Só DML: a transação externa mantém o estado antigo em qualquer falha."""
    anterior = ler_estado(conn)
    chave = lambda r: tuple(r[c] for c in CHAVE)
    velhos = {chave(r): r for r in anterior["lancamentos"]}
    novos = {chave(r): r for r in base.tabelas["lancamentos"]}
    eventos = []
    for estado, registros, exclusao in ((anterior, velhos, True), (base.tabelas, novos, False)):
        unidades = {r["id"]: r for r in estado["unidades"]}
        consultores = {r["id"]: r for r in estado["consultores"]}
        for k, r in registros.items():
            if (exclusao and k not in novos) or (not exclusao and r != velhos.get(k)):
                eventos.append(evento(r, unidades, consultores, "excel", lote, excluido=exclusao))
    inserir(conn, "lancamentos_historico", eventos)
    for tabela in reversed(TABELAS):
        conn.execute(text(f"DELETE FROM {tabela}"))
    for tabela in TABELAS:
        inserir(conn, tabela, base.tabelas[tabela])
    conferir_carga(conn, base)
    inserir(conn, "importacoes", [dict(id=lote, arquivo=base.arquivo, sha256=base.sha256,
                                      linhas=len(novos), faturamento=base.faturamento)])
    return len(eventos)


def conferir_carga(conn, base):
    for tabela in TABELAS:
        total = conn.execute(text(f"SELECT COUNT(*) FROM {tabela}")).scalar()
        if total != len(base.tabelas[tabela]):
            raise ValueError(f"Conferência falhou na tabela {tabela}; alterações canceladas.")
    total = conn.execute(text("SELECT COALESCE(SUM(total_geral), 0) FROM vw_base_tidy")).scalar()
    if total != base.faturamento:
        raise ValueError("Faturamento gravado diverge da planilha; alterações canceladas.")


def backup(conn, destino, lote):
    pasta = BASE_DIR / "backups"
    pasta.mkdir(exist_ok=True)
    estado = ler_estado(conn)
    for tabela in ("lancamentos_historico", "importacoes"):
        estado[tabela] = [dict(r) for r in conn.execute(text(f"SELECT * FROM {tabela}")).mappings()]
    caminho = pasta / f"{dt.datetime.now():%Y%m%d_%H%M%S}_{destino}_{lote}.json"
    conteudo = dict(formato="saga-backup-v1", banco=conn.engine.url.database,
                    criado_em=dt.datetime.now().isoformat(), tabelas=estado)
    with caminho.open("x", encoding="utf-8") as f:
        json.dump(conteudo, f, ensure_ascii=False, indent=2, default=str)
    return caminho


def erro_seguro(exc):
    # Erros do driver podem carregar parâmetros SQL: nunca imprimir a exceção inteira.
    if isinstance(exc, (ValueError, FileNotFoundError)):
        return str(exc)
    codigo = getattr(getattr(exc, "orig", None), "args", (None,))[0]
    return f"{type(exc).__name__}" + (f" (MySQL {codigo})" if isinstance(codigo, int) else "") + ": confira conexão, permissões e certificado."
