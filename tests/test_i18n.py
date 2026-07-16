"""Tests de la passe bilingue FR/EN du dashboard (trading_os.webapp.i18n)."""

import re

from trading_os.webapp import i18n


def test_translate_exact_and_unescape():
    # phrase fixe
    assert i18n.translate_text("PRIX") == "PRICE"
    # apostrophe rendue par html.escape (&#x27;) doit matcher les tables
    fr = "Suis-je dans une killzone autoris&#x27;e ?"  # forme escapée factice
    # cas réel : la clé checklist avec apostrophe
    node = "Ai-je d&#xe9;j&#xe0; pris ma perte max du jour ? Si oui : terminal ferm&#xe9;."
    assert i18n.translate_text(node) == \
        "Have I already taken my max daily loss? If so: terminal closed."


def test_translate_dynamic_rule_keeps_numbers():
    fr = ("La veille a balay&#xe9; le PDH (29,921.75) sans cl&#xf4;turer "
          "au-dessus (&#xe9;chec au niveau) &#x2192; cible : le PDL.")
    en = i18n.translate_text(fr)
    assert "29,921.75" in en
    assert "target: the PDL" in en
    assert "veille" not in en


def test_untranslated_stays_french():
    # un nœud non couvert doit rester identique (repli gracieux)
    s = "Zblork quux 42"
    assert i18n.translate_text(s) == s


def test_bilingualize_wraps_and_injects_toggle():
    page = ("<title>Trading OS — Prémarché</title><style>.x{color:red}</style>"
            '<div class="top"><span class="demo">DEMO</span></div>'
            '<h3>Espérance / trade</h3>'
            '<span class="klab">Win rate</span>'
            "<script>var a='Espérance / trade';</script>")
    out = i18n.bilingualize(page)
    # le heading est enveloppé avec sa traduction
    assert 'data-en="Expectancy / trade"' in out
    # le bouton + le JS du toggle sont injectés
    assert 'id="lang"' in out
    assert "tos-lang" in out
    # le contenu de <script>/<style>/<title> n'est PAS enveloppé
    assert "var a='Espérance / trade';" in out
    assert out.count('<span class="i18n"') >= 1
    # pas de double-enveloppe ni de balise cassée
    assert "<span class=\"i18n\" data-en=\"\"" not in out


def test_bilingualize_preserves_tag_structure():
    page = '<p>consensus <strong>x</strong> · précédent <strong>y</strong></p>'
    out = i18n.bilingualize(page)
    # « précédent » traduit, structure des <strong> intacte
    assert "<strong>x</strong>" in out
    assert "<strong>y</strong>" in out
    assert 'data-en="· previous"' in out


def test_no_bare_french_accents_leak_in_known_labels():
    # les libellés KPI clés ont tous une traduction
    for fr in ["Espérance / trade", "Référence backtest (24 mois, coûts inclus)",
               "Forward — le vrai test (depuis le gel)", "PRIX"]:
        assert i18n.translate_text(fr) != fr
        assert not re.search(r"[àâçéèêëîïôûù]", i18n.translate_text(fr))
