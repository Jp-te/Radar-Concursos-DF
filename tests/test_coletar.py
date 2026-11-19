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


class Avisos(unittest.TestCase):
    HOJE = date(2026, 11, 18)
    A = {"id": "a", "org": "Órgão A", "cargo": "Cargo & Cia", "ini": "2026-11-10", "fim": "2026-11-21", "vagas": "10", "sal": "R$ 5.000,00"}
    B = {"id": "b", "org": "Órgão B", "fim": "2026-11-19"}
    P = {"id": "p", "org": "Previsto", "tipo": "previsto"}

    def test_sem_historico_nao_avisa(self):
        self.assertEqual(c.avisos_do_dia(None, [self.A], self.HOJE, False), [])

    def test_novo_concurso(self):
        av = c.avisos_do_dia({"b"}, [self.A, self.B], self.HOJE, False)
        self.assertEqual([i["id"] for _, i in av], ["a"])
        self.assertEqual(av[0][0], "Novo concurso no radar")

    def test_novo_previsto(self):
        av = c.avisos_do_dia(set(), [self.P], self.HOJE, False)
        self.assertEqual(av[0][0], "Previsto")

    def test_lembretes_so_no_agendamento(self):
        base = {"a", "b", "p"}
        self.assertEqual(c.avisos_do_dia(base, [self.A, self.B], self.HOJE, False), [])
        av = c.avisos_do_dia(base, [self.A, self.B, self.P], self.HOJE, True)
        self.assertEqual([(m, i["id"]) for m, i in av],
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


if __name__ == "__main__":
    unittest.main()
