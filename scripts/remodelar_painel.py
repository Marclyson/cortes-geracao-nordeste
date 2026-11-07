# Remodelagem do painel CortesNordeste no padrão Dome Analytics (etapa 1: modelo, tema, página executiva).
# Uso: python3 remodelar.py <pasta powerbi>
import json, os, re, shutil, sys, uuid

PBI = sys.argv[1]
SM = os.path.join(PBI, "CortesNordeste.SemanticModel", "definition")
RP = os.path.join(PBI, "CortesNordeste.Report", "definition")
RS = os.path.join(PBI, "CortesNordeste.Report", "StaticResources")
FATO = "Restrição diária"
DENEB = "deneb7E15AEF80B9E4D4F8E12924291ECE89A"
HTMLC = "htmlContent443BE3AD55E043BF878BED274D3A6865"
SCHEMA_VC = "https://developer.microsoft.com/json-schemas/fabric/item/report/definition/visualContainer/2.3.0/schema.json"

def uid(seed): return str(uuid.uuid5(uuid.NAMESPACE_URL, "cortesnordeste/" + seed))
def rd(p): return open(p, encoding="utf-8").read()
def wr(p, t): open(p, "w", encoding="utf-8", newline="\n").write(t)

# =====================================================================================
# 1. MODELO SEMÂNTICO
# =====================================================================================
fato_p = os.path.join(SM, "tables", f"{FATO}.tmdl")
fato = rd(fato_p)

# 1a. colunas de origem (copiando o bloco da coluna nao_realizada_par_mwh)
m = re.search(r"\n\tcolumn nao_realizada_par_mwh\n(?:\t\t.*\n|\n(?=\t\t))*", fato)
bloco_par = m.group(0)
novas_cols = ""
for c in ("nao_realizada_loc_mwh", "nao_realizada_sis_mwh", "nao_realizada_sem_origem_mwh"):
    if f"column {c}\n" in fato: continue
    b = bloco_par.replace("nao_realizada_par_mwh", c)
    b = re.sub(r"lineageTag: .*", f"lineageTag: {uid('col/'+c)}", b)
    novas_cols += b

# 1b. medidas
def medida(nome, expr, fmt=None, pasta=None, desc=None, oculta=False):
    linhas = expr.strip("\n").split("\n")
    if len(linhas) == 1:
        t = f"\tmeasure '{nome}' = {linhas[0]}\n"
    else:
        t = f"\tmeasure '{nome}' =\n" + "".join(f"\t\t\t{l}\n" for l in linhas)
    if desc: t = f"\t/// {desc}\n" + t
    if fmt: t += f"\t\tformatString: {fmt}\n"
    if oculta: t += "\t\tisHidden\n"
    if pasta: t += f"\t\tdisplayFolder: {pasta}\n"
    t += f"\t\tlineageTag: {uid('m/'+nome)}\n\n"
    return t

M = []
M.append(medida("Geração possível (GWh)", "[Geração (GWh)] + [Não realizada (GWh)]", "#,0", "Base", "Geração verificada mais geração não realizada"))
M.append(medida("Sem razão (GWh)", f"DIVIDE(SUM('{FATO}'[nao_realizada_sem_razao_mwh]), 1000)", "#,0", "Por razão", "Geração não realizada sem razão informada pelo ONS"))
M.append(medida("Origem local (GWh)", f"DIVIDE(SUM('{FATO}'[nao_realizada_loc_mwh]), 1000)", "#,0", "Por origem", "Restrição de origem local (rede próxima à usina)"))
M.append(medida("Origem sistêmica (GWh)", f"DIVIDE(SUM('{FATO}'[nao_realizada_sis_mwh]), 1000)", "#,0", "Por origem", "Restrição de origem sistêmica (sistema interligado)"))
M.append(medida("Sem origem (GWh)", f"DIVIDE(SUM('{FATO}'[nao_realizada_sem_origem_mwh]), 1000)", "#,0", "Por origem", "Geração não realizada sem origem informada"))
M.append(medida("Horas de restrição", f"SUM('{FATO}'[horas_restricao])", "#,0", "Base", "Soma das horas com restrição de cada usina em cada dia"))
M.append(medida("Última data com dados", f"CALCULATE(MAX('{FATO}'[dia]), REMOVEFILTERS('Calendário'))", "dd/mm/yyyy", "Período", "Último dia com dados, ignorando o filtro de datas"))
M.append(medida("_Fim do período", "MIN(MAX('Calendário'[Data]), [Última data com dados])", "dd/mm/yyyy", "Período", "Fim do período analisado, limitado ao último dia com dados", oculta=True))

