# IA de atendimento no WhatsApp (Claude Code ou ChatGPT/Codex)

Coloca uma IA para responder quem chama no WhatsApp do seu negócio, no seu jeito de falar, levando
a conversa até a venda. Quando não sabe ou o caso é delicado, ela passa para você e te avisa.

- Usa a sua assinatura do **Claude** (Claude Code) **ou** do **ChatGPT** (Codex). Escolhe um.
- Roda no seu computador (Mac ou Linux). O computador precisa ficar ligado.
- Só responde conversa individual de quem te chamou. Nunca grupo, nunca disparo.
- Começa em **modo sombra**: escreve num arquivo o que responderia, sem mandar nada, até você aprovar.

## Instalar (o jeito fácil)

1. Tenha o **Claude Code** (`npm install -g @anthropic-ai/claude-code`) ou o **Codex**
   (`npm install -g @openai/codex`) instalado e logado.
2. Baixe este repositório:
   ```
   git clone https://github.com/MatheusSBPRO/ia-whatsapp-atendimento.git
   cd ia-whatsapp-atendimento
   ```
3. Abra o Claude (`claude`) ou o Codex (`codex`) dentro da pasta e fale:

   > **instala a IA de WhatsApp pra mim seguindo o CLAUDE.md**

   Ele te guia: instala, conecta o WhatsApp pelo QR Code, te entrevista sobre o negócio, aprende seu
   jeito de falar com as suas conversas, testa em sombra e só liga quando você aprovar.

## Como funciona

```
cliente manda msg → bridge do WhatsApp grava → a cada 1 min o agente.py olha o que chegou
  → manda a conversa + negocio.md + tom.md pro Claude/Codex → ele decide:
       responder | passar_humano (te avisa) | ignorar
  → sombra: escreve em sombra/AAAA-MM-DD.md   ·   ao_vivo: responde no WhatsApp
```

| Arquivo | Pra que serve |
|---|---|
| `negocio.md` | o que você vende, preços, pagamento, perguntas frequentes, quando passar pra você. **A IA só fala o que está aqui** |
| `tom.md` | seu jeito de escrever, com exemplos reais |
| `config.env` | sombra/ao vivo, Claude/Codex, horário, números de teste, quem a IA nunca responde |
| `prompt.md` | as regras gerais da IA (não precisa mexer) |
| `agente.py` | o robô (Python puro, sem instalar nada) |

## Travas de segurança que já vêm ligadas
- **Modo sombra** por padrão.
- **`SO_ESTES`**: no primeiro teste ao vivo ela só responde o seu número de teste.
- **Respondeu à mão, a IA sai**: se alguém da equipe escreveu naquela conversa, ela fica quieta por 12 h.
- **Espera 1 min** de silêncio antes de responder (cliente que manda 3 mensagens seguidas).
- **Não ressuscita conversa velha** (mais de 6 h) quando liga.
- **Nunca** responde grupo, lista de transmissão ou status.

## Comandos
```
./instalar.sh                    instala a bridge e cria o config.env
./bridge.sh                      conecta o WhatsApp (QR Code)
python3 agente.py --teste <jid>  testa uma conversa em sombra
./ligar-automatico.sh            deixa rodando sozinho (bridge + IA a cada 1 min)
./ligar-automatico.sh desligar   desliga
tail -f agente.log               ver o que a IA está fazendo
```

## Avisos
- A conexão usa o WhatsApp Web pela [whatsapp-mcp](https://github.com/lharries/whatsapp-mcp) (código
  aberto, não é a API oficial da Meta). Para atender quem te chama é tranquilo; não use para disparo
  em massa.
- Cada resposta consome um pouco da sua assinatura do Claude/ChatGPT. Para ficar mais barato:
  `MODELO=haiku` no `config.env` (Claude).
- Mantenha o computador sem dormir enquanto a IA estiver ligada.

Feito pela [Blessy Mídias](https://blessymidias.com.br). Licença MIT.
