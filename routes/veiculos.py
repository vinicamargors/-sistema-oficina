from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify
from database import supabase
from utils.auth_required import login_required, filtrar_empresa, get_empresa_id
import requests as req
import os

from dotenv import load_dotenv
load_dotenv()

bp = Blueprint('veiculos', __name__, url_prefix='/veiculos')


# ── CONSULTA DE PLACA (API externa) ───────────────────────
# jsonify necessário — chamado via fetch no frontend
@bp.route('/consultar-placa/<placa>')
@login_required
def consultar_placa(placa):
    TOKEN = os.getenv("WDAPIPLACAS_TOKEN")
    try:
        r = req.get(f'https://wdapi2.com.br/consulta/{placa}/{TOKEN}', timeout=5)
        if r.status_code == 200:
            dados = r.json()
            return jsonify({
                'marca':  dados.get('MARCA') or dados.get('marca', ''),
                'modelo': dados.get('MODELO') or dados.get('modelo', ''),
                'cor':    dados.get('cor', ''),
                'ano':    dados.get('ano', ''),
                'chassi': dados.get('chassi', ''),
            })
        return jsonify({'erro': 'Placa não encontrada'}), 404
    except Exception as e:
        return jsonify({'erro': str(e)}), 500


# ── LISTAR ─────────────────────────────────────────────────
@bp.route('/')
@login_required
def listar():
    try:
        veiculos = filtrar_empresa(
            supabase.table('veiculos').select('*, clientes(nome, telefone)').order('placa')
        ).execute().data
        return render_template('veiculos/listar.html', veiculos=veiculos)
    except Exception as e:
        flash(f'Erro ao carregar veículos: {str(e)}', 'danger')
        return render_template('veiculos/listar.html', veiculos=[])


# ── MODAL NOVO (chamado via fetch) ─────────────────────────
# jsonify necessário — resposta consumida pelo JS do modal
@bp.route('/modal/novo', methods=['POST'])
@login_required
def api_novo():
    try:
        dados = {
            'placa':      request.form.get('placa', '').upper().strip(),
            'modelo':     request.form.get('modelo', '').strip(),
            'marca':      request.form.get('marca', '').strip(),
            'cor':        request.form.get('cor', '').strip(),
            'km_atual':   None,
            'ano':        int(request.form.get('ano')) if request.form.get('ano') else None,
            'chassi':     request.form.get('chassi', '').strip() or None,
            'cliente_id': request.form.get('cliente_id'),
            'empresa_id': get_empresa_id()
        }

        if not dados['placa'] or not dados['modelo'] or not dados['cliente_id']:
            return jsonify({'erro': 'Placa, modelo e cliente são obrigatórios'}), 400

        duplicado = supabase.table('veiculos').select('id') \
        .eq('placa', dados['placa']) \
        .eq('empresa_id', get_empresa_id()) \
        .execute()
        if duplicado.data:
            return jsonify({'erro': f'Veículo com placa {dados["placa"]} já cadastrado!'}), 409

        response = supabase.table('veiculos').insert(dados).execute()
        return jsonify(response.data[0]), 201

    except Exception as e:
        return jsonify({'erro': f'Erro interno: {str(e)}'}), 500


# ── NOVO ───────────────────────────────────────────────────
@bp.route('/novo', methods=['GET', 'POST'])
@login_required
def novo():
    if request.method == 'POST':
        try:
            dados = {
                'placa':      request.form['placa'].upper().strip(),
                'modelo':     request.form['modelo'].strip(),
                'marca':      request.form.get('marca', '').strip(),
                'cor':        request.form.get('cor', '').strip(),
                'km_atual':   int(request.form['km_atual']) if request.form.get('km_atual') else None,
                'ano':        int(request.form['ano']) if request.form.get('ano') else None,
                'chassi':     request.form.get('chassi', '').strip() or None,
                'cliente_id': request.form['cliente_id'],
                'empresa_id': get_empresa_id()
            }

            duplicado = supabase.table('veiculos').select('id') \
            .eq('placa', dados['placa']) \
            .eq('empresa_id', get_empresa_id()) \
            .execute()
            if duplicado.data:
                flash(f'Veículo com placa {dados["placa"]} já existe!', 'warning')
                return redirect(url_for('veiculos.listar'))

            supabase.table('veiculos').insert(dados).execute()
            flash('Veículo cadastrado com sucesso!', 'success')
            return redirect(url_for('veiculos.listar'))

        except Exception as e:
            flash(f'Erro ao cadastrar: {str(e)}', 'danger')

    try:
        clientes = filtrar_empresa(
            supabase.table('clientes').select('id, nome, telefone').order('nome')
        ).execute().data
    except Exception:
        clientes = []
        flash('Erro ao carregar clientes', 'warning')

    return render_template('veiculos/form.html', veiculo=None, clientes=clientes)


