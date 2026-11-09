#!/bin/bash
# Sobe a bridge do WhatsApp. Na primeira vez mostra o QR Code: no celular, WhatsApp >
# Aparelhos conectados > Conectar um aparelho. Depois fica conectada sozinha.
# Deixe esta janela aberta (ou use ./ligar-automatico.sh, que sobe a bridge em segundo plano).
cd "$(dirname "$0")/whatsapp-mcp/whatsapp-bridge" || { echo "rode ./instalar.sh antes"; exit 1; }
exec ./whatsapp-bridge
