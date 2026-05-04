from flask import Blueprint, render_template, request, redirect, url_for, flash
from database import supabase
from utils.auth_required import login_required, filtrar_empresa, get_empresa_id

bp = Blueprint('estoque', __name__, url_prefix='/estoque')


@bp.route('/')
@login_required
def listar():
    try:
        categoria = request.args.get('categoria', '')

        query = filtrar_empresa(supabase.table('estoque').select('*').order('nome'))
        if categoria:
            query = query.eq('categoria', categoria)

        itens = query.execute().data

        stats = {
            'total_itens':  len(itens),
            'estoque_baixo': len([i for i in itens if i['quantidade'] <= i['minimo_alerta']]),
            'valor_total':  sum([i['quantidade'] * i['custo'] for i in itens])
        }

        return render_template('estoque/listar.html', itens=itens, stats=stats, categoria_filtro=categoria)
    except Exception as e:
        flash(f'Erro ao carregar estoque: {str(e)}', 'danger')
        return render_template('estoque/listar.html', itens=[], stats={})


@bp.route('/novo', methods=['GET', 'POST'])
@login_required
def novo():
    if request.method == 'POST':
        try:
            dados = {
                'nome':          request.form['nome'].strip(),
                'categoria':     request.form['categoria'],
                'quantidade':    int(request.form.get('quantidade', 0)),
                'custo':         float(request.form.get('custo', 0)),
                'venda':         float(request.form.get('venda', 0)),
                'minimo_alerta': int(request.form.get('minimo_alerta', 5)),
                'codigo':        request.form.get('codigo', '').strip(),
                'empresa_id':    get_empresa_id()
            }

            # Duplicado somente dentro da mesma empresa
            duplicado = filtrar_empresa(
                supabase.table('estoque').select('id')
                    .eq('nome', dados['nome'])
                    .eq('categoria', dados['categoria'])
            ).execute()

            if duplicado.data:
                flash(f'Item "{dados["nome"]}" já existe na categoria {dados["categoria"]}!', 'warning')
                return redirect(url_for('estoque.listar'))

            supabase.table('estoque').insert(dados).execute()
            flash('Item cadastrado com sucesso!', 'success')
            return redirect(url_for('estoque.listar'))

        except Exception as e:
            flash(f'Erro ao cadastrar: {str(e)}', 'danger')

    return render_template('estoque/form.html', item=None)


@bp.route('/editar/<item_id>', methods=['GET', 'POST'])
@login_required
def editar(item_id):
    if request.method == 'POST':
        try:
            dados = {
                'nome':          request.form['nome'],
                'categoria':     request.form['categoria'],
                'quantidade':    int(request.form.get('quantidade', 0)),
                'custo':         float(request.form.get('custo', 0)),
                'venda':         float(request.form.get('venda', 0)),
                'minimo_alerta': int(request.form.get('minimo_alerta', 5)),
                'codigo':        request.form.get('codigo', '')
            }
            supabase.table('estoque').update(dados).eq('id', item_id).execute()
            flash('Item atualizado com sucesso!', 'success')
            return redirect(url_for('estoque.listar'))

        except Exception as e:
            flash(f'Erro ao atualizar item: {str(e)}', 'danger')

    try:
        response = supabase.table('estoque').select('*').eq('id', item_id).execute()
        item = response.data[0] if response.data else None
        return render_template('estoque/form.html', item=item)
    except Exception as e:
        flash(f'Erro ao carregar item: {str(e)}', 'danger')
        return redirect(url_for('estoque.listar'))


@bp.route('/deletar/<item_id>', methods=['POST'])
@login_required
def deletar(item_id):
    try:
        itens_os = supabase.table('os_itens').select('id').eq('estoque_id', item_id).execute().data

        if itens_os:
            flash(
                f'📦 Este item não pode ser removido pois está vinculado a {len(itens_os)} '
                f'ordem(ns) de serviço. Remova-o das OS ou mantenha-o com quantidade zero.',
                'warning'
            )
            return redirect(url_for('estoque.listar'))

        supabase.table('estoque').delete().eq('id', item_id).execute()
        flash('Item deletado com sucesso!', 'success')

    except Exception as e:
        flash(f'Erro ao deletar item: {str(e)}', 'danger')

    return redirect(url_for('estoque.listar'))


@bp.route('/ajustar/<item_id>', methods=['POST'])
@login_required
def ajustar(item_id):
    try:
        tipo              = request.form['tipo']
        quantidade_ajuste = int(request.form['quantidade'])

        response          = supabase.table('estoque').select('quantidade').eq('id', item_id).execute()
        quantidade_atual  = response.data[0]['quantidade']

        if tipo == 'entrada':
            nova_quantidade = quantidade_atual + quantidade_ajuste
        else:
            nova_quantidade = max(0, quantidade_atual - quantidade_ajuste)

        supabase.table('estoque').update({'quantidade': nova_quantidade}).eq('id', item_id).execute()
        flash(f'Estoque ajustado! {"+" if tipo == "entrada" else "-"}{quantidade_ajuste} unidades', 'success')

    except Exception as e:
        flash(f'Erro ao ajustar estoque: {str(e)}', 'danger')

    return redirect(url_for('estoque.listar'))
