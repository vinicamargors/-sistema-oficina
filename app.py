from flask import Flask, render_template, session, redirect, url_for
import os
from dotenv import load_dotenv
from database import supabase
from datetime import datetime, timedelta
from utils.auth_required import login_required, pode_ver_financeiro

load_dotenv()

app = Flask(__name__)
app.secret_key = os.getenv('SECRET_KEY')

# Importar e registrar Blueprints
from routes import clientes, veiculos, estoque, os as os_routes, auth

app.register_blueprint(clientes.bp)
app.register_blueprint(veiculos.bp)
app.register_blueprint(estoque.bp)
app.register_blueprint(os_routes.bp)
app.register_blueprint(auth.bp)


# Middleware: Verificar login antes de cada requisição
@app.before_request
def verificar_login():
    """Proteger rotas (exceto login e estáticos)"""
    from flask import request
    
    # Rotas públicas (não precisam login)
    rotas_publicas = ['auth.login', 'static']
    
    # Se não está logado e não é rota pública
    if 'user_id' not in session and request.endpoint not in rotas_publicas:
        return redirect(url_for('auth.login'))


@app.route('/')
@login_required
def index():
    """Dashboard principal"""
    hoje = datetime.now()
    inicio_mes = hoje.replace(day=1)
    
    # Converter para string ISO sem timezone, compatível com Supabase
    inicio_mes_str = inicio_mes.isoformat()
    
    # 1) Buscar OS do mês atual
    os_mes = supabase.table('ordens_servico').select('*').gte('data_abertura', inicio_mes_str).execute().data
    
    # 2) Contar por status
    status_counts = {
        'ORCAMENTO': 0,
        'AGUARDANDO_PECA': 0,
        'EXECUCAO': 0,
        'FINALIZADO': 0,
        'PAGO': 0
    }
    faturamento_mes = 0
    lucro_mes = 0
    
    for os_ in os_mes:
        st = os_.get('status') or 'ORCAMENTO'
        if st in status_counts:
            status_counts[st] += 1
        faturamento_mes += float(os_.get('total_geral') or 0)
        lucro_mes += float(os_.get('lucro_estimado') or 0)
    
    total_abertas = status_counts['ORCAMENTO'] + status_counts['AGUARDANDO_PECA'] + status_counts['EXECUCAO']
    
    # 3) Estoque crítico
    estoque_critico = supabase.table('estoque').select('id, nome, quantidade, minimo_alerta, categoria').execute().data
    itens_criticos = [item for item in estoque_critico if item['quantidade'] <= item['minimo_alerta']]
    
    # 4) Últimas 5 OS
    ultimas_os = supabase.table('ordens_servico').select('''
            *,
            clientes(nome, telefone),
            veiculos(placa, modelo)
        ''').order('data_abertura', desc=True).limit(5).execute().data
    
    # 5) Faturamento últimos 6 meses (só para DONO)
    meses_labels = []
    meses_valores = []
    
    if pode_ver_financeiro():
        for i in range(5, -1, -1):
            ref = hoje.replace(day=1) - timedelta(days=30*i)
            mes_inicio = ref.replace(day=1)
            if ref.month == 12:
                mes_fim = ref.replace(day=31)
            else:
                mes_fim = (mes_inicio.replace(month=mes_inicio.month % 12 + 1, day=1) - timedelta(days=1))
            
            mes_inicio_str = mes_inicio.isoformat()
            mes_fim_str = mes_fim.isoformat()
            
            os_mes_ref = supabase.table('ordens_servico').select('total_geral, data_abertura').gte('data_abertura', mes_inicio_str).lte('data_abertura', mes_fim_str).execute().data
            soma_mes = sum(float(o.get('total_geral') or 0) for o in os_mes_ref)
            
            label = f'{mes_inicio.month:02d}/{mes_inicio.year}'
            meses_labels.append(label)
            meses_valores.append(round(soma_mes, 2))
    
    stats = {
        'total_abertas': total_abertas,
        'status_counts': status_counts,
        'faturamento_mes': faturamento_mes if pode_ver_financeiro() else 0,
        'lucro_mes': lucro_mes if pode_ver_financeiro() else 0,
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
    app.run(debug=True)
