#!/usr/bin/env python3
"""IA de atendimento no WhatsApp: uma rodada.

Lê as mensagens novas no banco da bridge (whatsapp-mcp), decide com o Claude Code ou o Codex
o que responder e, no modo ao_vivo, envia pela bridge. No modo sombra só escreve o que mandaria
em sombra/AAAA-MM-DD.md, para você conferir antes de ligar.

Roda a cada minuto (ver ligar-automatico.sh). Uma rodada por vez (trava em .lock).

Uso:
    python3 agente.py              # uma rodada
    python3 agente.py --teste JID  # roda só para esse chat, ignorando data e trava (sempre em sombra)
"""
import datetime as dt
import json
import os
import re
import shutil
import sqlite3
import subprocess
import sys
import time
import urllib.request
from pathlib import Path

RAIZ = Path(__file__).resolve().parent
LOG = RAIZ / "agente.log"
ESTADO = RAIZ / "estado.json"
TRAVA = RAIZ / ".lock"


# ---------------------------------------------------------------- config
def carregar_config():
    cfg = {
        "MODO": "sombra",                 # sombra | ao_vivo
        "MOTOR": "claude",                # claude | codex
        "MODELO": "",                     # vazio = padrão do motor (ex.: sonnet)
        "BANCO": str(RAIZ / "whatsapp-mcp/whatsapp-bridge/store/messages.db"),
        "BRIDGE_URL": "http://localhost:8080",
        "ESPERA_MIN": "1",                # minutos de silêncio antes de responder
        "IDADE_MAX_H": "6",               # mensagem mais velha que isso não é respondida
        "TRAVA_HUMANO_H": "12",           # alguém respondeu à mão? a IA fica quieta nesse chat por X h
        "HISTORICO_MSGS": "40",           # quantas mensagens da conversa a IA lê
        "HORARIO": "sempre",              # sempre | fora_expediente
        "EXPEDIENTE_INICIO": "09:00",
        "EXPEDIENTE_FIM": "18:00",
        "EXPEDIENTE_DIAS": "1,2,3,4,5",   # 1=segunda ... 7=domingo
        "SO_ESTES": "",                   # teste: só responde esses números/JIDs (vírgula). Vazio = todos
        "NUNCA_ESTES": "",                # nunca responde esses números/JIDs (família, fornecedor...)
        "AVISAR_DONO": "",                # número que recebe o aviso quando a IA passa para humano
    }
    arq = RAIZ / "config.env"
    if arq.exists():
        for linha in arq.read_text(encoding="utf-8").splitlines():
            linha = linha.strip()
            if not linha or linha.startswith("#") or "=" not in linha:
                continue
            k, v = linha.split("=", 1)
            cfg[k.strip()] = v.strip().strip('"').strip("'")
    return cfg


def log(msg):
    with LOG.open("a", encoding="utf-8") as f:
        f.write(f"[{dt.datetime.now():%Y-%m-%d %H:%M:%S}] {msg}\n")


def lista(valor):
    out = set()
    for item in valor.split(","):
        item = re.sub(r"\D", "", item) if "@" not in item else item.strip()
        if item:
            out.add(item)
    return out


def bate(jid, conjunto):
    """JID bate com a lista se for igual ou se o número (só dígitos) for igual."""
    return jid in conjunto or jid.split("@")[0] in conjunto


# ---------------------------------------------------------------- tempo
def agora():
    return dt.datetime.now().astimezone()


def fmt(t):
    """Mesmo formato que a bridge grava: 2026-11-08 11:41:00-03:00 (comparável como texto)."""
    s = t.strftime("%Y-%m-%d %H:%M:%S%z")
    return s[:-2] + ":" + s[-2:]


def dentro_do_horario(cfg):
    if cfg["HORARIO"] == "sempre":
        return True
    t = agora()
    dias = {int(d) for d in cfg["EXPEDIENTE_DIAS"].split(",") if d.strip()}
    ini = dt.time.fromisoformat(cfg["EXPEDIENTE_INICIO"])
    fim = dt.time.fromisoformat(cfg["EXPEDIENTE_FIM"])
    no_expediente = t.isoweekday() in dias and ini <= t.time() < fim
    return not no_expediente  # fora_expediente: a IA só atende quando a equipe não está


# ---------------------------------------------------------------- estado
def ler_estado():
    if ESTADO.exists():
        try:
            return json.loads(ESTADO.read_text(encoding="utf-8"))
        except Exception:
            pass
    return {}


def salvar_estado(e):
    tmp = ESTADO.with_suffix(".tmp")
    tmp.write_text(json.dumps(e, ensure_ascii=False, indent=1), encoding="utf-8")
    tmp.replace(ESTADO)


def normal(txt):
    return re.sub(r"\s+", " ", (txt or "")).strip().lower()


# ---------------------------------------------------------------- banco
def conectar(cfg):
    con = sqlite3.connect(f"file:{cfg['BANCO']}?mode=ro", uri=True, timeout=5)
    con.row_factory = sqlite3.Row
    return con


