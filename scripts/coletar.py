#!/usr/bin/env python3
"""Coleta concursos do DF e gera docs/dados.json.

Fluxo:
  1. Lê data/manual.json (itens curados à mão, como os previstos da LDO).
  2. Procura matérias novas sobre concursos do DF e extrai prazo, vagas, salário etc.
  3. Guarda o que achou em data/auto.json, para não perder entre execuções.
  4. Junta tudo em docs/dados.json, que o site lê.

Usa só a biblioteca padrão do Python. Com --offline não acessa a internet e só
regenera o dados.json a partir dos arquivos locais.
"""
import argparse
import hashlib
import html
import json
import re
import sys
import time
import urllib.request
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
MANUAL = RAIZ / "data" / "manual.json"
CACHE = RAIZ / "data" / "auto.json"
SAIDA = RAIZ / "docs" / "dados.json"

# Páginas que listam as matérias recentes sobre concursos do DF.
LISTAGENS = [
    "https://concursosnobrasil.com/concursos/df/",
    "https://concursosnobrasil.com/concursos/df/feed/",
    # Matérias nacionais (ministérios, agências): só entram se citarem Brasília ou o DF.
    "https://concursosnobrasil.com/concursos/",
]
SITE_URL = "https://radarconcursosdf.github.io/"
RE_MENCAO_DF = re.compile(r"bras[ií]lia|distrito federal|\(DF\)|\bDF\b", re.I)
RE_MENCAO_DF_NACIONAL = re.compile(r"bras[ií]lia|distrito federal|\(DF\)", re.I)
# Título com outro estado entre parênteses, como "MGS (MG)", indica concurso de fora do DF.
RE_OUTRA_UF = re.compile(r"\((AC|AL|AP|AM|BA|CE|ES|GO|MA|MT|MS|MG|PA|PB|PR|PE|PI|RJ|RN|RS|RO|RR|SC|SP|SE|TO)\)")


def relevante_nacional(titulo, texto):
    """Matéria nacional só interessa se citar Brasília ou o DF e não for de outro estado."""
    if RE_OUTRA_UF.search(titulo):
        return False
    return bool(RE_MENCAO_DF_NACIONAL.search(titulo + " " + texto))
UA = "RadarConcursosDF/1.0 (projeto pessoal de acompanhamento de concursos)"
MAX_ARTIGOS = 20      # limite de matérias novas por execução
JANELA_DIAS = 120     # ignora matérias mais antigas que isso
VALIDADE_ENCERRADO = 60  # dias que um concurso encerrado continua no arquivo

MESES = {
    "janeiro": 1, "fevereiro": 2, "março": 3, "marco": 3, "abril": 4, "maio": 5,
    "junho": 6, "julho": 7, "agosto": 8, "setembro": 9, "outubro": 10,
    "novembro": 11, "dezembro": 12,
}
MES = "(" + "|".join(MESES) + ")"
DIA = r"(?<!\d)(\d{1,2})(?!\d)\s*(?:º|°)?"
ANO = r"(?:\s+de\s+(\d{4}))?"
RE_P1 = re.compile(rf"{DIA}\s*(?:a|à|até|e)\s*{DIA}\s+de\s+{MES}{ANO}", re.I)
RE_P2 = re.compile(rf"{DIA}\s+de\s+{MES}{ANO}\s*(?:a|à|até)\s*{DIA}\s+de\s+{MES}{ANO}", re.I)
RE_UNICA = re.compile(rf"{DIA}\s+de\s+{MES}{ANO}", re.I)
RE_REAL = re.compile(r"R\$\s?(\d{1,3}(?:\.\d{3})*,\d{2})")

