"""Execute este arquivo para substituir a base Saga local e online pela planilha."""
import argparse
import datetime as dt
import json
import sys
import uuid

from configuracao import BASE_DIR, destinos
from planilha import ler_planilha
from repositorio import backup, erro_seguro, inicializar, substituir, transacao


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("arquivo", nargs="?", default=str(BASE_DIR / "BASE GRUPO SAGA.xlsx"))
    p.add_argument("--destino", choices=["local", "online", "todos"], default="todos")
    p.add_argument("--so-validar", action="store_true", help="Confere o Excel sem conectar ou alterar bancos.")
    args = p.parse_args(argv)
    engines = []
    try:
        base = ler_planilha(args.arquivo)
        print(f"Planilha validada: {len(base.tabelas['lancamentos'])} lançamentos; faturamento R$ {base.faturamento:.2f}.")
        for aviso in base.avisos:
            print(f"AVISO: {aviso}")
        if args.so_validar:
            return 0
        selecionados = destinos(args.destino)
        print("Destinos: " + ", ".join(n for n, _ in selecionados))
        if not any(n == "online" for n, _ in selecionados):
            print("Aiven não selecionado/configurado: nenhuma conexão online será feita.")
        # Verifica todos os destinos antes de substituir qualquer dado.
        for nome, cfg in selecionados:
            engines.append((nome, inicializar(cfg, online=nome == "online")))
        lote = str(uuid.uuid4())
        resultados = []
        for nome, eng in engines:
            try:
                with transacao(eng) as conn:
                    copia = backup(conn, nome, lote)
                    eventos = substituir(conn, base, lote)
                resultado = dict(destino=nome, status="OK", eventos=eventos, backup=str(copia))
                print(f"{nome.upper()}: OK — carga conferida e confirmada; {eventos} alterações no histórico.")
            except Exception as exc:
                resultado = dict(destino=nome, status="ERRO", erro=erro_seguro(exc))
                print(f"{nome.upper()}: ERRO — {resultado['erro']}")
            resultados.append(resultado)
        logs = BASE_DIR / "logs"
        logs.mkdir(exist_ok=True)
        log = logs / f"carga_{lote}.json"
        log.write_text(json.dumps(dict(lote=lote, arquivo=base.arquivo, sha256=base.sha256,
                           horario=dt.datetime.now().isoformat(), resultados=resultados),
                           indent=2, ensure_ascii=False), encoding="utf-8")
        print(f"Relatório: {log}")
        if any(r["status"] != "OK" for r in resultados):
            print("Não foi possível atualizar todos os destinos. Os destinos OK já foram confirmados.")
            print("Corrija a conexão e rode novamente com a mesma planilha; a carga não duplica dados.")
            return 1
        return 0
    except Exception as exc:
        print(f"ERRO: {erro_seguro(exc)}", file=sys.stderr)
        return 1
    finally:
        for _, eng in engines:
            eng.dispose()


if __name__ == "__main__":
    raise SystemExit(main())