BASES = [  # (prefixo, medida-base, formato)
    ("Não realizada", "[Não realizada (GWh)]", "#,0"),
    ("Geração", "[Geração (GWh)]", "#,0"),
    ("Usinas com corte", "[Usinas com corte]", "#,0"),
    ("ENE", "[Energética (ENE)]", "#,0"), ("CNF", "[Confiabilidade (CNF)]", "#,0"),
    ("REL", "[Indisponibilidade externa (REL)]", "#,0"), ("PAR", "[Parecer de acesso (PAR)]", "#,0"),
    ("Sem razão", "[Sem razão (GWh)]", "#,0"),
    ("Origem local", "[Origem local (GWh)]", "#,0"), ("Origem sistêmica", "[Origem sistêmica (GWh)]", "#,0"),
    ("Sem origem", "[Sem origem (GWh)]", "#,0"),
]
for pre, base, fmt in BASES:
    M.append(medida(f"{pre} · período", f"""VAR _Fim = [_Fim do período]
RETURN
    IF (
        ISFILTERED ( 'Calendário' ),
        CALCULATE ( {base}, KEEPFILTERS ( 'Calendário'[Data] <= _Fim ) ),
        CALCULATE ( {base}, DATESINPERIOD ( 'Calendário'[Data], _Fim, -12, MONTH ) )
    )""", fmt, "Período", f"{base} no período analisado: o filtro de datas, ou os últimos 12 meses quando não há filtro"))
    M.append(medida(f"{pre} · ano anterior", f"""VAR _Fim = [_Fim do período]
RETURN
    IF (
        ISFILTERED ( 'Calendário' ),
        CALCULATE (
            {base},
            REMOVEFILTERS ( 'Calendário' ),
            DATEADD ( CALCULATETABLE ( VALUES ( 'Calendário'[Data] ), KEEPFILTERS ( 'Calendário'[Data] <= _Fim ) ), -1, YEAR )
        ),
        CALCULATE (
            {base},
            REMOVEFILTERS ( 'Calendário' ),
            DATESINPERIOD ( 'Calendário'[Data], EDATE ( _Fim, -12 ), -12, MONTH )
        )
    )""", fmt, "Período", f"{base} no mesmo período um ano antes, cortado na mesma data"))

M.append(medida("% cortado · período", "DIVIDE([Não realizada · período], [Geração · período] + [Não realizada · período])", "0.0%", "Período"))
M.append(medida("% cortado · ano anterior", "DIVIDE([Não realizada · ano anterior], [Geração · ano anterior] + [Não realizada · ano anterior])", "0.0%", "Período"))
for pre in ("Não realizada", "Geração", "Usinas com corte"):
    M.append(medida(f"{pre} · var %", f"""VAR _A = [{pre} · período]
VAR _B = [{pre} · ano anterior]
RETURN
    IF ( NOT ISBLANK ( _B ) && _B <> 0, DIVIDE ( _A - _B, _B ) )""", "+0.0%;-0.0%;0.0%", "Período"))
M.append(medida("% cortado · var p.p.", """VAR _A = [% cortado · período]
VAR _B = [% cortado · ano anterior]
RETURN
    IF ( NOT ISBLANK ( _B ), ( _A - _B ) * 100 )""", "+0.0;-0.0;0.0", "Período", "Variação do percentual cortado em pontos percentuais"))
M.append(medida("Início do período", """VAR _Fim = [_Fim do período]
RETURN
    IF ( ISFILTERED ( 'Calendário' ), MIN ( 'Calendário'[Data] ), EDATE ( _Fim, -12 ) + 1 )""", "dd/mm/yyyy", "Período", oculta=True))
M.append(medida("Rótulo do período", """VAR _Fim = [_Fim do período]
VAR _Ini = [Início do período]
RETURN
    IF (
        ISFILTERED ( 'Calendário' ),
        FORMAT ( _Ini, "dd/mm/yyyy" ) & " a " & FORMAT ( _Fim, "dd/mm/yyyy" ) & " · comparado ao mesmo período do ano anterior",
        "Últimos 12 meses (" & FORMAT ( _Ini, "mmm/yy" ) & " a " & FORMAT ( _Fim, "mmm/yy" ) & ") · comparado aos 12 meses anteriores"
    )""", None, "Período"))

# --- sparkline SVG (24 meses até o fim do período, ignorando o filtro de datas)
def sparkline(nome, expr_mes, w=120, h=36):
    return medida(nome, f"""VAR _Fim = [_Fim do período]
VAR _Ini = EOMONTH ( _Fim, -24 ) + 1
VAR _Meses =
    ADDCOLUMNS (
        CALCULATETABLE ( VALUES ( 'Calendário'[Mês] ), REMOVEFILTERS ( 'Calendário' ), DATESBETWEEN ( 'Calendário'[Data], _Ini, _Fim ) ),
        "@v", VAR _m = 'Calendário'[Mês] RETURN CALCULATE ( {expr_mes}, REMOVEFILTERS ( 'Calendário' ), 'Calendário'[Mês] = _m )
    )
VAR _Min = MINX ( _Meses, [@v] )
VAR _Max = MAXX ( _Meses, [@v] )
VAR _N = COUNTROWS ( _Meses )
VAR _I = ADDCOLUMNS ( _Meses, "@i", RANKX ( _Meses, 'Calendário'[Mês], , ASC, DENSE ) )
VAR _C =
    ADDCOLUMNS (
        _I,
        "@x", DIVIDE ( [@i] - 1, _N - 1 ) * {w - 8} + 4,
        "@y", {h - 4} - DIVIDE ( [@v] - _Min, _Max - _Min ) * {h - 8}
    )
VAR _P = CONCATENATEX ( _C, FORMAT ( [@x], "0.0", "en-US" ) & "," & FORMAT ( [@y], "0.0", "en-US" ), " ", [@i], ASC )
VAR _U = TOPN ( 1, _C, [@i], DESC )
VAR _UX = FORMAT ( MAXX ( _U, [@x] ), "0.0", "en-US" )
VAR _UY = FORMAT ( MAXX ( _U, [@y] ), "0.0", "en-US" )
VAR _Parcial = _Fim < EOMONTH ( _Fim, 0 )
RETURN
    IF (
        _N >= 2,
        "<svg width='{w}' height='{h}' viewBox='0 0 {w} {h}'><polyline points='" & _P
            & "' fill='none' stroke='#8A8886' stroke-width='1.6' stroke-linejoin='round'/><circle cx='" & _UX & "' cy='" & _UY
            & "' r='3' " & IF ( _Parcial, "fill='#FFFFFF' stroke='#967100' stroke-width='1.5'", "fill='#F2C811'" ) & "/></svg>"
    )""", None, "Visual", f"Sparkline de 24 meses (SVG) de {expr_mes}", oculta=True)

