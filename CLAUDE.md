# Roteiro de instalação para o assistente (Claude Code ou Codex)

Você está ajudando o dono de um negócio a colocar uma IA para responder o WhatsApp dele. Ele não é
programador. Fale em português simples, um passo por vez, e espere ele confirmar antes de seguir.
Rode os comandos você mesmo; só peça para ele o que exige o celular ou a decisão dele.

## Passo 1 — Instalar
1. Rode `./instalar.sh`. Se faltar `go`, `git` ou `python3`, instale (Mac: `brew install ...`;
   sem Homebrew, mande ele instalar por https://brew.sh) e rode de novo.
2. Confira que `claude` ou `codex` responde (`claude -p "oi" --tools ""` ou `codex exec "oi"`).

## Passo 2 — Conectar o WhatsApp (precisa do celular dele)
1. Recomende usar o número COMERCIAL, não o pessoal. A IA só responde conversa individual (nunca
   grupo), mas no número pessoal ela vai ver família e amigos — nesse caso, preencher `NUNCA_ESTES`.
2. Peça para ele abrir um terminal na pasta e rodar `./bridge.sh` (o QR Code aparece lá; você não
   consegue mostrar o QR por aqui). No celular: WhatsApp > Aparelhos conectados > Conectar.
   Se aparecer `Client outdated (405)` no lugar do QR, a pasta está com a versão antiga: rode
   `git pull && ./instalar.sh` e depois `./bridge.sh` de novo.
3. Confirme que pareou: existe `whatsapp-mcp/whatsapp-bridge/store/messages.db` e ele cresce.
4. A bridge baixa o histórico recente nos primeiros minutos. Espere uns 5 minutos.
5. Avise: essa conexão usa o WhatsApp Web (não é a API oficial). Funciona, mas não é para disparo
   em massa. A IA só RESPONDE quem chamou, que é uso normal.

## Passo 3 — Ensinar o negócio (negocio.md)
Entreviste o dono, uma pergunta por vez, e preencha `negocio.md`: o que vende, preços, formas de
pagamento, prazo/entrega, link de pagamento ou como fecha a venda, perguntas que mais chegam, o que
a IA nunca pode fazer e quando passar para humano. A IA SÓ fala o que estiver ali, então capriche.

## Passo 4 — Ensinar o jeito de falar (tom.md)
Leia as conversas reais no banco (só leitura) e tire as respostas que o dono/equipe mandaram:
```
sqlite3 whatsapp-mcp/whatsapp-bridge/store/messages.db \
 "SELECT chat_jid, timestamp, is_from_me, content FROM messages
  WHERE chat_jid NOT LIKE '%@g.us' AND content <> ''
  ORDER BY timestamp DESC LIMIT 600;"
```
Escolha 10 a 20 respostas dele que mostram o jeito (cumprimento, como passa preço, como fecha) e
cole em `tom.md`. Use também para achar as perguntas frequentes do passo 3. Não copie dado pessoal
de cliente para os arquivos.

## Passo 5 — Testar em sombra (não envia nada)
1. `config.env` já vem com `MODO=sombra`.
2. Teste numa conversa real: `python3 agente.py --teste <jid>` (pegue um jid de cliente na consulta
   acima). Mostre ao dono o que a IA responderia. Ajuste `negocio.md`/`tom.md` até ele aprovar.
3. Faça isso com 5 a 10 conversas diferentes (cliente perguntando preço, pedindo desconto, mandando
   comprovante, mandando áudio).

## Passo 6 — Ao vivo só com o número de teste
1. Em `config.env`: `MODO=ao_vivo`, `SO_ESTES=<outro número do dono, com DDI>`,
   `AVISAR_DONO=<número do dono>`.
2. Peça para ele fechar o `./bridge.sh` (Ctrl+C) e rode `./ligar-automatico.sh`.
3. Ele manda mensagem do número de teste como se fosse cliente. Acompanhe `tail -f agente.log`.

## Passo 7 — Ligar para todo mundo
Apague o `SO_ESTES` (deixe vazio). Pronto. Se quiser só fora do expediente: `HORARIO=fora_expediente`.

## Depois de ligado (o dono vai pedir coisas assim)
- "A IA falou errado X" → corrigir `negocio.md` ou `tom.md` (não precisa reiniciar nada).
- "Mudou o preço/produto" → `negocio.md`.
- "Não quero que responda fulano" → `NUNCA_ESTES` no `config.env`.
- "Parou de responder" → `tail -50 agente.log` e `tail -50 bridge.log`. Bridge desconectada =
  rodar `./ligar-automatico.sh desligar`, `./bridge.sh` para parear de novo, e ligar de novo.
- "Desliga a IA" → `./ligar-automatico.sh desligar`, ou só `MODO=sombra` no `config.env`.
- Respondi à mão e a IA ficou quieta? É de propósito: fica `TRAVA_HUMANO_H` horas sem responder
  naquela conversa.

## Regras para você, assistente
- Nunca coloque `MODO=ao_vivo` sem o dono ter aprovado as respostas da sombra.
- Nunca envie mensagem pela bridge (`/api/send`) por conta própria durante a instalação.
- Não mexa na pasta `whatsapp-mcp/` além do que o `./instalar.sh` já faz.
