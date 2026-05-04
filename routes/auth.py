from flask import Blueprint, render_template, request, redirect, url_for, flash, session
from database import supabase
import bcrypt

from utils.auth_required import dono_required, filtrar_empresa

bp = Blueprint('auth', __name__)


# ── LOGIN ─────────────────────────────────────────────────
@bp.route('/login', methods=['GET', 'POST'])
def login():
    if 'user_id' in session:
        return redirect(url_for('index'))

    if request.method == 'POST':
        try:
            email = request.form['email'].lower().strip()
            senha = request.form['senha']

            response = supabase.table('usuarios').select('*').eq('email', email).eq('ativo', True).execute()

            if not response.data:
                flash('Email ou senha incorretos', 'danger')
                return render_template('auth/login.html')

            usuario = response.data[0]

            if not usuario.get('senha_hash'):
                flash('Erro na conta. Contate o administrador.', 'danger')
                return render_template('auth/login.html')

            senha_bytes = senha.encode('utf-8')
            hash_bytes  = usuario['senha_hash'].encode('utf-8')

            if bcrypt.checkpw(senha_bytes, hash_bytes):
                session['user_id']         = usuario['id']
                session['user_nome']       = usuario['nome']
                session['user_email']      = usuario['email']
                session['user_cargo']      = usuario['cargo']
                session['user_empresa_id'] = usuario.get('empresa_id')  # None se master

                flash(f'Bem-vindo, {usuario["nome"]}!', 'success')

                if usuario['cargo'] == 'master':
                    return redirect(url_for('admin.index'))

                return redirect(url_for('index'))
            else:
                flash('Email ou senha incorretos', 'danger')

        except Exception as e:
            import traceback
            traceback.print_exc()
            flash('Ocorreu um erro interno. Tente novamente.', 'danger')

    return render_template('auth/login.html')


# ── LOGOUT ────────────────────────────────────────────────
@bp.route('/logout')
def logout():
    session.clear()
    flash('Logout realizado com sucesso!', 'info')
    return redirect(url_for('auth.login'))


# ── LISTAR USUÁRIOS ───────────────────────────────────────
@bp.route('/usuarios')
@dono_required
def listar_usuarios():
    try:
        # DONO vê só da própria empresa, master vê todos
        usuarios = filtrar_empresa(
            supabase.table('usuarios').select('*').order('nome')
        ).execute().data
        return render_template('auth/usuarios.html', usuarios=usuarios)
    except Exception as e:
        import traceback
        traceback.print_exc()
        flash('Ocorreu um erro interno. Tente novamente.', 'danger')
        return render_template('auth/usuarios.html', usuarios=[])


# ── NOVO USUÁRIO ──────────────────────────────────────────
@bp.route('/usuarios/novo', methods=['GET', 'POST'])
@dono_required
def novo_usuario():
    if request.method == 'POST':
        try:
            nome  = request.form['nome']
            email = request.form['email'].lower().strip()
            senha = request.form['senha']
            cargo = request.form['cargo']

            if len(senha) < 6:
                flash('A senha deve ter pelo menos 6 caracteres', 'warning')
                return render_template('auth/form_usuario.html', usuario=None)

            senha_hash = bcrypt.hashpw(senha.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')

            dados = {
                'nome':       nome,
                'email':      email,
                'senha_hash': senha_hash,
                'cargo':      cargo,
                'ativo':      True,
                'empresa_id': session.get('user_empresa_id')  # herda empresa do criador
            }

            supabase.table('usuarios').insert(dados).execute()
            flash('Usuário cadastrado com sucesso!', 'success')
            return redirect(url_for('auth.listar_usuarios'))

        except Exception as e:
            import traceback
            traceback.print_exc()
            flash('Ocorreu um erro interno. Tente novamente.', 'danger')

    return render_template('auth/form_usuario.html', usuario=None)


# ── EDITAR USUÁRIO ────────────────────────────────────────
@bp.route('/usuarios/editar/<usuario_id>', methods=['GET', 'POST'])
@dono_required
def editar_usuario(usuario_id):
    if request.method == 'POST':
        try:
            dados = {
                'nome':  request.form['nome'],
                'email': request.form['email'].lower().strip(),
                'cargo': request.form['cargo']
            }

            nova_senha = request.form.get('nova_senha', '').strip()
            if nova_senha:
                if len(nova_senha) < 6:
                    flash('A senha deve ter pelo menos 6 caracteres', 'warning')
                    return redirect(url_for('auth.editar_usuario', usuario_id=usuario_id))
                dados['senha_hash'] = bcrypt.hashpw(
                    nova_senha.encode('utf-8'), bcrypt.gensalt()
                ).decode('utf-8')

            supabase.table('usuarios').update(dados).eq('id', usuario_id).execute()
            flash('Usuário atualizado com sucesso!', 'success')
            return redirect(url_for('auth.listar_usuarios'))

        except Exception as e:
            import traceback
            traceback.print_exc()
            flash('Ocorreu um erro interno. Tente novamente.', 'danger')

    try:
        response = supabase.table('usuarios').select('*').eq('id', usuario_id).execute()
        usuario  = response.data[0] if response.data else None
        return render_template('auth/form_usuario.html', usuario=usuario)
    except Exception as e:
        import traceback
        traceback.print_exc()
        flash('Ocorreu um erro interno. Tente novamente.', 'danger')
        return redirect(url_for('auth.listar_usuarios'))


# ── INATIVAR USUÁRIO ──────────────────────────────────────
@bp.route('/usuarios/inativar/<usuario_id>', methods=['POST'])
@dono_required
def inativar_usuario(usuario_id):
    if usuario_id == session.get('user_id'):
        flash('Você não pode inativar seu próprio usuário!', 'warning')
        return redirect(url_for('auth.listar_usuarios'))

    try:
        supabase.table('usuarios').update({'ativo': False}).eq('id', usuario_id).execute()
        flash('Usuário inativado com sucesso!', 'info')
    except Exception as e:
        import traceback
        traceback.print_exc()
        flash('Ocorreu um erro interno. Tente novamente.', 'danger')

    return redirect(url_for('auth.listar_usuarios'))


# ── ATIVAR USUÁRIO ────────────────────────────────────────
@bp.route('/usuarios/ativar/<usuario_id>', methods=['POST'])
@dono_required
def ativar_usuario(usuario_id):
    try:
        supabase.table('usuarios').update({'ativo': True}).eq('id', usuario_id).execute()
        flash('Usuário reativado com sucesso!', 'success')
    except Exception as e:
        import traceback
        traceback.print_exc()
        flash('Ocorreu um erro interno. Tente novamente.', 'danger')

    return redirect(url_for('auth.listar_usuarios'))
