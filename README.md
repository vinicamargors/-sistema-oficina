# Sistema de Gestão de Oficina Mecânica

Aplicação web para gerenciamento completo de oficinas mecânicas, desenvolvida com Python/Flask e banco de dados Supabase.

## Funcionalidades

- Cadastro e gestão de clientes e veículos
- Ordens de Serviço com visualização Kanban e drag & drop
- Controle de estoque com alertas de reposição
- Dashboard com indicadores financeiros e operacionais
- Sistema de login com 3 níveis de acesso (Dono, Mecânico, Recepção)
- Impressão de OS em PDF
- Interface responsiva (desktop e mobile)

## Tecnologias

- **Backend:** Python 3.11+ / Flask
- **Banco de dados:** Supabase (PostgreSQL)
- **Frontend:** HTML5, Bootstrap 5, Chart.js, JavaScript

---

## Pré-requisitos

- Python 3.11 ou superior
- Conta no [Supabase](https://supabase.com) (gratuita)
- Git

---

## Instalação e Execução Local

### 1. Clonar o repositório

```bash
git clone https://github.com/seu-usuario/sistema-oficina.git
cd sistema-oficina
```

### 2. Criar ambiente virtual
#### Windows
```bash
python -m venv venv
venv\Scripts\activate
```
#### Linux/macOS
```bash
python3 -m venv venv
source venv/bin/activate
```

### 3. Criar dependência
```bash
pip install -r requirements.txt
```

### 4. Configurar variáveis de ambiente
Crie um arquivo .env na raiz do projeto com base no .env.example:
```text
SUPABASE_URL=https://xxxxxxxxxxx.supabase.co
SUPABASE_KEY=sua_chave_anon_aqui
SECRET_KEY=uma_chave_secreta_longa_aqui
```
> *Para obter as credenciais do Supabase: acesse o projeto > Settings > API*

### 5. Configurar o banco de dados
Execute os scripts SQL abaixo no SQL Editor do Supabase, na ordem indicada:

##### Tabela: veiculos
```sql
CREATE TABLE veiculos (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    cliente_id UUID REFERENCES clientes(id),
    placa VARCHAR(10) NOT NULL,
    modelo VARCHAR(50),
    marca VARCHAR(50),
    ano INTEGER,
    cor VARCHAR(30),
    km_atual INTEGER,
    criado_em TIMESTAMP DEFAULT NOW()
);
```

##### Tabela: clientes
```sql
CREATE TABLE clientes (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    nome VARCHAR(100) NOT NULL,
    telefone VARCHAR(20),
    cpf_cnpj VARCHAR(20),
    endereco TEXT,
    criado_em TIMESTAMP DEFAULT NOW()
);
```

##### Tabela: clientes
```sql
CREATE TABLE clientes (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    nome VARCHAR(100) NOT NULL,
    telefone VARCHAR(20),
    cpf_cnpj VARCHAR(20),
    endereco TEXT,
    criado_em TIMESTAMP DEFAULT NOW()
);
```

##### Tabela: estoque
```sql
CREATE TABLE estoque (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    nome VARCHAR(100) NOT NULL,
    codigo VARCHAR(50),
    categoria VARCHAR(20) CHECK (categoria IN ('PECAS','FLUIDOS','PNEUS','ELETRICA','MAO_OBRA','OUTROS')),
    quantidade INTEGER DEFAULT 0,
    minimo_alerta INTEGER DEFAULT 0,
    custo NUMERIC(10,2) DEFAULT 0,
    venda NUMERIC(10,2) DEFAULT 0,
    ativo BOOLEAN DEFAULT TRUE,
    criado_em TIMESTAMP DEFAULT NOW()
);

```

##### Tabela: ordens de servico
```sql
CREATE TABLE ordens_servico (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    cliente_id UUID REFERENCES clientes(id),
    veiculo_id UUID REFERENCES veiculos(id),
    status VARCHAR(20) DEFAULT 'ORCAMENTO' CHECK (status IN ('ORCAMENTO','AGUARDANDO_PECA','EXECUCAO','FINALIZADO','PAGO')),
    descricao_problema TEXT,
    km_atual INTEGER,
    total_pecas NUMERIC(10,2) DEFAULT 0,
    total_mao_obra NUMERIC(10,2) DEFAULT 0,
    total_geral NUMERIC(10,2) DEFAULT 0,
    lucro_estimado NUMERIC(10,2) DEFAULT 0,
    forma_pagamento VARCHAR(30),
    data_abertura TIMESTAMP DEFAULT NOW(),
    data_fechamento TIMESTAMP
);
```

##### Tabela: os itens
```sql
CREATE TABLE os_itens (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    os_id UUID REFERENCES ordens_servico(id) ON DELETE CASCADE,
    estoque_id UUID REFERENCES estoque(id),
    tipo VARCHAR(10) CHECK (tipo IN ('PECA','SERVICO')),
    nome_item VARCHAR(100) NOT NULL,
    quantidade INTEGER DEFAULT 1,
    custo_unitario NUMERIC(10,2) DEFAULT 0,
    venda_unitario NUMERIC(10,2) DEFAULT 0,
    criado_em TIMESTAMP DEFAULT NOW()
);
```

##### Tabela: usuarios
```sql
CREATE TABLE usuarios (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    nome VARCHAR(100) NOT NULL,
    email VARCHAR(100) UNIQUE NOT NULL,
    senha_hash VARCHAR(255) NOT NULL,
    cargo VARCHAR(20) CHECK (cargo IN ('DONO','MECANICO','RECEPCAO')),
    ativo BOOLEAN DEFAULT TRUE,
    criado_em TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Senha padrão: admin123 — altere após o primeiro login
INSERT INTO usuarios (nome, email, senha_hash, cargo)
VALUES (
    'Administrador',
    'admin@oficina.com',
    '$2b$12$LQv3c1yqBWVHxkd0LHAkCOYz6TtxMeshGKZOHyqX5YL6f0KJaGZXO',
    'DONO'
);
```

### 6. Executar a aplicação
```bash
python app.py
```
Acesse: [http://127.0.0.1:5000](http://127.0.0.1:5000)

Login padrão:

> Email: admin@oficina.com
>
> Senha: admin123
>

> *Recomendado alterar a senha após o primeiro acesso.*

## Estrutura de pastas
```text
sistema-oficina/
│
├── app.py                  # Arquivo principal e rotas do dashboard
├── database.py             # Conexão com Supabase
├── requirements.txt        # Dependências do projeto
├── .env                    # Variáveis de ambiente (não versionar)
├── .env.example            # Exemplo de variáveis de ambiente
│
├── routes/                 # Blueprints das rotas
│   ├── clientes.py
│   ├── veiculos.py
│   ├── estoque.py
│   ├── os.py
│   └── auth.py
│
├── utils/                  # Utilitários
│   └── auth_required.py    # Decorators de autenticação
│
├── templates/              # Templates HTML (Jinja2)
│   ├── base.html
│   ├── index.html
│   ├── auth/
│   ├── clientes/
│   ├── veiculos/
│   ├── estoque/
│   └── os/
│
└── static/
    └── css/
        └── custom.css
```
