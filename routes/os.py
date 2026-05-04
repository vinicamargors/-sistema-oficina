import json
from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify, session
from database import supabase
from datetime import datetime
from utils.auth_required import login_required, filtrar_empresa, get_empresa_id

bp = Blueprint('os', __name__, url_prefix='/os')


def is_ajax_request():
    return (request.args.get('_method') or
            request.headers.get('X-Requested-With') == 'XMLHttpRequest' or
            request.content_type == 'application/json')


# ── LISTAR ─────────────────────────────────────────────────
@bp.route('/')
@login_required
def listar():
    try:
        visao = request.args.get('visao', 'lista')

        ordens = filtrar_empresa(
            supabase.table('ordens_servico').select('''
                *,
                clientes(nome, telefone),
                veiculos(placa, modelo, marca),
                usuarios(nome)
            ''').order('data_abertura', desc=True)
        ).execute().data

        ordens_por_status = {
            'ORCAMENTO': [], 'AGUARDANDO_PECA': [],
            'EXECUCAO': [],  'FINALIZADO': [], 'PAGO': []
        }
        for ordem in ordens:
            status = ordem.get('status', 'ORCAMENTO')
            if status in ordens_por_status:
                ordens_por_status[status].append(ordem)

        return render_template('os/listar.html',
                               ordens=ordens,
                               ordens_por_status=ordens_por_status,
                               visao=visao)
    except Exception as e:
        flash(f'Erro ao carregar ordens de serviço: {str(e)}', 'danger')
        return render_template('os/listar.html', ordens=[], ordens_por_status={}, visao='lista')


# ── NOVA ───────────────────────────────────────────────────
@bp.route('/nova', methods=['GET', 'POST'])
@login_required
def nova():
    mecanicos = filtrar_empresa(
        supabase.table('usuarios').select('id, nome').order('nome')
    ).execute().data

    if request.method == 'POST':
        try:
            veiculo_id   = request.form['veiculo_id']
            km_informado = int(request.form.get('km_atual', 0)) if request.form.get('km_atual') else None

            veiculo    = supabase.table('veiculos').select('km_atual').eq('id', veiculo_id).execute().data[0]
            km_veiculo = veiculo.get('km_atual')

            if km_informado and (not km_veiculo or km_informado >= km_veiculo):
                supabase.table('veiculos').update({'km_atual': km_informado}).eq('id', veiculo_id).execute()
                km_final = km_informado
            else:
                km_final = km_informado if km_informado else km_veiculo

            # Verifica OS aberta para o mesmo veículo (dentro da empresa)
            os_existente = filtrar_empresa(
                supabase.table('ordens_servico').select('id')
                    .eq('veiculo_id', veiculo_id)
                    .eq('status', 'ORCAMENTO')
            ).execute()

            if os_existente.data:
                os_id = os_existente.data[0]['id']
                if is_ajax_request():
                    return jsonify({'erro': f'Já existe OS #{os_id[:8]} aberta para este veículo!', 'os_id': os_id}), 409
                flash(f'Já existe OS #{os_id[:8]} aberta para este veículo!', 'warning')
                return redirect(url_for('os.editar', os_id=os_id))

            dados_os = {
                'cliente_id':              request.form['cliente_id'],
                'veiculo_id':              veiculo_id,
                'descricao_problema':      request.form.get('descricao_problema', ''),
                'km_atual':                km_final,
                'status':                  'ORCAMENTO',
                'total_pecas':             0,
                'total_mao_obra':          0,
                'total_geral':             0,
                'lucro_estimado':          0,
                'mecanico_responsavel_id': session.get('user_id') or None,
                'empresa_id':              get_empresa_id()          # ← grava empresa
            }

            os_response = supabase.table('ordens_servico').insert(dados_os).execute()
            os_id       = os_response.data[0]['id']

            flash('Ordem de Serviço criada! Agora adicione itens e serviços.', 'success')

            if is_ajax_request():
                return jsonify({'os_id': os_id}), 201

            return redirect(url_for('os.editar', os_id=os_id))

        except Exception as e:
            if is_ajax_request():
                return jsonify({'erro': f'Erro ao criar OS: {str(e)}'}), 500
            flash(f'Erro ao criar OS: {str(e)}', 'danger')

    try:
        clientes = filtrar_empresa(
            supabase.table('clientes').select('id, nome, telefone').order('nome')
        ).execute().data

        veiculos = filtrar_empresa(
            supabase.table('veiculos').select('id, placa, modelo, cliente_id, km_atual').order('placa')
        ).execute().data

        return render_template('os/form_nova.html', clientes=clientes, veiculos=veiculos, mecanicos=mecanicos)
    except Exception as e:
        flash(f'Erro ao carregar dados: {str(e)}', 'danger')
        return redirect(url_for('os.listar'))