M.append(sparkline("svg · sparkline não realizada", "[Não realizada (GWh)]"))
M.append(sparkline("svg · sparkline % cortado", "[% cortado]"))
M.append(sparkline("svg · sparkline geração", "[Geração (GWh)]"))
M.append(sparkline("svg · sparkline usinas", "[Usinas com corte]"))

# --- cartões de KPI (HTML Content)
def card_dax(i, rotulo, valor, var, svg, unidade, ruim_se_sobe=True, pp=False):
    v = f"_V{i}"
    sinal_ruim = f"{v} > 0" if ruim_se_sobe else f"{v} < 0"
    var_txt = f'FORMAT ( ABS ( {v} ), "0.0" ) & " p.p."' if pp else f'FORMAT ( ABS ( {v} ), "0.0%" )'
    return f"""    "<div class='card'><div class='rot'>{rotulo}</div><div class='lin'><div><div class='val'>" & {valor} & "<span class='un'>{unidade}</span></div>"
        & ( VAR {v} = {var} RETURN IF ( ISBLANK ( {v} ), "<div class='var neu'>sem base de comparação</div>",
            "<div class='var " & IF ( {sinal_ruim}, "ruim", "bom" ) & "'>" & IF ( {v} > 0, "▲ ", "▼ " ) & {var_txt} & "</div>" ) )
        & "</div><div class='spk'>" & {svg} & "</div></div></div>\""""

kpi_expr = f"""VAR _Cmp = IF ( ISFILTERED ( 'Calendário' ), "vs mesmo período do ano anterior", "vs 12 meses anteriores" )
RETURN
    "<div class='cab'><span class='per'>" & [Rótulo do período] & "</span><span class='dt'>Dados até " & FORMAT ( [Última data com dados], "dd/mm/yyyy" ) & " · tendência de 24 meses à direita</span></div><div class='kpis'>"
        & {card_dax(1, "Geração não realizada", 'FORMAT ( [Não realizada · período], "#,0" )', "[Não realizada · var %]", "[svg · sparkline não realizada]", " GWh")}
        & {card_dax(2, "% da geração possível cortada", 'FORMAT ( [% cortado · período], "0.0%" )', "[% cortado · var p.p.]", "[svg · sparkline % cortado]", "", pp=True)}
        & {card_dax(3, "Geração verificada", 'FORMAT ( [Geração · período], "#,0" )', "[Geração · var %]", "[svg · sparkline geração]", " GWh", ruim_se_sobe=False)}
        & {card_dax(4, "Usinas e conjuntos com corte", 'FORMAT ( [Usinas com corte · período], "#,0" )', "[Usinas com corte · var %]", "[svg · sparkline usinas]", "")}
        & "</div><div class='leg'>Variações " & _Cmp & ". Para cortes, alta é desfavorável (▲ em vermelho).</div>\""""
M.append(medida("html · KPIs", kpi_expr, None, "Visual", "Faixa de KPIs da página executiva (HTML Content)", oculta=True))

dest_expr = """VAR _T = [Não realizada · período]
VAR _Razoes =
    { ( "energética (ENE)", [ENE · período] ), ( "confiabilidade elétrica (CNF)", [CNF · período] ),
      ( "indisponibilidade externa (REL)", [REL · período] ), ( "parecer de acesso (PAR)", [PAR · período] ) }
VAR _RTop = TOPN ( 1, _Razoes, [Value2], DESC )
VAR _RNome = MAXX ( _RTop, [Value1] )
VAR _RPct = DIVIDE ( MAXX ( _RTop, [Value2] ), _T )
VAR _Sis = DIVIDE ( [Origem sistêmica · período], _T )
VAR _Est = TOPN ( 1, ADDCOLUMNS ( VALUES ( 'Estados'[Estado] ), "@v", [Não realizada · período] ), [@v], DESC )
VAR _EstNome = MAXX ( _Est, 'Estados'[Estado] )
VAR _EstPct = DIVIDE ( MAXX ( _Est, [@v] ), _T )
VAR _Us = TOPN ( 1, ADDCOLUMNS ( VALUES ( 'Usinas'[Usina] ), "@v", [Não realizada · período] ), [@v], DESC )
VAR _UsNome = MAXX ( _Us, 'Usinas'[Usina] )
VAR _UsGWh = MAXX ( _Us, [@v] )
VAR _Ini = [Início do período]
VAR _Fim = [_Fim do período]
VAR _Mes =
    TOPN ( 1,
        ADDCOLUMNS (
            CALCULATETABLE ( VALUES ( 'Calendário'[Mês] ), REMOVEFILTERS ( 'Calendário' ), DATESBETWEEN ( 'Calendário'[Data], _Ini, _Fim ) ),
            "@v", VAR _m = 'Calendário'[Mês] RETURN CALCULATE ( [Não realizada (GWh)], REMOVEFILTERS ( 'Calendário' ), 'Calendário'[Mês] = _m )
        ), [@v], DESC )
VAR _MesNome = FORMAT ( MAXX ( _Mes, 'Calendário'[Mês] ), "mmmm/yyyy" )
VAR _MesGWh = MAXX ( _Mes, [@v] )
RETURN
    IF ( ISBLANK ( _T ) || _T = 0, "<div class='vazio'>Sem geração não realizada no período e filtros selecionados.</div>",
    "<div class='tit'>" & IF ( ISFILTERED ( 'Calendário' ), "Destaques do período filtrado", "Destaques dos últimos 12 meses" ) & "</div><ul>"
        & "<li><b>" & FORMAT ( _RPct, "0%" ) & "</b> do corte teve razão <b>" & _RNome & "</b>.</li>"
        & IF ( NOT ISBLANK ( _Sis ), "<li><b>" & FORMAT ( _Sis, "0%" ) & "</b> veio de restrições <b>sistêmicas</b>, e não da rede local da usina.</li>" )
        & "<li><b>" & _EstNome & "</b> concentrou <b>" & FORMAT ( _EstPct, "0%" ) & "</b> da energia cortada.</li>"
        & "<li>Maior corte individual: <b>" & _UsNome & "</b>, com " & FORMAT ( _UsGWh, "#,0" ) & " GWh.</li>"
        & "<li>Mês com mais corte: <b>" & _MesNome & "</b> (" & FORMAT ( _MesGWh, "#,0" ) & " GWh).</li>"
        & "</ul><div class='nota'>Mesmo período dos cartões, com os filtros selecionados. Associação não implica causa.</div>" )"""