BANCAS = [
    "Cebraspe", "Cespe", "Quadrix", "FGV", "FCC", "Vunesp", "Fundatec", "IBFC",
    "Idecan", "Cesgranrio", "FAURGS", "Instituto ACCESS", "Instituto AOCP",
    "FAPETEC", "Consulplan", "IADES",
]
AREAS = [
    ("Saúde", r"médic|enfermeir|saúde|hospital|farmác|fisioterap|odont|nutricion|psicólog"),
    ("TI", r"tecnologia da informação|analista de ti|desenvolvimento de sistemas|banco de dados|programador"),
    ("Jurídica", r"direito|defensoria|procurador|tribunal de justiça|jurídic|juiz|magistrat|advogad"),
    ("Controle e fiscal", r"tribunal de contas|auditor|fiscal|controladoria|tributár"),
    ("Contabilidade", r"contabil|contábil|ciências contábeis"),
    ("Educação", r"professor|educação|magistério|pedagog|escola"),
    ("Segurança", r"polícia|policial|bombeiro|penal|segurança pública"),
    ("Legislativo", r"câmara dos deputados|câmara legislativa|legislativ|senado"),
    ("Engenharia e transporte", r"engenh|estradas|trânsito|transporte|metrô"),
    ("Assistência social", r"assistência social|desenvolvimento social"),
]
TITULO_VALIDO = re.compile(r"concurso|seletivo|edital|vagas|inscri", re.I)
TITULO_IGNORAR = re.compile(
    r"gabarito|resultado|convoca|retifica|nomea|homologa|aprovados|prorroga|cronograma|local de prova"
    r"|est[aá]gio|estagi[aá]ri",
    re.I,
)
VERBOS = (r"publica|divulga|abre|lança|lanca|oferta|oferece|disponibiliza|tem|terá|autoriza|"
          r"anuncia|libera|confirma|inicia|recebe|seleciona|reabre|é autorizad[oa]|autorizad[oa]|aprova|prevê")


# ---------------------------------------------------------------- rede

def baixar(url):
    req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept-Language": "pt-BR"})
    with urllib.request.urlopen(req, timeout=25) as r:
        return r.read().decode("utf-8", errors="replace")


# ---------------------------------------------------------------- texto

def para_texto(html_bruto):
    """Devolve (titulo, texto do corpo) de uma página de matéria."""
    m = re.search(r"<h1[^>]*>(.*?)</h1>", html_bruto, re.S | re.I)
    titulo = ""
    if m:
        titulo = html.unescape(re.sub(r"<[^>]+>", "", m.group(1))).strip()
        html_bruto = html_bruto[m.end():]
    fim = html_bruto.find("Comunicar erro")
    if fim > 0:
        html_bruto = html_bruto[:fim]
    # quebra de linha dentro do HTML é só espaço; parágrafo é só o que vem de tag
    html_bruto = re.sub(r"\s+", " ", html_bruto)
    t = re.sub(r"<(script|style)[^>]*>.*?</\1>", " ", html_bruto, flags=re.S | re.I)
    t = re.sub(r"</?(p|br|li|h[1-6]|div|tr)[^>]*>", "\n", t, flags=re.I)
    t = re.sub(r"<[^>]+>", " ", t)
    t = html.unescape(t)
    t = re.sub(r"[ \t\xa0]+", " ", t)
    t = re.sub(r"\n\s*\n+", "\n", t).strip()
    return titulo, t


def frases(texto):
    return [f.strip() for f in re.split(r"(?<=[.!?;])\s+|\n+", texto) if f.strip()]


def _data(dia, mes, ano):
    try:
        return date(ano, MESES[mes.lower()], int(dia))
    except (ValueError, KeyError):
        return None


# ---------------------------------------------------------------- datas

