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
( cd whatsapp-mcp/whatsapp-bridge && go build -o whatsapp-bridge . )

[ -f config.env ] || cp config.env.exemplo config.env
if ! command -v claude >/dev/null && command -v codex >/dev/null; then
  sed -i.bak 's/^MOTOR=.*/MOTOR=codex/' config.env && rm -f config.env.bak
fi
chmod +x bridge.sh ligar-automatico.sh agente.py

echo
echo "Pronto. Próximo passo: ./bridge.sh  (mostra o QR Code; escaneie em WhatsApp > Aparelhos conectados)"
