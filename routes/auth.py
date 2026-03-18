from flask import Blueprint, render_template, request, redirect, url_for, flash, session
from database import supabase
import bcrypt

from utils.auth_required import dono_required

bp = Blueprint('auth', __name__)


@bp.route('/login', methods=['GET', 'POST'])
def login():
    """Tela de login"""
    # Se já está logado, redirecionar
    if 'user_id' in session:
        return redirect(url_for('index'))
    
    if request.method == 'POST':
        try:
            email = request.form['email'].lower().strip()
            senha = request.form['senha']
            
            # Buscar usuário
            response = supabase.table('usuarios').select('*').eq('email', email).eq('ativo', True).execute()
            
            if not response.data:
                flash('Email ou senha incorretos', 'danger')
                return render_template('auth/login.html')
            
            usuario = response.data[0]
            
            # Verificar senha (usando senha_hash)
            senha_hash = usuario['senha_hash'].encode('utf-8')
            if bcrypt.checkpw(senha.encode('utf-8'), senha_hash):
                # Login bem-sucedido
                session['user_id'] = usuario['id']
                session['user_nome'] = usuario['nome']
                session['user_email'] = usuario['email']
                session['user_cargo'] = usuario['cargo']
                
                flash(f'Bem-vindo, {usuario["nome"]}!', 'success')
                return redirect(url_for('index'))
            else:
                flash('Email ou senha incorretos', 'danger')
                
        except Exception as e:
            flash(f'Erro ao fazer login: {str(e)}', 'danger')
    
    return render_template('auth/login.html')


@bp.route('/logout')
def logout():
    """Fazer logout"""
    session.clear()
    flash('Logout realizado com sucesso!', 'info')
    return redirect(url_for('auth.login'))


@bp.route('/usuarios')
@dono_required
def listar_usuarios():
    """Listar usuários (apenas DONO)"""
    # Verificar se está logado e é DONO
    if 'user_id' not in session:
        flash('Faça login para acessar', 'warning')
        return redirect(url_for('auth.login'))
    
    if session.get('user_cargo') != 'DONO':
        flash('Acesso negado. Apenas o dono pode gerenciar usuários.', 'danger')
        return redirect(url_for('index'))
    
    try:
        response = supabase.table('usuarios').select('*').order('nome').execute()
        usuarios = response.data
        return render_template('auth/usuarios.html', usuarios=usuarios)
    except Exception as e:
        flash(f'Erro ao carregar usuários: {str(e)}', 'danger')
        return render_template('auth/usuarios.html', usuarios=[])


@bp.route('/usuarios/novo', methods=['GET', 'POST'])
@dono_required
def novo_usuario():
    """Cadastrar novo usuário (apenas DONO)"""
    # Verificar se está logado e é DONO
    if 'user_id' not in session:
        flash('Faça login para acessar', 'warning')
        return redirect(url_for('auth.login'))
    
    if session.get('user_cargo') != 'DONO':
        flash('Acesso negado', 'danger')
        return redirect(url_for('index'))
    
    if request.method == 'POST':
        try:
            nome = request.form['nome']
            email = request.form['email'].lower().strip()
            senha = request.form['senha']
            cargo = request.form['cargo']
            
            # Validar
            if len(senha) < 6:
                flash('A senha deve ter pelo menos 6 caracteres', 'warning')
                return render_template('auth/form_usuario.html', usuario=None)
            
            # Hash da senha
            senha_hash = bcrypt.hashpw(senha.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')
            
            # Inserir (usando senha_hash)
            dados = {
                'nome': nome,
                'email': email,
                'senha_hash': senha_hash,
                'cargo': cargo,
                'ativo': True
            }
            
            supabase.table('usuarios').insert(dados).execute()
            flash('Usuário cadastrado com sucesso!', 'success')
            return redirect(url_for('auth.listar_usuarios'))
            
        except Exception as e:
            flash(f'Erro ao cadastrar usuário: {str(e)}', 'danger')
    
    return render_template('auth/form_usuario.html', usuario=None)


@bp.route('/usuarios/editar/<usuario_id>', methods=['GET', 'POST'])
@dono_required
def editar_usuario(usuario_id):
    """Editar usuário"""
    if 'user_id' not in session or session.get('user_cargo') != 'DONO':
        flash('Acesso negado', 'danger')
        return redirect(url_for('index'))
    
    if request.method == 'POST':
        try:
            dados = {
                'nome': request.form['nome'],
                'email': request.form['email'].lower().strip(),
                'cargo': request.form['cargo']
            }
            
            # Se informou nova senha
            nova_senha = request.form.get('nova_senha', '').strip()
            if nova_senha:
                if len(nova_senha) < 6:
                    flash('A senha deve ter pelo menos 6 caracteres', 'warning')
                    return redirect(url_for('auth.editar_usuario', usuario_id=usuario_id))
                
                senha_hash = bcrypt.hashpw(nova_senha.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')
                dados['senha_hash'] = senha_hash
            
            supabase.table('usuarios').update(dados).eq('id', usuario_id).execute()
            flash('Usuário atualizado com sucesso!', 'success')
            return redirect(url_for('auth.listar_usuarios'))
            
        except Exception as e:
            flash(f'Erro ao atualizar usuário: {str(e)}', 'danger')
    
    # GET
    try:
        response = supabase.table('usuarios').select('*').eq('id', usuario_id).execute()
        usuario = response.data[0] if response.data else None
        return render_template('auth/form_usuario.html', usuario=usuario)
    except Exception as e:
        flash(f'Erro ao carregar usuário: {str(e)}', 'danger')
        return redirect(url_for('auth.listar_usuarios'))


@bp.route('/usuarios/inativar/<usuario_id>', methods=['POST'])
@dono_required
def inativar_usuario(usuario_id):
    """Inativar usuário"""
    if 'user_id' not in session or session.get('user_cargo') != 'DONO':
        flash('Acesso negado', 'danger')
        return redirect(url_for('index'))
    
    # Não pode inativar a si mesmo
    if usuario_id == session.get('user_id'):
        flash('Você não pode inativar seu próprio usuário!', 'warning')
        return redirect(url_for('auth.listar_usuarios'))
    
    try:
        supabase.table('usuarios').update({'ativo': False}).eq('id', usuario_id).execute()
        flash('Usuário inativado com sucesso!', 'info')
    except Exception as e:
        flash(f'Erro ao inativar usuário: {str(e)}', 'danger')
    
    return redirect(url_for('auth.listar_usuarios'))


@bp.route('/usuarios/ativar/<usuario_id>', methods=['POST'])
@dono_required
def ativar_usuario(usuario_id):
    """Reativar usuário"""
    if 'user_id' not in session or session.get('user_cargo') != 'DONO':
        flash('Acesso negado', 'danger')
        return redirect(url_for('index'))
    
    try:
        supabase.table('usuarios').update({'ativo': True}).eq('id', usuario_id).execute()
        flash('Usuário reativado com sucesso!', 'success')
    except Exception as e:
        flash(f'Erro ao reativar usuário: {str(e)}', 'danger')
    
    return redirect(url_for('auth.listar_usuarios'))
