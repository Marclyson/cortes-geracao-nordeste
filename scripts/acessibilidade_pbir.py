#!/usr/bin/env python3
"""Acessibilidade no PBIR: texto alternativo e ordem de tabulação na sequência de leitura.

Uso:
    python3 acessibilidade_pbir.py <pasta definition do relatório> [textos.json]

- Ordem de tabulação (position.tabOrder), por página: título → filtros → conteúdo
  (de cima para baixo, da esquerda para a direita, em faixas de 40 px). Visuais
  dentro de grupos e os do tour (prefixo "tour_") vão para o fim, na ordem atual.
- Texto alternativo (visualContainerObjects.general.altText), para visuais de dados:
  vem de textos.json ({"pagina/visual": "texto"} ou {"visual": "texto"}); sem entrada,
  usa o título do visual. Páginas de dica e segmentações ficam de fora.
Idempotente: pode rodar depois de cada geração.
"""
import json, sys
from pathlib import Path

SEM_ALT = {"textbox", "shape", "image", "actionButton", "basicShape", "slicer",
           "advancedSlicerVisual", "pageNavigator", "bookmarkNavigator"}


def lit(texto):
    return {"expr": {"Literal": {"Value": "'" + texto.replace("'", "''") + "'"}}}


def titulo(vis):
    for it in (vis.get("visualContainerObjects") or {}).get("title", []):
        v = ((it.get("properties") or {}).get("text") or {}).get("expr", {}).get("Literal", {}).get("Value")
        if v:
            return v.strip("'").replace("''", "'")
    return None


def main():
    d = Path(sys.argv[1])
    textos = json.loads(Path(sys.argv[2]).read_text(encoding="utf-8")) if len(sys.argv) > 2 else {}
    alt_n = tab_n = 0
    for pf in sorted((d / "pages").glob("*/page.json")):
        page = json.loads(pf.read_text(encoding="utf-8"))
        nome_pg = page.get("name", pf.parent.name)
        itens = []
        for vf in sorted((pf.parent / "visuals").glob("*/visual.json")):
            itens.append((vf, json.loads(vf.read_text(encoding="utf-8"))))

        def chave(item):
            v = item[1]
            vis, pos = v.get("visual") or {}, v.get("position", {})
            tipo = vis.get("visualType", "")
            fim = v["name"].startswith("tour_") or bool(v.get("parentGroupName")) or "visualGroup" in v
            if fim:
                return (3, pos.get("tabOrder", 0), 0, 0)
            grupo = 0 if tipo == "textbox" and pos.get("y", 0) < 60 else (1 if tipo in ("slicer", "advancedSlicerVisual") else 2)
            return (grupo, round(pos.get("y", 0) / 40), pos.get("x", 0), 0)

        ordem = sorted(itens, key=chave)
        proximo = 1000
        for vf, v in ordem:
            mudou = False
            if chave((vf, v))[0] < 3:
                if v["position"].get("tabOrder") != proximo:
                    v["position"]["tabOrder"] = proximo
                    mudou = True
                    tab_n += 1
                proximo += 1000
            vis = v.get("visual") or {}
            tipo = vis.get("visualType")
            if tipo and tipo not in SEM_ALT and vis.get("query") and page.get("type") != "Tooltip":
                texto = textos.get(f"{nome_pg}/{v['name']}") or textos.get(v["name"]) or titulo(vis)
                if texto:
                    vco = vis.setdefault("visualContainerObjects", {})
                    gen = vco.setdefault("general", [{"properties": {}}])
                    props = gen[0].setdefault("properties", {})
                    if props.get("altText") != lit(texto):
                        props["altText"] = lit(texto)
                        mudou = True
                        alt_n += 1
            if mudou:
                vf.write_text(json.dumps(v, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"texto alternativo: {alt_n} visuais; ordem de tabulação: {tab_n} ajustes")


if __name__ == "__main__":
    main()
