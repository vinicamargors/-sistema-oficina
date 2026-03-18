from flask import Blueprint, render_template, request, redirect, url_for, flash
from database import supabase

bp = Blueprint('veiculos', __name__, url_prefix='/veiculos')


@bp.route('/')
def listar():
    """Lista todos os veículos com informações do cliente"""
    try:
        response = supabase.table('veiculos').select('*, clientes(nome, telefone)').order('placa').execute()
        veiculos = response.data
        return render_template('veiculos/listar.html', veiculos=veiculos)
    except Exception as e:
        flash(f'Erro ao carregar veículos: {str(e)}', 'danger')
        return render_template('veiculos/listar.html', veiculos=[])


@bp.route('/novo', methods=['GET', 'POST'])
def novo():
    """Cadastrar novo veículo"""
    if request.method == 'POST':
        try:
            dados = {
                'placa': request.form['placa'].upper(),
                'modelo': request.form['modelo'],
                'marca': request.form.get('marca', ''),
                'cor': request.form.get('cor', ''),
                'km_atual': int(request.form.get('km_atual', 0)) if request.form.get('km_atual') else None,
                'cliente_id': request.form['cliente_id']
            }
            
            supabase.table('veiculos').insert(dados).execute()
            flash('Veículo cadastrado com sucesso!', 'success')
            return redirect(url_for('veiculos.listar'))
            
        except Exception as e:
            flash(f'Erro ao cadastrar veículo: {str(e)}', 'danger')
    
    # Buscar clientes para o dropdown
    try:
        clientes_response = supabase.table('clientes').select('id, nome, telefone').order('nome').execute()
        clientes = clientes_response.data
    except:
        clientes = []
        flash('Erro ao carregar clientes', 'warning')
    
    return render_template('veiculos/form.html', veiculo=None, clientes=clientes)


@bp.route('/editar/<veiculo_id>', methods=['GET', 'POST'])
def editar(veiculo_id):
    """Editar veículo existente"""
    if request.method == 'POST':
        try:
            dados = {
                'placa': request.form['placa'].upper(),
                'modelo': request.form['modelo'],
                'marca': request.form.get('marca', ''),
                'cor': request.form.get('cor', ''),
                'km_atual': int(request.form.get('km_atual', 0)) if request.form.get('km_atual') else None,
                'cliente_id': request.form['cliente_id']
            }
            
            supabase.table('veiculos').update(dados).eq('id', veiculo_id).execute()
            flash('Veículo atualizado com sucesso!', 'success')
            return redirect(url_for('veiculos.listar'))
            
        except Exception as e:
            flash(f'Erro ao atualizar veículo: {str(e)}', 'danger')
    
    # GET
    try:
        veiculo_response = supabase.table('veiculos').select('*').eq('id', veiculo_id).execute()
        veiculo = veiculo_response.data[0] if veiculo_response.data else None
        
        clientes_response = supabase.table('clientes').select('id, nome, telefone').order('nome').execute()
        clientes = clientes_response.data
        
        return render_template('veiculos/form.html', veiculo=veiculo, clientes=clientes)
    except Exception as e:
        flash(f'Erro ao carregar veículo: {str(e)}', 'danger')
        return redirect(url_for('veiculos.listar'))


@bp.route('/deletar/<veiculo_id>', methods=['POST'])
def deletar(veiculo_id):
    """Deletar veículo"""
    try:
        supabase.table('veiculos').delete().eq('id', veiculo_id).execute()
        flash('Veículo deletado com sucesso!', 'success')
    except Exception as e:
        flash(f'Erro ao deletar veículo: {str(e)}', 'danger')
    
    return redirect(url_for('veiculos.listar'))


@bp.route('/buscar')
def buscar():
    """Buscar veículo por placa"""
    placa = request.args.get('placa', '').upper()
    
    if not placa:
        return render_template('veiculos/buscar.html', veiculo=None)
    
    try:
        response = supabase.table('veiculos').select('*, clientes(nome, telefone)').eq('placa', placa).execute()
        veiculo = response.data[0] if response.data else None
        
        if veiculo:
            flash(f'Veículo encontrado: {veiculo["modelo"]}', 'success')
        else:
            flash(f'Nenhum veículo encontrado com a placa {placa}', 'warning')
            
        return render_template('veiculos/buscar.html', veiculo=veiculo)
    except Exception as e:
        flash(f'Erro ao buscar veículo: {str(e)}', 'danger')
        return render_template('veiculos/buscar.html', veiculo=None)

@bp.route('/api', methods=['GET'])
def api_listar():
    """API para retornar veículos em JSON"""
    try:
        response = supabase.table('veiculos').select('id, placa, modelo, cliente_id').order('placa').execute()
        return {'veiculos': response.data}, 200
    except Exception as e:
        return {'error': str(e)}, 400
