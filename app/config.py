"""Configuração lida das variáveis de ambiente (arquivo .env)."""
import os

from dotenv import load_dotenv

load_dotenv()


def _texto(nome: str, padrao: str = "") -> str:
    return os.getenv(nome, padrao).strip() or padrao


def _inteiro(nome: str, padrao: int) -> int:
    return int(_texto(nome, str(padrao)))


def _decimal(nome: str, padrao: float | None) -> float | None:
    valor = _texto(nome).replace(",", ".")
    return float(valor) if valor else padrao


class Settings:
    # Chave da API do Google Gemini (https://aistudio.google.com/apikey)
    gemini_api_key: str = _texto("GEMINI_API_KEY")
    # Modelo usado na classificação
    gemini_model: str = _texto("GEMINI_MODEL", "gemini-3.8-flash")
    # Modelo usado na última tentativa se o principal estiver sobrecarregado (erro 503).
    # Vazio = escolhe automaticamente outro modelo "flash" liberado para a chave.
    gemini_model_reserva: str = _texto("GEMINI_MODEL_RESERVA")
    # "gemini" usa a IA de verdade; "simulado" usa regras locais (útil para testar sem chave)
    ia_modo: str = _texto("IA_MODO", "gemini").lower()
    # Tentativas de chamar a IA antes de cair no fallback
    max_tentativas: int = _inteiro("IA_MAX_TENTATIVAS", 3)
    # Espera máxima entre tentativas quando o Gemini devolve 429 (limite de requisições)
    espera_max_seg: float = _decimal("IA_ESPERA_MAX_SEG", 30.0)
    # Tempo máximo de cada chamada ao Gemini
    timeout_seg: float = _decimal("IA_TIMEOUT_SEG", 60.0)
    # Temperatura do modelo. Vazio = usa o padrão do próprio modelo.
    temperatura: float | None = _decimal("IA_TEMPERATURA", None)
    # Abaixo desta confiança a mensagem vai para revisão humana
    limite_confianca: float = _decimal("LIMITE_CONFIANCA", 0.6)


settings = Settings()
