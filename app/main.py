"""API FastAPI do classificador de mensagens."""
import logging

from fastapi import FastAPI
from fastapi.responses import RedirectResponse

from .config import settings
from .ia import classificar_mensagem
from .schemas import ClassificacaoResposta, MensagemEntrada

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")

app = FastAPI(
    title="Classificador de Mensagens de Clientes",
    description="Recebe a mensagem de um cliente (formulário do site ou WhatsApp), classifica com IA "
    "(Gemini) e devolve um JSON validado com categoria, setor, prioridade, resumo e a resposta ao cliente.",
    version="1.1.0",
)


@app.get("/", include_in_schema=False)
def raiz():
    return RedirectResponse("/docs")


@app.get("/health", tags=["status"])
def health():
    return {"status": "ok", "ia_modo": settings.ia_modo, "modelo": settings.gemini_model}


@app.post("/classificar", response_model=ClassificacaoResposta, tags=["classificação"])
def classificar(entrada: MensagemEntrada) -> ClassificacaoResposta:
    """Classifica uma mensagem. Entrada inválida gera erro 422 automaticamente (Pydantic)."""
    return classificar_mensagem(entrada)
