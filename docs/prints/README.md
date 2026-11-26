# Prints do fluxo n8n

Salve as capturas nesta pasta **com exatamente estes nomes** (PNG): o README principal já aponta para eles.

Antes de capturar, gere as execuções:

```bash
python exemplos/enviar_exemplos.py      # 8 mensagens pelo formulário
python exemplos/simular_whatsapp.py     # 5 mensagens no formato do WhatsApp
```

Os nodes abertos a partir da aba **Executions** mostram a configuração, a entrada e a saída na mesma tela, que é o que o desafio pede.

## Visão geral

| Arquivo | O que capturar |
|---|---|
| `01-fluxo-completo.png` | Canvas do n8n com os 22 nodes e as notas visíveis. |
| `02-execucao-formulario.png` | Uma execução iniciada pelo node **Webhook**, com os nodes do caminho em verde. |
| `03-execucao-whatsapp.png` | Uma execução iniciada pelo node **WhatsApp - Recebe mensagem**. |

## Configuração de cada node

| Arquivo | Node | O que precisa aparecer |
|---|---|---|
| `04-node-webhook.png` | Webhook | Método, path e *Respond: Using 'Respond to Webhook' node*. |
| `05-node-extrai-formulario.png` | Extrai dados do formulário | Os cinco campos e a saída. |
| `06-node-whatsapp-recebe.png` | WhatsApp - Recebe mensagem | Método, path e a entrada no formato da Meta. |
| `07-node-whatsapp-confirma.png` | WhatsApp - Confirma recebimento | A resposta de texto enviada à Meta. |
| `08-node-extrai-whatsapp.png` | Extrai dados do WhatsApp | O código e a saída com `canal`, `nome`, `telefone` e `mensagem`. |
| `09-node-normaliza.png` | Normaliza dados | As expressões e a saída com `id` e `recebido_em`. |
| `10-node-classificar-ia.png` | Classificar com IA (API) | URL, corpo JSON e a **saída com o JSON da IA**. |
| `11-node-contingencia.png` | Classificação de contingência | Os campos. Para vê-lo executado, pare a API e envie uma mensagem. |
| `12-node-monta-registro.png` | Monta registro | Os campos e a saída completa. |
| `13-node-canal-resposta.png` | Canal de resposta | As duas regras. |
| `14-node-responde-cliente.png` | Responde ao cliente | O JSON de resposta. |
| `15-node-whatsapp-responde.png` | WhatsApp - Responde ao cliente | URL, credencial (só o nome aparece) e corpo. |
| `16-node-planilha.png` | Registra na planilha | Operação, planilha, aba e colunas mapeadas. |
| `17-node-precisa-revisao.png` | Precisa de revisão? | A condição e o resultado (true ou false). |
| `18-node-roteia-setor.png` | Roteia por setor | As quatro regras. |
| `19-node-email.png` | Um dos nodes de e-mail | Destinatário, assunto e corpo. |
| `20-node-whatsapp-verificacao.png` | WhatsApp - Responde verificação | A expressão que confere o token. |

## Resultados

| Arquivo | O que capturar |
|---|---|
| `21-saida-api.png` | O JSON retornado pela API (pode ser do Swagger em `localhost:8000/docs`). |
| `22-planilha.png` | A planilha do Google Sheets com as linhas dos dois canais. |
| `23-emails.png` | A caixa de entrada com os e-mails por setor. |
| `24-whatsapp-conversa.png` | A conversa no celular: a mensagem enviada e a resposta automática com o protocolo. Só é possível com o WhatsApp real configurado (seção 6.5 do README). |

## Cuidados

- Confira se nenhum print mostra chave de API, token ou senha. As credenciais do n8n mostram só o nome, mas a tela da Meta e o arquivo `.env` mostram os valores.
- Se não for configurar o WhatsApp real, o print 24 pode ser trocado pela execução simulada, deixando isso claro no texto do README.