# ── EDITAR ─────────────────────────────────────────────────
@bp.route('/editar/<os_id>', methods=['GET', 'POST'])
@login_required
def editar(os_id):
    mecanicos = filtrar_empresa(
        supabase.table('usuarios').select('id, nome').order('nome')
    ).execute().data

    try:
        os_response = supabase.table('ordens_servico').select('''
            *,
            clientes(nome, telefone, cpf_cnpj),
            veiculos(placa, modelo, marca, cor, ano, chassi, km_atual)
        ''').eq('id', os_id).execute()

        ordem = os_response.data[0] if os_response.data else None

        if not ordem:
            flash('Ordem de serviço não encontrada', 'danger')
            return redirect(url_for('os.listar'))

        itens   = supabase.table('os_itens').select('*').eq('os_id', os_id).execute().data

        estoque = filtrar_empresa(
            supabase.table('estoque').select('*').order('nome')
        ).execute().data

        return render_template('os/editar.html', ordem=ordem, itens=itens, estoque=estoque, mecanicos=mecanicos)

    except Exception as e:
        flash(f'Erro ao carregar OS: {str(e)}', 'danger')
        return redirect(url_for('os.listar'))


# ── ADICIONAR ITEM ─────────────────────────────────────────
@bp.route('/<os_id>/adicionar_item', methods=['POST'])
@login_required
def adicionar_item(os_id):
    try:
        payload_itens = request.form.get('payload_itens')

        if payload_itens:
            itens = json.loads(payload_itens)
            itens_inseridos = []

            for item in itens:
                tipo   = item.get('tipo')
                origem = item.get('origem', 'manual')

                if tipo not in ['PECA', 'MAO_OBRA', 'TERCEIRIZADO']:
                    raise Exception('Tipo inválido')

                if origem == 'estoque':
                    estoque_id  = item.get('estoque_id')
                    quantidade  = int(item.get('quantidade', 1))
                    item_est    = supabase.table('estoque').select('*').eq('id', estoque_id).execute().data

                    if not item_est:
                        raise Exception('Item de estoque não encontrado')
                    item_est = item_est[0]

                    if item_est['quantidade'] < quantidade:
                        raise Exception(f"Estoque insuficiente para {item_est['nome']}")

                    item_dados = {
                        'os_id': os_id, 'estoque_id': estoque_id, 'tipo': tipo,
                        'nome_item':       item.get('nome_item') or item_est['nome'],
                        'quantidade':      quantidade,
                        'custo_unitario':  float(item.get('custo_unitario', item_est['custo'])),
                        'venda_unitario':  float(item.get('venda_unitario', item_est['venda']))
                    }
                    supabase.table('estoque').update(
                        {'quantidade': item_est['quantidade'] - quantidade}
                    ).eq('id', estoque_id).execute()
                else:
                    item_dados = {
                        'os_id': os_id, 'estoque_id': None, 'tipo': tipo,
                        'nome_item':      item.get('nome_item', '').strip(),
                        'quantidade':     int(item.get('quantidade', 1)),
                        'custo_unitario': float(item.get('custo_unitario', 0)),
                        'venda_unitario': float(item.get('venda_unitario', 0))
                    }

                supabase.table('os_itens').insert(item_dados).execute()
                itens_inseridos.append(item_dados)

            recalcular_totais_os(os_id)
            flash(f'{len(itens_inseridos)} item(ns) adicionados com sucesso!', 'success')
            return redirect(url_for('os.editar', os_id=os_id))

        # Item único
        tipo   = request.form['tipo']
        origem = request.form.get('origem', 'manual')

        if origem == 'estoque':
            estoque_id = request.form['estoque_id']
            quantidade = int(request.form['quantidade'])
            item_est   = supabase.table('estoque').select('*').eq('id', estoque_id).execute().data

            if not item_est:
                raise Exception('Item de estoque não encontrado')
            item_est = item_est[0]

            if item_est['quantidade'] < quantidade:
                flash(f'Estoque insuficiente! Disponível: {item_est["quantidade"]}', 'warning')
                return redirect(url_for('os.editar', os_id=os_id))

            item_dados = {
                'os_id': os_id, 'estoque_id': estoque_id, 'tipo': tipo,
                'nome_item':      item_est['nome'],
                'quantidade':     quantidade,
                'custo_unitario': float(item_est['custo']),
                'venda_unitario': float(item_est['venda'])
            }
            supabase.table('estoque').update(
                {'quantidade': item_est['quantidade'] - quantidade}
            ).eq('id', estoque_id).execute()
        else:
            item_dados = {
                'os_id': os_id, 'estoque_id': None, 'tipo': tipo,
                'nome_item':      request.form['nome_item'].strip(),
                'quantidade':     int(request.form['quantidade']),
                'custo_unitario': float(request.form.get('custo_unitario', 0)),
                'venda_unitario': float(request.form['venda_unitario'])
            }

        supabase.table('os_itens').insert(item_dados).execute()
        recalcular_totais_os(os_id)
        flash('Item adicionado com sucesso!', 'success')

        tipo = request.form['tipo']
        if tipo not in ['PECA', 'MAO_OBRA', 'TERCEIRIZADO']:
            raise Exception('Tipo inválido')

    except Exception as e:
        flash(f'Erro ao adicionar item: {str(e)}', 'danger')

    return redirect(url_for('os.editar', os_id=os_id))


