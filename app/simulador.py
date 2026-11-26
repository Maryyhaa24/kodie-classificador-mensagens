"""Classificador por regras, usado no modo IA_MODO=simulado.

Devolve o mesmo contrato do Gemini. Serve para testar a API e o fluxo do n8n
sem chave de API e sem internet. Não substitui a IA: só reconhece palavras-chave.
"""
import re
import unicodedata

from .schemas import Classificacao


def sem_acento(texto: str) -> str:
    """Minúsculas e sem acentos, para comparar textos."""
    decomposto = unicodedata.normalize("NFD", texto.lower())
    return "".join(c for c in decomposto if unicodedata.category(c) != "Mn")


_NEG = [r"nao funciona", r"nao consigo", r"problema", r"absurdo", r"pessim", r"cobrad[oa].*duas",
        r"duas vezes", r"atrasad", r"defeito", r"quebrad", r"errad", r"insatisfeit", r"reclama",
        r"ainda nao chegou", r"nunca chegou", r"\berro\b", r"descaso"]
_POS = [r"parabens", r"otim[oa]", r"excelente", r"adorei", r"obrigad", r"muito bom", r"gostei"]
_SOL = [r"gostaria", r"\bquero\b", r"preciso", r"solicito", r"cancelar", r"trocar", r"segunda via",
        r"alterar", r"orcamento"]
_DUV = [r"\?", r"\bcomo\b", r"\bqual\b", r"\bquando\b", r"\bqnd\b", r"\bonde\b", r"\bcade\b",
        r"\bquanto\b", r"duvida"]
_URG = [r"urgente", r"imediat", r"procon", r"advogad", r"justica", r"estorno"]
_SETORES = {
    "financeiro": [r"boleto", r"cobran", r"cobrad", r"pagamento", r"fatura", r"reembolso", r"estorno",
                   r"nota fiscal", r"\bpix\b", r"segunda via", r"dinheiro"],
    "logistica": [r"entreg", r"pedido", r"chegou", r"frete", r"rastre", r"transportadora", r"prazo", r"envio"],
    "comercial": [r"orcamento", r"preco", r"desconto", r"compr", r"proposta", r"revend", r"catalogo", r"licenc"],
    "suporte": [r"acess", r"senha", r"sistema", r"\berro\b", r"login", r"aplicativo", r"instal", r"defeito",
                r"funciona", r"atendimento"],
}
_ROTULO = {"suporte": "Suporte", "financeiro": "Financeiro", "comercial": "Comercial",
           "logistica": "Logística", "revisao_humana": "Revisão humana"}
_TEMA = {"financeiro": "assunto financeiro", "logistica": "entrega/pedido",
         "comercial": "proposta comercial", "suporte": "uso do serviço"}
_CAT = {"duvida": "Dúvida", "reclamacao": "Reclamação", "solicitacao": "Solicitação",
        "elogio": "Elogio", "outro": "Outro"}


def classificar_simulado(nome: str, mensagem: str) -> Classificacao:
    t = sem_acento(mensagem)

    def hits(padroes: list[str]) -> int:
        return sum(1 for p in padroes if re.search(p, t))

    neg, pos, sol, duv, urg = hits(_NEG), hits(_POS), hits(_SOL), hits(_DUV), hits(_URG)

    if len(t.strip()) < 6 or neg + pos + sol + duv == 0:
        categoria = "outro"
    elif pos and not neg:
        categoria = "elogio"
    elif neg:
        categoria = "reclamacao"
    elif sol:
        categoria = "solicitacao"
    else:
        categoria = "duvida"

    setor, melhor = "suporte", 0
    for nome_setor in ("financeiro", "logistica", "comercial", "suporte"):
        h = hits(_SETORES[nome_setor])
        if h > melhor:
            setor, melhor = nome_setor, h
    if categoria == "outro":
        setor = "revisao_humana"

    if categoria == "outro":
        prioridade = "media"
    elif urg:
        prioridade = "urgente"
    elif categoria == "reclamacao":
        prioridade = "alta"
    elif categoria == "solicitacao":
        prioridade = "media"
    else:
        prioridade = "baixa"

    sentimento = "negativo" if neg > pos else "positivo" if pos > neg else "neutro"
    confianca = 0.35 if categoria == "outro" else min(0.97, round(0.6 + 0.07 * (melhor + neg + pos + sol + duv), 2))

    primeiro_nome = (nome.strip().split() or ["cliente"])[0]
    s = _ROTULO[setor]
    texto = mensagem.strip()
    trecho = texto[:70] + "…" if len(texto) > 70 else texto
    if categoria == "outro":
        resumo = "Mensagem sem conteúdo suficiente para classificação automática."
    else:
        resumo = f'{_CAT[categoria]} sobre {_TEMA[setor]}: "{trecho}"'

    resposta = {
        "reclamacao": f"Olá {primeiro_nome}, lamentamos muito o ocorrido. Sua mensagem foi encaminhada com "
                      f"prioridade ao setor {s}, que entrará em contato em breve.",
        "duvida": f"Olá {primeiro_nome}, obrigado pelo contato! Sua dúvida foi enviada ao setor {s}, que "
                  f"responderá com as informações em breve.",
        "solicitacao": f"Olá {primeiro_nome}, recebemos sua solicitação e ela já está com o setor {s}. "
                       f"Avisaremos assim que houver andamento.",
        "elogio": f"Olá {primeiro_nome}, muito obrigado pelo carinho! Vamos compartilhar seu elogio com toda a equipe.",
        "outro": f"Olá {primeiro_nome}, recebemos sua mensagem. Poderia nos contar com mais detalhes como podemos ajudar?",
    }[categoria]

    return Classificacao(
        categoria=categoria,
        setor=setor,
        prioridade=prioridade,
        sentimento=sentimento,
        resumo=resumo,
        resposta_sugerida=resposta,
        confianca=confianca,
    )
