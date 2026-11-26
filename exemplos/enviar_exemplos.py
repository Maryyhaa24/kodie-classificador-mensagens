"""Dispara as mensagens de exemplo no webhook do n8n (ou direto na API).

Uso:
    python exemplos/enviar_exemplos.py
        envia os exemplos do formulário para o webhook de produção do n8n (workflow ativo)

    python exemplos/enviar_exemplos.py --url http://localhost:5678/webhook-test/mensagem
        idem, no modo de teste do n8n (o "Listen for test event" aceita uma mensagem por vez)

    python exemplos/enviar_exemplos.py --url http://localhost:8000/classificar --todos
        chama a API direto, com os exemplos de todos os canais

A pausa entre os envios (padrão: 7 s) respeita o limite de requisições por minuto do plano
gratuito do Gemini. Com IA_MODO=simulado use --pausa 0.

Só usa a biblioteca padrão do Python.
"""
import argparse
import json
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8", errors="replace")  # acentos e emojis no terminal do Windows

parser = argparse.ArgumentParser(description="Envia as mensagens de exemplo.")
parser.add_argument("--url", default="http://localhost:5678/webhook/mensagem")
parser.add_argument("--pausa", type=float, default=7.0, help="segundos entre um envio e outro")
parser.add_argument("--todos", action="store_true", help="inclui também os exemplos do WhatsApp")
args = parser.parse_args()

exemplos = json.loads((Path(__file__).parent / "mensagens.json").read_text(encoding="utf-8"))
if not args.todos:
    exemplos = [ex for ex in exemplos if ex["canal"] == "formulario"]

for i, ex in enumerate(exemplos):
    if i:
        time.sleep(args.pausa)
    corpo = {k: ex[k] for k in ("canal", "nome", "email", "telefone", "mensagem") if k in ex}
    req = urllib.request.Request(
        args.url, data=json.dumps(corpo).encode(), headers={"Content-Type": "application/json"}, method="POST"
    )
    try:
        with urllib.request.urlopen(req, timeout=150) as resp:
            dados = json.loads(resp.read() or b"{}")
            print(f"[{resp.status}] {ex['rotulo']:<18} -> {json.dumps(dados, ensure_ascii=False)}")
    except urllib.error.HTTPError as e:
        print(f"[{e.code}] {ex['rotulo']:<18} -> {e.read().decode(errors='replace')}")
    except urllib.error.URLError as e:
        sys.exit(f"Não foi possível conectar em {args.url}: {e.reason}")