# ── REMOVER ITEM ───────────────────────────────────────────
@bp.route('/<os_id>/remover_item/<item_id>', methods=['POST'])
@login_required
def remover_item(os_id, item_id):
    try:
        item = supabase.table('os_itens').select('*').eq('id', item_id).execute().data[0]

        if item['estoque_id']:
            estoque  = supabase.table('estoque').select('quantidade').eq('id', item['estoque_id']).execute().data[0]
            nova_qtd = estoque['quantidade'] + item['quantidade']
            supabase.table('estoque').update({'quantidade': nova_qtd}).eq('id', item['estoque_id']).execute()

        supabase.table('os_itens').delete().eq('id', item_id).execute()
        recalcular_totais_os(os_id)
        flash('Item removido com sucesso!', 'success')
    except Exception as e:
        flash(f'Erro ao remover item: {str(e)}', 'danger')

    return redirect(url_for('os.editar', os_id=os_id))


# ── ATUALIZAR STATUS ───────────────────────────────────────
@bp.route('/<os_id>/atualizar_status', methods=['POST'])
@login_required
def atualizar_status(os_id):
    try:
        novo_status  = request.form.get('status') or request.json.get('status')
        dados_update = {'status': novo_status}

        if novo_status in ['FINALIZADO', 'PAGO']:
            atual = supabase.table('ordens_servico').select('data_fechamento').eq('id', os_id).execute().data[0]
            if not atual.get('data_fechamento'):
                dados_update['data_fechamento'] = datetime.now().isoformat()

        supabase.table('ordens_servico').update(dados_update).eq('id', os_id).execute()
        return jsonify({'success': True, 'message': 'Status atualizado!'})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 400


# ── ATUALIZAR DETALHES ─────────────────────────────────────
@bp.route('/<os_id>/atualizar_detalhes', methods=['POST'])
@login_required
def atualizar_detalhes(os_id):
    try:
        dados_update = {}

        if 'status' in request.form:
            dados_update['status'] = request.form['status']
        if 'forma_pagamento' in request.form:
            dados_update['forma_pagamento'] = request.form['forma_pagamento']
        if 'mecanico_responsavel_id' in request.form:
            dados_update['mecanico_responsavel_id'] = request.form.get('mecanico_responsavel_id') or None

        if dados_update.get('status') == 'PAGO':
            dados_update['data_fechamento'] = datetime.now().isoformat()

        supabase.table('ordens_servico').update(dados_update).eq('id', os_id).execute()
        flash('OS atualizada com sucesso!', 'success')
    except Exception as e:
        flash(f'Erro ao atualizar OS: {str(e)}', 'danger')

    return redirect(url_for('os.editar', os_id=os_id))


# ── ATUALIZAR INFO ─────────────────────────────────────────
@bp.route('/<os_id>/atualizar_info', methods=['POST'])
@login_required
def atualizar_info(os_id):
    try:
        descricao    = request.form.get('descricao_problema', '')
        km_informado = int(request.form.get('km_atual', 0)) if request.form.get('km_atual') else None

        os_atual   = supabase.table('ordens_servico').select('veiculo_id, km_atual').eq('id', os_id).execute().data[0]
        veiculo_id = os_atual['veiculo_id']
        veiculo    = supabase.table('veiculos').select('km_atual').eq('id', veiculo_id).execute().data[0]
        km_veiculo = veiculo.get('km_atual')

        if km_informado and (not km_veiculo or km_informado >= km_veiculo):
            supabase.table('veiculos').update({'km_atual': km_informado}).eq('id', veiculo_id).execute()
            flash(f'KM do veículo atualizado para {km_informado:,} km', 'info')

        supabase.table('ordens_servico').update({
            'descricao_problema': descricao,
            'km_atual':           km_informado
        }).eq('id', os_id).execute()

        flash('Informações atualizadas com sucesso!', 'success')
    except Exception as e:
        flash(f'Erro ao atualizar: {str(e)}', 'danger')

    return redirect(url_for('os.editar', os_id=os_id))


