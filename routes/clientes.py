from flask import Blueprint, render_template, request, redirect, url_for, flash
from database import supabase

bp = Blueprint('clientes', __name__, url_prefix='/clientes')


@bp.route('/')
def listar():
    """Lista todos os clientes"""
    try:
        response = supabase.table('clientes').select('*').order('nome').execute()
        clientes = response.data
        return render_template('clientes/listar.html', clientes=clientes)
    except Exception as e:
        flash(f'Erro ao carregar clientes: {str(e)}', 'danger')
        return render_template('clientes/listar.html', clientes=[])


@bp.route('/novo', methods=['GET', 'POST'])
def novo():
    """Cadastrar novo cliente"""
    if request.method == 'POST':
        try:
            dados = {
                'nome': request.form['nome'],
                'telefone': request.form['telefone'],
                'cpf_cnpj': request.form.get('cpf_cnpj', ''),
                'endereco': request.form.get('endereco', '')
            }
            
            supabase.table('clientes').insert(dados).execute()
            flash('Cliente cadastrado com sucesso!', 'success')
            return redirect(url_for('clientes.listar'))
            
        except Exception as e:
            flash(f'Erro ao cadastrar cliente: {str(e)}', 'danger')
    
    return render_template('clientes/form.html', cliente=None)


@bp.route('/editar/<cliente_id>', methods=['GET', 'POST'])
def editar(cliente_id):
    """Editar cliente existente"""
    if request.method == 'POST':
        try:
            dados = {
                'nome': request.form['nome'],
                'telefone': request.form['telefone'],
                'cpf_cnpj': request.form.get('cpf_cnpj', ''),
                'endereco': request.form.get('endereco', '')
            }
            
            supabase.table('clientes').update(dados).eq('id', cliente_id).execute()
            flash('Cliente atualizado com sucesso!', 'success')
            return redirect(url_for('clientes.listar'))
            
        except Exception as e:
            flash(f'Erro ao atualizar cliente: {str(e)}', 'danger')
    
    # GET - Buscar dados do cliente
    try:
        response = supabase.table('clientes').select('*').eq('id', cliente_id).execute()
        cliente = response.data[0] if response.data else None
        return render_template('clientes/form.html', cliente=cliente)
    except Exception as e:
        flash(f'Erro ao carregar cliente: {str(e)}', 'danger')
        return redirect(url_for('clientes.listar'))


@bp.route('/deletar/<cliente_id>', methods=['POST'])
def deletar(cliente_id):
    """Deletar cliente"""
    try:
        supabase.table('clientes').delete().eq('id', cliente_id).execute()
        flash('Cliente deletado com sucesso!', 'success')
    except Exception as e:
        flash(f'Erro ao deletar cliente: {str(e)}', 'danger')
    
    return redirect(url_for('clientes.listar'))

@bp.route('/api', methods=['GET'])
def api_listar():
    """API para retornar clientes em JSON"""
    try:
        response = supabase.table('clientes').select('id, nome, telefone').order('nome').execute()
        return {'clientes': response.data}, 200
    except Exception as e:
        return {'error': str(e)}, 400
