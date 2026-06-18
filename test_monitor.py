#!/usr/bin/env python3
"""Tests de non-regression pour la veille. Aucun reseau requis.
Lancer : python -m unittest -v
"""
import os
os.environ.setdefault("TELEGRAM_TOKEN", "test")
os.environ.setdefault("TELEGRAM_CHAT_ID", "test")

import unittest
import monitor as m

RULES = {
    "groupe_a": ["apl", "aide au logement", "taxe", "titre de sejour"],
    "groupe_b": ["etudiant", "etranger", "international"],
    "signaux": ["decret", "journal officiel", "entree en vigueur", "publie", "arrete"],
    "exclusions": ["sondage"],
}


class TestClassify(unittest.TestCase):
    def conf(self, title):
        ok, pr, lbl, c = m.classify(title, RULES)
        return c if ok else "HORS"

    def test_confirme(self):
        self.assertEqual(self.conf("APL etudiants etrangers : decret paru au journal officiel"), "confirme")

    def test_rumeur(self):
        self.assertEqual(self.conf("Le decret APL pour etudiants etrangers devrait paraitre"), "rumeur")

    def test_probable(self):
        self.assertEqual(self.conf("Decret APL etudiants etrangers : ce qui change"), "probable")

    def test_lie(self):
        self.assertEqual(self.conf("Les etudiants etrangers et l'aide au logement en debat"), "lie")

    def test_hors_sujet(self):
        self.assertEqual(self.conf("Hausse des APL pour tous les locataires"), "HORS")

    def test_exclusion(self):
        self.assertEqual(self.conf("Sondage : APL et etudiants etrangers, l'avis des Francais"), "HORS")

    def test_report_negation(self):
        # "pas encore publie" ne doit PAS etre confirme
        self.assertEqual(self.conf("Le decret APL pour etudiants etrangers n'est pas encore publie"), "report")

    def test_report_suspension(self):
        self.assertEqual(self.conf("APL etudiants etrangers : le decret suspendu par le gouvernement"), "report")


class TestMatching(unittest.TestCase):
    def test_word_boundary(self):
        # "taxe" ne doit pas matcher dans "syntaxe"
        self.assertFalse(m.term_in(m.norm("Cours de syntaxe a l'universite"), "taxe"))

    def test_plural(self):
        # "etranger" doit matcher "etrangers"
        self.assertTrue(m.term_in(m.norm("aide aux etudiants etrangers"), "etranger"))

    def test_accents(self):
        self.assertTrue(m.term_in(m.norm("DÉCRET officiel"), "decret"))


class TestDedup(unittest.TestCase):
    def test_reworded_duplicate(self):
        a = m.title_key("APL etudiants etrangers : le decret publie au Journal officiel")
        b = m.title_key("Le decret APL pour etudiants etrangers publie au Journal officiel")
        self.assertEqual(a, b)


    def test_synonym_duplicate(self):
        # "paru" et "publie" doivent donner la meme cle
        a = m.title_key("APL etudiants etrangers : le decret est paru au Journal officiel")
        b = m.title_key("Le decret APL pour etudiants etrangers publie au Journal officiel")
        self.assertEqual(a, b)

    def test_different_topic(self):
        a = m.title_key("Decret APL etudiants etrangers publie")
        c = m.title_key("Hausse de la taxe sur les titres de sejour")
        self.assertNotEqual(a, c)


class TestPageFingerprint(unittest.TestCase):
    def setUp(self):
        self._orig = m.fetch_html

    def tearDown(self):
        m.fetch_html = self._orig

    def test_digit_insensitive(self):
        m.fetch_html = lambda *a, **k: "<html><body>Texte stable, vu 123 fois le 17/06</body></html>"
        fp1 = m.page_fingerprint("x")
        m.fetch_html = lambda *a, **k: "<html><body>Texte stable, vu 999 fois le 18/06</body></html>"
        fp2 = m.page_fingerprint("x")
        self.assertEqual(fp1, fp2)

    def test_detects_real_change(self):
        m.fetch_html = lambda *a, **k: "<html><body>Ancien texte</body></html>"
        fp1 = m.page_fingerprint("x")
        m.fetch_html = lambda *a, **k: "<html><body>Nouveau texte important</body></html>"
        fp2 = m.page_fingerprint("x")
        self.assertNotEqual(fp1, fp2)

    def test_region_markers(self):
        html_doc = "<html>HEADER bruit<main>contenu utile</main>FOOTER bruit</html>"
        m.fetch_html = lambda *a, **k: html_doc
        only_main = m.page_text("x", start="<main>", end="</main>")
        self.assertIn("contenu utile", only_main)
        self.assertNotIn("bruit", only_main)


class TestSessions(unittest.TestCase):
    def s(self, title, words):
        ok, pr, lbl, c = m.classify(title, {"match_all": words})
        return (c if ok else "HORS")

    def test_all_words_required(self):
        self.assertEqual(self.s("Bourse CROUS pour etudiant etranger", ["bourse", "crous", "etudiant"]), "lie")

    def test_missing_word(self):
        self.assertEqual(self.s("Bourse CROUS attribuee", ["bourse", "crous", "etudiant"]), "HORS")

    def test_session_confirmed(self):
        self.assertEqual(self.s("Bourse CROUS etudiant : decret publie au journal officiel", ["bourse", "crous", "etudiant"]), "confirme")

    def test_session_report(self):
        self.assertEqual(self.s("Bourse CROUS etudiant : reforme suspendue", ["bourse", "crous", "etudiant"]), "report")


if __name__ == "__main__":
    unittest.main(verbosity=2)
