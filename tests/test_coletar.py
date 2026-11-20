import sys
import unittest
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))
import coletar as c  # noqa: E402

DPDF_HTML = """
<html><body><h1>Concurso DPDF oferta mais de 700 vagas com iniciais de R$ 11 mil</h1>
<p>Saiu o edital n.º 1 do concurso DPDF (Defensoria Pública do Distrito Federal) com abertura de 707 vagas,
entre imediatas e formação de cadastro reserva, para profissionais de nível superior.</p>
<p>O concurso público está sendo organizado pelo Instituto de Acesso à Educação, Capacitação Profissional e
Desenvolvimento Humano – Instituto ACCESS.</p>
<ul><li>Analista de Apoio à Assistência Judiciária (Direito e Legislação): exige o curso de graduação em Direito;</li>
<li>Analista de Apoio à Assistência Judiciária (Contabilidade): requer graduação em Ciências Contábeis;</li>
<li>Analista de Apoio à Assistência Judiciária – Informática (Redes): graduação em Tecnologia da Informação.</li></ul>
<p>A remuneração inicial ofertada aos profissionais é de R$ 11.514,95, mais auxílio-alimentação no valor mensal
de R$ 1.701,41, para atuação em jornadas semanais de 35 horas.</p>
<p>As inscrições no concurso DPDF deverão ser realizadas de maneira online, a partir de 3 de dezembro de 2026,
e seguirão até a data provável de 7 de janeiro de 2026, por meio do site do Instituto ACCESS.</p>
<p>Para confirmar o pedido de inscrição, será preciso pagar uma taxa no valor de R$ 110,00.</p>
<p>Todos os candidatos serão avaliados por meio de prova objetiva e discursiva, que serão aplicadas na data
provável de 21 de fevereiro de 2027.</p>
<p>Comunicar erro</p><p>Leia também: IGESDF abre vagas com inscrições até 30 de dezembro de 2026</p>
</body></html>
"""


class Datas(unittest.TestCase):
    def test_mesmo_mes(self):
        f = "Os editais 120/2026 e 121/2026 recebem inscrições de 9 a 18 de novembro de 2026."
        self.assertEqual(c.intervalo(f, 2026), (date(2026, 11, 9), date(2026, 11, 18)))

    def test_meses_diferentes(self):
        f = "As inscrições vão de 15 de outubro a 17 de novembro de 2026."
        self.assertEqual(c.intervalo(f, 2026), (date(2026, 10, 15), date(2026, 11, 17)))

    def test_virada_de_ano_sem_ano_no_inicio(self):
        f = "Inscrições de 20 de dezembro a 10 de janeiro de 2027."
        self.assertEqual(c.intervalo(f, 2026), (date(2026, 12, 20), date(2027, 1, 10)))

    def test_apenas_fim(self):
        f = "As inscrições seguem abertas até 22 de julho de 2026."
        self.assertEqual(c.intervalo(f, 2026), (None, date(2026, 7, 22)))

    def test_apenas_inicio(self):
        f = "As inscrições começam em 3 de dezembro de 2026."
        self.assertEqual(c.intervalo(f, 2026), (date(2026, 12, 3), None))

    def test_ano_errado_no_fim_e_corrigido(self):
        f = "a partir de 3 de dezembro de 2026, e seguirão até a data provável de 7 de janeiro de 2026"
        self.assertEqual(c.intervalo(f, 2026), (date(2026, 12, 3), date(2027, 1, 7)))

    def test_sem_data(self):
        self.assertEqual(c.intervalo("Sem datas por aqui.", 2026), (None, None))