# ── EDITAR ─────────────────────────────────────────────────
@bp.route('/editar/<veiculo_id>', methods=['GET', 'POST'])
@login_required
def editar(veiculo_id):
    if request.method == 'POST':
        try:
            dados = {
                'placa':      request.form['placa'].upper(),
                'modelo':     request.form['modelo'],
                'marca':      request.form.get('marca', ''),
                'cor':        request.form.get('cor', ''),
                'km_atual':   int(request.form['km_atual']) if request.form.get('km_atual') else None,
                'ano':        int(request.form['ano']) if request.form.get('ano') else None,
                'chassi':     request.form.get('chassi', '').strip() or None,
                'cliente_id': request.form['cliente_id']
            }
            supabase.table('veiculos').update(dados).eq('id', veiculo_id).execute()
            flash('Veículo atualizado com sucesso!', 'success')
            return redirect(url_for('veiculos.listar'))

        except Exception as e:
            flash(f'Erro ao atualizar veículo: {str(e)}', 'danger')

    try:
        veiculo  = supabase.table('veiculos').select('*').eq('id', veiculo_id).execute().data
        veiculo  = veiculo[0] if veiculo else None
        clientes = filtrar_empresa(
            supabase.table('clientes').select('id, nome, telefone').order('nome')
        ).execute().data
        return render_template('veiculos/form.html', veiculo=veiculo, clientes=clientes)
    except Exception as e:
        flash(f'Erro ao carregar veículo: {str(e)}', 'danger')
        return redirect(url_for('veiculos.listar'))


# ── DELETAR ────────────────────────────────────────────────
@bp.route('/deletar/<veiculo_id>', methods=['POST'])
@login_required
def deletar(veiculo_id):
    try:
        supabase.table('veiculos').delete().eq('id', veiculo_id).execute()
        flash('Veículo deletado com sucesso!', 'success')
    except Exception as e:
        erro = str(e)
        if 'ordens_servico_veiculo_id_fkey' in erro:
            flash('🚗 Este veículo não pode ser removido pois está vinculado a uma ou mais Ordens de Serviço.', 'warning')
        elif 'foreign key' in erro.lower() or 'violates' in erro.lower():
            flash('⚠️ Este registro não pode ser removido pois está sendo utilizado em outro lugar do sistema.', 'warning')
        else:
            flash(f'Erro ao deletar veículo: {erro}', 'danger')

    return redirect(url_for('veiculos.listar'))


# ── BUSCAR POR PLACA ───────────────────────────────────────
@bp.route('/buscar')
@login_required
def buscar():
    placa = request.args.get('placa', '').upper()

    if not placa:
        return render_template('veiculos/buscar.html', veiculo=None)

    try:
        response = filtrar_empresa(
            supabase.table('veiculos').select('*, clientes(nome, telefone)').eq('placa', placa)
        ).execute()
        veiculo = response.data[0] if response.data else None

        if veiculo:
            flash(f'Veículo encontrado: {veiculo["modelo"]}', 'success')
        else:
            flash(f'Nenhum veículo encontrado com a placa {placa}', 'warning')

        return render_template('veiculos/buscar.html', veiculo=veiculo)
    except Exception as e:
        flash(f'Erro ao buscar veículo: {str(e)}', 'danger')
        return render_template('veiculos/buscar.html', veiculo=None)


# ── API LISTAR (chamado via fetch no frontend) ─────────────
# jsonify necessário — resposta consumida pelo JS da nova OS
@bp.route('/api', methods=['GET'])
@login_required
def api_listar():
    try:
        veiculos = filtrar_empresa(
            supabase.table('veiculos').select('id, placa, modelo, cliente_id').order('placa')
        ).execute().data
        return {'veiculos': veiculos}, 200
    except Exception as e:
        return {'error': str(e)}, 400
