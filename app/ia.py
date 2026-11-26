"""Integração com o Gemini: chamada, normalização e validação do JSON, novas tentativas e fallback."""
import json
import logging
import re
import time

from pydantic import ValidationError

from .config import settings
from .prompt import GEMINI_SCHEMA, SYSTEM_PROMPT, montar_mensagem_usuario
from .schemas import Classificacao, ClassificacaoResposta, MensagemEntrada
from .simulador import classificar_simulado, sem_acento

log = logging.getLogger("classificador.ia")

SOBRECARGA = (500, 502, 503, 504)  # falhas temporárias do lado do Gemini
SEM_SOLUCAO = (400, 401, 403, 404)  # pedido inválido, chave errada, modelo inexistente: não adianta repetir

_client = None

# Alguns modelos não aceitam prompt de sistema e/ou schema JSON. O ajuste fica lembrado por modelo.
_COMPAT: dict[str, dict[str, bool]] = {}
_RE_SEM_SYSTEM = re.compile(r"(developer|system)[ _]?instruction", re.IGNORECASE)
_RE_SEM_SCHEMA = re.compile(
    r"json mode|response_?schema|response_?mime|structured output|controlled generation", re.IGNORECASE
)


class ConfiguracaoInvalida(RuntimeError):
    """Erro que não adianta repetir (ex.: chave ausente)."""


def _gemini_client():
    global _client
    if _client is None:
        if not settings.gemini_api_key:
            raise ConfiguracaoInvalida("GEMINI_API_KEY não configurada (veja o .env.example)")
        from google import genai
        from google.genai import types

        _client = genai.Client(
            api_key=settings.gemini_api_key,
            http_options=types.HttpOptions(timeout=int(settings.timeout_seg * 1000)),  # em milissegundos
        )
    return _client


def _chamar_gemini(entrada: MensagemEntrada, modelo: str | None = None) -> str:
    """Chama o Gemini e devolve o texto (JSON) da resposta."""
    from google.genai import errors, types

    nome_modelo = modelo or settings.gemini_model
    compat = _COMPAT.setdefault(nome_modelo, {"sem_system": False, "sem_schema": False})
    texto_usuario = montar_mensagem_usuario(entrada.nome, entrada.mensagem, entrada.canal)

    for _ in range(3):  # a chamada normal e até dois ajustes de compatibilidade
        config: dict = {}
        if settings.temperatura is not None:
            config["temperature"] = settings.temperatura
        if not compat["sem_system"]:
            config["system_instruction"] = SYSTEM_PROMPT
        if not compat["sem_schema"]:
            config["response_mime_type"] = "application/json"  # força JSON
            config["response_schema"] = GEMINI_SCHEMA  # força os campos e valores permitidos
        conteudo = f"{SYSTEM_PROMPT}\n\n---\n\n{texto_usuario}" if compat["sem_system"] else texto_usuario
        try:
            resp = _gemini_client().models.generate_content(
                model=nome_modelo, contents=conteudo, config=types.GenerateContentConfig(**config)
            )
        except errors.ClientError as erro:
            msg = str(erro)
            if erro.code == 400 and not compat["sem_system"] and _RE_SEM_SYSTEM.search(msg):
                log.warning("Modelo %s não aceita prompt de sistema; enviando o prompt junto da mensagem", nome_modelo)
                compat["sem_system"] = True
                continue
            if erro.code == 400 and not compat["sem_schema"] and _RE_SEM_SCHEMA.search(msg):
                log.warning("Modelo %s não aceita schema JSON; o formato será garantido só pela validação", nome_modelo)
                compat["sem_schema"] = True
                continue
            raise
        if not resp.text:
            motivo = resp.candidates[0].finish_reason if resp.candidates else "sem candidatos"
            raise ValueError(f"Gemini não devolveu texto (finish_reason: {motivo})")
        return resp.text
    raise RuntimeError(f"Não consegui adaptar a chamada ao modelo {nome_modelo}")


