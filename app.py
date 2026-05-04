from flask import Flask, render_template, session, redirect, url_for, request
import os
from dotenv import load_dotenv
from database import supabase
from datetime import datetime, timedelta
from utils.auth_required import login_required, pode_ver_financeiro, filtrar_empresa, get_empresa_id
from utils.logo import get_logo_base64
from routes import clientes, veiculos, estoque, os as os_routes, auth, logs, empresas, admin

load_dotenv()

app = Flask(__name__)
secret = os.getenv('SECRET_KEY')
if not secret:
    raise RuntimeError("SECRET_KEY não definida no ambiente!")
app.secret_key = secret

# ── Blueprints ─────────────────────────────────────────────
app.register_blueprint(clientes.bp)
app.register_blueprint(veiculos.bp)
app.register_blueprint(estoque.bp)
app.register_blueprint(os_routes.bp)
app.register_blueprint(auth.bp)
app.register_blueprint(logs.bp)
app.register_blueprint(empresas.bp)
app.register_blueprint(admin.bp)


# ── Middleware de autenticação ─────────────────────────────
@app.before_request
def verificar_login():
    rotas_publicas = ['auth.login', 'static']
    if 'user_id' not in session and request.endpoint not in rotas_publicas:
        return redirect(url_for('auth.login'))


# ── Context processors ─────────────────────────────────────
LOGO_B64 = get_logo_base64()

@app.context_processor
def inject_globals():
    from utils.auth_required import get_cargo, get_empresa_id
    empresa_config  = None
    master_empresas = []
    empresa_id      = get_empresa_id()

    if empresa_id:
        res = supabase.table('configuracoes_empresa') \
            .select('*').eq('empresa_id', empresa_id).execute()
        if res.data:
            empresa_config = res.data[0]
            # Se não tem logo no banco, usa a logo do arquivo físico
            if not empresa_config.get('logo_b64') and LOGO_B64:
                empresa_config['logo_b64'] = LOGO_B64

    if session.get('user_cargo') == 'master':
        master_empresas = supabase.table('empresas') \
            .select('id, nome_fantasia, ativo') \
            .order('nome_fantasia').execute().data

    return {
        'logo_b64':       LOGO_B64,
        'empresa_config': empresa_config,
        'user_cargo':     session.get('user_cargo', ''),
        'user_nome':      session.get('user_nome', ''),
        'master_empresas': master_empresas,
    }

# ── Helpers de sessão ─────────────────────────────────────
@app.errorhandler(401)
def unauthorized(e):
    session.clear()
    return redirect(url_for('auth.login'))


# ── Dashboard ──────────────────────────────────────────────
@app.route('/')
@login_required
def index():
    hoje       = datetime.now()
    inicio_mes = hoje.replace(day=1).isoformat()

    # OS do mês filtradas por empresa
    os_mes = filtrar_empresa(
        supabase.table('ordens_servico').select('*').gte('data_abertura', inicio_mes)
    ).execute().data

    status_counts = {
        'ORCAMENTO': 0, 'AGUARDANDO_PECA': 0,
        'EXECUCAO':  0, 'FINALIZADO': 0, 'PAGO': 0
    }
    faturamento_mes = 0
    lucro_mes       = 0

    for os_ in os_mes:
        st = os_.get('status') or 'ORCAMENTO'
        if st in status_counts:
            status_counts[st] += 1
        faturamento_mes += float(os_.get('total_geral')     or 0)
        lucro_mes       += float(os_.get('lucro_estimado')  or 0)

    total_abertas = (
        status_counts['ORCAMENTO'] +
        status_counts['AGUARDANDO_PECA'] +
        status_counts['EXECUCAO']
    )

    # Estoque crítico filtrado por empresa
    estoque_todos = filtrar_empresa(
        supabase.table('estoque').select('id, nome, quantidade, minimo_alerta, categoria')
    ).execute().data
    itens_criticos = [i for i in estoque_todos if i['quantidade'] <= i['minimo_alerta']]

    # Últimas 5 OS filtradas por empresa
    ultimas_os = filtrar_empresa(
        supabase.table('ordens_servico').select('''
            *,
            clientes(nome, telefone),
            veiculos(placa, modelo)
        ''').order('data_abertura', desc=True).limit(5)
    ).execute().data

    # Faturamento últimos 6 meses (só DONO/master)
    meses_labels  = []
    meses_valores = []

    if pode_ver_financeiro():
        for i in range(5, -1, -1):
            ref        = hoje.replace(day=1) - timedelta(days=30 * i)
            mes_inicio = ref.replace(day=1)
            if ref.month == 12:
                mes_fim = ref.replace(day=31)
            else:
                mes_fim = (mes_inicio.replace(month=mes_inicio.month % 12 + 1, day=1) - timedelta(days=1))

            os_ref = filtrar_empresa(
                supabase.table('ordens_servico')
                    .select('total_geral, data_abertura')
                    .gte('data_abertura', mes_inicio.isoformat())
                    .lte('data_abertura', mes_fim.isoformat())
            ).execute().data

            meses_labels.append(f'{mes_inicio.month:02d}/{mes_inicio.year}')
            meses_valores.append(round(sum(float(o.get('total_geral') or 0) for o in os_ref), 2))

    stats = {
        'total_abertas':        total_abertas,
        'status_counts':        status_counts,
        'faturamento_mes':      faturamento_mes if pode_ver_financeiro() else 0,
        'lucro_mes':            lucro_mes       if pode_ver_financeiro() else 0,
        'estoque_critico_count': len(itens_criticos)
    }

    return render_template(
        'index.html',
        stats=stats,
        ultimas_os=ultimas_os,
        meses_labels=meses_labels,
        meses_valores=meses_valores,
        itens_criticos=itens_criticos,
        pode_ver_financeiro=pode_ver_financeiro()
    )


if __name__ == '__main__':
    app.run(debug=False)