# ── DELETAR ────────────────────────────────────────────────
@bp.route('/<os_id>/deletar', methods=['POST'])
@login_required
def deletar(os_id):
    motivo = request.form.get('motivo', '').strip()

    if not motivo:
        flash('Informe o motivo da exclusão.', 'warning')
        return redirect(url_for('os.listar'))

    try:
        itens = supabase.table('os_itens').select('*').eq('os_id', os_id).execute().data

        for item in itens:
            if item['estoque_id']:
                estoque  = supabase.table('estoque').select('quantidade').eq('id', item['estoque_id']).execute().data[0]
                nova_qtd = estoque['quantidade'] + item['quantidade']
                supabase.table('estoque').update({'quantidade': nova_qtd}).eq('id', item['estoque_id']).execute()

        supabase.table('os_itens').delete().eq('os_id', os_id).execute()
        supabase.table('ordens_servico').delete().eq('id', os_id).execute()

        flash('OS deletada com sucesso! Itens devolvidos ao estoque.', 'success')
    except Exception as e:
        flash(f'Erro ao deletar OS: {str(e)}', 'danger')

    return redirect(url_for('os.listar'))


# ── IMPRIMIR ───────────────────────────────────────────────
@bp.route('/<os_id>/imprimir')
@login_required
def imprimir(os_id):
    try:
        os_response = supabase.table('ordens_servico').select('''
            *,
            clientes(nome, telefone, cpf_cnpj, endereco),
            veiculos(placa, modelo, marca, cor, ano, chassi, km_atual)
        ''').eq('id', os_id).execute()

        ordem = os_response.data[0] if os_response.data else None

        if not ordem:
            flash('Ordem de serviço não encontrada', 'danger')
            return redirect(url_for('os.listar'))

        itens    = supabase.table('os_itens').select('*').eq('os_id', os_id).execute().data
        mecanico = None

        if ordem.get('mecanico_responsavel_id'):
            resultado = supabase.table('usuarios').select('id, nome') \
                .eq('id', ordem['mecanico_responsavel_id']).execute().data
            if resultado:
                mecanico = resultado[0]

        empresa_info = None
        empresa_id   = get_empresa_id()
        if empresa_id:
            res = supabase.table('empresas') \
                .select('nome_fantasia, cnpj, telefone, email, endereco') \
                .eq('id', empresa_id).execute()
            if res.data:
                empresa_info = res.data[0]

        # Só passa empresa_info se a OS pertence à empresa logada
        if ordem.get('empresa_id') == empresa_id:
            return render_template('os/imprimir.html',
                                   ordem=ordem, itens=itens, 
                                   mecanico=mecanico, empresa_info=empresa_info)
        else:
            return render_template('os/imprimir.html',
                                   ordem=ordem, itens=itens, mecanico=mecanico)

    except Exception as e:
        flash(f'Erro ao carregar OS: {str(e)}', 'danger')
        return redirect(url_for('os.listar'))


# ── HELPER ─────────────────────────────────────────────────
def recalcular_totais_os(os_id):
    try:
        itens          = supabase.table('os_itens').select('*').eq('os_id', os_id).execute().data
        total_pecas    = 0
        total_mao_obra = 0
        lucro          = 0

        for item in itens:
            subtotal_venda = item['quantidade'] * item['venda_unitario']
            subtotal_custo = item['quantidade'] * item['custo_unitario']

            if item['tipo'] in ['PECA', 'TERCEIRIZADO']:
                total_pecas += subtotal_venda
            else:
                total_mao_obra += subtotal_venda

            lucro += (subtotal_venda - subtotal_custo)

        supabase.table('ordens_servico').update({
            'total_pecas':    total_pecas,
            'total_mao_obra': total_mao_obra,
            'total_geral':    total_pecas + total_mao_obra,
            'lucro_estimado': lucro
        }).eq('id', os_id).execute()

    except Exception as e:
        print(f"Erro ao recalcular totais: {e}")