INDIVIDUAL = ("chat_jid NOT LIKE '%@g.us' AND chat_jid NOT LIKE '%@newsletter' "
              "AND chat_jid NOT LIKE 'status@%' AND chat_jid NOT LIKE '%@broadcast'")


def candidatos(con, desde, ate):
    """Chats individuais com mensagem nova do cliente cuja ÚLTIMA mensagem é do cliente."""
    sql = f"""
      SELECT m.chat_jid FROM messages m
      WHERE m.is_from_me = 0 AND m.timestamp > ? AND m.timestamp <= ? AND {INDIVIDUAL}
        AND (SELECT x.is_from_me FROM messages x WHERE x.chat_jid = m.chat_jid
             ORDER BY x.timestamp DESC LIMIT 1) = 0
      GROUP BY m.chat_jid"""
    return [r[0] for r in con.execute(sql, (desde, ate))]


def conversa(con, jid, n):
    rows = con.execute(
        "SELECT timestamp, is_from_me, content, media_type FROM messages "
        "WHERE chat_jid = ? ORDER BY timestamp DESC LIMIT ?", (jid, n)).fetchall()
    return list(reversed(rows))


def nome_do_chat(con, jid):
    try:
        r = con.execute("SELECT name FROM chats WHERE jid = ?", (jid,)).fetchone()
        return (r[0] if r and r[0] else "") or jid.split("@")[0]
    except Exception:
        return jid.split("@")[0]


def humano_respondeu(rows, enviados, horas):
    """Mensagem nossa nas últimas X h que a IA não mandou = alguém da equipe respondeu à mão."""
    limite = fmt(agora() - dt.timedelta(hours=horas))
    meus = {normal(t) for t in enviados}
    for r in rows:
        if r["is_from_me"] and r["timestamp"] >= limite and normal(r["content"]) and normal(r["content"]) not in meus:
            return True
    return False


def transcricao(rows):
    linhas = []
    for r in rows:
        quem = "NÓS" if r["is_from_me"] else "CLIENTE"
        txt = (r["content"] or "").strip()
        if r["media_type"]:
            rotulo = {"audio": "áudio", "image": "imagem", "video": "vídeo", "document": "documento"}.get(
                r["media_type"], r["media_type"])
            txt = f"[mandou {rotulo}]" + (f" {txt}" if txt else "")
        if txt:
            linhas.append(f"[{str(r['timestamp'])[:16]}] {quem}: {txt}")
    return "\n".join(linhas)


# ---------------------------------------------------------------- IA
def montar_prompt(nome, texto):
    partes = [(RAIZ / "prompt.md").read_text(encoding="utf-8")]
    for arq in ("negocio.md", "tom.md"):
        p = RAIZ / arq
        if p.exists():
            partes.append(f"\n\n=== {arq} ===\n" + p.read_text(encoding="utf-8"))
    partes.append(f"\n\n=== AGORA ===\n{agora():%A, %d/%m/%Y %H:%M}")
    partes.append(f"\n\n=== CONVERSA COM {nome} (mais antiga em cima) ===\n{texto}")
    partes.append("\n\nResponda SOMENTE com o JSON pedido, sem nada antes ou depois.")
    return "".join(partes)


def chamar_ia(cfg, prompt):
    if cfg["MOTOR"] == "codex":
        saida = RAIZ / ".codex-saida.txt"
        cmd = ["codex", "exec", "--skip-git-repo-check", "--ephemeral", "-s", "read-only",
               "-o", str(saida)]
        if cfg["MODELO"]:
            cmd += ["-m", cfg["MODELO"]]
        cmd.append("-")
        subprocess.run(cmd, input=prompt, text=True, capture_output=True, timeout=300, cwd=RAIZ)
        bruto = saida.read_text(encoding="utf-8") if saida.exists() else ""
    else:
        cmd = ["claude", "-p", "--tools", "", "--no-session-persistence", "--output-format", "text"]
        cmd += ["--model", cfg["MODELO"] or "sonnet"]
        r = subprocess.run(cmd, input=prompt, text=True, capture_output=True, timeout=300, cwd=RAIZ)
        bruto = r.stdout
    ini, fim = bruto.find("{"), bruto.rfind("}")
    if ini < 0 or fim < 0:
        raise ValueError(f"IA não devolveu JSON: {bruto[:300]!r}")
    return json.loads(bruto[ini:fim + 1])


# ---------------------------------------------------------------- envio
def enviar(cfg, destino, texto):
    req = urllib.request.Request(
        cfg["BRIDGE_URL"].rstrip("/") + "/api/send",
        data=json.dumps({"recipient": destino, "message": texto}).encode(),
        headers={"Content-Type": "application/json"}, method="POST")
    with urllib.request.urlopen(req, timeout=30) as resp:
        return resp.status == 200