def intervalo(frase, ano_ref):
    """Extrai (início, fim) de uma frase como 'de 9 a 18 de novembro de 2026'."""
    ini = fim = None
    m = RE_P2.search(frase)
    if m:
        d1, m1, a1, d2, m2, a2 = m.groups()
        ano_fim = int(a2 or a1 or ano_ref)
        ano_ini = int(a1 or ano_fim)
        ini, fim = _data(d1, m1, ano_ini), _data(d2, m2, ano_fim)
        if ini and fim and ini > fim and not a1:
            ini = _data(d1, m1, ano_fim - 1)
    else:
        m = RE_P1.search(frase)
        if m:
            d1, d2, mes, a = m.groups()
            ano = int(a or ano_ref)
            ini, fim = _data(d1, mes, ano), _data(d2, mes, ano)
        else:
            achados = list(RE_UNICA.finditer(frase))
            if not achados:
                return None, None
            anos = [int(x.group(3)) if x.group(3) else None for x in achados]
            proximo = ano_ref
            for i in range(len(anos) - 1, -1, -1):  # completa anos que faltam, da direita p/ esquerda
                if anos[i] is None:
                    anos[i] = proximo
                proximo = anos[i]
            datas = [_data(x.group(1), x.group(2), anos[i]) for i, x in enumerate(achados)]
            datas = [d for d in datas if d]
            if len(datas) >= 2:
                ini, fim = datas[0], datas[-1]
            elif len(datas) == 1:
                antes = frase[max(0, achados[0].start() - 30):achados[0].start()].lower()
                if re.search(r"partir|começ|inici|abrem|abertura", antes):
                    ini = datas[0]
                else:
                    fim = datas[0]
    # corrige erro de digitação de ano (fim antes do início por mais de 6 meses)
    if ini and fim and fim < ini and (ini - fim).days > 180:
        fim = fim.replace(year=fim.year + 1)
    return ini, fim


def achar_inscricoes(texto, ano_ref):
    for f in frases(texto):
        if re.search(r"inscri", f, re.I) and (RE_UNICA.search(f) or RE_P1.search(f)):
            ini, fim = intervalo(f, ano_ref)
            if ini or fim:
                return ini, fim
    return None, None


def achar_prova(texto, ano_ref):
    for f in frases(texto):
        if re.search(r"\bprovas?\b", f, re.I) and not re.search(r"inscri", f, re.I) and RE_UNICA.search(f):
            m = RE_UNICA.search(f)
            ano = int(m.group(3)) if m.group(3) else ano_ref
            d = _data(m.group(1), m.group(2), ano)
            if d:
                provavel = re.search(r"provável|prevista|previsto|previstas", f, re.I)
                txt = d.strftime("%d/%m/%Y") + (" (data provável)" if provavel else "")
                return txt, d
    return None, None


# ---------------------------------------------------------------- campos

def moeda_para_numero(s):
    return float(s.replace(".", "").replace(",", "."))


def achar_valor(texto, palavras):
    for f in frases(texto):
        if re.search(palavras, f, re.I):
            m = RE_REAL.search(f)
            if m:
                return "R$ " + m.group(1), moeda_para_numero(m.group(1))
    return None, None


def achar_vagas(titulo, texto):
    # o corpo vem primeiro: o título costuma arredondar ("mais de 700 vagas")
    for fonte in (texto, titulo):
        for m in re.finditer(r"(\d{1,3}(?:\.\d{3})*)\s+vagas", fonte, re.I):
            if re.search(r"mais de\s*$", fonte[max(0, m.start() - 10):m.start()], re.I):
                continue
            return m.group(1) + " vagas"
    if re.search(r"cadastro (de )?reserva", texto, re.I):
        return "Cadastro reserva"
    return None


def achar_nivel(texto):
    t = texto.lower()
    out = []
    if re.search(r"nível médio|nivel medio|ensino médio", t):
        out.append("medio")
    if re.search(r"nível técnico|curso técnico|ensino técnico", t):
        out.append("tecnico")
    if re.search(r"nível superior|nivel superior|graduação|ensino superior", t):
        out.append("superior")
    return out


def achar_areas(titulo, texto):
    base = (titulo + " " + texto[:2500]).lower()
    achadas = [nome for nome, rx in AREAS if re.search(rx, base)]
    return achadas[:3] or ["Outras"]


def achar_banca(texto):
    for b in BANCAS:
        if re.search(rf"\b{re.escape(b)}\b", texto, re.I):
            return b
    return None


