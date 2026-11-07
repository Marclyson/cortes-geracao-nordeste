#!/usr/bin/env python3
"""Liga o filtro cruzado (clicar filtra a página) em visuais Deneb de um relatório PBIR.

Uso:
    python3 interatividade_pbir.py <pasta definition do relatório> pagina/visual [pagina/visual ...]

Para cada visual indicado:
  - liga vega.enableSelection e vega.selectionMaxDataPoints (250);
  - em cada marca selecionável (bar, rect, circle, point, square, tick, text, arc) que não agrega
    dados, acrescenta a opacidade condicionada a __selected__ (os não selecionados ficam a 25%,
    ou a 25% da opacidade da marca). Linhas, áreas e regras ficam como estão, porque uma linha
    representa várias linhas do dataset e não é resolvida para um ponto só.
Avisa quando a marca agrega (aggregate no encoding ou na transform da camada): nesse caso o
clique não é resolvido para uma linha do dataset; traga do DAX o grão do gráfico.
Idempotente.
"""
import json, sys
from pathlib import Path

SELECIONAVEIS = {"bar", "rect", "circle", "point", "square", "tick", "text", "arc"}


def lit(v):
    return {"expr": {"Literal": {"Value": v}}}


def literal_txt(v):
    s = v["expr"]["Literal"]["Value"]
    return s[1:-1].replace("''", "'")


def agrega(unidade):
    enc = json.dumps(unidade.get("encoding", {}))
    trans = json.dumps(unidade.get("transform", []))
    return '"aggregate"' in enc or '"aggregate"' in trans


def tipo_marca(unidade):
    m = unidade.get("mark")
    return m.get("type") if isinstance(m, dict) else m


def marcar(unidade, avisos, onde, herdou_agregacao=False):
    agregada = herdou_agregacao or '"aggregate"' in json.dumps(unidade.get("transform", []))
    alterou = 0
    if "layer" in unidade:
        for camada in unidade["layer"]:
            alterou += marcar(camada, avisos, onde, agregada)
        return alterou
    tipo = tipo_marca(unidade)
    if tipo not in SELECIONAVEIS:
        return 0
    if agregada or agrega(unidade):
        avisos.append(f"{onde}: camada '{tipo}' agrega dados; o clique nela não filtra")
        return 0
    enc = unidade.setdefault("encoding", {})
    base = unidade["mark"].get("opacity", 1) if isinstance(unidade["mark"], dict) else 1
    alvo = {"condition": {"test": "datum.__selected__ == 'off'", "value": round(base * 0.25, 2)}, "value": base}
    if enc.get("opacity") != alvo:
        if "opacity" in enc and "__selected__" not in json.dumps(enc["opacity"]):
            avisos.append(f"{onde}: camada '{tipo}' já tinha opacidade própria; substituída")
        enc["opacity"] = alvo
        alterou = 1
    return alterou


def main():
    if len(sys.argv) < 3:
        print(__doc__)
        return 2
    d = Path(sys.argv[1])
    avisos, feitos = [], 0
    for alvo in sys.argv[2:]:
        pagina, visual = alvo.split("/")
        vf = d / "pages" / pagina / "visuals" / visual / "visual.json"
        if not vf.exists():
            avisos.append(f"{alvo}: visual não encontrado")
            continue
        v = json.loads(vf.read_text(encoding="utf-8"))
        vega = (v.get("visual", {}).get("objects", {}).get("vega") or [None])[0]
        if not vega:
            avisos.append(f"{alvo}: não é um visual Deneb")
            continue
        p = vega["properties"]
        spec = json.loads(literal_txt(p["jsonSpec"]))
        n = marcar(spec, avisos, alvo)
        p["jsonSpec"] = lit("'" + json.dumps(spec, ensure_ascii=False, indent=2).replace("'", "''") + "'")
        p["enableSelection"] = lit("true")
        p["selectionMaxDataPoints"] = lit("250D")
        vf.write_text(json.dumps(v, ensure_ascii=False, indent=2), encoding="utf-8")
        feitos += 1
        print(f"{alvo}: filtro cruzado ligado ({n} camada(s) com destaque da seleção)")
    for a in avisos:
        print("aviso:", a)
    print(f"{feitos} visuais")


if __name__ == "__main__":
    sys.exit(main())
