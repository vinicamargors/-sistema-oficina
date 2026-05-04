#!/usr/bin/env python3
"""
migrate_legacy.py
Migra tbclientes.csv + tbos.csv para o Supabase.

Como usar:
  1. Coloque este script na raiz do projeto Flask (onde está database.py)
  2. Coloque tbclientes.csv e tbos.csv também na raiz
  3. python migrate_legacy.py
"""

import re
import json
import csv
import sys
import os
from database import supabase

ARQUIVO_CLIENTES = "tbclientes.csv"
ARQUIVO_OS = "tbos.csv"

# nome legado -> uuid supabase
MECANICOS = {
    "wilson": "5f873734-a25a-4fb4-8707-42892eca73fe",
    "carlos": "8dedfff9-9c70-4434-8b03-71a262f615db",
    "miguel": "e0902ccd-5020-4f3c-a9a7-199f440cef2e",
}

STATUS_MAP = {
    "finalizado": "FINALIZADO",
    "em manutenção": "EXECUCAO",
    "em manutencao": "EXECUCAO",
    "orçamento": "ORCAMENTO",
    "orcamento": "ORCAMENTO",
    "aberto": "ORCAMENTO",
    "pago": "PAGO",
}

PALAVRAS_MO = [
    "m.o", "mão de obra", "mao de obra", "revisão", "revisao",
    "troca ", "higienização", "higienizacao", "diagnóstico", "diagnostico",
    "limpeza", "remoção", "remocao", "instalação", "instalacao",
    "serviço", "servico", "reparo", "anulação", "usinagem",
    "verificação", "calibração", "sangria", "alinhamento",
    "balanceamento", "geometria", "regulagem", "ajuste", "reaperto",
]

NOMES_SKIP = {"peças", "pecas", "mão de obra", "mao de obra"}

def limpar_telefone(tel):
    if not tel or str(tel).strip() in ["0", "nan", ""]:
        return ""
    t = re.sub(r"[^\d]", "", str(tel))
    return t if len(t) >= 8 else ""

def limpar_cpf(cpf):
    if not cpf or str(cpf).strip() in ["0", "nan", "n/a", ""]:
        return None
    c = re.sub(r"[^\d]", "", str(cpf))
    return c if len(c) >= 8 else None

def extrair_km(texto):
    m = re.search(r"KM[\s:.]*(\d[\d.,]*)", texto or "", re.IGNORECASE)
    if m:
        try:
            return int(m.group(1).replace(".", "").replace(",", ""))
        except ValueError:
            pass
    return None

def resolver_mecanico(nome_legado):
    chave = nome_legado.strip().lower().split()[0] if nome_legado else ""
    return MECANICOS.get(chave)

def eh_mao_obra(nome):
    n = nome.lower().strip()
    return any(n.startswith(p) or p in n for p in PALAVRAS_MO)

def parse_itens_json(raw):
    itens = []
    try:
        dados = json.loads(raw)
        for item in dados:
            nome = str(item.get("name", "")).strip()
            preco = float(item.get("price", 0))
            if not nome or nome.lower().strip() in NOMES_SKIP:
                continue
            itens.append({
                "nome_item": nome,
                "venda_unitario": preco,
                "custo_unitario": 0.0,
                "quantidade": 1,
                "tipo": "MAO_OBRA" if eh_mao_obra(nome) else "PECA",
            })
    except Exception:
        pass
    return itens

