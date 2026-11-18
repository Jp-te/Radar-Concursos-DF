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
]
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
    r"gabarito|resultado|convoca|retifica|nomea|homologa|aprovados|prorroga|cronograma|local de prova",
    re.I,
)
VERBOS = (r"publica|divulga|abre|lança|lanca|oferta|oferece|disponibiliza|tem|terá|autoriza|"
          r"anuncia|libera|confirma|inicia|recebe|seleciona|reabre")


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
        "org": org_do_titulo(titulo),
        "cargo": titulo,
        "esfera": "Distrito Federal",
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
    for m in re.finditer(r"https://concursosnobrasil\.com/concursos/df/\d{4}/\d{2}/\d{2}/[a-z0-9\-]+/?", texto):
        u = m.group(0)
        if not u.endswith("/"):
            u += "/"
        if u not in vistos:
            vistos.add(u)
            saida.append(u)
    return saida


def coletar(cache, ocultar, hoje):
    candidatos, falhas = [], 0
    for pagina in LISTAGENS:
        try:
            candidatos += links_de_materias(baixar(pagina))
        except Exception as e:  # rede, bloqueio, página mudou
            falhas += 1
            print(f"::warning::Não consegui abrir {pagina}: {e}")
        time.sleep(1)
    if falhas == len(LISTAGENS):
        print("::warning::Nenhuma listagem respondeu; mantendo os dados já coletados.")
        return
    novos = []
    for u in dict.fromkeys(candidatos):
        d = data_da_url(u)
        if u in cache or u in ocultar or not d or (hoje - d).days > JANELA_DIAS:
            continue
        novos.append((d, u))
    novos.sort(reverse=True)
    for d, u in novos[:MAX_ARTIGOS]:
        try:
            titulo, texto = para_texto(baixar(u))
        except Exception as e:
            print(f"::warning::Falha ao ler {u}: {e}")
            continue
        time.sleep(1)
        if not titulo or not TITULO_VALIDO.search(titulo) or TITULO_IGNORAR.search(titulo):
            cache[u] = {"ignorado": True, "publicado": d.isoformat()}  # não olhar de novo
            continue
        cache[u] = montar_item(u, titulo, texto, d)
        print("novo:", cache[u]["org"], "|", cache[u].get("fim", "sem prazo"))


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


def carregar_json(caminho, padrao):
    try:
        return json.loads(caminho.read_text(encoding="utf-8"))
    except (FileNotFoundError, json.JSONDecodeError):
        return padrao


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--offline", action="store_true", help="não acessa a internet")
    args = ap.parse_args()

    hoje = datetime.now(timezone(timedelta(hours=-3))).date()
    manual = carregar_json(MANUAL, {"concursos": [], "ocultar_urls": []})
    cache = carregar_json(CACHE, {})

    if not args.offline:
        coletar(cache, set(manual.get("ocultar_urls", [])), hoje)

    cache = {u: i for u, i in cache.items() if not vencido(i, hoje)}
    auto = [i for i in cache.values() if not i.get("ignorado")]

    saida = {
        "atualizado": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "concursos": manual.get("concursos", []) + auto,
    }
    SAIDA.parent.mkdir(parents=True, exist_ok=True)
    SAIDA.write_text(json.dumps(saida, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    CACHE.write_text(json.dumps(cache, ensure_ascii=False, indent=1, sort_keys=True) + "\n", encoding="utf-8")
    print(f"dados.json: {len(manual.get('concursos', []))} manuais + {len(auto)} automáticos")


if __name__ == "__main__":
    sys.exit(main())
