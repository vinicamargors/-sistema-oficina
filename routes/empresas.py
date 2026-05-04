from flask import Blueprint, render_template, request, redirect, url_for, flash, session
from database import supabase
from utils.auth_required import login_required, master_required, dono_required, get_empresa_id
import bcrypt

bp = Blueprint('empresas', __name__, url_prefix='/empresas')

PLANOS = ['basico', 'profissional', 'enterprise']


# ── LISTAR ─────────────────────────────────────────────────
@bp.route('/')
@login_required
def listar():
    try:
        if session.get('user_cargo') == 'master':
            empresas = supabase.table('empresas').select('*').order('nome_fantasia').execute().data
        else:
            empresas = supabase.table('empresas').select('*') \
                .eq('id', get_empresa_id()).execute().data
        return render_template('empresas/listar.html', empresas=empresas)
    except Exception as e:
        flash(f'Erro ao carregar empresas: {str(e)}', 'danger')
        return render_template('empresas/listar.html', empresas=[])


# ── NOVA EMPRESA (só master) ───────────────────────────────
@bp.route('/nova', methods=['GET', 'POST'])
@master_required
def nova():
    if request.method == 'POST':
        try:
            nome_fantasia = request.form['nome_fantasia'].strip()
            razao_social  = request.form.get('razao_social', '').strip() or None
            cnpj          = request.form.get('cnpj', '').strip() or None
            email         = request.form.get('email', '').lower().strip() or None
            telefone      = request.form.get('telefone', '').strip() or None
            plano         = request.form.get('plano', 'basico')
            endereco = request.form.get('endereco', '').strip() or None
            nome_dono     = request.form['nome_dono'].strip()
            email_dono    = request.form['email_dono'].lower().strip()
            senha_dono    = request.form['senha_dono']

            if not nome_fantasia or not email_dono or not senha_dono or not nome_dono:
                flash('Nome da empresa, dados do dono e senha são obrigatórios.', 'warning')
                return render_template('empresas/form.html', empresa=None, planos=PLANOS)

            if len(senha_dono) < 6:
                flash('A senha do dono deve ter pelo menos 6 caracteres.', 'warning')
                return render_template('empresas/form.html', empresa=None, planos=PLANOS)

            # Verifica e-mail do dono já em uso
            existente = supabase.table('usuarios').select('id').eq('email', email_dono).execute()
            if existente.data:
                flash('Já existe um usuário com esse e-mail.', 'warning')
                return render_template('empresas/form.html', empresa=None, planos=PLANOS)

            # 1) Cria a empresa
            empresa = supabase.table('empresas').insert({
                'nome_fantasia': nome_fantasia,
                'razao_social':  razao_social,
                'cnpj':          cnpj,
                'email':         email,
                'telefone':      telefone,
                'endereco':      endereco, 
                'plano':         plano,
                'ativo':         True
            }).execute().data[0]

            empresa_id = empresa['id']

            # 2) Cria configurações padrão
            supabase.table('configuracoes_empresa').insert({
                'empresa_id':     empresa_id,
                'cor_primaria':   '#1e3a8a',
                'cor_secundaria': '#f97316',
                'nome_exibicao':  nome_fantasia
            }).execute()

            # 3) Cria o usuário DONO
            senha_hash = bcrypt.hashpw(senha_dono.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')
            supabase.table('usuarios').insert({
                'nome':       nome_dono,
                'email':      email_dono,
                'senha_hash': senha_hash,
                'cargo':      'DONO',
                'ativo':      True,
                'empresa_id': empresa_id
            }).execute()

            flash(f'Empresa "{nome_fantasia}" criada com sucesso!', 'success')
            return redirect(url_for('empresas.listar'))

        except Exception as e:
            import traceback; traceback.print_exc()
            flash(f'Erro ao criar empresa: {str(e)}', 'danger')

    return render_template('empresas/form.html', empresa=None, planos=PLANOS)


# ── EDITAR EMPRESA ─────────────────────────────────────────
@bp.route('/editar/<empresa_id>', methods=['GET', 'POST'])
@login_required
def editar(empresa_id):
    cargo = session.get('user_cargo')

    if cargo != 'master' and str(get_empresa_id()) != str(empresa_id):
        flash('Acesso negado.', 'danger')
        return redirect(url_for('empresas.listar'))

    if request.method == 'POST':
        try:
            dados = {
                'nome_fantasia': request.form['nome_fantasia'].strip(),
                'razao_social':  request.form.get('razao_social', '').strip() or None,
                'cnpj':          request.form.get('cnpj', '').strip() or None,
                'email':         request.form.get('email', '').lower().strip() or None,
                'endereco':      request.form.get('endereco', '').strip() or None,
                'telefone':      request.form.get('telefone', '').strip() or None,
            }
            # Só master pode alterar plano e status
            if cargo == 'master':
                dados['plano'] = request.form.get('plano', 'basico')
                dados['ativo'] = request.form.get('ativo') == 'on'

            supabase.table('empresas').update(dados).eq('id', empresa_id).execute()
            flash('Empresa atualizada com sucesso!', 'success')
            return redirect(url_for('empresas.listar'))

        except Exception as e:
            flash(f'Erro ao atualizar empresa: {str(e)}', 'danger')

    try:
        empresa = supabase.table('empresas').select('*').eq('id', empresa_id).execute().data
        empresa = empresa[0] if empresa else None
        return render_template('empresas/form.html', empresa=empresa, planos=PLANOS)
    except Exception as e:
        flash(f'Erro ao carregar empresa: {str(e)}', 'danger')
        return redirect(url_for('empresas.listar'))


# ── DELETAR (só master, só se tabelas vazias) ──────────────
@bp.route('/deletar/<empresa_id>', methods=['POST'])
@master_required
def deletar(empresa_id):
    try:
        clientes = supabase.table('clientes').select('id').eq('empresa_id', empresa_id).limit(1).execute().data
        veiculos = supabase.table('veiculos').select('id').eq('empresa_id', empresa_id).limit(1).execute().data
        ordens   = supabase.table('ordens_servico').select('id').eq('empresa_id', empresa_id).limit(1).execute().data

        bloqueios = []
        if clientes: bloqueios.append('clientes')
        if veiculos: bloqueios.append('veículos')
        if ordens:   bloqueios.append('ordens de serviço')

        if bloqueios:
            flash(
                f'⚠️ Não é possível excluir esta empresa pois ela possui '
                f'{", ".join(bloqueios)} cadastrados.',
                'warning'
            )
            return redirect(url_for('empresas.listar'))

        supabase.table('configuracoes_empresa').delete().eq('empresa_id', empresa_id).execute()
        supabase.table('usuarios').delete().eq('empresa_id', empresa_id).execute()
        supabase.table('empresas').delete().eq('id', empresa_id).execute()

        flash('Empresa excluída com sucesso.', 'info')

    except Exception as e:
        flash(f'Erro ao excluir empresa: {str(e)}', 'danger')

    return redirect(url_for('empresas.listar'))


# ── CONFIGURAÇÕES DA EMPRESA (DONO) ───────────────────────
@bp.route('/configuracoes', methods=['GET', 'POST'])
@dono_required
def configuracoes():
    empresa_id = get_empresa_id()

    if request.method == 'POST':
        try:
            # Salva configurações visuais
            dados_config = {
                'nome_exibicao':  request.form.get('nome_exibicao', '').strip() or None,
                'cor_primaria':   request.form.get('cor_primaria', '#1e3a8a').strip(),
                'cor_secundaria': request.form.get('cor_secundaria', '#f97316').strip(),
            }
            logo_b64 = request.form.get('logo_b64', '').strip()
            if request.form.get('remover_logo'):
                dados_config['logo_b64'] = None
            elif logo_b64:
                dados_config['logo_b64'] = logo_b64

            existente = supabase.table('configuracoes_empresa') \
                .select('id').eq('empresa_id', empresa_id).execute()
            if existente.data:
                supabase.table('configuracoes_empresa') \
                    .update(dados_config).eq('empresa_id', empresa_id).execute()
            else:
                dados_config['empresa_id'] = empresa_id
                supabase.table('configuracoes_empresa').insert(dados_config).execute()

            # Salva dados editáveis da empresa (cnpj, telefone, email)
            dados_empresa = {
                'cnpj':     request.form.get('cnpj', '').strip() or None,
                'telefone': request.form.get('telefone', '').strip() or None,
                'email':    request.form.get('email', '').strip() or None,
                'endereco':      request.form.get('endereco', '').strip() or None,
            }
            supabase.table('empresas').update(dados_empresa).eq('id', empresa_id).execute()

            flash('Configurações salvas com sucesso!', 'success')
            return redirect(url_for('empresas.configuracoes'))

        except Exception as e:
            flash(f'Erro ao salvar configurações: {str(e)}', 'danger')

    try:
        config  = supabase.table('configuracoes_empresa') \
            .select('*').eq('empresa_id', empresa_id).execute().data
        config  = config[0] if config else {}

        empresa = supabase.table('empresas') \
            .select('nome_fantasia, razao_social, cnpj, email, telefone, plano, endereco') \
            .eq('id', empresa_id).execute().data
        empresa = empresa[0] if empresa else {}

        return render_template('empresas/configuracoes.html', config=config, empresa=empresa)

    except Exception as e:
        flash(f'Erro ao carregar configurações: {str(e)}', 'danger')
        return redirect(url_for('empresas.listar'))


# ── DETALHE (só master) ────────────────────────────────────
@bp.route('/detalhe/<empresa_id>')
@master_required
def detalhe(empresa_id):
    try:
        empresa  = supabase.table('empresas').select('*').eq('id', empresa_id).execute().data
        empresa  = empresa[0] if empresa else None

        usuarios = supabase.table('usuarios') \
            .select('id, nome, email, cargo, ativo') \
            .eq('empresa_id', empresa_id).order('nome').execute().data

        config   = supabase.table('configuracoes_empresa') \
            .select('*').eq('empresa_id', empresa_id).execute().data
        config   = config[0] if config else {}

        stats = {
            'clientes': len(supabase.table('clientes').select('id').eq('empresa_id', empresa_id).execute().data),
            'veiculos': len(supabase.table('veiculos').select('id').eq('empresa_id', empresa_id).execute().data),
            'ordens':   len(supabase.table('ordens_servico').select('id').eq('empresa_id', empresa_id).execute().data),
        }

        return render_template('empresas/detalhe.html',
                               empresa=empresa, usuarios=usuarios,
                               config=config, stats=stats)
    except Exception as e:
        flash(f'Erro ao carregar empresa: {str(e)}', 'danger')
        return redirect(url_for('empresas.listar'))

# ── MASTER TROCAR EMPRESA (só master) ───────────────────────
@bp.route('/master/trocar', methods=['POST'])
@master_required
def master_trocar_empresa():
    empresa_id = request.form.get('empresa_id', '').strip()
    if empresa_id:
        empresa = supabase.table('empresas').select('id, nome_fantasia') \
            .eq('id', empresa_id).execute().data
        if empresa:
            session['user_empresa_id']      = empresa[0]['id']
            session['master_empresa_id']    = empresa[0]['id']
            session['master_empresa_nome']  = empresa[0]['nome_fantasia']
            flash(f'Visualizando empresa: {empresa[0]["nome_fantasia"]}', 'info')
    else:
        # Volta para visão global
        session.pop('user_empresa_id', None)
        session.pop('master_empresa_id', None)
        session.pop('master_empresa_nome', None)
        flash('Voltando para visão global.', 'info')
    return redirect(request.referrer or url_for('index'))