class Campos(unittest.TestCase):
    def test_org_do_titulo(self):
        self.assertEqual(c.org_do_titulo("Concurso DPDF oferta mais de 700 vagas com iniciais de R$ 11 mil"), "DPDF")
        self.assertEqual(c.org_do_titulo("IGESDF (DF) divulga novos editais de seletivo"), "IGESDF")
        self.assertEqual(c.org_do_titulo("Câmara dos Deputados publica edital de concurso com 184 vagas"), "Câmara dos Deputados")
        self.assertEqual(c.org_do_titulo("Processo seletivo ABDI (DF) abre 180 vagas com ganhos de R$ 16 mil"), "ABDI")

    def test_links_de_materias(self):
        pagina = ('<a href="https://concursosnobrasil.com/concursos/df/2026/11/10/igesdf-divulga-seis/">x</a>'
                  '<a href="https://concursosnobrasil.com/concursos/df/2026/11/10/igesdf-divulga-seis/">x</a>'
                  '<a href="https://concursosnobrasil.com/concursos/df/brasilia/">cidade</a>')
        self.assertEqual(len(c.links_de_materias(pagina)), 1)

    def test_data_da_url(self):
        self.assertEqual(c.data_da_url("https://x.com/concursos/df/2026/10/26/abc/"), date(2026, 10, 26))


class Ajustes(unittest.TestCase):
    def test_estagio_e_ignorado(self):
        self.assertTrue(c.TITULO_IGNORAR.search("DF: ANCINE abre seletivo com cadastro reserva para estágio de nível superior"))
        self.assertTrue(c.TITULO_IGNORAR.search("Órgão abre vagas para estagiários"))
        self.assertFalse(c.TITULO_IGNORAR.search("Concurso DPDF oferta mais de 700 vagas com iniciais de R$ 11 mil"))

    def test_org_com_verbo_autorizado(self):
        self.assertEqual(c.org_do_titulo("IBRAM DF é autorizado com 100 vagas para Analista e Técnico"), "IBRAM DF")

    def test_cargo_do_titulo(self):
        self.assertEqual(c.cargo_do_titulo("IBRAM DF é autorizado com 100 vagas para Analista e Técnico"), "Analista e Técnico")
        self.assertEqual(c.cargo_do_titulo("Concurso X abre 50 vagas para Auditor com salários de até R$ 20 mil"), "Auditor")
        titulo = "Câmara dos Deputados publica edital de concurso com 184 vagas e iniciais de R$ 32 mil"
        self.assertEqual(c.cargo_do_titulo(titulo), titulo)

    def test_reprocessar_item_antigo(self):
        antigo = {"org": "IBRAM DF é autorizado com 100 vagas para Analista e Técnico",
                  "cargo": "IBRAM DF é autorizado com 100 vagas para Analista e Técnico", "publicado": "2026-11-17"}
        novo = c.reprocessar(dict(antigo))
        self.assertEqual((novo["org"], novo["cargo"]), ("IBRAM DF", "Analista e Técnico"))
        estagio = {"cargo": "DF: ANCINE abre seletivo com cadastro reserva para estágio de nível superior"}
        self.assertTrue(c.reprocessar(estagio).get("descartar"))


class Fontes(unittest.TestCase):
    def test_links_nacionais_e_regionais(self):
        pagina = ('<a href="https://concursosnobrasil.com/concursos/2026/11/12/ministerio-da-saude-abre/">a</a>'
                  '<a href="https://concursosnobrasil.com/concursos/df/2026/11/10/igesdf-divulga/">b</a>')
        links = c.links_de_materias(pagina)
        self.assertEqual(len(links), 2)
        self.assertTrue(c.eh_regional(links[1]))
        self.assertFalse(c.eh_regional(links[0]))

    def test_mencao_ao_df(self):
        self.assertTrue(c.RE_MENCAO_DF.search("Os candidatos atuarão em Brasília (DF) ou Goiânia"))
        self.assertTrue(c.RE_MENCAO_DF.search("vagas no Distrito Federal"))
        self.assertFalse(c.RE_MENCAO_DF.search("Prefeitura de Pilar do Sul abre vagas em São Paulo"))

    def test_esfera_nacional(self):
        url = "https://concursosnobrasil.com/concursos/2026/11/12/ministerio-da-saude-abre/"
        item = c.montar_item(url, "Ministério da Saúde abre processo seletivo com 759 vagas", "Vagas em Brasília.", date(2026, 11, 12))
        self.assertIn("Nacional", item["esfera"])


