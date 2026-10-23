import os, base64, io, zipfile
from jinja2 import Environment, FileSystemLoader
from weasyprint import HTML, CSS
from datetime import datetime

_FUNDO_DEFAULT = "https://vesgrrejcehseygchigh.supabase.co/storage/v1/object/public/logos/certificado_conecta_fundo.png"
_FUNDO_TREINNAR = "https://vesgrrejcehseygchigh.supabase.co/storage/v1/object/public/logos/Certificados_treinnar.jpg"

def _resolver_imagem(p):
    if not p: return ""
    p = str(p).strip()
    if p.startswith(("http://", "https://", "data:")): return p
    if os.path.exists(p):
        try:
            ext = os.path.splitext(p)[1].lower().lstrip(".")
            mime = {"jpg":"jpeg","jpeg":"jpeg","png":"png"}.get(ext,"png")
            return f"data:image/{mime};base64," + base64.b64encode(open(p,"rb").read()).decode()
        except Exception: return ""
    return ""

def _fundo_do_ct(ct):
    ct = ct or {}
    for key in ("fundo_certificado_url","fundo_certificado","certificado_fundo_url","fundo_url"):
        v = (ct.get(key) or "").strip()
        if v: return v
    for k,v in ct.items():
        if isinstance(v,str) and v.startswith("http") and "certificado" in v.lower():
            return v.strip()
    if "treinnar" in f"{ct.get('name') or ''} {ct.get('full_name') or ''}".lower():
        return _FUNDO_TREINNAR
    return ""

def gerar_certificado_html(aluno, turma, instrutor, empresa=None, ct=None, normativa="", cidade_data="", caminho_fundo=None, caminho_pasta_templates="src/templates"):
    env = Environment(loader=FileSystemLoader(caminho_pasta_templates))
    tpl = env.get_template("template_certificado.html")
    fundo = (caminho_fundo or "").strip() or _fundo_do_ct(ct) or _FUNDO_DEFAULT
    img = _resolver_imagem(fundo) or _FUNDO_DEFAULT
    ass_i = _resolver_imagem(instrutor.get("assinatura") or instrutor.get("assinatura_url") or "")
    ass_r = _resolver_imagem(turma.get("assinatura_resp_url") or "")
    cpf, rg = aluno.get("cpf",""), aluno.get("rg","")
    parts = []
    if rg: parts.append(f"RG: {rg}")
    if cpf:
        cf = f"{cpf[:3]}.{cpf[3:6]}.{cpf[6:9]}-{cpf[9:]}" if len(cpf)==11 else cpf
        parts.append(cf)
    ci = instrutor.get("cpf","")
    cif = f"{ci[:3]}.{ci[3:6]}.{ci[6:9]}-{ci[9:]}" if len(ci)==11 else ci
    dn = ""
    raw = aluno.get("data_nasc") or ""
    if raw:
        try: dn = datetime.strptime(str(raw).split("T")[0], "%Y-%m-%d").strftime("%d/%m/%Y")
        except Exception: dn = str(raw)
    cr = turma.get("cpf_resp_tecnico","")
    crf = f"{cr[:3]}.{cr[3:6]}.{cr[6:9]}-{cr[9:]}" if len(cr)==11 else cr
    formacao_i = (instrutor.get("formacao") or "").strip()
    formacao_r = (turma.get("formacao_resp_tecnico") or "").strip()
    diz = turma.get("dizeres_certificado_aluno") or (
        f'Certificamos que o aluno acima identificado realizou o treinamento de "{turma.get("curso_nome","Treinamento")}"'
        + (f", em conformidade com as exigencias da {normativa}." if normativa else ".")
    )
    return tpl.render(
        IMAGEM_FUNDO=img, NOME_ALUNO=aluno.get("name",""), RG_CPF=" / ".join(parts),
        DATA_NASCIMENTO=dn, EMPRESA=(empresa or {}).get("name",""),
        ENDERECO_EMPRESA=(empresa or {}).get("full_address",""),
        NIVEL=(turma.get("nivel") or "").strip() or "Formacao",
        MODALIDADE=(turma.get("modalidade") or "").strip() or "Presencial",
        CARGA_HORARIA=(turma.get("carga_horaria") or "").strip() or "8 Horas",
        NORMATIVA=normativa, CIDADE_DATA=cidade_data,
        ASSINATURA_INSTRUTOR=ass_i, NOME_INSTRUTOR=instrutor.get("name",""),
        CPF_INSTRUTOR=cif, RE_INSTRUTOR=(instrutor.get("re") or "").strip(),
        FORMACAO_INSTRUTOR=formacao_i,
        RESP_TECNICO=turma.get("resp_tecnico",""), CPF_RESP=crf,
        RE_RESP=(turma.get("re_resp_tecnico") or "").strip(),
        FORMACAO_RESP=formacao_r,
        ASSINATURA_RESP_TECNICO=ass_r, CURSO_NOME=turma.get("curso_nome",""),
        DIZERES_CERTIFICADO=diz,
    )

def gerar_certificados_pdf(alunos_matriculas, turma, instrutor, empresa=None, ct=None, normativa="", cidade_data="", caminho_fundo=None, caminho_pasta_templates="src/templates"):
    from pypdf import PdfWriter, PdfReader
    w = PdfWriter()
    for a in alunos_matriculas:
        t = {**turma, "carga_horaria": a.get("horas", turma.get("carga_horaria", "8 Horas"))}
        html = gerar_certificado_html(a, t, instrutor, empresa, ct, normativa, cidade_data, caminho_fundo, caminho_pasta_templates)
        pdf = HTML(string=html).write_pdf(stylesheets=[CSS(string="@page { size: A4 landscape; margin: 0; }")])
        for p in PdfReader(io.BytesIO(pdf)).pages: w.add_page(p)
    out = io.BytesIO(); w.write(out); return out.getvalue()

def gerar_certificados_pdf_zip(alunos_matriculas, turma, instrutor, empresa=None, ct=None, normativa="", cidade_data="", caminho_fundo=None, caminho_pasta_templates="src/templates"):
    if not alunos_matriculas: raise ValueError("Nenhum aluno para gerar certificado.")
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        for a in alunos_matriculas:
            t = {**turma, "carga_horaria": a.get("horas", turma.get("carga_horaria", "8 Horas"))}
            html = gerar_certificado_html(a, t, instrutor, empresa, ct, normativa, cidade_data, caminho_fundo, caminho_pasta_templates)
            pdf = HTML(string=html).write_pdf(stylesheets=[CSS(string="@page { size: A4 landscape; margin: 0; }")])
            nome = "".join(c if c.isalnum() or c in " -_" else "" for c in (a.get("name") or "aluno")).strip().replace(" ", "_")
            zf.writestr(f"{nome}.pdf", pdf)
    buf.seek(0); return buf.getvalue()
