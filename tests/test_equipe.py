from decimal import Decimal

from openpyxl import load_workbook, Workbook
import pytest

from configuracao import BASE_DIR
from importar_verbas_unidade import importar
from planilha import ler_planilha


def test_resultado_real_sem_duplicar_tecnicos():
    base = ler_planilha(BASE_DIR / 'BASE GRUPO SAGA.xlsx')
    t = base.tabelas
    assert base.faturamento == Decimal('2490.00')
    assert len(t['unidades']) == 3
    assert len(t['consultores']) == 11
    assert len(t['equipe']) == 16
    assert len(t['lancamentos']) == 3
    assert {u['gerente'] for u in t['unidades']} == {'Ricardo', 'Flávio', 'Rafael'}
    assert {u['preco_diant'] for u in t['unidades']} == {249}
    assert all(f['passagens'] is None for f in t['lancamentos'])
    assert sum(f['refil_diant'] for f in t['lancamentos']) == 10
    assert all(f['refil_tras'] == 0 for f in t['lancamentos'])
    assert {c['nome'] for c in t['consultores']} >= {'KATIELEN NEVES NASCIMENTO'}
    for cargo, esperado in [('consultor', 120), ('técnico', 80)]:
        com = [r for r in t['comissoes_equipe'] if r['cargo'] == cargo]
        assert sum(r['refil_diant'] for r in com) == 10
        assert sum(r['refil_diant'] * r['verba_diant'] for r in com) == esperado


@pytest.mark.parametrize('linha,valor,mensagem', [(2, 99, 'divergem'), (5, 99, 'excedem')])
def test_comissao_divergente_recusada(tmp_path, linha, valor, mensagem):
    wb = load_workbook(BASE_DIR / 'BASE GRUPO SAGA.xlsx')
    wb['Comissões Equipe'].cell(linha, 6, valor)
    arquivo = tmp_path / 'invalida.xlsx'
    wb.save(arquivo)
    wb.close()
    with pytest.raises(ValueError, match=mensagem):
        ler_planilha(arquivo)


def test_importacao_mensal_preserva_outros_meses_e_cadastros(tmp_path):
    base = tmp_path / 'base.xlsx'
    base.write_bytes((BASE_DIR / 'BASE GRUPO SAGA.xlsx').read_bytes())
    wb = Workbook()
    ws = wb.active
    ws.append(['NOME', 'CARGO', 'VERBA', 'VENDAS', 'A RECEBER'])
    ws.append(['PAULA REZENDE', 'Consultor', 12, 2, 24])
    ws.append(['Alex lima Santos', 'Técnico', 8, 2, 16])
    origem = tmp_path / 'novembro.xlsx'
    wb.save(origem)
    wb.close()
    for _ in range(2):
        importar(origem, loja='T9', marca='JEEP', mes='2026-11', base=base)
    b = ler_planilha(base)
    assert b.faturamento == 2988
    assert len(b.tabelas['lancamentos']) == 4
    assert len(b.tabelas['consultores']) == 11
    assert len(b.tabelas['equipe']) == 16
    assert len(b.tabelas['comissoes_equipe']) == 10


def test_importacao_invalida_preserva_excel(tmp_path):
    base = tmp_path / 'base.xlsx'
    antes = (BASE_DIR / 'BASE GRUPO SAGA.xlsx').read_bytes()
    base.write_bytes(antes)
    wb = Workbook()
    ws = wb.active
    ws.append(['NOME', 'CARGO', 'VERBA', 'VENDAS', 'A RECEBER'])
    ws.append(['PAULA REZENDE', 'Consultor', 12, 2, 100])
    origem = tmp_path / 'invalida.xlsx'
    wb.save(origem)
    wb.close()
    with pytest.raises(ValueError, match='A RECEBER diverge'):
        importar(origem, loja='T9', marca='JEEP', mes='2026-11', base=base)
    assert base.read_bytes() == antes