class Qualidade(unittest.TestCase):
    def test_nacional_de_outro_estado_nao_entra(self):
        self.assertFalse(c.relevante_nacional("MGS (MG) abre 643 vagas e oferece remuneração de até R$ 4,5 mil", "Vagas em Brasília e BH"))

    def test_nacional_com_brasilia_entra(self):
        self.assertTrue(c.relevante_nacional("Ministério da Saúde abre processo seletivo", "Vagas em Brasília, Goiânia e Recife."))
        self.assertFalse(c.relevante_nacional("Prefeitura abre vagas", "Vagas em Campinas."))

    def test_reprocessar_descarta_outro_estado(self):
        item = {"link": "https://concursosnobrasil.com/concursos/2026/10/21/mgs/", "cargo": "MGS (MG) abre 643 vagas"}
        self.assertTrue(c.reprocessar(item).get("descartar"))

    def test_duplicado_mesmo_orgao_e_prazo(self):
        manuais = [{"org": "Rede SARAH · Editais 13 e 14/2026", "ini": "2026-11-23", "fim": "2026-12-17"},
                   {"org": "Controladoria-Geral da União (CGU)", "fim": "2026-11-04"},
                   {"org": "IGESDF · Edital 120/2026", "ini": "2026-11-09", "fim": "2026-11-18"}]
        self.assertTrue(c.duplicado({"org": "Rede SARAH", "ini": "2026-11-23", "fim": "2026-12-17"}, manuais))
        self.assertTrue(c.duplicado({"org": "CGU", "ini": "2026-10-10"}, manuais))  # sem fim: considera repetido
        # novo edital do mesmo órgão com outro prazo não é repetido
        self.assertFalse(c.duplicado({"org": "IGESDF", "ini": "2026-11-20", "fim": "2026-11-30"}, manuais))
        self.assertFalse(c.duplicado({"org": "Órgão novo", "fim": "2026-11-30"}, manuais))


class Avisos(unittest.TestCase):
    HOJE = date(2026, 11, 18)
    A = {"id": "a", "org": "Órgão A", "cargo": "Cargo & Cia", "ini": "2026-11-10", "fim": "2026-11-21", "vagas": "10", "sal": "R$ 5.000,00"}
    B = {"id": "b", "org": "Órgão B", "fim": "2026-11-19"}
    P = {"id": "p", "org": "Previsto", "tipo": "previsto"}

    def test_sem_historico_nao_avisa(self):
        self.assertEqual(c.avisos_do_dia(None, [self.A], self.HOJE, False), [])

    def test_novo_concurso(self):
        av = c.avisos_do_dia({"b"}, [self.A, self.B], self.HOJE, False)
        self.assertEqual([i["id"] for _, i, _x in av], ["a"])
        self.assertEqual(av[0][0], "Novo concurso no radar")

    def test_novo_previsto(self):
        av = c.avisos_do_dia(set(), [self.P], self.HOJE, False)
        self.assertEqual(av[0][0], "Previsto")

    def test_lembretes_so_no_agendamento(self):
        base = {"a", "b", "p"}
        self.assertEqual(c.avisos_do_dia(base, [self.A, self.B], self.HOJE, False), [])
        av = c.avisos_do_dia(base, [self.A, self.B, self.P], self.HOJE, True)
        self.assertEqual([(m, i["id"]) for m, i, _x in av],
                         [("Inscrições terminam em 3 dias", "a"), ("Inscrições terminam em 1 dia", "b")])

    def test_texto_escapa_html_e_tem_link(self):
        t = c.texto_aviso(self.A, "Novo concurso no radar")
        self.assertIn("Cargo &amp; Cia", t)
        self.assertIn("Inscrições: 10/11/2026 a 21/11/2026", t)
        self.assertTrue(t.endswith("#concurso=a"))


class Materia(unittest.TestCase):
    def setUp(self):
        titulo, texto = c.para_texto(DPDF_HTML)
        url = "https://concursosnobrasil.com/concursos/df/2026/10/26/concurso-dpdf-oferta/"
        self.item = c.montar_item(url, titulo, texto, date(2026, 10, 26))

    def test_corpo_ignora_relacionadas(self):
        _, texto = c.para_texto(DPDF_HTML)
        self.assertNotIn("30 de dezembro", texto)

    def test_campos(self):
        i = self.item
        self.assertEqual(i["org"], "DPDF")
        self.assertEqual(i["vagas"], "707 vagas")
        self.assertEqual(i["sal"], "R$ 11.514,95")
        self.assertAlmostEqual(i["salN"], 11514.95)
        self.assertEqual(i["taxa"], "R$ 110,00")
        self.assertEqual(i["banca"], "Instituto ACCESS")
        self.assertEqual(i["nivel"], ["superior"])
        self.assertEqual((i["ini"], i["fim"]), ("2026-12-03", "2027-01-07"))
        self.assertEqual(i["prova"], "21/02/2027 (data provável)")
        self.assertEqual(i["provaData"], "2027-02-21")
        for area in ("Jurídica", "Contabilidade", "TI"):
            self.assertIn(area, i["area"])
        self.assertTrue(i["auto"])


