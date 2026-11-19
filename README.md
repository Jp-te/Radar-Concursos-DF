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

## O que o site tem

- **Filtros:** situação, escolaridade, área ou formação, faixa de salário, busca por órgão, cargo ou banca, e ordenação por prazo ou salário.
- **Fecham nos próximos 7 dias:** faixa no topo com o que está acabando.
- **Calendário:** visão mensal com abertura de inscrições, fim das inscrições e provas. Clique em um dia para ver só os eventos dele.
- **Página de cada concurso:** endereço `#concurso=ID`, com cronograma, informações, o que conferir no edital e links. O endereço pode ser compartilhado.
- **Compartilhar e lembrar:** botão de WhatsApp, copiar link e "Adicionar ao calendário" (arquivo .ics com lembrete um dia antes).
- **Confiança nos dados:** selo "Conferido em dd/mm" em cada item, link do edital oficial quando cadastrado e status da última coleta no rodapé.

## Instalar como app no celular

O site é um app instalável (PWA) e funciona sem internet, mostrando os últimos dados carregados.

- **Android (Chrome):** abra o site, toque no botão **Instalar o app** que aparece no topo (ou no menu ⋮ → Instalar app).
- **iPhone (Safari):** toque em **Compartilhar** e escolha **Adicionar à Tela de Início**.
- **Computador (Chrome ou Edge):** clique no ícone de instalar na barra de endereço.

Quando você publicar uma versão nova do site, o app pega a versão nova na próxima vez que abrir com internet. Se mudar o `sw.js`, troque o texto de `VERSAO` nele (por exemplo `radar-v2`) para limpar os arquivos guardados.

## Avisos no Telegram (opcional)

O robô pode avisar quando um concurso novo entra na lista e lembrar 3 dias, 1 dia e no último dia de inscrição.

1. No Telegram, converse com o **@BotFather**, envie `/newbot` e siga as perguntas. Ele devolve um **token** (guarde em segredo).
2. Crie um **canal** público (por exemplo `Radar Concursos DF`), adicione o bot como **administrador** com permissão de publicar mensagens.
3. O identificador do canal é `@nome_do_canal` (o nome do link público).
4. No repositório do GitHub, abra **Settings → Secrets and variables → Actions → New repository secret** e crie dois segredos: `TELEGRAM_BOT_TOKEN` (o token) e `TELEGRAM_CHAT_ID` (por exemplo `@radar_concursos_df`).
5. Em `data/manual.json`, preencha `"telegram": "https://t.me/nome_do_canal"` para o site mostrar o botão "Receber avisos no Telegram".

Sem os dois segredos, nada é enviado e o resto funciona normalmente.

## Endereço próprio (opcional)

1. Registre um domínio (por exemplo em registro.br).
2. Em **Settings → Pages → Custom domain**, digite o domínio e salve. O GitHub cria o arquivo `CNAME` sozinho.
3. No painel do domínio, aponte o DNS conforme a tela do GitHub (registros A ou CNAME) e marque **Enforce HTTPS**.
4. Troque `https://radarconcursosdf.github.io/` pelo novo endereço em `docs/index.html` (tags `og:url` e `og:image`) e em `SITE_URL` no `scripts/coletar.py`.

## Como funciona

| Arquivo | Para que serve |
| --- | --- |
| `data/manual.json` | Concursos que você mantém à mão: previstos, editais que o coletor não entende bem, correções. Campos úteis: `conferido` (data da última conferência), `edital` (link oficial), `telegram` (link do canal). |
| `scripts/coletar.py` | Lê as matérias novas de concursos do DF, extrai prazo, vagas, salário, banca, escolaridade e área, e grava em `data/auto.json`. |
| `data/auto.json` | Memória do coletor entre as execuções (o robô atualiza). |
| `docs/dados.json` | Resultado final que o site lê (manual + automático). |
| `docs/index.html` | O site. Calcula situação e contagem de dias com a data de quem abre. |
| `docs/manifest.webmanifest`, `docs/sw.js`, `docs/icon-*.png` | Fazem o site virar app instalável e abrir offline. |
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

- **Fonte única:** a coleta lê o portal Concursos no Brasil (seção do DF e matérias nacionais que citam Brasília ou o DF). Se o portal mudar o endereço ou o layout, o coletor não acha matérias novas. O workflow continua funcionando, mas aparece um aviso amarelo na execução.
- **Uma matéria, um item:** quando uma matéria trata de vários editais (como as do IGESDF), o item automático pega só o primeiro prazo. Para detalhar, cadastre cada edital em `manual.json` e oculte a matéria.
- **Extração por regras:** funciona bem para textos no padrão "inscrições de 9 a 18 de novembro de 2026". Frases fora desse padrão ficam sem data e o item aparece em "Prazo a confirmar".
- **Respeito ao site de origem:** o coletor lê poucas páginas por dia, com pausa entre elas e identificação própria. Não aumente a frequência sem necessidade.
- **Previstos:** não são coletados sozinhos. Vêm de `manual.json` (LDO 2027 e projetos de orçamento).

## Ideias para evoluir

- Trocar a extração por regras por uma chamada a um modelo de linguagem para ler cada matéria, guardando a chave como *secret* do repositório.
- Acrescentar outras fontes em `LISTAGENS` (por exemplo, páginas de bancas como Cebraspe e Quadrix) com leitores próprios.
- Avisar por e-mail ou Telegram quando um concurso novo aparecer.