M.append(medida("html · Destaques", dest_expr, None, "Visual", "Painel de destaques da página executiva (HTML Content)", oculta=True))

def _nome(x): return re.search(r"measure '([^']+)'", x).group(1)
for x in M:  # substitui medidas já existentes, para que mudanças no texto sejam aplicadas
    fato = re.sub(r"(?:\t/// [^\n]*\n)?\tmeasure '" + re.escape(_nome(x)) + r"' =[^\n]*\n(?:\t\t[^\n]*\n|\n(?=\t\t))*", "", fato)
medidas_txt = "".join(M)
idx = fato.index("\tpartition ")
fato = fato[:idx] + medidas_txt + fato[idx:]
if novas_cols:
    idx = fato.index("\n\tpartition ")
    fato = fato[:idx] + novas_cols.rstrip("\n") + "\n" + fato[idx:]
wr(fato_p, fato)

# 1c. novas tabelas
def col(nome, src, tipo, oculta=False, fmt=None, chave=False, resumo="none", sort=None):
    t = f"\tcolumn {nome}\n\t\tdataType: {tipo}\n"
    if chave: t += "\t\tisKey\n"
    if oculta: t += "\t\tisHidden\n"
    if fmt: t += f"\t\tformatString: {fmt}\n"
    t += f"\t\tlineageTag: {uid('c/'+nome+src)}\n\t\tsummarizeBy: {resumo}\n\t\tsourceColumn: {src}\n"
    if sort: t += f"\t\tsortByColumn: {sort}\n"
    if tipo == "dateTime": t += "\n\t\tannotation UnderlyingDateTimeDataType = Date\n"
    return t + "\n"

def tabela(nome, desc, cols, m_expr, medidas=""):
    qn = f"'{nome}'" if " " in nome else nome
    t = f"/// {desc}\ntable {qn}\n\tlineageTag: {uid('t/'+nome)}\n\n"
    t += medidas + "".join(cols)
    t += f"\tpartition {qn} = m\n\t\tmode: import\n\t\tsource =\n"
    t += "".join(f"\t\t\t\t{l}\n" for l in m_expr.strip("\n").split("\n"))
    return t + "\n"

dim_usina = 'Tabela = Fonte{[Schema = "marts", Item = "dim_usina"]}[Data],'
wr(os.path.join(SM, "tables", "Fontes.tmdl"), tabela("Fontes", "Fontes de geração (a partir de marts.dim_usina)",
    [col("Fonte", "fonte_nome", "string"), col("Código", "fonte", "string", oculta=True, chave=True)],
    f"""let
    Fonte = PostgreSQL.Database(Servidor, Banco),
    {dim_usina}
    Colunas = Table.Distinct(Table.SelectColumns(Tabela, {{"fonte", "fonte_nome"}}))
in
    Colunas"""))
wr(os.path.join(SM, "tables", "Estados.tmdl"), tabela("Estados", "Estados das usinas (a partir de marts.dim_usina)",
    [col("UF", "uf", "string", chave=True), col("Estado", "estado", "string")],
    f"""let
    Fonte = PostgreSQL.Database(Servidor, Banco),
    {dim_usina}
    Colunas = Table.Distinct(Table.SelectColumns(Tabela, {{"uf", "estado"}}))
in
    Colunas"""))
perfil_medidas = (
    medida("Não realizada no horário (GWh)", "DIVIDE(SUM('Perfil horário'[nao_realizada_mwh]), 1000)", "#,0", None, "Geração não realizada no patamar de 30 minutos")
    + medida("% cortado no horário", "DIVIDE(SUM('Perfil horário'[nao_realizada_mwh]), SUM('Perfil horário'[geracao_mwh]) + SUM('Perfil horário'[nao_realizada_mwh]))", "0.0%", None, "Parte da geração possível cortada no patamar de 30 minutos")
    + medida("Geração no horário (GWh)", "DIVIDE(SUM('Perfil horário'[geracao_mwh]), 1000)", "#,0", None))
cols_perfil = [col("mes", "mes", "dateTime", oculta=True, fmt="mmm/yyyy"), col("fonte", "fonte", "string", oculta=True),
               col("uf", "uf", "string", oculta=True), col("Patamar", "patamar", "string"), col("Hora", "hora", "int64", fmt="0")]