class Validade(unittest.TestCase):
    def test_encerrado_antigo_vence(self):
        item = {"fim": "2026-08-01", "publicado": "2026-07-01"}
        self.assertTrue(c.vencido(item, date(2026, 11, 17)))

    def test_encerrado_com_prova_futura_fica(self):
        item = {"fim": "2026-08-01", "provaData": "2027-01-17", "publicado": "2026-07-01"}
        self.assertFalse(c.vencido(item, date(2026, 11, 17)))

    def test_sem_prazo_vence_em_45_dias(self):
        self.assertFalse(c.vencido({"publicado": "2026-11-01"}, date(2026, 11, 17)))
        self.assertTrue(c.vencido({"publicado": "2026-09-01"}, date(2026, 11, 17)))


class Mudancas(unittest.TestCase):
    HOJE = date(2026, 11, 19)
    A0 = {"id": "a", "org": "A", "fim": "2026-11-20", "vagas": "10 vagas"}

    def test_prazo_prorrogado_e_detectado(self):
        novo = dict(self.A0, fim="2026-11-27")
        m = c.detectar_mudancas([self.A0], [novo])
        self.assertEqual(m, [{"id": "a", "campo": "fim", "de": "2026-11-20", "para": "2026-11-27"}])

    def test_valor_que_sumiu_nao_conta(self):
        novo = {"id": "a", "org": "A", "fim": "2026-11-20"}
        self.assertEqual(c.detectar_mudancas([self.A0], [novo]), [])

    def test_dado_que_passou_a_existir_conta(self):
        antes = {"id": "a", "org": "A"}
        m = c.detectar_mudancas([antes], [self.A0])
        self.assertEqual({x["campo"] for x in m}, {"fim", "vagas"})
        self.assertTrue(all(x["de"] is None for x in m))

    def test_item_novo_nao_e_mudanca(self):
        self.assertEqual(c.detectar_mudancas([], [self.A0]), [])

    def test_registro_nao_repete_e_vence(self):
        m = [{"id": "a", "campo": "fim", "de": "x", "para": "y"}]
        guardadas, novas = c.registrar_mudancas({}, m, {"a"}, self.HOJE)
        self.assertEqual(len(novas), 1)
        guardadas, novas = c.registrar_mudancas(guardadas, m, {"a"}, self.HOJE)
        self.assertEqual(novas, [])
        self.assertEqual(len(guardadas["a"]), 1)
        depois, _ = c.registrar_mudancas(guardadas, [], {"a"}, date(2026, 12, 20))
        self.assertEqual(depois, {})
        sumido, _ = c.registrar_mudancas(guardadas, [], set(), self.HOJE)
        self.assertEqual(sumido, {})

    def test_aviso_de_mudanca(self):
        novo = dict(self.A0, fim="2026-11-27")
        m = [{"id": "a", "campo": "fim", "de": "2026-11-20", "para": "2026-11-27"}]
        av = c.avisos_do_dia({"a"}, [novo], self.HOJE, False, m)
        self.assertEqual(av[0][0], "Concurso atualizado")
        self.assertIn("20/11/2026 → 27/11/2026", av[0][2])
        self.assertIn("20/11/2026 → 27/11/2026", c.texto_aviso(novo, av[0][0], av[0][2]))