def org_do_titulo(titulo):
    t = re.sub(r"^(DF:\s*)", "", titulo.strip())
    t = re.sub(r"^(Concurso|Processo seletivo|Seletivo)\s+", "", t, flags=re.I)
    esquerda = re.split(rf"\s+(?:{VERBOS})\b", t, maxsplit=1, flags=re.I)[0].strip()
    esquerda = re.sub(r"\s*\((DF|Distrito Federal)\)", "", esquerda).strip()
    return esquerda or titulo


def cargo_do_titulo(titulo):
    """Tenta pegar os cargos do título ("... 100 vagas para Analista e Técnico")."""
    m = re.search(r"\bvagas?\s+(?:para|de|em|no|na)\s+(.+?)(?:\s+(?:com|e|,)\s+(?:sal[aá]rios?|ganhos|iniciais|remunera)|$)",
                  titulo, re.I)
    if m:
        cargo = m.group(1).strip(" ,.")
        if 3 <= len(cargo) <= 90:
            return cargo[0].upper() + cargo[1:]
    return titulo


def data_da_url(url):
    m = re.search(r"/(\d{4})/(\d{2})/(\d{2})/", url)
    return date(int(m.group(1)), int(m.group(2)), int(m.group(3))) if m else None


def montar_item(url, titulo, texto, publicado):
    ano_ref = publicado.year
    ini, fim = achar_inscricoes(texto, ano_ref)
    prova_txt, prova_dt = achar_prova(texto, ano_ref)
    sal, sal_n = achar_valor(texto, r"remunera|salário|vencimento|inicia(l|is)")
    taxa, _ = achar_valor(texto, r"taxa")
    item = {
        "id": "auto-" + hashlib.sha1(url.encode()).hexdigest()[:8],
        "auto": True,
        "titulo": titulo,
        "org": org_do_titulo(titulo),
        "cargo": cargo_do_titulo(titulo),
        "esfera": "Distrito Federal" if eh_regional(url) else "Nacional, com vagas em Brasília",
        "nivel": achar_nivel(texto),
        "area": achar_areas(titulo, texto),
        "banca": achar_banca(texto),
        "ini": ini.isoformat() if ini else None,
        "fim": fim.isoformat() if fim else None,
        "prova": prova_txt,
        "provaData": prova_dt.isoformat() if prova_dt else None,
        "vagas": achar_vagas(titulo, texto),
        "sal": sal,
        "salN": sal_n,
        "taxa": taxa,
        "link": url,
        "linkTxt": "Matéria com detalhes do edital",
        "publicado": publicado.isoformat(),
    }
    return {k: v for k, v in item.items() if v not in (None, "")}


# ---------------------------------------------------------------- coleta

def links_de_materias(texto):
    vistos, saida = set(), []
    for m in re.finditer(r"https://concursosnobrasil\.com/concursos/(?:df/)?\d{4}/\d{2}/\d{2}/[a-z0-9\-]+/?", texto):
        u = m.group(0)
        if not u.endswith("/"):
            u += "/"
        if u not in vistos:
            vistos.add(u)
            saida.append(u)
    return saida


def eh_regional(url):
    return "/concursos/df/" in url


def coletar(cache, ocultar, hoje):
    """Atualiza o cache. Devolve {"fontes": [{url, ok}], "novos": [urls]}."""
    candidatos, fontes = [], []
    for pagina in LISTAGENS:
        try:
            candidatos += links_de_materias(baixar(pagina))
            fontes.append({"url": pagina, "ok": True})
        except Exception as e:  # rede, bloqueio, página mudou
            fontes.append({"url": pagina, "ok": False})
            print(f"::warning::Não consegui abrir {pagina}: {e}")
        time.sleep(1)
    if not any(f["ok"] for f in fontes):
        print("::warning::Nenhuma listagem respondeu; mantendo os dados já coletados.")
        return {"fontes": fontes, "novos": []}
    pendentes = []
    for u in dict.fromkeys(candidatos):
        d = data_da_url(u)
        if u in cache or u in ocultar or not d or (hoje - d).days > JANELA_DIAS:
            continue
        pendentes.append((d, u))
    pendentes.sort(reverse=True)
    novos = []
    for d, u in pendentes[:MAX_ARTIGOS]:
        try:
            titulo, texto = para_texto(baixar(u))
        except Exception as e:
            print(f"::warning::Falha ao ler {u}: {e}")
            continue
        time.sleep(1)
        if not titulo or not TITULO_VALIDO.search(titulo) or TITULO_IGNORAR.search(titulo):
            cache[u] = {"ignorado": True, "publicado": d.isoformat()}  # não olhar de novo
            continue
        if not eh_regional(u) and not relevante_nacional(titulo, texto):
            cache[u] = {"ignorado": True, "publicado": d.isoformat()}  # nacional sem vagas no DF
            continue
        cache[u] = montar_item(u, titulo, texto, d)
        novos.append(u)
        print("novo:", cache[u]["org"], "|", cache[u].get("fim", "sem prazo"))
    return {"fontes": fontes, "novos": novos}