def parse_os_bloco(bloco):
    bloco_clean = bloco.replace("\n", " ")

    m = re.match(
        r"^(\d+),"
        r'"?([\d\-: ]+?)"?,'
        r'"([^"]+?)",'
        r"([A-Za-z0-9\-]+),"
        r"([^,]+),"
        r"([\d.]+),"
        r'"(.*?)",\s*'
        r"(\d+),"
        r"([^,\[]+)",
        bloco_clean,
    )

    itens_match = re.search(r"\[(\{.*\})\]", bloco_clean)
    itens_raw = "[" + itens_match.group(1) + "]" if itens_match else "[]"

    if m:
        return {
            "os": m.group(1),
            "data_os": m.group(2).strip(),
            "carro": m.group(3),
            "placa": m.group(4).upper(),
            "tecnico": m.group(5).strip(),
            "valor": m.group(6),
            "servico": m.group(7),
            "idclie": m.group(8),
            "status": m.group(9).strip().strip('"'),
            "itens_raw": itens_raw,
        }

    partes = bloco_clean.split(",", 9)
    if len(partes) >= 9:
        return {
            "os": partes[0].strip(),
            "data_os": partes[1].strip().strip('"'),
            "carro": partes[2].strip().strip('"'),
            "placa": partes[3].strip().upper(),
            "tecnico": partes[4].strip(),
            "valor": partes[5].strip(),
            "servico": "",
            "idclie": partes[7].strip() if len(partes) > 7 else "",
            "status": partes[8].strip().strip('"') if len(partes) > 8 else "",
            "itens_raw": itens_raw,
        }

    return None

def migrar_clientes():
    print("\n[1/4] Migrando clientes...")
    mapa = {}

    with open(ARQUIVO_CLIENTES, newline="", encoding="utf-8") as f:
        for row in csv.DictReader(f):
            id_leg = int(row["id"])
            end = str(row.get("endereco", "")).strip()
            if end.lower() in ["0", "nan", "n/a", ""]:
                end = ""

            dados = {
                "nome": str(row["nome"]).strip(),
                "telefone": limpar_telefone(row.get("telefone", "")),
                "endereco": end,
                "cpf_cnpj": limpar_cpf(row.get("cpf", "")),
            }

            try:
                resp = supabase.table("clientes").insert(dados).execute()
                novo_id = resp.data[0]["id"]
                mapa[id_leg] = novo_id
                print(f"  ✓ #{id_leg:>3}  {dados['nome']}")
            except Exception as e:
                print(f"  ✗ Erro cliente #{id_leg} ({dados['nome']}): {e}")

    print(f"  ▶ Inseridos: {len(mapa)}")
    return mapa

def migrar_veiculos(blocos, mapa_clientes):
    print("\n[2/4] Migrando veículos (deduplica por placa)...")
    veiculos = {}

    for b in blocos:
        r = parse_os_bloco(b)
        if not r:
            continue

        placa = r["placa"].strip()
        if not placa:
            continue

        km = extrair_km(r["servico"])
        id_leg = int(r["idclie"]) if r["idclie"].isdigit() else None

        if placa not in veiculos:
            veiculos[placa] = {
                "placa": placa,
                "modelo": r["carro"].title().strip(),
                "cliente_id_legado": id_leg,
                "km_atual": km,
            }
        elif km and (veiculos[placa]["km_atual"] is None or km > veiculos[placa]["km_atual"]):
            veiculos[placa]["km_atual"] = km

    mapa = {}

    for placa, v in veiculos.items():
        cliente_uuid = mapa_clientes.get(v["cliente_id_legado"])
        if not cliente_uuid:
            print(f"  ⚠ {placa}: cliente legado #{v['cliente_id_legado']} não mapeado — pulando")
            continue

        dados = {
            "placa": v["placa"],
            "modelo": v["modelo"],
            "km_atual": v["km_atual"],
            "cliente_id": cliente_uuid,
        }

        try:
            resp = supabase.table("veiculos").insert(dados).execute()
            novo_id = resp.data[0]["id"]
            mapa[placa] = novo_id
            print(f"  ✓ {placa}  {v['modelo']}")
        except Exception as e:
            print(f"  ✗ Erro veículo {placa}: {e}")

    print(f"  ▶ Inseridos: {len(mapa)}/{len(veiculos)}")
    return mapa

