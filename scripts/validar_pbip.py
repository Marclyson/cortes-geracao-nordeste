#!/usr/bin/env python3
"""Validação estrutural de um projeto PBIP/PBIR antes de reabrir no Power BI Desktop.

Uso:
    python3 validar_pbip.py <pasta do projeto ou <Nome>.Report> [--schemas <clone de microsoft/json-schemas>]

Erros (bloqueiam):
  - JSON inválido; páginas em pages.json sem pasta (e o contrário); activePageName inexistente
  - nomes de página ou de visual repetidos
  - campo ligado a tabela/medida/coluna que não existe no TMDL
  - dica de ferramenta apontando para página inexistente ou que não é do tipo Tooltip
  - botão apontando para indicador ou página inexistente
  - visual personalizado usado sem registro em report.json (publicCustomVisuals)
  - spec Deneb que não é JSON válido; tema personalizado sem o arquivo em RegisteredResources
  - medida com o mesmo nome em duas tabelas
  - arquivo que não passa no esquema oficial (com --schemas)
Avisos:
  - visual fora dos limites da página; visual de dados sem texto alternativo
  - tabOrder repetido na página; página de dica com filtros próprios
  - Deneb sem filtro cruzado ligado
"""
import json, re, sys
from pathlib import Path

NATIVOS_SEM_DADOS = {"slicer", "advancedSlicerVisual", "textbox", "shape", "image", "actionButton", "basicShape", "pageNavigator", "bookmarkNavigator"}
ERROS, AVISOS = [], []


def erro(onde, msg): ERROS.append(f"{onde}: {msg}")
def aviso(onde, msg): AVISOS.append(f"{onde}: {msg}")


def ler(p: Path, base: Path):
    try:
        return json.loads(p.read_text(encoding="utf-8-sig"))
    except Exception as e:  # noqa: BLE001
        erro(p.relative_to(base), f"JSON inválido ({e})")
        return None


def literal(v):
    """Valor de {"expr":{"Literal":{"Value":"'x'"}}} sem aspas."""
    try:
        s = v["expr"]["Literal"]["Value"]
    except (KeyError, TypeError):
        return None
    if s.startswith("'") and s.endswith("'"):
        return s[1:-1].replace("''", "'")
    return s


def props(objs, nome):
    for item in (objs or {}).get(nome, []) or []:
        yield item.get("properties", {})


# ---------- TMDL ----------
def nome_tmdl(resto):
    resto = resto.strip()
    if resto.startswith("'"):
        m = re.match(r"'((?:[^']|'')*)'", resto)
        return m.group(1).replace("''", "'") if m else None
    m = re.match(r"([^\s=]+)", resto)
    return m.group(1) if m else None


def ler_modelo(sm: Path):
    tabelas = {}  # tabela -> {"measure": set, "column": set}
    for f in sorted((sm / "definition" / "tables").glob("*.tmdl")) if sm else []:
        atual = None
        for linha in f.read_text(encoding="utf-8-sig").splitlines():
            if linha.startswith("table "):
                atual = nome_tmdl(linha[6:])
                tabelas.setdefault(atual, {"measure": set(), "column": set()})
            elif atual and linha.startswith("\t") and not linha.startswith("\t\t"):
                for kw in ("measure", "column"):
                    if linha.startswith(f"\t{kw} "):
                        n = nome_tmdl(linha[len(kw) + 2:])
                        if n:
                            tabelas[atual][kw].add(n)
    vistos = {}
    for t, d in tabelas.items():
        for m in d["measure"]:
            if m in vistos:
                erro("modelo", f"medida '{m}' existe em '{vistos[m]}' e em '{t}'")
            vistos[m] = t
    return tabelas


def refs_campos(no, aliases=None):
    """Gera (tabela, nome, tipo) de Column/Measure/HierarchyLevel em qualquer profundidade."""
    aliases = aliases or {}
    if isinstance(no, dict):
        if "From" in no and isinstance(no["From"], list):
            aliases = {**aliases, **{f.get("Name"): f.get("Entity") for f in no["From"] if isinstance(f, dict)}}
        for kw in ("Column", "Measure"):
            alvo = no.get(kw)
            if isinstance(alvo, dict) and "Property" in alvo:
                src = (alvo.get("Expression") or {}).get("SourceRef") or {}
                tab = src.get("Entity") or aliases.get(src.get("Source"))
                if tab:
                    yield tab, alvo["Property"], kw.lower()
        for v in no.values():
            yield from refs_campos(v, aliases)
    elif isinstance(no, list):
        for v in no:
            yield from refs_campos(v, aliases)