def vencido(item, hoje):
    pub = datetime.strptime(item["publicado"], "%Y-%m-%d").date() if item.get("publicado") else hoje
    if item.get("ignorado"):
        return (hoje - pub).days > JANELA_DIAS
    fim = item.get("fim")
    if fim:
        fim_d = datetime.strptime(fim, "%Y-%m-%d").date()
        prova = item.get("provaData")
        prova_futura = prova and datetime.strptime(prova, "%Y-%m-%d").date() >= hoje
        return (hoje - fim_d).days > VALIDADE_ENCERRADO and not prova_futura
    return (hoje - pub).days > 45


def _norm(txt):
    import unicodedata
    t = unicodedata.normalize("NFKD", txt or "").encode("ascii", "ignore").decode().lower()
    return re.sub(r"[^a-z0-9]+", " ", t).strip()


def duplicado(auto, manuais):
    """Item automático que repete um item cadastrado à mão: mesmo órgão e mesmo prazo (ou prazo desconhecido)."""
    org = _norm(auto.get("org"))
    if not org:
        return False
    for m in manuais:
        if org not in _norm(m.get("org")) and _norm(m.get("org")) not in org:
            continue
        if not auto.get("fim") or auto.get("fim") == m.get("fim") or (auto.get("ini") and auto.get("ini") == m.get("ini")):
            return True
    return False


def reprocessar(item):
    """Aplica as regras atuais a itens guardados por versões antigas do coletor."""
    if item.get("ignorado"):
        return item
    titulo = item.get("titulo") or item.get("cargo", "")
    if TITULO_IGNORAR.search(titulo):
        return {"descartar": True}
    if not eh_regional(item.get("link", "")) and RE_OUTRA_UF.search(titulo):
        return {"descartar": True}
    item["titulo"] = titulo
    item["org"] = org_do_titulo(titulo)
    item["cargo"] = cargo_do_titulo(titulo)
    return item


def carregar_json(caminho, padrao):
    try:
        return json.loads(caminho.read_text(encoding="utf-8"))
    except (FileNotFoundError, json.JSONDecodeError):
        return padrao


# ---------------------------------------------------------------- avisos

def _h(txt):
    return html.escape(str(txt), quote=False)


def texto_aviso(item, motivo):
    """Mensagem em HTML do Telegram para um concurso."""
    linhas = [f"<b>{_h(motivo)}</b>", f"{_h(item.get('org', ''))}"]
    if item.get("cargo"):
        linhas.append(_h(item["cargo"]))
    if item.get("ini") and item.get("fim"):
        linhas.append(f"Inscrições: {_br(item['ini'])} a {_br(item['fim'])}")
    elif item.get("fim"):
        linhas.append(f"Inscrições até {_br(item['fim'])}")
    if item.get("vagas"):
        linhas.append(f"Vagas: {_h(item['vagas'])}")
    if item.get("sal") and item["sal"] != "A definir":
        linhas.append(f"Salário: {_h(item['sal'])}")
    linhas.append(f"{SITE_URL}#concurso={item['id']}")
    return "\n".join(linhas)


