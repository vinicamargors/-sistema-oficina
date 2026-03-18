from functools import wraps
from flask import session, redirect, url_for, flash


def login_required(f):
    """Decorator para proteger rotas que precisam de login"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session:
            flash('Faça login para acessar esta página', 'warning')
            return redirect(url_for('auth.login'))
        return f(*args, **kwargs)
    return decorated_function


def dono_required(f):
    """Decorator para rotas exclusivas do DONO"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session:
            flash('Faça login para acessar esta página', 'warning')
            return redirect(url_for('auth.login'))
        
        if session.get('user_cargo') != 'DONO':
            flash('⚠️ Acesso negado. Esta área é exclusiva para o dono.', 'danger')
            return redirect(url_for('index'))
        
        return f(*args, **kwargs)
    return decorated_function


def pode_ver_financeiro():
    """Verifica se o usuário pode ver dados financeiros"""
    return session.get('user_cargo') == 'DONO'


def pode_gerenciar_usuarios():
    """Verifica se o usuário pode gerenciar usuários"""
    return session.get('user_cargo') == 'DONO'
