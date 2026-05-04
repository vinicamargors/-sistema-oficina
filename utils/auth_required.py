from functools import wraps
import uuid
from flask import abort, session, jsonify, redirect, url_for


# ── Helpers de sessão ─────────────────────────────────────

def get_cargo() -> str:
    return session.get('user_cargo', '')


def get_empresa_id():
    """
    - master sem empresa selecionada → None (vê tudo)
    - master COM empresa selecionada → master_empresa_id
    - DONO / MECANICO / RECEPCAO    → user_empresa_id (fixo no login)
    """
    if get_cargo() == 'master':
        return session.get('master_empresa_id')  # None = visão global
    return session.get('user_empresa_id')


def filtrar_empresa(query):
    empresa_id = get_empresa_id()
    cargo      = get_cargo()

    if empresa_id:
        # Valida se é UUID antes de mandar pro Supabase
        try:
            uuid.UUID(str(empresa_id))
        except (ValueError, AttributeError):
            # Sessão corrompida — aborta com 401 em vez de 500
            abort(401)
        return query.eq('empresa_id', empresa_id)

    # Master sem empresa selecionada → visão global, sem filtro
    if cargo == 'master':
        return query

    # DONO/MECANICO/RECEPCAO sem empresa_id → sessão inválida, aborta
    abort(401)


# ── Decorators de rota ────────────────────────────────────

def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session:
            return redirect(url_for('auth.login'))
        return f(*args, **kwargs)
    return decorated_function


def dono_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session:
            return redirect(url_for('auth.login'))
        if get_cargo() not in ('DONO', 'master'):
            return jsonify({'error': 'Acesso negado. Área exclusiva para o dono.'}), 403
        return f(*args, **kwargs)
    return decorated_function


def master_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session:
            return redirect(url_for('auth.login'))
        if get_cargo() != 'master':
            return redirect(url_for('index'))  # era 'dashboard.index' — blueprint inexistente
        return f(*args, **kwargs)
    return decorated_function


# ── Verificações de permissão ─────────────────────────────

def pode_ver_financeiro() -> bool:
    return get_cargo() in ('DONO', 'master')

def pode_gerenciar_usuarios() -> bool:
    return get_cargo() in ('DONO', 'master')

def is_master() -> bool:
    return get_cargo() == 'master'