# ---------- esquemas ----------
def validador_esquemas(raiz):
    if not raiz:
        return None
    try:
        import jsonschema
        from referencing import Registry, Resource
    except ImportError:
        aviso("esquemas", "instale jsonschema e referencing para validar contra os esquemas")
        return None
    raiz = Path(raiz)
    prefixo = "https://developer.microsoft.com/json-schemas/"

    def buscar(uri):
        caminho = raiz / uri.replace(prefixo, "")
        return Resource.from_contents(json.loads(caminho.read_text(encoding="utf-8")))

    reg = Registry(retrieve=buscar)

    def validar(doc, onde):
        uri = doc.get("$schema") if isinstance(doc, dict) else None
        if not uri or not uri.startswith(prefixo):
            return
        try:
            esquema = buscar(uri).contents
        except FileNotFoundError:
            aviso(onde, f"esquema não encontrado no clone: {uri}")
            return
        cls = jsonschema.validators.validator_for(esquema)
        for e in sorted(cls(esquema, registry=reg).iter_errors(doc), key=lambda e: list(e.path))[:3]:
            erro(onde, f"esquema: {'/'.join(map(str, e.path))} {e.message[:160]}")

    return validar


# ---------- relatório ----------
def main():
    args = sys.argv[1:]
    if not args:
        print(__doc__)
        return 2
    esquemas = None
    if "--schemas" in args:
        i = args.index("--schemas")
        esquemas = args[i + 1]
        del args[i:i + 2]
    alvo = Path(args[0]).resolve()
    relatorios = [alvo] if alvo.name.endswith(".Report") else sorted(alvo.glob("*.Report"))
    if not relatorios:
        print("Nenhuma pasta .Report encontrada.")
        return 2
    validar = validador_esquemas(esquemas)

    for rep in relatorios:
        base = rep.parent
        d = rep / "definition"
        sm = None
        pbir = ler(rep / "definition.pbir", base) if (rep / "definition.pbir").exists() else None
        caminho_sm = ((pbir or {}).get("datasetReference") or {}).get("byPath", {}).get("path")
        if caminho_sm:
            sm = (rep / caminho_sm).resolve()
        modelo = ler_modelo(sm) if sm and sm.exists() else {}
        if not modelo:
            aviso(rep.name, "modelo TMDL não encontrado; ligações de campo não conferidas")

        for f in d.rglob("*.json"):
            doc = ler(f, base)
            if doc is not None and validar:
                validar(doc, f.relative_to(base))

        report = ler(d / "report.json", base) or {}
        registrados = set(report.get("publicCustomVisuals", []) or [])
        tema = ((report.get("themeCollection") or {}).get("customTheme") or {}).get("name")
        if tema:
            if not list((rep / "StaticResources" / "RegisteredResources").glob(f"{tema}*")):
                erro("report.json", f"tema personalizado '{tema}' sem arquivo em StaticResources/RegisteredResources")

        indicadores = {p.name.split(".")[0] for p in (d / "bookmarks").glob("*.bookmark.json")}
        pj = ler(d / "pages" / "pages.json", base) or {}
        ordem = pj.get("pageOrder", [])
        # a página é identificada pelo "name" do page.json (a pasta pode ter outro nome)
        paginas, pasta_de = {}, {}
        for pf in sorted((d / "pages").glob("*/page.json")):
            pg = ler(pf, base) or {}
            n = pg.get("name", pf.parent.name)
            if n in paginas:
                erro(pf.parent.name, f"página com name '{n}' repetido")
            paginas[n], pasta_de[n] = pg, pf.parent.name
        for p in set(ordem) - set(paginas):
            erro("pages.json", f"página '{p}' do pageOrder não existe")
        for p in set(paginas) - set(ordem):
            erro("pages.json", f"página '{p}' ({pasta_de[p]}) fora do pageOrder")
        if pj.get("activePageName") and pj["activePageName"] not in paginas:
            erro("pages.json", f"activePageName '{pj['activePageName']}' não existe")

        for p, pg in paginas.items():
            W, H = pg.get("width", 1280), pg.get("height", 720)
            if pg.get("type") == "Tooltip" and (pg.get("filterConfig") or {}).get("filters"):
                aviso(p, "página de dica com filtros próprios; o ponto sob o mouse já filtra")
            nomes, ordens = set(), {}
            for vf in sorted((d / "pages" / pasta_de[p] / "visuals").glob("*/visual.json")):
                v = ler(vf, base)
                if not v:
                    continue
                onde = f"{pasta_de[p]}/{vf.parent.name}"
                if v.get("name") in nomes:
                    erro(onde, "nome repetido na página")
                nomes.add(v.get("name"))
                pos = v.get("position", {})
                if pos.get("x", 0) < 0 or pos.get("y", 0) < 0 or pos.get("x", 0) + pos.get("width", 0) > W + 1 or pos.get("y", 0) + pos.get("height", 0) > H + 1:
                    aviso(onde, f"fora dos limites da página {W}×{H}")
                if "tabOrder" in pos and "visualGroup" not in v and not v.get("parentGroupName") and not v.get("name", "").startswith("tour_"):
                    ordens.setdefault(pos["tabOrder"], []).append(v.get("name"))

                vis = v.get("visual") or {}
                tipo = vis.get("visualType")
                if tipo and re.search(r"[A-F0-9]{32}$", tipo) and tipo not in registrados:
                    erro(onde, f"visual personalizado '{tipo}' não registrado em report.json publicCustomVisuals")
                for tab, nome, kind in refs_campos(vis.get("query")):
                    if modelo:
                        t = modelo.get(tab)
                        if t is None:
                            erro(onde, f"tabela '{tab}' não existe no modelo")
                        elif nome not in t["measure"] | t["column"]:
                            erro(onde, f"'{tab}'[{nome}] ({kind}) não existe no modelo")
                for pr in props(vis.get("objects"), "vega"):
                    if pg.get("type") != "Tooltip" and literal(pr.get("enableSelection")) != "true":
                        aviso(onde, "Deneb sem filtro cruzado (vega.enableSelection); clicar não filtra a página")
                    spec = literal(pr.get("jsonSpec"))
                    if spec:
                        try:
                            js = json.loads(spec)
                            dn = (js.get("data") or {})
                            if isinstance(dn, dict) and dn.get("name") != "dataset":
                                aviso(onde, "spec Deneb sem data.name = 'dataset'")
                        except json.JSONDecodeError as e:
                            erro(onde, f"spec Deneb não é JSON válido ({e})")
                vco = vis.get("visualContainerObjects") or {}
                for pr in props(vco, "visualTooltip"):
                    sec = literal(pr.get("section"))
                    if sec:
                        if sec not in paginas:
                            erro(onde, f"dica aponta para página inexistente '{sec}'")
                        elif paginas[sec].get("type") != "Tooltip":
                            erro(onde, f"dica aponta para '{sec}', que não é do tipo Tooltip")
                for pr in props(vco, "visualLink"):
                    bm, nav = literal(pr.get("bookmark")), literal(pr.get("navigationSection"))
                    if bm and bm not in indicadores:
                        erro(onde, f"botão aponta para indicador inexistente '{bm}'")
                    if nav and nav not in paginas:
                        erro(onde, f"botão aponta para página inexistente '{nav}'")
                if tipo and tipo not in NATIVOS_SEM_DADOS and vis.get("query") and pg.get("type") != "Tooltip":
                    if not any(literal(pr.get("altText")) for pr in props(vco, "general")):
                        aviso(onde, "visual de dados sem texto alternativo (general.altText)")
            for o, vs in ordens.items():
                if len(vs) > 1:
                    aviso(p, f"tabOrder {o} repetido: {', '.join(vs)}")

    for titulo, lista in (("ERROS", ERROS), ("AVISOS", AVISOS)):
        print(f"\n{titulo} ({len(lista)})")
        for linha in lista:
            print("  -", linha)
    return 1 if ERROS else 0


if __name__ == "__main__":
    sys.exit(main())
