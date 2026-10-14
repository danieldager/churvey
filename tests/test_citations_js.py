"""ff/src/background/citations.js run in QuickJS (dev dependency; no node on this machine)."""
import json
import pathlib
import unittest

try:
    import quickjs
except ImportError:  # pragma: no cover
    quickjs = None

SRC = pathlib.Path(__file__).resolve().parents[1] / "ff/src/background/citations.js"

# 2026-10-14 probe: ChatGPT's DIL markup carried the sources as <Link url title/> and names as <Entity value/>.
DIL = ('<title size="xl">Vierzon</title>\n\n'
       '**<Entity category="organization" value="Ville de Vierzon" disambig="mairie"/>**\n\n'
       '      Le maire a mis en cause l’ancienne majorité.\n\n'
       '      <text size="sm">Source : <Link url="https://www.vierzonitude.com/blog/x-182" title="Vierzonitude — 13 octobre"/>.</text>\n'
       '    </box>\n'
       '  <text><Link url="https://www.ville-vierzon.fr/?utm_source=chatgpt.com" title="Site de la ville"/></text>\n')


def sse_message(text):
    msg = {"id": "m1", "author": {"role": "assistant"}, "content": {"content_type": "text", "parts": [text]},
           "status": "finished_successfully", "metadata": {}, "channel": "final"}
    return "event: delta\ndata: " + json.dumps({"v": {"message": msg}, "c": 1}) + "\n\n"


@unittest.skipUnless(quickjs, "quickjs not installed (uv sync --group dev)")
class CitationsJs(unittest.TestCase):
    def setUp(self):
        self.ctx = quickjs.Context()
        self.ctx.eval(SRC.read_text())

    def call(self, expr, *args):
        return json.loads(self.ctx.eval(f"JSON.stringify({expr}(...{json.dumps(list(args))}))"))

    def test_dil_link_and_entity_keep_their_text(self):
        r = self.call("Probe.citations.dilClean", DIL)
        self.assertIn("Ville de Vierzon", r["text"])
        self.assertIn("Source : Vierzonitude — 13 octobre.", r["text"])
        self.assertIn("Site de la ville", r["text"])
        self.assertNotIn("<", r["text"])
        self.assertEqual([l["url"] for l in r["links"]], ["https://www.vierzonitude.com/blog/x-182", "https://www.ville-vierzon.fr/?utm_source=chatgpt.com"])
        first = r["links"][0]
        self.assertEqual(r["text"][first["pos"]:first["end"]], "Vierzonitude — 13 octobre")

    def test_chatgpt_link_is_a_citation(self):
        cites = self.call("Probe.citations.parse", "chatgpt", sse_message(DIL))
        links = [c for c in cites if c["via"] == "chatgpt_link"]
        self.assertEqual([c["url"] for c in links], ["https://www.vierzonitude.com/blog/x-182", "https://www.ville-vierzon.fr/"])
        self.assertEqual(links[0]["title"], "Vierzonitude — 13 octobre")
        self.assertEqual(links[0]["anchor_text"], "Source :")

    def test_text_without_markup_is_unchanged(self):
        r = self.call("Probe.citations.dilClean", "Bonjour <b>pas du DIL\n\nfin")
        self.assertEqual(r["links"], [])
        self.assertEqual(self.call("Probe.citations.dilClean", "plain text")["text"], "plain text")


if __name__ == "__main__":
    unittest.main()