for c in ("usinas", "registros", "registros_limitados"): cols_perfil.append(col(c, c, "int64", oculta=True, resumo="sum"))
for c in ("geracao_mwh", "referencia_mwh", "nao_realizada_mwh", "nao_realizada_ene_mwh", "nao_realizada_cnf_mwh", "nao_realizada_rel_mwh", "nao_realizada_par_mwh"):
    cols_perfil.append(col(c, c, "double", oculta=True, resumo="sum"))
wr(os.path.join(SM, "tables", "Perfil horário.tmdl"), tabela("Perfil horário",
    "Geração e geração não realizada por mês, fonte, estado e patamar de 30 minutos (marts.fct_restricao_perfil_horario)",
    cols_perfil, """let
    Fonte = PostgreSQL.Database(Servidor, Banco),
    Tabela = Fonte{[Schema = "marts", Item = "fct_restricao_perfil_horario"]}[Data],
    Patamar = Table.TransformColumns(Tabela, {{"patamar", each Time.ToText(_, "HH:mm"), type text}})
in
    Patamar""", perfil_medidas))

# 1d. relacionamentos e modelo
rel_p = os.path.join(SM, "relationships.tmdl"); rel = rd(rel_p)
for nome, de, para in [("perfil-cal", "'Perfil horário'.mes", "Calendário.Data"), ("perfil-fonte", "'Perfil horário'.fonte", "Fontes.Código"),
                       ("perfil-uf", "'Perfil horário'.uf", "Estados.UF"), ("usina-fonte", "Usinas.'Código da fonte'", "Fontes.Código"),
                       ("usina-uf", "Usinas.UF", "Estados.UF")]:
    if f"fromColumn: {de}\n" not in rel:
        rel += f"\nrelationship {uid('r/'+nome)}\n\tfromColumn: {de}\n\ttoColumn: {para}\n"
wr(rel_p, rel)
mod_p = os.path.join(SM, "model.tmdl"); mod = rd(mod_p)
for t in ("Fontes", "Estados", "'Perfil horário'"):
    if f"ref table {t}\n" not in mod: mod = mod.rstrip("\n") + f"\nref table {t}\n"
mod = re.sub(r'annotation PBI_QueryOrder = \[.*\]', 'annotation PBI_QueryOrder = ["Servidor","Banco","Restrição diária","Usinas","Calendário","Fontes","Estados","Perfil horário"]', mod)
wr(mod_p, mod)

# =====================================================================================
# 2. TEMA DOME
# =====================================================================================
tema = {
  "name": "Dome Analytics",
  "dataColors": ["#252423", "#F2C811", "#8A8886", "#967100", "#C8C6C4", "#1F4E8C", "#605E5C", "#FAD227"],
  "foreground": "#191919", "foregroundNeutralSecondary": "#605E5C", "foregroundNeutralTertiary": "#8A8886",
  "background": "#FFFFFF", "backgroundLight": "#F6F5F3", "backgroundNeutral": "#E1DFDD",
  "tableAccent": "#F2C811", "good": "#107C10", "neutral": "#B54708", "bad": "#C84720",
  "maximum": "#967100", "center": "#F2C811", "minimum": "#FDF8DC",
  "textClasses": {
    "callout": {"fontSize": 26, "fontFace": "Segoe UI Semibold", "color": "#191919"},
    "title": {"fontSize": 11, "fontFace": "Segoe UI Semibold", "color": "#191919"},
    "header": {"fontSize": 11, "fontFace": "Segoe UI Semibold", "color": "#191919"},
    "label": {"fontSize": 9, "fontFace": "Segoe UI", "color": "#605E5C"}},
  "visualStyles": {
    "page": {"*": {"background": [{"color": {"solid": {"color": "#F6F5F3"}}, "transparency": 0}]}},
    "*": {"*": {
        "background": [{"show": True, "color": {"solid": {"color": "#FFFFFF"}}, "transparency": 0}],
        "border": [{"show": True, "color": {"solid": {"color": "#E1DFDD"}}, "radius": 2}],
        "padding": [{"top": 10, "bottom": 10, "left": 12, "right": 12}],
        "visualHeader": [{"show": False}]}},
    "textbox": {"*": {"background": [{"show": False}], "border": [{"show": False}],
                      "padding": [{"top": 0, "bottom": 0, "left": 0, "right": 0}]}},
    # sem o padding do "*": com 10/12 px a caixa da lista suspensa fica cortada embaixo
    "slicer": {"*": {"background": [{"show": False}], "border": [{"show": False}],
                     "padding": [{"top": 0, "bottom": 4, "left": 0, "right": 0}]}},
    "actionButton": {"*": {"padding": [{"top": 0, "bottom": 0, "left": 0, "right": 0}]}}}
}
os.makedirs(os.path.join(RS, "RegisteredResources"), exist_ok=True)
TEMA_ARQ = "DomeAnalytics.json"
json.dump(tema, open(os.path.join(RS, "RegisteredResources", TEMA_ARQ), "w", encoding="utf-8"), ensure_ascii=False, indent=2)
rep_p = os.path.join(RP, "report.json"); rep = json.load(open(rep_p, encoding="utf-8"))
ver = rep["themeCollection"]["baseTheme"]["reportVersionAtImport"]
rep["themeCollection"]["customTheme"] = {"name": TEMA_ARQ, "reportVersionAtImport": ver, "type": "RegisteredResources"}
rep["resourcePackages"] = [p for p in rep["resourcePackages"] if p["type"] != "RegisteredResources"]
rep["resourcePackages"].append({"name": "RegisteredResources", "type": "RegisteredResources",
                                "items": [{"name": TEMA_ARQ, "path": TEMA_ARQ, "type": "CustomTheme"}]})