def _br(iso):
    a, m, d = iso.split("-")
    return f"{d}/{m}/{a}"


def enviar_telegram(token, chat, texto):
    corpo = json.dumps({"chat_id": chat, "text": texto, "parse_mode": "HTML",
                        "disable_web_page_preview": False}).encode()
    req = urllib.request.Request(f"https://api.telegram.org/bot{token}/sendMessage", data=corpo,
                                 headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=20) as r:
        return r.status == 200


def avisos_do_dia(anteriores, atuais, hoje, enviar_lembretes):
    """Lista (motivo, item): concursos novos e, no agendamento diário, prazos que acabam logo."""
    saida = []
    if anteriores is not None:
        for i in atuais:
            if i["id"] not in anteriores:
                motivo = "Previsto" if i.get("tipo") == "previsto" else "Novo concurso no radar"
                saida.append((motivo, i))
    if enviar_lembretes:
        for i in atuais:
            if i.get("tipo") == "previsto" or not i.get("fim"):
                continue
            falta = (datetime.strptime(i["fim"], "%Y-%m-%d").date() - hoje).days
            if falta in (3, 1):
                saida.append((f"Inscrições terminam em {falta} {'dia' if falta == 1 else 'dias'}", i))
            elif falta == 0:
                saida.append(("Último dia de inscrição hoje", i))
    return saida[:12]


def notificar(avisos):
    import os
    token, chat = os.environ.get("TELEGRAM_BOT_TOKEN"), os.environ.get("TELEGRAM_CHAT_ID")
    if not avisos:
        return
    if not token or not chat:
        print(f"{len(avisos)} aviso(s) pendente(s), mas o Telegram não está configurado.")
        return
    for motivo, item in avisos:
        try:
            enviar_telegram(token, chat, texto_aviso(item, motivo))
            time.sleep(1)
        except Exception as e:
            print(f"::warning::Não consegui enviar o aviso de {item.get('org')}: {e}")


def main():
    import os
    ap = argparse.ArgumentParser()
    ap.add_argument("--offline", action="store_true", help="não acessa a internet")
    args = ap.parse_args()

    hoje = datetime.now(timezone(timedelta(hours=-3))).date()
    manual = carregar_json(MANUAL, {"concursos": [], "ocultar_urls": []})
    cache = carregar_json(CACHE, {})
    anterior = carregar_json(SAIDA, None)
    ids_anteriores = {c["id"] for c in anterior["concursos"]} if anterior else None
    coleta = (anterior or {}).get("coleta")

    if not args.offline:
        resultado = coletar(cache, set(manual.get("ocultar_urls", [])), hoje)
        coleta = {"quando": datetime.now(timezone.utc).isoformat(timespec="seconds"),
                  "fontes": resultado["fontes"], "novos": len(resultado["novos"])}

    cache = {u: reprocessar(i) for u, i in cache.items() if not vencido(i, hoje)}
    cache = {u: i for u, i in cache.items() if not i.get("descartar")}
    manuais = manual.get("concursos", [])
    auto = [i for i in cache.values() if not i.get("ignorado") and not duplicado(i, manuais)]
    todos = manuais + auto

    saida = {
        "atualizado": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "coleta": coleta,
        "concursos": todos,
    }
    if manual.get("telegram"):
        saida["telegram"] = manual["telegram"]  # link do canal, mostrado como botão no site
    SAIDA.parent.mkdir(parents=True, exist_ok=True)
    SAIDA.write_text(json.dumps(saida, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    CACHE.write_text(json.dumps(cache, ensure_ascii=False, indent=1, sort_keys=True) + "\n", encoding="utf-8")
    print(f"dados.json: {len(manual.get('concursos', []))} manuais + {len(auto)} automáticos")

    if not args.offline:
        agendado = os.environ.get("GITHUB_EVENT_NAME") == "schedule"
        notificar(avisos_do_dia(ids_anteriores, todos, hoje, agendado))


if __name__ == "__main__":
    sys.exit(main())
