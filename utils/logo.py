import base64
import os

def get_logo_base64():
    # Monta o caminho e mostra no terminal
    logo_path = os.path.join(os.path.dirname(__file__), '..', 'static', 'img', 'logo.png')
    logo_path = os.path.abspath(logo_path)  # caminho absoluto pra não ter dúvida
    
    print(f"[LOGO] Procurando em: {logo_path}")
    print(f"[LOGO] Arquivo existe: {os.path.exists(logo_path)}")
    
    try:
        with open(logo_path, 'rb') as f:
            dados = f.read()
        
        print(f"[LOGO] Arquivo lido com sucesso! Tamanho: {len(dados)} bytes")
        
        b64 = base64.b64encode(dados).decode('utf-8')
        
        print(f"[LOGO] Base64 gerado! Primeiros 50 chars: {b64[:50]}")
        
        return f"data:image/png;base64,{b64}"
    
    except FileNotFoundError:
        print(f"[LOGO] ❌ ARQUIVO NÃO ENCONTRADO: {logo_path}")
        return None
    except Exception as e:
        print(f"[LOGO] ❌ ERRO INESPERADO: {repr(e)}")
        return None