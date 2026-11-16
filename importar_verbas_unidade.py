"""Incorpora resultado mensal NOME/CARGO/VERBA/VENDAS/A RECEBER ao Excel Saga.

Depois execute atualizar_base.py para sincronizar os dois bancos.
"""
import argparse
import datetime as dt
from pathlib import Path
import shutil
import tempfile

from openpyxl import load_workbook

from configuracao import BASE_DIR
from planilha import data, ler_planilha, linhas, numero, texto


def importar(origem, *, loja, marca, mes, base=None):
    base = Path(base or BASE_DIR / 'BASE GRUPO SAGA.xlsx')
    mes = data(mes, 'Mês', mes=True)
    wb = load_workbook(base)
    fonte = load_workbook(origem, data_only=True)
    temporario = None
    try:
        precos = [r for r, _ in linhas(wb, 'Preço por Unidade', ['Loja', 'Marca', 'Gerente'])
                  if (r['Loja'], r['Marca']) == (loja, marca)]
        if len(precos) != 1:
            raise ValueError('Cadastre a unidade, os preços e o gerente em Preço por Unidade antes de importar.')
        unidade = precos[0]
        consultores, comissoes, equipe = [], [], []
        nd_total = 0
        for r, ctx in linhas(fonte, fonte.sheetnames[0], ['NOME', 'CARGO', 'VERBA', 'VENDAS', 'A RECEBER']):
            nome = texto(r['NOME'], ctx).upper()
            cargo = texto(r['CARGO'], ctx).lower()
            if cargo not in ('consultor', 'técnico'):
                raise ValueError(f'{ctx}: cargo desconhecido.')
            nd = numero(r['VENDAS'], ctx, inteiro=True)
            verba = numero(r['VERBA'], ctx)
            receber = numero(r['A RECEBER'], ctx)
            if receber != nd * verba:
                raise ValueError(f'{ctx}: A RECEBER diverge de VENDAS × VERBA.')
            equipe.append([nome, cargo, loja, marca])
            comissoes.append([nome, cargo, loja, marca, mes, nd, 0, verba, 0])
            if cargo == 'consultor':
                consultores.append([nome, loja, marca, mes, None, nd, 0,
                                    unidade['Preço Diant. (R$)'], unidade['Preço Tras. (R$)']])
                nd_total += nd
        if not consultores:
            raise ValueError('Nenhum resultado de consultor encontrado; importação cancelada.')

        def substituir_mes(aba, cabecalho, novos):
            existentes = []
            if aba in wb.sheetnames:
                for r, ctx in linhas(wb, aba, cabecalho):
                    mesma = (r['Loja'], r['Marca']) == (loja, marca) and data(r['Mês (data)'], ctx, mes=True) == mes
                    if not mesma:
                        existentes.append([r.get(c) for c in cabecalho])
                del wb[aba]
            ws = wb.create_sheet(aba)
            ws.append(cabecalho)
            for valores in existentes + novos:
                ws.append(valores)

        substituir_mes('Consultores', ['Consultor', 'Loja', 'Marca', 'Mês (data)', 'Passagens',
            'Refil Diant. (qtd)', 'Refil Tras. (qtd)', 'Preço Diant. (R$)', 'Preço Tras. (R$)'], consultores)
        substituir_mes('Gerentes', ['Gerente', 'Loja', 'Marca', 'Mês (data)', 'Passagens',
            'Refil Diant. (qtd)', 'Refil Tras. (qtd)'], [[unidade['Gerente'], loja, marca, mes, None, nd_total, 0]])
        substituir_mes('Comissões Equipe', ['Nome', 'Cargo', 'Loja', 'Marca', 'Mês (data)',
            'Refil Diant. (qtd)', 'Refil Tras. (qtd)', 'Verba Diant. (R$)', 'Verba Tras. (R$)'], comissoes)
        if 'Equipe' not in wb.sheetnames:
            wb.create_sheet('Equipe').append(['Nome', 'Cargo', 'Loja', 'Marca'])
        atuais = {tuple(r[c] for c in ['Nome', 'Cargo', 'Loja', 'Marca'])
                  for r, _ in linhas(wb, 'Equipe', ['Nome', 'Cargo', 'Loja', 'Marca'])}
        for registro in equipe:
            if tuple(registro) not in atuais:
                wb['Equipe'].append(registro)
                atuais.add(tuple(registro))
        from openpyxl.styles import Font, PatternFill
        for ws in wb:
            ws.freeze_panes = 'A2'
            ws.auto_filter.ref = ws.dimensions
            for cell in ws[1]:
                cell.fill = PatternFill('solid', fgColor='16376A')
                cell.font = Font(color='FFFFFF', bold=True)
                ws.column_dimensions[cell.column_letter].width = 28
            for row in ws.iter_rows(min_row=2):
                for cell in row:
                    if isinstance(cell.value, (dt.date, dt.datetime)):
                        cell.number_format = 'mm/yyyy'
        with tempfile.NamedTemporaryFile(dir=base.parent, suffix='.xlsx', delete=False) as arquivo:
            temporario = Path(arquivo.name)
        wb.save(temporario)
        validada = ler_planilha(temporario)
        pasta = BASE_DIR / 'backups'
        pasta.mkdir(exist_ok=True)
        shutil.copy2(base, pasta / f'{dt.datetime.now():%Y%m%d_%H%M%S_%f}_{base.name}')
        temporario.replace(base)
        print(f'Excel atualizado: {base.name}; faturamento acumulado R$ {validada.faturamento:.2f}.')
    finally:
        fonte.close()
        wb.close()
        if temporario and temporario.exists():
            temporario.unlink()


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('arquivo', type=Path)
    p.add_argument('--loja', required=True, help='Exemplo: T9')
    p.add_argument('--marca', default='JEEP')
    p.add_argument('--mes', required=True, help='AAAA-MM')
    args = p.parse_args()
    importar(args.arquivo, loja=args.loja, marca=args.marca, mes=args.mes)


if __name__ == '__main__':
    main()