class Historico(unittest.TestCase):
    HOJE = date(2026, 11, 19)

    def test_arquiva_so_encerrados_com_prazo(self):
        itens = [
            {"id": "x", "org": "X", "fim": "2026-11-01", "vagas": "5 vagas"},
            {"id": "y", "org": "Y", "fim": "2026-12-01"},
            {"id": "z", "org": "Z", "tipo": "previsto"},
            {"id": "w", "org": "W"},
        ]
        h = c.arquivar({}, itens, self.HOJE)
        self.assertEqual(list(h), ["x"])
        self.assertEqual(h["x"]["vagas"], "5 vagas")

    def test_lista_do_site(self):
        auto = {"x": {"id": "x", "org": "IGESDF · Edital 99/2026", "fim": "2026-11-01"}}
        manual = [{"k": ["pcdf"], "org": "PCDF", "ano": 2014}]
        lista = c.historico_para_site(manual, auto)
        self.assertEqual(lista[0]["org"], "PCDF")
        self.assertEqual(lista[1]["k"], ["igesdf"])
        self.assertEqual(lista[1]["ano"], 2026)

    def test_arquivo_manual_do_repositorio_e_valido(self):
        import json
        lista = json.loads((c.HIST_MANUAL).read_text(encoding="utf-8"))
        self.assertGreater(len(lista), 3)
        for h in lista:
            self.assertTrue(h["k"] and h["org"] and h["ano"] and h["link"], h)


class LeituraIA(unittest.TestCase):
    PUB = date(2026, 11, 10)
    TEXTO = ("A Defensoria abre 707 vagas. As inscrições vão de 3 de dezembro a 7 de janeiro de 2027, "
             "pelo Instituto ACCESS. Remuneração de R$ 11.514,95. Taxa de R$ 110,00. Prova em 21 de fevereiro de 2027.")

    def ia(self, **extra):
        base = {"relevante_df": True, "inscricao_inicio": "2026-12-03", "inscricao_fim": "2027-01-07",
                "prova_data": "2027-02-21", "vagas": "707 vagas", "salario": 11514.95, "taxa": 110,
                "banca": "Instituto ACCESS", "nivel": ["superior"], "area": ["Jurídica"],
                "cargo": "analista de apoio", "orgao": "Defensoria"}
        base.update(extra)
        return base

    def test_resposta_correta_passa(self):
        v = c.validar_ia(self.ia(), self.TEXTO, self.PUB)
        self.assertEqual((v["ini"], v["fim"], v["provaData"]), ("2026-12-03", "2027-01-07", "2027-02-21"))
        self.assertEqual(v["vagas"], "707 vagas")
        self.assertEqual(v["sal"], "R$ 11.514,95")
        self.assertEqual(v["taxa"], "R$ 110,00")
        self.assertEqual(v["cargo"], "Analista de apoio")

    def test_data_inventada_e_descartada(self):
        v = c.validar_ia(self.ia(inscricao_fim="2027-01-15"), self.TEXTO, self.PUB)
        self.assertNotIn("fim", v)
        self.assertEqual(v["ini"], "2026-12-03")

    def test_valores_que_nao_estao_no_texto_sao_descartados(self):
        v = c.validar_ia(self.ia(vagas="900 vagas", salario=99999.0, banca="Cebraspe"), self.TEXTO, self.PUB)
        for campo in ("vagas", "sal", "banca"):
            self.assertNotIn(campo, v)

    def test_lixo_e_ignorado(self):
        self.assertIsNone(c.validar_ia("texto solto", self.TEXTO, self.PUB))
        v = c.validar_ia(self.ia(nivel=["doutorado"], area=["Magia"], inscricao_inicio="ontem"), self.TEXTO, self.PUB)
        for campo in ("nivel", "area", "ini"):
            self.assertNotIn(campo, v)

    def test_inicio_depois_do_fim_descarta_o_par(self):
        v = c.validar_ia(self.ia(inscricao_inicio="2027-01-07", inscricao_fim="2026-12-03"), self.TEXTO, self.PUB)
        self.assertNotIn("ini", v)
        self.assertNotIn("fim", v)

    def test_nao_relevante(self):
        self.assertFalse(c.validar_ia(self.ia(relevante_df=False), self.TEXTO, self.PUB)["relevante_df"])

    def test_sem_chave_nao_chama_e_usa_regras(self):
        import os
        antigo = os.environ.pop("ANTHROPIC_API_KEY", None)
        try:
            self.assertIsNone(c.ler_com_ia("t", self.TEXTO, self.PUB))
        finally:
            if antigo:
                os.environ["ANTHROPIC_API_KEY"] = antigo

    def test_com_chave_usa_ia_e_erro_cai_nas_regras(self):
        import os
        os.environ["ANTHROPIC_API_KEY"] = "teste"
        original = c.chamar_ia
        try:
            c.chamar_ia = lambda t, x, k: self.ia()
            self.assertEqual(c.ler_com_ia("t", self.TEXTO, self.PUB)["fim"], "2027-01-07")

            def falha(t, x, k):
                raise OSError("sem rede")
            c.chamar_ia = falha
            self.assertIsNone(c.ler_com_ia("t", self.TEXTO, self.PUB))
        finally:
            c.chamar_ia = original
            del os.environ["ANTHROPIC_API_KEY"]

    def test_item_montado_com_ia_marca_lido(self):
        ia = c.validar_ia(self.ia(), self.TEXTO, self.PUB)
        item = c.montar_item("https://concursosnobrasil.com/concursos/df/2026/11/10/x/", "DPDF abre vagas",
                             self.TEXTO, self.PUB, ia)
        self.assertEqual(item["lido"], "ia")
        self.assertEqual(item["fim"], "2027-01-07")
        sem = c.montar_item("https://concursosnobrasil.com/concursos/df/2026/11/10/x/", "DPDF abre vagas",
                            self.TEXTO, self.PUB)
        self.assertNotIn("lido", sem)

    def test_data_no_texto(self):
        self.assertTrue(c.data_no_texto(date(2026, 11, 9), "inscrições de 9 a 18 de novembro"))
        self.assertTrue(c.data_no_texto(date(2026, 11, 18), "inscrições de 9 a 18 de novembro"))
        self.assertTrue(c.data_no_texto(date(2026, 11, 9), "até 09/11/2026"))
        self.assertFalse(c.data_no_texto(date(2026, 11, 10), "inscrições de 9 a 18 de novembro"))
        self.assertTrue(c.data_no_texto(date(2026, 3, 5), "dia 5 de março"))


