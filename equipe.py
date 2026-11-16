"""Cadastros independentes de vendas e comissões mensais por participante."""
from collections import defaultdict

from planilha import data, identificador, linhas, numero, texto


def ler_equipe(wb, tabelas):
    unidades = {r['id']: r for r in tabelas['unidades']}
    for r, ctx in linhas(wb, 'Preço por Unidade', ['Loja', 'Marca']):
        if not r.get('Gerente'):
            continue
        marca, loja = texto(r['Marca'], ctx, 140), texto(r['Loja'], ctx, 140)
        uid = identificador(marca, loja)
        unidades.setdefault(uid, dict(id=uid, nome_exibicao=f'{marca} · {loja}',
            marca=marca, loja=loja, gerente=texto(r['Gerente'], ctx),
            preco_diant=numero(r['Preço Diant. (R$)'], ctx),
            preco_tras=numero(r['Preço Tras. (R$)'], ctx)))
        unidades[uid]['gerente'] = texto(r['Gerente'], ctx)
    tabelas['unidades'] = list(unidades.values())
    consultores = {r['id']: r for r in tabelas['consultores']}
    vinculos = {(r['consultor_id'], r['unidade_id']) for r in tabelas['consultor_unidade']}
    equipe = {}
    if 'Equipe' in wb.sheetnames:
        for r, ctx in linhas(wb, 'Equipe', ['Nome', 'Cargo', 'Loja', 'Marca']):
            nome = texto(r['Nome'], ctx)
            cargo = texto(r['Cargo'], ctx).lower()
            if cargo not in ('consultor', 'técnico'):
                raise ValueError(f'{ctx}: Cargo deve ser Consultor ou Técnico.')
            uid = identificador(texto(r['Marca'], ctx, 140), texto(r['Loja'], ctx, 140))
            if uid not in unidades:
                raise ValueError(f'{ctx}: unidade sem cadastro de preço e gerente.')
            pid = identificador(nome)
            chave = (cargo, pid, uid)
            if chave in equipe:
                raise ValueError(f'{ctx}: cadastro de equipe duplicado.')
            equipe[chave] = dict(cargo=cargo, pessoa_id=pid, unidade_id=uid, nome=nome)
            if cargo == 'consultor':
                consultores[pid] = dict(id=pid, nome=nome)
                vinculos.add((pid, uid))
    # Bases anteriores continuam compatíveis, mesmo sem a aba Equipe.
    for cid, uid in vinculos:
        equipe.setdefault(('consultor', cid, uid), dict(cargo='consultor', pessoa_id=cid,
            unidade_id=uid, nome=consultores[cid]['nome']))
    tabelas['consultores'] = list(consultores.values())
    tabelas['consultor_unidade'] = [dict(consultor_id=c, unidade_id=u) for c, u in sorted(vinculos)]
    tabelas['equipe'] = list(equipe.values())
    fatos = {(f['consultor_id'], f['unidade_id'], f['mes']): f for f in tabelas['lancamentos']}
    vendas = defaultdict(lambda: [0, 0])
    for f in fatos.values():
        for i, col in enumerate(('refil_diant', 'refil_tras')):
            vendas[f['unidade_id'], f['mes']][i] += f[col]
    tecnicos = defaultdict(lambda: [0, 0])
    chaves = set()
    if 'Comissões Equipe' in wb.sheetnames:
        cols = ['Nome', 'Cargo', 'Loja', 'Marca', 'Mês (data)', 'Refil Diant. (qtd)',
                'Refil Tras. (qtd)', 'Verba Diant. (R$)', 'Verba Tras. (R$)']
        for r, ctx in linhas(wb, 'Comissões Equipe', cols):
            nome, cargo = texto(r['Nome'], ctx), texto(r['Cargo'], ctx).lower()
            uid = identificador(texto(r['Marca'], ctx, 140), texto(r['Loja'], ctx, 140))
            pid, mes = identificador(nome), data(r['Mês (data)'], ctx, mes=True)
            if (cargo, pid, uid) not in equipe:
                raise ValueError(f'{ctx}: participante não cadastrado na Equipe.')
            chave = (cargo, pid, uid, mes)
            if chave in chaves:
                raise ValueError(f'{ctx}: comissão mensal duplicada.')
            chaves.add(chave)
            nd, nt = (numero(r[c], ctx, inteiro=True) for c in cols[5:7])
            vd, vt = (numero(r[c], ctx) for c in cols[7:9])
            if cargo == 'consultor':
                fato = fatos.get((pid, uid, mes))
                if fato is None or (nd, nt) != (fato['refil_diant'], fato['refil_tras']):
                    raise ValueError(f'{ctx}: quantidades da comissão divergem das vendas do consultor.')
            else:
                tecnicos[uid, mes][0] += nd
                tecnicos[uid, mes][1] += nt
            tabelas['comissoes_equipe'].append(dict(cargo=cargo, pessoa_id=pid,
                unidade_id=uid, mes=mes, refil_diant=nd, refil_tras=nt,
                verba_diant=vd, verba_tras=vt))
    for chave, qtde in tecnicos.items():
        if any(q > v for q, v in zip(qtde, vendas[chave])):
            raise ValueError('Comissões Equipe: refis atribuídos aos técnicos excedem as vendas da unidade/mês.')
    config = {}
    if 'Configuração' in wb.sheetnames:
        for r, ctx in linhas(wb, 'Configuração', ['Chave', 'Valor']):
            chave = texto(r['Chave'], ctx, 50)
            if chave not in ('tipo_base', 'somente_dianteiro') or chave in config:
                raise ValueError(f'{ctx}: chave desconhecida ou duplicada.')
            valor = texto(r['Valor'], ctx, 100).lower()
            aceitos = ('real', 'ficticia') if chave == 'tipo_base' else ('sim', 'não', 'nao')
            if valor not in aceitos:
                raise ValueError(f'{ctx}: valor de configuração inválido.')
            config[chave] = valor
    if config.get('somente_dianteiro') == 'sim' and any(f['refil_tras'] for f in fatos.values()):
        raise ValueError('Esta base está configurada para vender somente refis dianteiros.')
    tabelas['base_config'] = [dict(chave=k, valor=v) for k, v in config.items()]