def migrar_os_e_itens(blocos, mapa_clientes, mapa_veiculos):
    print("\n[3/4] Inserindo ordens_servico...")
    print("[4/4] Inserindo os_itens...\n")

    os_ok = 0
    itens_ok = 0
    erros = 0

    for b in blocos:
        r = parse_os_bloco(b)
        if not r:
            erros += 1
            continue

        placa = r["placa"].strip()
        cliente_uuid = mapa_clientes.get(int(r["idclie"])) if r["idclie"].isdigit() else None
        veiculo_uuid = mapa_veiculos.get(placa)
        mecanico_id = resolver_mecanico(r["tecnico"])
        status = STATUS_MAP.get(r["status"].lower().strip(), "ORCAMENTO")
        km = extrair_km(r["servico"])
        itens = parse_itens_json(r["itens_raw"])

        total_pecas = round(sum(i["venda_unitario"] for i in itens if i["tipo"] == "PECA"), 2)
        total_mo = round(sum(i["venda_unitario"] for i in itens if i["tipo"] == "MAO_OBRA"), 2)
        total_geral = round(float(r["valor"]) if r["valor"] else total_pecas + total_mo, 2)

        if not cliente_uuid or not veiculo_uuid:
            print(f"  ⚠ OS #{r['os']}: cliente ou veículo não mapeado — pulando")
            erros += 1
            continue

        if not mecanico_id:
            print(f"  ⚠ OS #{r['os']}: mecânico '{r['tecnico']}' não encontrado — inserindo sem vínculo")

        dados_os = {
            "cliente_id": cliente_uuid,
            "veiculo_id": veiculo_uuid,
            "mecanico_responsavel_id": mecanico_id,
            "status": status,
            "descricao_problema": r["servico"],
            "km_atual": km,
            "total_pecas": total_pecas,
            "total_mao_obra": total_mo,
            "total_geral": total_geral,
            "data_abertura": r["data_os"],
            "data_fechamento": r["data_os"] if status in ("FINALIZADO", "PAGO") else None,
        }

        try:
            resp_os = supabase.table("ordens_servico").insert(dados_os).execute()
            os_uuid = resp_os.data[0]["id"]
            os_ok += 1

            mecanico_label = r["tecnico"] if mecanico_id else f"{r['tecnico']} (sem vínculo)"
            print(
                f"  ✓ OS #{r['os']:>3}  {placa:<10}  [{status:<11}]  "
                f"R$ {total_geral:>8.2f}  🔧 {mecanico_label}  ({len(itens)} itens)"
            )
        except Exception as e:
            print(f"  ✗ Erro OS #{r['os']}: {e}")
            erros += 1
            continue

        for item in itens:
            dados_item = {
                "os_id": os_uuid,
                "estoque_id": None,
                "tipo": item["tipo"],
                "nome_item": item["nome_item"],
                "quantidade": item["quantidade"],
                "custo_unitario": item["custo_unitario"],
                "venda_unitario": item["venda_unitario"],
            }
            try:
                supabase.table("os_itens").insert(dados_item).execute()
                itens_ok += 1
            except Exception as e:
                print(f"      ✗ Item '{item['nome_item']}': {e}")

    print(f"\n  ▶ OS inseridas:    {os_ok}")
    print(f"  ▶ Itens inseridos: {itens_ok}")
    print(f"  ▶ Erros/pulados:   {erros}")

if __name__ == "__main__":
    for arq in [ARQUIVO_CLIENTES, ARQUIVO_OS]:
        if not os.path.exists(arq):
            print(f"ERRO: arquivo não encontrado → {arq}")
            sys.exit(1)

    with open(ARQUIVO_OS, "r", encoding="utf-8") as f:
        conteudo = f.read()

    blocos = re.split(r"\n(?=\d+,)", conteudo)[1:]

    print("=" * 60)
    print("   MIGRAÇÃO SISTEMA LEGADO → SUPABASE")
    print(f"   {len(blocos)} OS encontradas no arquivo")
    print("=" * 60)

    mapa_cli = migrar_clientes()
    mapa_vei = migrar_veiculos(blocos, mapa_cli)
    migrar_os_e_itens(blocos, mapa_cli, mapa_vei)

    print("\n✅ Migração concluída!")