class Releitura(unittest.TestCase):
    def test_texto_mudou_atualiza_prazo(self):
        hoje = date(2026, 11, 19)
        url = "https://concursosnobrasil.com/concursos/df/2026/11/10/x/"
        antigo_html = "<h1>DPDF abre vagas</h1><p>As inscrições vão de 3 a 20 de novembro de 2026.</p>"
        novo_html = "<h1>DPDF abre vagas</h1><p>As inscrições vão de 3 a 30 de novembro de 2026, prorrogadas.</p>"
        _, texto = c.para_texto(antigo_html)
        item = c.montar_item(url, "DPDF abre vagas", texto, date(2026, 11, 10))
        cache = {url: item}
        original, pausa = c.baixar, c.time.sleep
        c.time.sleep = lambda s: None
        try:
            c.baixar = lambda u: antigo_html
            c.reler(cache, hoje)
            self.assertEqual(cache[url]["fim"], "2026-11-20")
            c.baixar = lambda u: novo_html
            c.reler(cache, hoje)
            self.assertEqual(cache[url]["fim"], "2026-11-30")
            c.baixar = lambda u: "<h1>DPDF abre vagas</h1><p>Texto sem datas nenhumas.</p>"
            c.reler(cache, hoje)
            self.assertEqual(cache[url]["fim"], "2026-11-30")  # não perde o que já sabia
        finally:
            c.baixar, c.time.sleep = original, pausa

    def test_item_antigo_sem_hash_so_marca(self):
        hoje = date(2026, 11, 19)
        url = "https://concursosnobrasil.com/concursos/df/2026/11/10/x/"
        cache = {url: {"publicado": "2026-11-10", "fim": "2026-11-25", "org": "X"}}
        original, pausa = c.baixar, c.time.sleep
        c.time.sleep = lambda s: None
        try:
            c.baixar = lambda u: "<h1>X abre vagas</h1><p>inscrições até 30 de novembro de 2026.</p>"
            c.reler(cache, hoje)
            self.assertEqual(cache[url]["fim"], "2026-11-25")
            self.assertIn("h", cache[url])
        finally:
            c.baixar, c.time.sleep = original, pausa


if __name__ == "__main__":
    unittest.main()