def normalizar_saida(texto: str) -> dict:
    """Corrige variações comuns antes de validar: cercas ```json, "Dúvida" -> "duvida", 95 -> 0.95, "0,9" -> 0.9."""
    texto = re.sub(r"^\s*```(?:json)?\s*|\s*```\s*$", "", texto)
    try:
        dados = json.loads(texto)
    except json.JSONDecodeError:
        # sem schema JSON o modelo pode escrever algo antes ou depois: aproveita só o objeto
        inicio, fim = texto.find("{"), texto.rfind("}")
        if inicio < 0 or fim <= inicio:
            raise ValueError(f"a IA não devolveu um JSON: {texto[:120]!r}") from None
        dados = json.loads(texto[inicio : fim + 1])
    if not isinstance(dados, dict):
        raise ValueError("a resposta da IA não é um objeto JSON")
    for campo in ("categoria", "setor", "prioridade", "sentimento"):
        if isinstance(dados.get(campo), str):
            dados[campo] = re.sub(r"[\s-]+", "_", sem_acento(dados[campo].strip()))
    conf = dados.get("confianca")
    if isinstance(conf, str):
        conf = float(conf.replace(",", "."))
    if isinstance(conf, (int, float)) and 1 < conf <= 100:
        conf = round(conf / 100, 2)
    dados["confianca"] = conf
    return dados


def _modelos_disponiveis() -> list[str]:
    nomes: list[str] = []
    try:
        for modelo in _gemini_client().models.list():
            if "generateContent" in (getattr(modelo, "supported_actions", None) or []):
                nomes.append(modelo.name.removeprefix("models/"))
    except Exception as erro:
        log.warning("Não consegui listar os modelos: %s", erro)
    return nomes


def _modelo_substituto(msg_erro: str) -> str | None:
    """Modelo para usar quando o atual foi aposentado (erro 404).

    Prefere o modelo indicado na própria mensagem de erro do Gemini; senão, um "flash" estável
    da lista de modelos liberados para a chave.
    """
    achado = re.search(r"use (?:models/)?(gemini-[\w.\-]+)", msg_erro, re.IGNORECASE)
    indicado = achado.group(1).rstrip(".") if achado else None
    disponiveis = _modelos_disponiveis()
    if indicado and (not disponiveis or indicado in disponiveis):
        return indicado
    instaveis = re.compile(r"preview|exp|tts|image|live|lite|audio|thinking")
    candidatos = ([m for m in disponiveis if "flash" in m and not instaveis.search(m)]
                  or [m for m in disponiveis if "flash" in m] or disponiveis)
    return candidatos[0] if candidatos else indicado


def _modelo_reserva(atual: str) -> str | None:
    """Outro modelo "flash" da chave, usado quando o principal está sobrecarregado (erro 503)."""
    if settings.gemini_model_reserva:
        return settings.gemini_model_reserva
    fora = re.compile(r"tts|image|live|audio|embedding|thinking")
    outros = [m for m in _modelos_disponiveis() if m != atual and "flash" in m and not fora.search(m)]
    estaveis = [m for m in outros if not re.search(r"preview|exp", m)]
    return (estaveis or outros or [None])[0]


def _espera_antes_de_repetir(erro: Exception, tentativa: int) -> float | None:
    """Quantos segundos esperar antes da próxima tentativa, ou None se não adianta repetir."""
    if isinstance(erro, ConfiguracaoInvalida):
        return None
    codigo = getattr(erro, "code", None)
    if codigo in SEM_SOLUCAO:
        return None
    if codigo == 429:  # limite de requisições do plano: o Gemini informa quanto esperar
        espera = 15.0 * tentativa
        try:
            for detalhe in erro.details["error"]["details"]:
                if "retryDelay" in detalhe:
                    espera = float(str(detalhe["retryDelay"]).rstrip("s"))
        except (AttributeError, KeyError, TypeError, ValueError):
            pass
        return min(espera, settings.espera_max_seg)
    if codigo in SOBRECARGA:
        return 5.0 * tentativa
    return 2.0 * tentativa


def _descrever_erro(erro: Exception) -> str:
    """Texto curto do erro, para o log e para o campo erro_ia."""
    codigo, mensagem = getattr(erro, "code", None), getattr(erro, "message", None)
    if codigo and mensagem:  # erros do SDK do Gemini
        return f"Gemini respondeu {codigo}: {mensagem}"
    return f"{type(erro).__name__}: {erro}"


