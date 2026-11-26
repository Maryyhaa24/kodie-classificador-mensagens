"""Simula mensagens chegando pelo WhatsApp.

Envia ao n8n o mesmo formato de aviso (webhook) que a WhatsApp Cloud API da Meta envia.
Serve para testar e tirar os prints do ramo do WhatsApp sem precisar de conta na Meta.

Uso:
    python exemplos/simular_whatsapp.py
        envia os exemplos do WhatsApp para o webhook de produção do n8n (workflow ativo)

    python exemplos/simular_whatsapp.py --url http://localhost:5678/webhook-test/whatsapp
        idem, no modo de teste do n8n (uma mensagem por vez)

    python exemplos/simular_whatsapp.py --texto "cadê meu pedido?" --nome "Ivo" --telefone 5531988887777
        envia uma única mensagem, com o texto que você quiser

Atenção: a resposta ao cliente é enviada pela API da Meta. Na simulação esse envio falha, porque
o número de teste não existe, e isso é esperado: o node "WhatsApp - Responde ao cliente" continua
em caso de erro, então a planilha e os e-mails saem normalmente.

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

parser = argparse.ArgumentParser(description="Simula mensagens do WhatsApp no formato da Meta.")
parser.add_argument("--url", default="http://localhost:5678/webhook/whatsapp")
parser.add_argument("--pausa", type=float, default=7.0, help="segundos entre um envio e outro")
parser.add_argument("--texto", help="envia só esta mensagem, em vez dos exemplos")
parser.add_argument("--nome", default="Cliente de Teste")
parser.add_argument("--telefone", default="5531900000000")
args = parser.parse_args()


def aviso_da_meta(nome: str, telefone: str, texto: str, numero: int) -> dict:
    """Monta o JSON no formato do webhook "messages" da WhatsApp Cloud API."""
    mensagem = {"from": telefone, "id": f"wamid.SIMULADO{numero:04d}", "timestamp": str(int(time.time()))}
    if texto.startswith("[") and texto.endswith("]"):  # ex.: [audio] vira uma mensagem de mídia, sem texto
        tipo = texto[1:-1]
        mensagem.update({"type": tipo, tipo: {"id": "MIDIA_SIMULADA"}})
    else:
        mensagem.update({"type": "text", "text": {"body": texto}})
    return {
        "object": "whatsapp_business_account",
        "entry": [{
            "id": "CONTA_SIMULADA",
            "changes": [{
                "field": "messages",
                "value": {
                    "messaging_product": "whatsapp",
                    "metadata": {"display_phone_number": "5531900000000", "phone_number_id": "NUMERO_SIMULADO"},
                    "contacts": [{"profile": {"name": nome}, "wa_id": telefone}],
                    "messages": [mensagem],
                },
            }],
        }],
    }


if args.texto:
    exemplos = [{"rotulo": "mensagem-avulsa", "nome": args.nome, "telefone": args.telefone, "mensagem": args.texto}]
else:
    todos = json.loads((Path(__file__).parent / "mensagens.json").read_text(encoding="utf-8"))
    exemplos = [ex for ex in todos if ex["canal"] == "whatsapp"]

for i, ex in enumerate(exemplos):
    if i:
        time.sleep(args.pausa)
    corpo = aviso_da_meta(ex["nome"], ex["telefone"], ex["mensagem"], i + 1)
    req = urllib.request.Request(
        args.url, data=json.dumps(corpo).encode(), headers={"Content-Type": "application/json"}, method="POST"
    )
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            # o n8n responde na hora (como a Meta exige) e processa a mensagem em seguida
            print(f"[{resp.status}] {ex['rotulo']:<18} -> entregue ao n8n: {ex['mensagem']}")
    except urllib.error.HTTPError as e:
        print(f"[{e.code}] {ex['rotulo']:<18} -> {e.read().decode(errors='replace')}")
    except urllib.error.URLError as e:
        sys.exit(f"Não foi possível conectar em {args.url}: {e.reason}")

print("\nVeja o resultado em Executions, no n8n, na planilha e na caixa de e-mail.")