for v in (DENEB, HTMLC):
    if v not in rep.setdefault("publicCustomVisuals", []): rep["publicCustomVisuals"].append(v)
json.dump(rep, open(rep_p, "w", encoding="utf-8"), ensure_ascii=False, indent=2)

# =====================================================================================
# 3. PÁGINA EXECUTIVA
# =====================================================================================
def lit(v): return {"expr": {"Literal": {"Value": v}}}
def s(v): return lit("'" + v.replace("'", "''") + "'")
def cor(c): return {"solid": {"color": s(c)}}
def proj_m(ent, nome): return {"field": {"Measure": {"Expression": {"SourceRef": {"Entity": ent}}, "Property": nome}}, "queryRef": f"{ent}.{nome}", "nativeQueryRef": nome}
def proj_c(ent, nome): return {"field": {"Column": {"Expression": {"SourceRef": {"Entity": ent}}, "Property": nome}}, "queryRef": f"{ent}.{nome}", "nativeQueryRef": nome}

def container(titulo=None, fundo=True, borda=True):
    o = {"title": [{"properties": {"show": lit("true" if titulo else "false"), **({"text": s(titulo), "fontSize": lit("11D"), "fontColor": cor("#191919"), "bold": lit("true")} if titulo else {})}}],
         "background": [{"properties": {"show": lit("true" if fundo else "false"), **({"color": cor("#FFFFFF"), "transparency": lit("0D")} if fundo else {})}}],
         "border": [{"properties": {"show": lit("true" if borda else "false"), **({"color": cor("#E1DFDD"), "width": lit("1D"), "radius": lit("2D")} if borda else {})}}],
         "visualHeader": [{"properties": {"show": lit("false")}}]}
    return o

def vc(nome, x, y, w, h, z, visual):
    return {"$schema": SCHEMA_VC, "name": nome, "position": {"x": x, "y": y, "z": z, "height": h, "width": w, "tabOrder": z}, "visual": visual}

def html_visual(medida_nome, css, titulo=None, fundo=True, borda=True):
    return {"visualType": HTMLC, "query": {"queryState": {"content": {"projections": [proj_m(FATO, medida_nome)]}}},
            "objects": {"compatibility": [{"properties": {"legacyRendering": lit("false")}}],
                        "stylesheet": [{"properties": {"stylesheet": s(css)}}]},
            "visualContainerObjects": container(titulo, fundo, borda), "drillFilterOtherVisuals": True}

DENEB_CFG = {
  "locale": {"number": {"decimal": ",", "thousands": ".", "grouping": [3], "currency": ["R$ ", ""]},
             "time": {"dateTime": "%A, %e de %B de %Y. %X", "date": "%d/%m/%Y", "time": "%H:%M:%S", "periods": ["AM", "PM"],
                      "days": ["domingo", "segunda", "terça", "quarta", "quinta", "sexta", "sábado"],
                      "shortDays": ["dom", "seg", "ter", "qua", "qui", "sex", "sáb"],
                      "months": ["janeiro", "fevereiro", "março", "abril", "maio", "junho", "julho", "agosto", "setembro", "outubro", "novembro", "dezembro"],
                      "shortMonths": ["jan", "fev", "mar", "abr", "mai", "jun", "jul", "ago", "set", "out", "nov", "dez"]}},
  "autosize": {"type": "fit", "contains": "padding"}, "background": "transparent", "font": "Segoe UI, Open Sans, sans-serif",
  "view": {"stroke": None},
  "axis": {"labelColor": "#605E5C", "titleColor": "#605E5C", "labelFontSize": 10, "titleFontSize": 10, "titleFontWeight": "normal",
           "gridColor": "#EDEBE9", "domain": False, "tickColor": "#E1DFDD"},
  "axisX": {"grid": False}, "legend": {"labelColor": "#605E5C", "titleColor": "#605E5C", "labelFontSize": 10, "symbolType": "square"},
  "bar": {"cornerRadiusEnd": 0}, "line": {"strokeWidth": 2}}

def deneb_visual(campos, spec, titulo):
    return {"visualType": DENEB, "query": {"queryState": {"dataset": {"projections": campos}}},
            "objects": {"vega": [{"properties": {"jsonSpec": s(json.dumps(spec, ensure_ascii=False, indent=2)),
                                                 "jsonConfig": s(json.dumps(DENEB_CFG, ensure_ascii=False, indent=2)),
                                                 "provider": s("vegaLite"), "renderMode": s("svg"), "enableTooltips": lit("true")}}],
                        "developer": [{"properties": {"locale": s("pt-BR")}}]},
            "visualContainerObjects": container(titulo), "drillFilterOtherVisuals": True}

def run(t, tam, c, b=False): return {"value": t, "textStyle": {"fontSize": f"{tam}pt", "fontWeight": "bold" if b else "normal", "color": c}}