def _avaliar_revisao(c: Classificacao) -> list[str]:
    motivos = []
    if c.prioridade == "urgente":
        motivos.append("prioridade urgente")
    if c.confianca < settings.limite_confianca:
        motivos.append(f"confiança {c.confianca} abaixo de {settings.limite_confianca}")
    if c.setor == "revisao_humana":
        motivos.append("IA não conseguiu classificar")
    return motivos


def montar_resposta_cliente(entrada: MensagemEntrada, c: Classificacao, precisa_revisao: bool) -> str:
    """Texto que o n8n pode enviar automaticamente ao cliente (WhatsApp ou resposta do formulário).

    A sugestão da IA só segue direto quando o caso NÃO precisa de revisão humana. Casos urgentes,
    duvidosos ou não classificados recebem apenas a confirmação de recebimento, e quem responde
    de verdade é uma pessoa.
    """
    primeiro_nome = entrada.nome.split()[0]
    if precisa_revisao or not c.resposta_sugerida.strip():
        return f"Olá, {primeiro_nome}! Recebemos sua mensagem e um atendente vai falar com você em breve."
    return c.resposta_sugerida.strip()


def _resposta(
    entrada: MensagemEntrada, c: Classificacao, origem: str, tentativas: int, erro: str | None = None
) -> ClassificacaoResposta:
    motivos = _avaliar_revisao(c)
    return ClassificacaoResposta(
        **c.model_dump(),
        canal=entrada.canal,
        revisao_humana=bool(motivos),
        motivos_revisao=motivos,
        resposta_cliente=montar_resposta_cliente(entrada, c, bool(motivos)),
        origem=origem,
        tentativas=tentativas,
        erro_ia=erro,
    )


def classificar_mensagem(entrada: MensagemEntrada) -> ClassificacaoResposta:
    if settings.ia_modo == "simulado":
        return _resposta(entrada, classificar_simulado(entrada.nome, entrada.mensagem), "simulado", 1)

    ultimo_erro = "desconhecido"
    trocou_modelo = False
    reserva: str | None = None
    tentativa = 0
    while tentativa < settings.max_tentativas:
        tentativa += 1
        try:
            if reserva:
                log.warning("Usando o modelo reserva %s (principal sobrecarregado)", reserva)
                texto = _chamar_gemini(entrada, modelo=reserva)
            else:
                texto = _chamar_gemini(entrada)
            classificacao = Classificacao.model_validate(normalizar_saida(texto))  # valida o JSON da IA
            return _resposta(entrada, classificacao, "gemini", tentativa)
        except ValidationError as erro:
            ultimo_erro = f"JSON fora do formato: {erro.errors(include_url=False, include_input=False)}"
            espera = 1.0
        except Exception as erro:  # rede, cota, chave inválida, JSON quebrado...
            ultimo_erro = _descrever_erro(erro)
            espera = _espera_antes_de_repetir(erro, tentativa)
            codigo = getattr(erro, "code", None)
            # 404 = modelo aposentado: troca uma vez pelo substituto e tenta de novo sem gastar tentativa
            if codigo == 404 and not trocou_modelo:
                trocou_modelo = True
                novo = _modelo_substituto(str(erro))
                if novo and novo != settings.gemini_model:
                    log.warning("Modelo %s indisponível; trocando para %s (atualize GEMINI_MODEL no .env)",
                                settings.gemini_model, novo)
                    settings.gemini_model = novo
                    tentativa -= 1
                    continue
            # erro 5xx repetido: a última tentativa vai para um modelo reserva
            if codigo in SOBRECARGA and tentativa == settings.max_tentativas - 1 and not reserva:
                reserva = _modelo_reserva(settings.gemini_model)
        log.warning("Tentativa %s falhou: %s", tentativa, ultimo_erro)
        if espera is None or tentativa >= settings.max_tentativas:
            break
        log.info("Nova tentativa em %.0f s", espera)
        time.sleep(espera)

    log.error("IA falhou; usando fallback (revisão humana). Último erro: %s", ultimo_erro)
    return _resposta(entrada, Classificacao.fallback(), "fallback", tentativa, ultimo_erro[:500])
