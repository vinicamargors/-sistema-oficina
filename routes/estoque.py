from flask import Blueprint, render_template, request, redirect, url_for, flash
from database import supabase

bp = Blueprint('estoque', __name__, url_prefix='/estoque')


@bp.route('/')
def listar():
    """Lista todos os itens do estoque"""
    try:
        categoria = request.args.get('categoria', '')
        
        if categoria:
            response = supabase.table('estoque').select('*').eq('categoria', categoria).order('nome').execute()
        else:
            response = supabase.table('estoque').select('*').order('nome').execute()
        
        itens = response.data
        
        # Estatísticas
        total_itens = len(itens)
        estoque_baixo = len([i for i in itens if i['quantidade'] <= i['minimo_alerta']])
        valor_total = sum([i['quantidade'] * i['custo'] for i in itens])
        
        stats = {
            'total_itens': total_itens,
            'estoque_baixo': estoque_baixo,
            'valor_total': valor_total
        }
        
        return render_template('estoque/listar.html', itens=itens, stats=stats, categoria_filtro=categoria)
    except Exception as e:
        flash(f'Erro ao carregar estoque: {str(e)}', 'danger')
        return render_template('estoque/listar.html', itens=[], stats={})


@bp.route('/novo', methods=['GET', 'POST'])
def novo():
    """Cadastrar novo item no estoque"""
    if request.method == 'POST':
        try:
            dados = {
                'nome': request.form['nome'],
                'categoria': request.form['categoria'],
                'quantidade': int(request.form.get('quantidade', 0)),
                'custo': float(request.form.get('custo', 0)),
                'venda': float(request.form.get('venda', 0)),
                'minimo_alerta': int(request.form.get('minimo_alerta', 5)),
                'codigo': request.form.get('codigo', '')
            }
            
            supabase.table('estoque').insert(dados).execute()
            flash('Item cadastrado com sucesso!', 'success')
            return redirect(url_for('estoque.listar'))
            
        except Exception as e:
            flash(f'Erro ao cadastrar item: {str(e)}', 'danger')
    
    return render_template('estoque/form.html', item=None)


@bp.route('/editar/<item_id>', methods=['GET', 'POST'])
def editar(item_id):
    """Editar item do estoque"""
    if request.method == 'POST':
        try:
            dados = {
                'nome': request.form['nome'],
                'categoria': request.form['categoria'],
                'quantidade': int(request.form.get('quantidade', 0)),
                'custo': float(request.form.get('custo', 0)),
                'venda': float(request.form.get('venda', 0)),
                'minimo_alerta': int(request.form.get('minimo_alerta', 5)),
                'codigo': request.form.get('codigo', '')
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
def deletar(item_id):
    """Deletar item do estoque"""
    try:
        # Verificar se o item está sendo usado em alguma OS
        itens_os = supabase.table('os_itens').select('id').eq('estoque_id', item_id).execute().data
        
        if len(itens_os) > 0:
            flash(f'⚠️ Não é possível deletar este item! Ele está vinculado a {len(itens_os)} ordem(ns) de serviço. Para removê-lo do sistema, primeiro remova-o das OS ou mantenha-o com quantidade zero.', 'warning')
            return redirect(url_for('estoque.listar'))
        
        # Se não está em uso, pode deletar
        supabase.table('estoque').delete().eq('id', item_id).execute()
        flash('Item deletado com sucesso!', 'success')
        
    except Exception as e:
        flash(f'Erro ao deletar item: {str(e)}', 'danger')
    
    return redirect(url_for('estoque.listar'))


@bp.route('/ajustar/<item_id>', methods=['POST'])
def ajustar(item_id):
    """Ajustar quantidade do estoque"""
    try:
        tipo = request.form['tipo']
        quantidade_ajuste = int(request.form['quantidade'])
        
        response = supabase.table('estoque').select('quantidade').eq('id', item_id).execute()
        quantidade_atual = response.data[0]['quantidade']
        
        if tipo == 'entrada':
            nova_quantidade = quantidade_atual + quantidade_ajuste
        else:
            nova_quantidade = max(0, quantidade_atual - quantidade_ajuste)
        
        supabase.table('estoque').update({'quantidade': nova_quantidade}).eq('id', item_id).execute()
        
        flash(f'Estoque ajustado! {"+" if tipo == "entrada" else "-"}{quantidade_ajuste} unidades', 'success')
    except Exception as e:
        flash(f'Erro ao ajustar estoque: {str(e)}', 'danger')
    
    return redirect(url_for('estoque.listar'))
