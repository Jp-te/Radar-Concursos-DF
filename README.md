# Radar Concursos DF

Site que acompanha os concursos abertos, em breve e previstos no Distrito Federal, com filtro por escolaridade, área e situação. Uma rotina diária no GitHub Actions procura matérias novas, atualiza os dados e republica o site no GitHub Pages. Não precisa de servidor nem de custo.

## Como colocar no ar

1. Crie um repositório vazio no GitHub (por exemplo `radar-concursos-df`) e, nesta pasta, rode:

   ```bash
   git init -b main
   git add .
   git commit -m "Radar Concursos DF"
   git remote add origin git@github.com:SEU_USUARIO/radar-concursos-df.git
   git push -u origin main
   ```

2. No GitHub, abra **Settings → Pages** e em **Source** escolha **GitHub Actions**.
3. Abra a aba **Actions**, escolha **Atualizar e publicar** e clique em **Run workflow**. Em um ou dois minutos o endereço do site aparece no resumo da execução (algo como `https://SEU_USUARIO.github.io/radar-concursos-df/`).

Depois disso ele roda sozinho todo dia às 6h (horário de Brasília) e a cada `push`.

## Como funciona

| Arquivo | Para que serve |
| --- | --- |
| `data/manual.json` | Concursos que você mantém à mão: previstos da LDO, editais que o coletor não entende bem, correções. |
| `scripts/coletar.py` | Lê as matérias novas de concursos do DF, extrai prazo, vagas, salário, banca, escolaridade e área, e grava em `data/auto.json`. |
| `data/auto.json` | Memória do coletor entre as execuções (o robô atualiza). |
| `docs/dados.json` | Resultado final que o site lê (manual + automático). |
| `docs/index.html` | O site. Calcula situação e contagem de dias com a data de quem abre. |
| `.github/workflows/atualizar.yml` | Agendamento diário, testes, coleta e publicação. |

O que aparece no site com o selo **Detectado automaticamente** foi extraído do texto de uma matéria por regras simples. Ele traz o link da matéria, mas confira sempre no edital.

## O que você precisa manter

- **Previstos e itens importantes:** edite `data/manual.json`. Cada item segue o mesmo formato dos que já estão lá (`org`, `cargo`, `nivel`, `area`, `ini`, `fim`, `vagas`, `sal`, `link`...). Para um previsto, use `"tipo": "previsto"`.
- **Evitar duplicidade:** se você cadastrar à mão um concurso que o coletor também acha, coloque o link da matéria em `ocultar_urls` dentro de `manual.json`.
- **Encerrados:** saem do site 60 dias depois do fim da inscrição, ou depois da prova, se ela ainda for futura.

## Testar no computador

```bash
python3 -m unittest discover -s tests     # testes do coletor
python3 scripts/coletar.py --offline      # regenera dados.json sem internet
python3 scripts/coletar.py                # coleta de verdade
python3 -m http.server -d docs            # abre em http://localhost:8000
```

## Limites que valem saber

- **Fonte única:** a coleta lê a seção de Distrito Federal do portal Concursos no Brasil. Se o portal mudar o endereço ou o layout, o coletor não acha matérias novas. O workflow continua funcionando, mas aparece um aviso amarelo na execução.
- **Uma matéria, um item:** quando uma matéria trata de vários editais (como as do IGESDF), o item automático pega só o primeiro prazo. Para detalhar, cadastre cada edital em `manual.json` e oculte a matéria.
- **Extração por regras:** funciona bem para textos no padrão "inscrições de 9 a 18 de novembro de 2026". Frases fora desse padrão ficam sem data e o item aparece em "Prazo a confirmar".
- **Respeito ao site de origem:** o coletor lê poucas páginas por dia, com pausa entre elas e identificação própria. Não aumente a frequência sem necessidade.
- **Previstos:** não são coletados sozinhos. Vêm de `manual.json` (LDO 2027 e projetos de orçamento).

## Ideias para evoluir

- Trocar a extração por regras por uma chamada a um modelo de linguagem para ler cada matéria, guardando a chave como *secret* do repositório.
- Acrescentar outras fontes em `LISTAGENS` (por exemplo, páginas de bancas como Cebraspe e Quadrix) com leitores próprios.
- Avisar por e-mail ou Telegram quando um concurso novo aparecer.

