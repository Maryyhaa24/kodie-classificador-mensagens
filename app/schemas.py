"""Contratos de entrada e saída da API (validados com Pydantic)."""
import re
from typing import Literal

from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator, model_validator

Canal = Literal["formulario", "whatsapp"]
Categoria = Literal["duvida", "reclamacao", "solicitacao", "elogio", "outro"]
Setor = Literal["suporte", "financeiro", "comercial", "logistica", "revisao_humana"]
Prioridade = Literal["baixa", "media", "alta", "urgente"]
Sentimento = Literal["positivo", "neutro", "negativo"]


class MensagemEntrada(BaseModel):
    """O que o n8n envia para a API, venha a mensagem do formulário do site ou do WhatsApp."""

    model_config = ConfigDict(str_strip_whitespace=True)

    canal: Canal = Field(default="formulario", description="Por onde a mensagem chegou")
    nome: str = Field(min_length=1, max_length=100, examples=["Ana Souza"])
    email: EmailStr | None = Field(default=None, examples=["ana.souza@cliente.demo"])
    telefone: str | None = Field(
        default=None,
        description="Telefone com DDI e DDD. Aceita qualquer formatação; a API guarda só os dígitos.",
        examples=["5531988887777"],
    )
    mensagem: str = Field(
        min_length=1,
        max_length=4096,  # tamanho máximo de uma mensagem de texto do WhatsApp
        examples=["Fui cobrada duas vezes no boleto de outubro! Quero o estorno urgente."],
    )

    @field_validator("email", mode="before")
    @classmethod
    def _email_vazio_vira_nulo(cls, valor):
        return None if isinstance(valor, str) and not valor.strip() else valor

    @field_validator("telefone", mode="before")
    @classmethod
    def _telefone_so_com_digitos(cls, valor):
        if valor is None:
            return None
        digitos = re.sub(r"\D", "", str(valor))
        if not digitos:
            return None
        if not 8 <= len(digitos) <= 15:
            raise ValueError("telefone deve ter de 8 a 15 dígitos (com DDI e DDD)")
        return digitos

    @model_validator(mode="after")
    def _exige_um_contato(self):
        if not self.email and not self.telefone:
            raise ValueError("informe email ou telefone para que a empresa possa responder")
        return self


class Classificacao(BaseModel):
    """O JSON que a IA precisa devolver."""

    categoria: Categoria
    setor: Setor
    prioridade: Prioridade
    sentimento: Sentimento
    resumo: str
    resposta_sugerida: str
    confianca: float = Field(ge=0, le=1)

    @classmethod
    def fallback(cls) -> "Classificacao":
        """Resposta segura quando a IA falha: manda para revisão humana."""
        return cls(
            categoria="outro",
            setor="revisao_humana",
            prioridade="media",
            sentimento="neutro",
            resumo="Não foi possível classificar automaticamente.",
            resposta_sugerida="",
            confianca=0,
        )


class ClassificacaoResposta(Classificacao):
    """Resposta final da API: a classificação mais os campos de controle usados pelo n8n."""

    canal: Canal
    revisao_humana: bool = Field(description="True se a mensagem precisa passar por uma pessoa")
    motivos_revisao: list[str] = Field(default_factory=list)
    resposta_cliente: str = Field(
        description="Texto que pode ser enviado automaticamente ao cliente. "
        "Só traz a sugestão da IA quando o caso não precisa de revisão humana."
    )
    origem: Literal["gemini", "simulado", "fallback"]
    tentativas: int
    erro_ia: str | None = Field(default=None, description="Último erro da IA quando houve fallback")