CSS_KPI = """.cab{display:flex;justify-content:space-between;font-family:'Segoe UI',sans-serif;font-size:11px;color:#605E5C;margin:0 2px 8px 2px}
.cab .per{color:#191919;font-weight:600}
.kpis{display:flex;gap:12px;font-family:'Segoe UI',sans-serif}
.card{flex:1;background:#FFFFFF;border:1px solid #E1DFDD;border-top:3px solid #191919;padding:10px 12px;border-radius:2px}
.card:first-child{border-top-color:#F2C811}
.rot{font-size:10px;letter-spacing:.08em;text-transform:uppercase;color:#605E5C}
.lin{display:flex;justify-content:space-between;align-items:flex-end;margin-top:4px}
.val{font-size:28px;font-weight:600;color:#191919;line-height:1.1}
.un{font-size:13px;font-weight:400;color:#605E5C;margin-left:3px}
.var{font-size:12px;font-weight:600;margin-top:3px}
.ruim{color:#C84720}.bom{color:#107C10}.neu{color:#8A8886;font-weight:400}
.spk{padding-bottom:2px}
.leg{font-family:'Segoe UI',sans-serif;font-size:10px;color:#8A8886;margin:6px 2px 0 2px}"""
CSS_DEST = """.tit{font-family:'Segoe UI',sans-serif;font-size:11px;letter-spacing:.08em;text-transform:uppercase;color:#F2C811;font-weight:700;margin-bottom:8px}
ul{list-style:none;margin:0;padding:0;font-family:'Segoe UI',sans-serif}
li{position:relative;padding:0 0 10px 16px;font-size:13px;line-height:1.35;color:#FFFFFF}
li:before{content:'';position:absolute;left:0;top:6px;width:7px;height:7px;background:#F2C811}
b{color:#FFFFFF;font-weight:700}
.nota{font-family:'Segoe UI',sans-serif;font-size:10px;color:#C8C6C4;margin-top:4px}
.vazio{font-family:'Segoe UI',sans-serif;font-size:13px;color:#C8C6C4}"""

spec_barras = {
  "data": {"name": "dataset"}, "width": "container", "height": "container",
  "transform": [{"calculate": "datum['Não realizada (GWh)']", "as": "gwh"}],
  "mark": {"type": "bar", "width": {"band": 0.78}},
  "encoding": {
    "x": {"field": "Mês", "type": "temporal", "timeUnit": "yearmonth", "title": None,
          "axis": {"format": "%Y", "tickCount": "year", "labelAlign": "left", "labelPadding": 6}},
    "y": {"field": "gwh", "type": "quantitative", "stack": "zero", "title": "GWh", "axis": {"format": ",.0f", "tickCount": 5}},
    "color": {"field": "Fonte", "type": "nominal", "scale": {"domain": ["Eólica", "Solar"], "range": ["#252423", "#F2C811"]},
              "legend": {"orient": "top", "direction": "horizontal", "title": None, "offset": 4}},
    "order": {"field": "Fonte", "sort": "ascending"},
    "tooltip": [{"field": "Mês", "type": "temporal", "timeUnit": "yearmonth", "title": "Mês", "format": "%m/%Y"},
                {"field": "Fonte", "type": "nominal"},
                {"field": "gwh", "type": "quantitative", "title": "Não realizada (GWh)", "format": ",.0f"}]}}
spec_pct = {
  "data": {"name": "dataset"}, "width": "container", "height": "container",
  "transform": [{"calculate": "datum['Não realizada (GWh)'] / (datum['Geração (GWh)'] + datum['Não realizada (GWh)'])", "as": "pct"},
                {"filter": "isValid(datum.pct)"}],
  "mark": {"type": "line", "interpolate": "monotone", "strokeWidth": 2, "point": {"size": 12, "filled": True}},
  "encoding": {
    "x": {"field": "Mês", "type": "temporal", "timeUnit": "yearmonth", "title": None, "axis": {"format": "%Y", "tickCount": "year", "labelAlign": "left", "labelPadding": 6}},
    "y": {"field": "pct", "type": "quantitative", "title": None, "axis": {"format": ".0%", "tickCount": 4}},
    "color": {"field": "Fonte", "type": "nominal", "scale": {"domain": ["Eólica", "Solar"], "range": ["#252423", "#E0B000"]}, "legend": None},
    "tooltip": [{"field": "Mês", "type": "temporal", "timeUnit": "yearmonth", "title": "Mês", "format": "%m/%Y"},
                {"field": "Fonte", "type": "nominal"}, {"field": "pct", "type": "quantitative", "title": "% cortado", "format": ".1%"}]}}
cats = ["ENE", "CNF", "REL", "PAR", "Sem razão", "Origem local", "Origem sistêmica", "Sem origem"]
spec_razoes = {
  "data": {"name": "dataset"}, "width": "container", "height": "container",
  "transform": [
    {"fold": [f"{c} · período" for c in cats], "as": ["medida", "gwh"]},
    {"calculate": "replace(datum.medida, ' · período', '')", "as": "cat"},
    {"calculate": "indexof(['Origem local','Origem sistêmica','Sem origem'], datum.cat) >= 0 ? 'Origem' : 'Razão'", "as": "grupo"},
    {"calculate": "indexof(['ENE','CNF','REL','PAR','Sem razão','Origem local','Origem sistêmica','Sem origem'], datum.cat)", "as": "ordem"},
    {"joinaggregate": [{"op": "sum", "field": "gwh", "as": "tot"}], "groupby": ["grupo"]},
    {"calculate": "datum.tot > 0 ? datum.gwh / datum.tot : 0", "as": "pct"},
    {"window": [{"op": "sum", "field": "pct", "as": "fim"}], "groupby": ["grupo"], "sort": [{"field": "ordem"}], "frame": [None, 0]},
    {"calculate": "datum.fim - datum.pct", "as": "ini"},
    {"calculate": "datum.fim - datum.pct / 2", "as": "meio"}],
  "encoding": {"y": {"field": "grupo", "type": "nominal", "title": None, "sort": ["Razão", "Origem"],
                     "axis": {"labelFontSize": 11, "labelColor": "#191919", "labelFontWeight": "bold", "ticks": False}}},
  "layer": [
    {"mark": {"type": "bar", "height": {"band": 0.62}},
     "encoding": {
       "x": {"field": "ini", "type": "quantitative", "axis": None, "scale": {"domain": [0, 1]}},
       "x2": {"field": "fim"},
       "color": {"field": "cat", "type": "nominal", "scale": {"domain": cats, "range": ["#252423", "#605E5C", "#A19F9D", "#967100", "#E1DFDD", "#F2C811", "#191919", "#E1DFDD"]},
                 "legend": {"orient": "bottom", "columns": 4, "title": None, "labelFontSize": 9, "symbolSize": 60, "columnPadding": 8, "labelLimit": 90,
                            "labelExpr": "replace(replace(datum.label, 'Origem local', 'Local'), 'Origem sistêmica', 'Sistêmica')"}},
       "tooltip": [{"field": "grupo", "title": "Grupo"}, {"field": "cat", "title": "Categoria"},
                   {"field": "gwh", "title": "GWh", "format": ",.0f"}, {"field": "pct", "title": "Participação", "format": ".1%"}]}},
    {"transform": [{"filter": "datum.pct >= 0.07"}],
     "mark": {"type": "text", "fontSize": 10, "fontWeight": "bold", "align": "center"},
     "encoding": {
       "x": {"field": "meio", "type": "quantitative"},
       "text": {"field": "pct", "format": ".0%"},
       "color": {"condition": {"test": "indexof(['ENE','CNF','Origem sistêmica','PAR'], datum.cat) >= 0", "value": "#FFFFFF"}, "value": "#191919"}}}]}

