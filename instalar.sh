#!/bin/bash
# Instala a bridge do WhatsApp (whatsapp-mcp, código aberto) e prepara a config.
set -euo pipefail
cd "$(dirname "$0")"

falta=()
command -v git >/dev/null     || falta+=(git)
command -v go >/dev/null      || falta+=(go)
command -v python3 >/dev/null || falta+=(python3)
if [ ${#falta[@]} -gt 0 ]; then
  echo "Falta instalar: ${falta[*]}"
  if [ "$(uname)" = "Darwin" ]; then
    echo "No Mac:   brew install ${falta[*]}   (sem Homebrew? https://brew.sh)"
  else
    echo "No Linux: sudo apt install -y ${falta[*]/go/golang}"
  fi
  exit 1
fi
if ! command -v claude >/dev/null && ! command -v codex >/dev/null; then
  echo "Aviso: não achei nem 'claude' (Claude Code) nem 'codex' (ChatGPT) no PATH."
  echo "  Claude Code: npm install -g @anthropic-ai/claude-code   (e rode 'claude' uma vez para logar)"
  echo "  Codex:       npm install -g @openai/codex               (e rode 'codex' uma vez para logar)"
fi

if [ ! -d whatsapp-mcp ]; then
  git clone --depth 1 https://github.com/lharries/whatsapp-mcp.git
fi
# O whatsapp-mcp original fixa um whatsmeow de 03/2025, que o WhatsApp recusa com
# "Client outdated (405)" e o QR Code nunca aparece. Atualiza para uma versão testada
# (12/11/2026) e ajusta as 5 chamadas que passaram a pedir context. Pode rodar de novo à vontade.
WHATSMEOW_VERSAO="v0.0.0-20261110152934-c88388f983b4"
(
  cd whatsapp-mcp/whatsapp-bridge
  if ! grep -q "whatsmeow $WHATSMEOW_VERSAO" go.mod; then
    go get "go.mau.fi/whatsmeow@$WHATSMEOW_VERSAO"
    go mod tidy
  fi
  if ! grep -q 'sqlstore.New(context.Background()' main.go; then
    sed -i.bak \
      -e 's/client\.Download(/client.Download(context.Background(), /' \
      -e 's/sqlstore\.New("sqlite3"/sqlstore.New(context.Background(), "sqlite3"/' \
      -e 's/container\.GetFirstDevice()/container.GetFirstDevice(context.Background())/' \
      -e 's/client\.GetGroupInfo(/client.GetGroupInfo(context.Background(), /' \
      -e 's/client\.Store\.Contacts\.GetContact(/client.Store.Contacts.GetContact(context.Background(), /' \
      main.go && rm -f main.go.bak
  fi
  go build -o whatsapp-bridge .
)

[ -f config.env ] || cp config.env.exemplo config.env
if ! command -v claude >/dev/null && command -v codex >/dev/null; then
  sed -i.bak 's/^MOTOR=.*/MOTOR=codex/' config.env && rm -f config.env.bak
fi
chmod +x bridge.sh ligar-automatico.sh agente.py

echo
echo "Pronto. Próximo passo: ./bridge.sh  (mostra o QR Code; escaneie em WhatsApp > Aparelhos conectados)"
