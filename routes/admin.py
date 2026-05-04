from flask import Blueprint, render_template, redirect, url_for
from utils.auth_required import master_required

bp = Blueprint('admin', __name__, url_prefix='/admin')

@bp.route('/')
@master_required
def index():
    return redirect(url_for('empresas.listar'))  # redireciona pro painel de empresas