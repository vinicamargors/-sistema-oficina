from flask import Blueprint, render_template, request, Response
from database import supabase
from datetime import datetime
from utils.auth_required import login_required, dono_required, filtrar_empresa

bp = Blueprint('logs', __name__, url_prefix='/logs')


@bp.route('/')
@dono_required
def listar():
    tabela   = request.args.get('tabela', '')
    operacao = request.args.get('operacao', '')
    data_ini = request.args.get('data_ini', '')
    data_fim = request.args.get('data_fim', '')

    query = filtrar_empresa(
        supabase.table('audit_logs').select('*').order('criado_em', desc=True).limit(500)
    )

    if tabela:   query = query.eq('tabela', tabela)
    if operacao: query = query.eq('operacao', operacao)
    if data_ini: query = query.gte('criado_em', data_ini)
    if data_fim: query = query.lte('criado_em', data_fim + 'T23:59:59')

    logs = query.execute().data
    return render_template('logs/listar.html', logs=logs)


@bp.route('/exportar')
@dono_required
def exportar():
    data_ini = request.args.get('data_ini', '')
    data_fim = request.args.get('data_fim', '')

    query = filtrar_empresa(
        supabase.table('audit_logs').select('*').order('criado_em', desc=True)
    )
    if data_ini: query = query.gte('criado_em', data_ini)
    if data_fim: query = query.lte('criado_em', data_fim + 'T23:59:59')

    logs = query.execute().data

    linhas = [f"=== LOG DE AUDITORIA — {datetime.now().strftime('%d/%m/%Y %H:%M')} ===\n"]
    for log in logs:
        dt = log['criado_em'][:19].replace('T', ' ')
        linhas.append(
            f"[{dt}] {log['operacao']:6} | Tabela: {log['tabela']:20} | ID: {log.get('registro_id', '')}"
        )
        if log['operacao'] == 'DELETE' and log.get('dados_antes'):
            motivo = log['dados_antes'].get('motivo_exclusao', '')
            if motivo:
                linhas.append(f"         Motivo: {motivo}")
        linhas.append('')

    txt  = '\n'.join(linhas)
    nome = f"log_{datetime.now().strftime('%Y%m%d_%H%M')}.txt"

    return Response(txt, mimetype='text/plain',
                    headers={'Content-Disposition': f'attachment; filename={nome}'})