def anotar_sombra(nome, jid, decisao):
    pasta = RAIZ / "sombra"
    pasta.mkdir(exist_ok=True)
    with (pasta / f"{agora():%Y-%m-%d}.md").open("a", encoding="utf-8") as f:
        f.write(f"\n## {agora():%H:%M} · {nome} ({jid})\n")
        f.write(f"Ação: {decisao.get('acao')} · Motivo: {decisao.get('motivo', '')}\n\n")
        for m in decisao.get("mensagens") or []:
            f.write(f"> {m}\n\n")


# ---------------------------------------------------------------- rodada
def atender(cfg, con, estado, jid, forcar_sombra=False):
    rows = conversa(con, jid, int(cfg["HISTORICO_MSGS"]))
    nome = nome_do_chat(con, jid)
    enviados = estado.setdefault("enviados", {}).setdefault(jid, [])
    texto = transcricao(rows)
    if not texto:
        return
    decisao = chamar_ia(cfg, montar_prompt(nome, texto))
    acao = decisao.get("acao")
    msgs = [m.strip() for m in (decisao.get("mensagens") or []) if m and m.strip()][:3]
    sombra = forcar_sombra or cfg["MODO"] != "ao_vivo"
    log(f"{nome} ({jid}): {acao} — {decisao.get('motivo', '')}{' [sombra]' if sombra else ''}")

    if sombra:
        anotar_sombra(nome, jid, decisao)
        return

    if acao == "responder" and msgs:
        for i, m in enumerate(msgs):
            enviados.append(m)          # antes de enviar: o eco não pode parecer resposta humana
            del enviados[:-30]
            salvar_estado(estado)
            if i:
                time.sleep(2)
            enviar(cfg, jid, m)
    if acao == "passar_humano":
        estado.setdefault("com_humano", {})[jid] = fmt(agora())
        if msgs:
            enviados.append(msgs[0])
            salvar_estado(estado)
            enviar(cfg, jid, msgs[0])
        if cfg["AVISAR_DONO"]:
            numero = jid.split("@")[0]
            enviar(cfg, cfg["AVISAR_DONO"],
                   f"🙋 A IA passou um atendimento pra você\n{nome} ({numero})\nMotivo: {decisao.get('motivo', '')}")
    salvar_estado(estado)


def rodada(cfg):
    if not Path(cfg["BANCO"]).exists():
        log(f"banco da bridge não existe ({cfg['BANCO']}): a bridge já foi pareada?")
        return
    estado = ler_estado()
    teto = fmt(agora() - dt.timedelta(minutes=float(cfg["ESPERA_MIN"])))
    piso = fmt(agora() - dt.timedelta(hours=float(cfg["IDADE_MAX_H"])))
    desde = max(estado.get("ultimo", piso), piso)

    if not dentro_do_horario(cfg):
        estado["ultimo"] = teto        # horário da equipe: o que chegou é dela
        salvar_estado(estado)
        return

    so, nunca = lista(cfg["SO_ESTES"]), lista(cfg["NUNCA_ESTES"])
    trava_h = float(cfg["TRAVA_HUMANO_H"])
    con = conectar(cfg)
    try:
        for jid in candidatos(con, desde, teto):
            if so and not bate(jid, so):
                continue
            if nunca and bate(jid, nunca):
                continue
            entregue = estado.get("com_humano", {}).get(jid)
            if entregue and entregue >= fmt(agora() - dt.timedelta(hours=trava_h)):
                continue
            rows = conversa(con, jid, int(cfg["HISTORICO_MSGS"]))
            if trava_h and humano_respondeu(rows, estado.get("enviados", {}).get(jid, []), trava_h):
                continue
            try:
                atender(cfg, con, estado, jid)
            except Exception as e:
                log(f"erro no chat {jid}: {e}")
    finally:
        con.close()
    estado["ultimo"] = teto
    salvar_estado(estado)


def main():
    cfg = carregar_config()
    if cfg["MOTOR"] not in ("claude", "codex") or not shutil.which(cfg["MOTOR"]):
        log(f"motor '{cfg['MOTOR']}' não encontrado no PATH")
        sys.exit(1)

    if len(sys.argv) == 3 and sys.argv[1] == "--teste":
        con = conectar(cfg)
        estado = ler_estado()
        atender(cfg, con, estado, sys.argv[2], forcar_sombra=True)
        print((RAIZ / "sombra" / f"{agora():%Y-%m-%d}.md").read_text(encoding="utf-8")[-3000:])
        return

    # trava: uma rodada por vez; trava de processo morto é reaproveitada
    try:
        TRAVA.mkdir()
    except FileExistsError:
        pid = (TRAVA / "pid").read_text().strip() if (TRAVA / "pid").exists() else ""
        velha = time.time() - TRAVA.stat().st_mtime > 3600
        vivo = False
        if pid.isdigit():
            try:
                os.kill(int(pid), 0)
                vivo = True
            except OSError:
                pass
        if vivo and not velha:
            return
        shutil.rmtree(TRAVA, ignore_errors=True)
        TRAVA.mkdir()
    (TRAVA / "pid").write_text(str(os.getpid()))
    try:
        rodada(cfg)
    finally:
        shutil.rmtree(TRAVA, ignore_errors=True)


if __name__ == "__main__":
    main()