pg = os.path.join(RP, "pages", "visao_geral")
vis_dir = os.path.join(pg, "visuals")
# guarda os filtros, apaga o resto (inclusive o tour antigo desta página)
filtros = {}
for n in os.listdir(vis_dir):
    if n.startswith("filtro_"): filtros[n] = json.load(open(os.path.join(vis_dir, n, "visual.json"), encoding="utf-8"))
    shutil.rmtree(os.path.join(vis_dir, n))
page = json.load(open(os.path.join(pg, "page.json"), encoding="utf-8")); page["displayName"] = "Visão executiva"
json.dump(page, open(os.path.join(pg, "page.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=2)

def salvar(v):
    d = os.path.join(vis_dir, v["name"]); os.makedirs(d, exist_ok=True)
    json.dump(v, open(os.path.join(d, "visual.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=2)

def retarget_filtros(f):
    q = f["visual"]["query"]["queryState"]["Values"]["projections"][0]
    prop = q["field"]["Column"]["Property"]
    if q["field"]["Column"]["Expression"]["SourceRef"]["Entity"] == "Usinas":
        ent = "Fontes" if prop == "Fonte" else "Estados"
        q["field"]["Column"]["Expression"]["SourceRef"]["Entity"] = ent
        q["queryRef"] = f"{ent}.{prop}"
    f["visual"]["visualContainerObjects"] = container(None, fundo=False, borda=False)
    return f

for n, f in filtros.items(): salvar(retarget_filtros(f))

salvar(vc("titulo", 24, 8, 600, 70, 1000, {"visualType": "textbox", "objects": {"general": [{"properties": {"paragraphs": [
    {"textRuns": [run("CORTES DE GERAÇÃO EÓLICA E SOLAR · BRASIL", 9, "#967100", True)]},
    {"textRuns": [run("Quanta energia o ONS mandou não gerar", 16, "#191919", True)]},
    {"textRuns": [run("Constrained-off das usinas eólicas e solares · ONS, dados abertos · Dome Analytics", 9, "#605E5C")]}]}}]},
    "visualContainerObjects": container(None, False, False), "drillFilterOtherVisuals": True}))
kpis = html_visual("html · KPIs", CSS_KPI, fundo=False, borda=False)
kpis["visualContainerObjects"]["padding"] = [{"properties": {k: lit("0D") for k in ("top", "bottom", "left", "right")}}]
salvar(vc("kpis", 24, 80, 1232, 144, 2000, kpis))
campos_mes = [proj_c("Calendário", "Mês"), proj_c("Fontes", "Fonte"), proj_m(FATO, "Não realizada (GWh)"), proj_m(FATO, "Geração (GWh)")]
salvar(vc("hero_barras", 24, 232, 800, 300, 3000, deneb_visual(campos_mes, spec_barras, "Geração não realizada por mês e fonte (GWh)")))
salvar(vc("hero_pct", 24, 540, 800, 160, 4000, deneb_visual(campos_mes, spec_pct, "% da geração possível que foi cortada, por fonte")))
dest = html_visual("html · Destaques", CSS_DEST, fundo=False, borda=False)
dest["visualContainerObjects"]["background"] = [{"properties": {"show": lit("true"), "color": cor("#191919"), "transparency": lit("0D")}}]
dest["visualContainerObjects"]["padding"] = [{"properties": {k: lit("16D") for k in ("top", "bottom", "left", "right")}}]
salvar(vc("destaques", 840, 232, 416, 268, 5000, dest))
salvar(vc("razoes_origem", 840, 510, 416, 190, 6000, deneb_visual([proj_m(FATO, f"{c} · período") for c in cats], spec_razoes, "Razão e origem do corte, no período dos cartões")))

# página 2: filtros nas novas dimensões
pg2 = os.path.join(RP, "pages", "estados_usinas", "visuals")
for n in os.listdir(pg2):
    if n.startswith("filtro_"):
        p = os.path.join(pg2, n, "visual.json")
        json.dump(retarget_filtros(json.load(open(p, encoding="utf-8"))), open(p, "w", encoding="utf-8"), ensure_ascii=False, indent=2)
print("ok: modelo, tema e página executiva")
