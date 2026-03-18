from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify
from database import supabase
from datetime import datetime

bp = Blueprint('os', __name__, url_prefix='/os')


@bp.route('/')
def listar():
    """Lista ordens de serviço (visão lista ou kanban)"""
    try:
        visao = request.args.get('visao', 'lista')
        
        # Buscar todas as OS com informações relacionadas
        response = supabase.table('ordens_servico').select('''
            *,
            clientes(nome, telefone),
            veiculos(placa, modelo, marca),
            usuarios(nome)
        ''').order('data_abertura', desc=True).execute()
        
        ordens = response.data
        
        # Separar por status para o Kanban
        ordens_por_status = {
            'ORCAMENTO': [],
            'AGUARDANDO_PECA': [],
            'EXECUCAO': [],
            'FINALIZADO': [],
            'PAGO': []
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


@bp.route('/nova', methods=['GET', 'POST'])
@bp.route('/nova', methods=['GET', 'POST'])
def nova():
    """Criar nova ordem de serviço"""
    if request.method == 'POST':
        try:
            veiculo_id = request.form['veiculo_id']
            km_informado = int(request.form.get('km_atual', 0)) if request.form.get('km_atual') else None
            
            # Buscar KM atual do veículo
            veiculo = supabase.table('veiculos').select('km_atual').eq('id', veiculo_id).execute().data[0]
            km_veiculo = veiculo.get('km_atual')
            
            # Se informou KM na OS e é maior que o do veículo, atualizar o veículo
            if km_informado and (not km_veiculo or km_informado >= km_veiculo):
                supabase.table('veiculos').update({'km_atual': km_informado}).eq('id', veiculo_id).execute()
                km_final = km_informado
            else:
                km_final = km_informado if km_informado else km_veiculo
            
            # Dados básicos da OS
            dados_os = {
                'cliente_id': request.form['cliente_id'],
                'veiculo_id': veiculo_id,
                'descricao_problema': request.form.get('descricao_problema', ''),
                'km_atual': km_final,
                'status': 'ORCAMENTO',
                'total_pecas': 0,
                'total_mao_obra': 0,
                'total_geral': 0,
                'lucro_estimado': 0
            }
            
            # Inserir OS
            os_response = supabase.table('ordens_servico').insert(dados_os).execute()
            os_id = os_response.data[0]['id']
            
            flash('Ordem de Serviço criada! Agora adicione itens e serviços.', 'success')
            return redirect(url_for('os.editar', os_id=os_id))
            
        except Exception as e:
            flash(f'Erro ao criar OS: {str(e)}', 'danger')
    
    # Buscar clientes e veículos
    try:
        clientes_response = supabase.table('clientes').select('id, nome, telefone').order('nome').execute()
        veiculos_response = supabase.table('veiculos').select('id, placa, modelo, cliente_id, km_atual').order('placa').execute()
        
        clientes = clientes_response.data
        veiculos = veiculos_response.data
        
        return render_template('os/form_nova.html', clientes=clientes, veiculos=veiculos)
    except Exception as e:
        flash(f'Erro ao carregar dados: {str(e)}', 'danger')
        return redirect(url_for('os.listar'))


@bp.route('/editar/<os_id>', methods=['GET', 'POST'])
def editar(os_id):
    """Editar OS e gerenciar itens"""
    try:
        # Buscar dados da OS
        os_response = supabase.table('ordens_servico').select('''
            *,
            clientes(nome, telefone, cpf_cnpj),
            veiculos(placa, modelo, marca, cor, km_atual)
        ''').eq('id', os_id).execute()
        
        ordem = os_response.data[0] if os_response.data else None
        
        if not ordem:
            flash('Ordem de serviço não encontrada', 'danger')
            return redirect(url_for('os.listar'))
        
        # Buscar itens da OS
        itens_response = supabase.table('os_itens').select('*').eq('os_id', os_id).execute()
        itens = itens_response.data
        
        # Buscar estoque para adicionar itens
        estoque_response = supabase.table('estoque').select('*').order('nome').execute()
        estoque = estoque_response.data
        
        return render_template('os/editar.html', ordem=ordem, itens=itens, estoque=estoque)
        
    except Exception as e:
        flash(f'Erro ao carregar OS: {str(e)}', 'danger')
        return redirect(url_for('os.listar'))


@bp.route('/<os_id>/adicionar_item', methods=['POST'])
def adicionar_item(os_id):
    """Adicionar item à OS (do estoque ou manual)"""
    try:
        tipo = request.form['tipo']  # PECA ou MAO_OBRA
        origem = request.form.get('origem', 'manual')  # 'estoque' ou 'manual'
        
        if origem == 'estoque':
            # Item do estoque
            estoque_id = request.form['estoque_id']
            quantidade = int(request.form['quantidade'])
            
            # Buscar dados do item no estoque
            item_estoque = supabase.table('estoque').select('*').eq('id', estoque_id).execute().data[0]
            
            # Verificar se tem quantidade suficiente
            if item_estoque['quantidade'] < quantidade:
                flash(f'Estoque insuficiente! Disponível: {item_estoque["quantidade"]}', 'warning')
                return redirect(url_for('os.editar', os_id=os_id))
            
            item_dados = {
                'os_id': os_id,
                'estoque_id': estoque_id,
                'tipo': tipo,
                'nome_item': item_estoque['nome'],
                'quantidade': quantidade,
                'custo_unitario': float(item_estoque['custo']),
                'venda_unitario': float(item_estoque['venda'])
            }
            
            # Atualizar quantidade no estoque (diminuir)
            nova_qtd = item_estoque['quantidade'] - quantidade
            supabase.table('estoque').update({'quantidade': nova_qtd}).eq('id', estoque_id).execute()
            
        else:
            # Item manual (criar no estoque também)
            nome_item = request.form['nome_item']
            quantidade = int(request.form['quantidade'])
            custo = float(request.form.get('custo_unitario', 0))
            venda = float(request.form['venda_unitario'])
            
            # Criar no estoque com quantidade 0 (pois já foi consumido)
            novo_estoque = {
                'nome': nome_item,
                'categoria': 'PECAS' if tipo == 'PECA' else 'MAO_OBRA',
                'quantidade': 0,  # Já consumido
                'custo': custo,
                'venda': venda,
                'minimo_alerta': 0
            }
            
            estoque_novo = supabase.table('estoque').insert(novo_estoque).execute()
            estoque_id = estoque_novo.data[0]['id']
            
            item_dados = {
                'os_id': os_id,
                'estoque_id': estoque_id,
                'tipo': tipo,
                'nome_item': nome_item,
                'quantidade': quantidade,
                'custo_unitario': custo,
                'venda_unitario': venda
            }
        
        # Inserir item na OS
        supabase.table('os_itens').insert(item_dados).execute()
        
        # Recalcular totais da OS
        recalcular_totais_os(os_id)
        
        flash('Item adicionado com sucesso!', 'success')
        
    except Exception as e:
        flash(f'Erro ao adicionar item: {str(e)}', 'danger')
    
    return redirect(url_for('os.editar', os_id=os_id))


@bp.route('/<os_id>/remover_item/<item_id>', methods=['POST'])
def remover_item(os_id, item_id):
    """Remover item da OS"""
    try:
        # Buscar dados do item
        item = supabase.table('os_itens').select('*').eq('id', item_id).execute().data[0]
        
        # Devolver ao estoque se veio do estoque
        if item['estoque_id']:
            estoque = supabase.table('estoque').select('quantidade').eq('id', item['estoque_id']).execute().data[0]
            nova_qtd = estoque['quantidade'] + item['quantidade']
            supabase.table('estoque').update({'quantidade': nova_qtd}).eq('id', item['estoque_id']).execute()
        
        # Deletar item
        supabase.table('os_itens').delete().eq('id', item_id).execute()
        
        # Recalcular totais
        recalcular_totais_os(os_id)
        
        flash('Item removido com sucesso!', 'success')
    except Exception as e:
        flash(f'Erro ao remover item: {str(e)}', 'danger')
    
    return redirect(url_for('os.editar', os_id=os_id))


@bp.route('/<os_id>/atualizar_status', methods=['POST'])
def atualizar_status(os_id):
    """Atualizar status da OS (para o Kanban drag & drop)"""
    try:
        novo_status = request.form.get('status') or request.json.get('status')
        
        dados_update = {'status': novo_status}
        
        # Se finalizou ou pagou, marcar data de fechamento
        if novo_status in ['FINALIZADO', 'PAGO']:
            if not supabase.table('ordens_servico').select('data_fechamento').eq('id', os_id).execute().data[0].get('data_fechamento'):
                dados_update['data_fechamento'] = datetime.now().isoformat()
        
        supabase.table('ordens_servico').update(dados_update).eq('id', os_id).execute()
        
        return jsonify({'success': True, 'message': 'Status atualizado!'})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 400


@bp.route('/<os_id>/atualizar_detalhes', methods=['POST'])
def atualizar_detalhes(os_id):
    """Atualizar detalhes da OS (status, forma pagamento, etc)"""
    try:
        dados_update = {}
        
        if 'status' in request.form:
            dados_update['status'] = request.form['status']
        
        if 'forma_pagamento' in request.form:
            dados_update['forma_pagamento'] = request.form['forma_pagamento']
        
        # Se marcou como pago, registrar data
        if dados_update.get('status') == 'PAGO':
            dados_update['data_fechamento'] = datetime.now().isoformat()
        
        supabase.table('ordens_servico').update(dados_update).eq('id', os_id).execute()
        
        flash('OS atualizada com sucesso!', 'success')
    except Exception as e:
        flash(f'Erro ao atualizar OS: {str(e)}', 'danger')
    
    return redirect(url_for('os.editar', os_id=os_id))


@bp.route('/<os_id>/deletar', methods=['POST'])
def deletar(os_id):
    """Deletar OS (com cuidado - devolver itens ao estoque)"""
    try:
        # Buscar itens da OS
        itens = supabase.table('os_itens').select('*').eq('os_id', os_id).execute().data
        
        # Devolver todos os itens ao estoque
        for item in itens:
            if item['estoque_id']:
                estoque = supabase.table('estoque').select('quantidade').eq('id', item['estoque_id']).execute().data[0]
                nova_qtd = estoque['quantidade'] + item['quantidade']
                supabase.table('estoque').update({'quantidade': nova_qtd}).eq('id', item['estoque_id']).execute()
        
        # Deletar itens da OS
        supabase.table('os_itens').delete().eq('os_id', os_id).execute()
        
        # Deletar OS
        supabase.table('ordens_servico').delete().eq('id', os_id).execute()
        
        flash('OS deletada com sucesso! Itens devolvidos ao estoque.', 'success')
    except Exception as e:
        flash(f'Erro ao deletar OS: {str(e)}', 'danger')
    
    return redirect(url_for('os.listar'))


def recalcular_totais_os(os_id):
    """Recalcula totais da OS baseado nos itens"""
    try:
        # Buscar todos os itens
        itens = supabase.table('os_itens').select('*').eq('os_id', os_id).execute().data
        
        total_pecas = 0
        total_mao_obra = 0
        lucro = 0
        
        for item in itens:
            subtotal_venda = item['quantidade'] * item['venda_unitario']
            subtotal_custo = item['quantidade'] * item['custo_unitario']
            
            if item['tipo'] == 'PECA':
                total_pecas += subtotal_venda
            else:
                total_mao_obra += subtotal_venda
            
            lucro += (subtotal_venda - subtotal_custo)
        
        total_geral = total_pecas + total_mao_obra
        
        # Atualizar OS
        supabase.table('ordens_servico').update({
            'total_pecas': total_pecas,
            'total_mao_obra': total_mao_obra,
            'total_geral': total_geral,
            'lucro_estimado': lucro
        }).eq('id', os_id).execute()
        
    except Exception as e:
        print(f"Erro ao recalcular totais: {e}")

@bp.route('/<os_id>/atualizar_info', methods=['POST'])
def atualizar_info(os_id):
    """Atualizar descrição e KM da OS"""
    try:
        descricao = request.form.get('descricao_problema', '')
        km_informado = int(request.form.get('km_atual', 0)) if request.form.get('km_atual') else None
        
        # Buscar OS para pegar veiculo_id
        os_atual = supabase.table('ordens_servico').select('veiculo_id, km_atual').eq('id', os_id).execute().data[0]
        veiculo_id = os_atual['veiculo_id']
        
        # Buscar KM do veículo
        veiculo = supabase.table('veiculos').select('km_atual').eq('id', veiculo_id).execute().data[0]
        km_veiculo = veiculo.get('km_atual')
        
        # Se informou KM e é maior que o do veículo, atualizar o veículo
        if km_informado and (not km_veiculo or km_informado >= km_veiculo):
            supabase.table('veiculos').update({'km_atual': km_informado}).eq('id', veiculo_id).execute()
            flash(f'KM do veículo atualizado para {km_informado:,} km', 'info')
        
        # Atualizar OS
        dados_update = {
            'descricao_problema': descricao,
            'km_atual': km_informado
        }
        
        supabase.table('ordens_servico').update(dados_update).eq('id', os_id).execute()
        
        flash('Informações atualizadas com sucesso!', 'success')
    except Exception as e:
        flash(f'Erro ao atualizar: {str(e)}', 'danger')
    
    return redirect(url_for('os.editar', os_id=os_id))

@bp.route('/<os_id>/imprimir')
def imprimir(os_id):
    """Visualizar OS para impressão"""
    try:
        # Buscar dados completos da OS
        os_response = supabase.table('ordens_servico').select('''
            *,
            clientes(nome, telefone, cpf_cnpj, endereco),
            veiculos(placa, modelo, marca, cor, km_atual)
        ''').eq('id', os_id).execute()
        
        ordem = os_response.data[0] if os_response.data else None
        
        if not ordem:
            flash('Ordem de serviço não encontrada', 'danger')
            return redirect(url_for('os.listar'))
        
        # Buscar itens da OS
        itens_response = supabase.table('os_itens').select('*').eq('os_id', os_id).execute()
        itens = itens_response.data
        
        return render_template('os/imprimir.html', ordem=ordem, itens=itens)
        
    except Exception as e:
        flash(f'Erro ao carregar OS: {str(e)}', 'danger')
        return redirect(url_for('os.listar'))
