#!/bin/bash
# Deixa a bridge e a IA rodando sozinhas (a IA roda a cada 1 minuto).
#   ./ligar-automatico.sh          liga
#   ./ligar-automatico.sh desligar desliga
# Pareie a bridge com ./bridge.sh ANTES (o QR Code só aparece no terminal).
set -euo pipefail
DIR="$(cd "$(dirname "$0")" && pwd)"
ACAO="${1:-ligar}"
PY="$(command -v python3)"
CAMINHO="$(dirname "$(command -v claude || command -v codex || echo /usr/local/bin/x)"):/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin"

if [ "$(uname)" = "Darwin" ]; then
  LA="$HOME/Library/LaunchAgents"; mkdir -p "$LA"
  B="$LA/com.ia-whatsapp.bridge.plist"; A="$LA/com.ia-whatsapp.agente.plist"
  launchctl unload "$B" 2>/dev/null || true
  launchctl unload "$A" 2>/dev/null || true
  if [ "$ACAO" = "desligar" ]; then rm -f "$B" "$A"; echo "Desligado."; exit 0; fi

  cat > "$B" <<EOF
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0"><dict>
  <key>Label</key><string>com.ia-whatsapp.bridge</string>
  <key>WorkingDirectory</key><string>$DIR/whatsapp-mcp/whatsapp-bridge</string>
  <key>ProgramArguments</key><array><string>$DIR/whatsapp-mcp/whatsapp-bridge/whatsapp-bridge</string></array>
  <key>RunAtLoad</key><true/><key>KeepAlive</key><true/>
  <key>StandardOutPath</key><string>$DIR/bridge.log</string>
  <key>StandardErrorPath</key><string>$DIR/bridge.log</string>
</dict></plist>
EOF
  cat > "$A" <<EOF
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0"><dict>
  <key>Label</key><string>com.ia-whatsapp.agente</string>
  <key>WorkingDirectory</key><string>$DIR</string>
  <key>ProgramArguments</key><array><string>$PY</string><string>$DIR/agente.py</string></array>
  <key>EnvironmentVariables</key><dict><key>PATH</key><string>$CAMINHO</string><key>HOME</key><string>$HOME</string></dict>
  <key>StartInterval</key><integer>60</integer>
  <key>StandardOutPath</key><string>$DIR/agente.out</string>
  <key>StandardErrorPath</key><string>$DIR/agente.out</string>
</dict></plist>
EOF
  launchctl load "$B"; launchctl load "$A"
  echo "Ligado no Mac (launchd). O Mac não pode dormir: Ajustes > Bateria/Energia > impedir repouso."
else
  LINHA_A="* * * * * cd $DIR && PATH=$CAMINHO $PY agente.py >> agente.out 2>&1"
  LINHA_B="@reboot cd $DIR/whatsapp-mcp/whatsapp-bridge && nohup ./whatsapp-bridge >> $DIR/bridge.log 2>&1 &"
  ATUAL="$(crontab -l 2>/dev/null | grep -v 'ia-whatsapp-atendimento\|whatsapp-bridge\|agente.py' || true)"
  if [ "$ACAO" = "desligar" ]; then
    printf '%s\n' "$ATUAL" | crontab -; pkill -f whatsapp-bridge || true; echo "Desligado."; exit 0
  fi
  printf '%s\n%s\n%s\n' "$ATUAL" "$LINHA_A" "$LINHA_B" | sed '/^$/d' | crontab -
  pgrep -f whatsapp-bridge >/dev/null || (cd "$DIR/whatsapp-mcp/whatsapp-bridge" && nohup ./whatsapp-bridge >> "$DIR/bridge.log" 2>&1 &)
  echo "Ligado no Linux (cron)."
fi
echo "Acompanhe: tail -f $DIR/agente.log"
