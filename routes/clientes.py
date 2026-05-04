from flask import Blueprint, render_template, request, redirect, url_for, flash, session
from database import supabase
from utils.auth_required import login_required, filtrar_empresa, get_empresa_id

bp = Blueprint('clientes', __name__, url_prefix='/clientes')


@bp.route('/')
@login_required
def listar():
    try:
        clientes = filtrar_empresa(
            supabase.table('clientes').select('*').order('nome')
        ).execute().data
        return render_template('clientes/listar.html', clientes=clientes)
    except Exception as e:
        flash(f'Erro ao carregar clientes: {str(e)}', 'danger')
        return render_template('clientes/listar.html', clientes=[])


@bp.route('/novo', methods=['GET', 'POST'])
@login_required
def novo():
    if request.method == 'POST':
        try:
            nome     = request.form.get('nome', '').strip()
            telefone = request.form.get('telefone', '').strip()
            cpf      = request.form.get('cpf_cnpj', '').strip()
            endereco = request.form.get('endereco', '').strip()

            if not nome or not telefone:
                flash('Nome e telefone são obrigatórios', 'warning')
                return redirect(url_for('clientes.novo'))

            # Verifica duplicado somente dentro da mesma empresa
            duplicado = filtrar_empresa(
                supabase.table('clientes').select('id').eq('telefone', telefone)
            ).execute()

            if duplicado.data:
                flash(f'Cliente com telefone {telefone} já existe', 'warning')
                return redirect(url_for('clientes.listar'))

            supabase.table('clientes').insert({
                'nome':       nome,
                'telefone':   telefone,
                'cpf_cnpj':   cpf or None,
                'endereco':   endereco or None,
                'empresa_id': get_empresa_id()
            }).execute()

            flash('Cliente cadastrado com sucesso!', 'success')
            return redirect(url_for('clientes.listar'))

        except Exception as e:
            flash(f'Erro ao cadastrar cliente: {str(e)}', 'danger')
            return redirect(url_for('clientes.novo'))

    return render_template('clientes/form.html', cliente=None)


@bp.route('/editar/<cliente_id>', methods=['GET', 'POST'])
@login_required
def editar(cliente_id):
    if request.method == 'POST':
        try:
            dados = {
                'nome':     request.form['nome'],
                'telefone': request.form['telefone'],
                'cpf_cnpj': request.form.get('cpf_cnpj', ''),
                'endereco': request.form.get('endereco', '')
            }
            supabase.table('clientes').update(dados).eq('id', cliente_id).execute()
            flash('Cliente atualizado com sucesso!', 'success')
            return redirect(url_for('clientes.listar'))

        except Exception as e:
            flash(f'Erro ao atualizar cliente: {str(e)}', 'danger')

    try:
        response = supabase.table('clientes').select('*').eq('id', cliente_id).execute()
        cliente  = response.data[0] if response.data else None
        return render_template('clientes/form.html', cliente=cliente)
    except Exception as e:
        flash(f'Erro ao carregar cliente: {str(e)}', 'danger')
        return redirect(url_for('clientes.listar'))


@bp.route('/deletar/<cliente_id>', methods=['POST'])
@login_required
def deletar(cliente_id):
    try:
        supabase.table('clientes').delete().eq('id', cliente_id).execute()
        flash('Cliente deletado com sucesso!', 'success')
    except Exception as e:
        erro = str(e)
        if 'veiculos_cliente_id_fkey' in erro:
            flash('👤 Este cliente não pode ser removido pois possui veículos cadastrados.', 'warning')
        elif 'ordens_servico_cliente_id_fkey' in erro:
            flash('👤 Este cliente não pode ser removido pois está vinculado a Ordens de Serviço.', 'warning')
        elif 'foreign key' in erro.lower():
            flash('⚠️ Este cliente não pode ser removido pois está em uso no sistema.', 'warning')
        else:
            flash(f'Erro ao deletar cliente: {erro}', 'danger')

    return redirect(url_for('clientes.listar'))


@bp.route('/api', methods=['GET'])
@login_required
def api_listar():
    try:
        clientes = filtrar_empresa(
            supabase.table('clientes').select('id, nome, telefone').order('nome')
        ).execute().data
        return {'clientes': clientes}, 200
    except Exception as e:
        return {'error': str(e)}, 400
