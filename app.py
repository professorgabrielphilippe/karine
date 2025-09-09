# app_final_google.py
# -*- coding: utf-8 -*-
"""
Aplicativo Streamlit otimizado para navegação de registros por Categoria → Conceito → Registros.
Paginação interna, Link/DOI com fallback Google Scholar e atualização imediata do status "Lido".
"""

import json
from typing import List
import pandas as pd
import streamlit as st
import urllib.parse
from datetime import datetime

st.set_page_config(
    page_title="Arquivo de Experiência",
    page_icon="📚",
    layout="wide",
)

# -------------------- CSS personalizado --------------------
CUSTOM_CSS = """
<style>
.block-container { padding-top: 1rem !important; }
h1,h2,h3 { color: #111827; }
.badge-cat { display:inline-block; padding: 0.15rem 0.5rem; border-radius:999px; background:#EEF2FF; color:#4F46E5; font-weight:600; font-size:0.8rem; }
.registro { padding:0.35rem 0.5rem; border:1px solid #E5E7EB; border-radius:10px; margin-bottom:0.25rem; background:#fff; }
.registro:hover { border-color:#4F46E5; box-shadow:0 1px 6px rgba(79,70,229,0.08); }
.desc { color:#374151; font-size:0.9rem; margin-top:0.2rem; }
.pill { display:inline-block; padding:0.1rem 0.35rem; border-radius:999px; font-size:0.75rem; font-weight:600; margin-left:0.3rem; }
.pill-ok { background: rgba(16,185,129,0.12); color:#10B981; }
.pill-nok { background: #F3F4F6; color:#6B7280; }
.stButton>button { padding: 0.2rem 0.5rem !important; font-size:0.8rem !important; height:1.8rem !important; }
</style>
"""
st.markdown(CUSTOM_CSS, unsafe_allow_html=True)

# -------------------- Configuração --------------------
REQUIRED_COLS: List[str] = [
    "id_registro","id_extracao","titulo_artigo","area_publicacao",
    "periodico","ano_publicacao","autoria","link_acesso",
    "doi","categoria","conceito","descricao"
]

PAGE_SIZE = 20  # Número de registros por página

# -------------------- Funções --------------------
@st.cache_data(show_spinner=False)
def read_excel(file) -> pd.DataFrame:
    return pd.read_excel(file, engine="openpyxl")

def validate_columns(df: pd.DataFrame) -> List[str]:
    return [c for c in REQUIRED_COLS if c not in df.columns]

def ensure_session_state():
    if "df" not in st.session_state:
        st.session_state["df"] = None
    if "status_map" not in st.session_state:
        st.session_state["status_map"] = {}
    if "data_dict" not in st.session_state:
        st.session_state["data_dict"] = {}

def make_record_key(row: dict) -> str:
    base = f"{row.get('id_registro','')}-{row.get('conceito','')}"
    idx = str(row.get("__idx__", ""))
    return f"k::{base}::{idx}"

def export_progress() -> str:
    return json.dumps(st.session_state["status_map"], ensure_ascii=False, indent=2)

def import_progress(json_text: str):
    try:
        data = json.loads(json_text)
        if isinstance(data, dict):
            st.session_state["status_map"].update({k: bool(v) for k, v in data.items()})
            st.success("Progresso importado com sucesso!")
        else:
            st.error("Arquivo de progresso inválido: conteúdo não é um objeto JSON.")
    except Exception as e:
        st.error(f"Falha ao importar progresso: {e}")

def preprocess_data(df: pd.DataFrame) -> dict:
    """Agrupa registros por categoria e conceito para renderização rápida"""
    df = df.reset_index(drop=False).rename(columns={"index": "__idx__"})
    df["categoria"] = df["categoria"].astype(str)
    df["conceito"] = df["conceito"].astype(str)
    df_sorted = df.sort_values(by=["categoria","conceito","id_registro","ano_publicacao"], ascending=True)
    data_dict = {}
    for cat, df_cat in df_sorted.groupby("categoria", sort=False):
        data_dict[cat] = {}
        for conc, df_conc in df_cat.groupby("conceito", sort=False):
            data_dict[cat][conc] = df_conc.to_dict(orient="records")
    return data_dict

# Callback para atualização imediata do status lido
def toggle_lido_callback(key):
    st.session_state["status_map"][key] = st.session_state[f"tgl::{key}"]

# -------------------- Interface --------------------
st.title("📚 Arquivo de Experiência")
st.caption("Carregue um arquivo Excel (.xlsx) para processamento na interface")

ensure_session_state()

# --- Upload e processamento ---
with st.container(border=True):
    st.subheader("⬆️ Carregar arquivo Excel (.xlsx)")
    uploaded = st.file_uploader("Selecione um arquivo Excel (.xlsx)", type=["xlsx"], accept_multiple_files=False)
    valid = False
    df = None
    if uploaded is not None:
        with st.spinner("Carregando arquivo..."):
            df = read_excel(uploaded)
        missing = validate_columns(df)
        if missing:
            st.error("Arquivo inválido. Colunas ausentes: " + ", ".join(missing))
        else:
            st.success("Arquivo válido! Você pode processar os dados.")
            valid = True
    process = st.button("⚙️ Processar dados", type="primary", disabled=not valid)
    if process and df is not None and valid:
        st.session_state["df"] = df.copy()
        st.session_state["data_dict"] = preprocess_data(df)
        st.toast("Dados processados e prontos!", icon="✅")

# --- Exibição dos registros ---
if st.session_state["df"] is not None:
    data_dict = st.session_state["data_dict"]

    with st.sidebar:
        st.header("🎯 Filtros")
        all_cats = sorted(data_dict.keys())
        selected_cats = st.multiselect("Categorias", options=all_cats, default=[], help="Selecione uma ou mais categorias para visualizar os registros.")
        st.divider()
        st.header("💾 Progresso")

        date_now = datetime.now()
        json_name = "progresso_leitura_" + date_now.strftime("%d_%m_%Y-%H_%M") + ".json"

        st.download_button("⬇️ Exportar progresso (JSON)", data=export_progress(), file_name=json_name, mime="application/json", use_container_width=True)
        prog_file = st.file_uploader("Importar progresso (JSON)", type=["json"], key="progress_upl")
        if prog_file is not None:
            import_progress(prog_file.read().decode("utf-8"))

    if not selected_cats:
        st.info("Selecione ao menos uma categoria para visualizar os registros.")
    else:
        for cat in selected_cats:
            if cat not in data_dict:
                continue
            with st.expander(f"📂 {cat}", expanded=False):
                for conc, records in data_dict[cat].items():
                    with st.expander(f"🧩 {conc}", expanded=False):
                        start = st.session_state.get(f"page_{cat}_{conc}", 0)
                        end = start + PAGE_SIZE
                        for row in records[start:end]:
                            id_reg = row.get("id_registro", "")
                            titulo = str(row.get("titulo_artigo","")).strip()
                            desc = str(row.get("descricao","")).strip()

                            # Link Google Scholar baseado no título
                            google_scholar_title = urllib.parse.quote_plus(titulo)
                            link_google_scholar = f"https://scholar.google.com/scholar?q={google_scholar_title}"

                            # Link e DOI com fallback
                            link_raw = str(row.get("link_acesso","")).strip()
                            doi_raw = str(row.get("doi","")).strip()

                            link_final = link_raw if link_raw.lower().startswith(("http://","https://")) else link_google_scholar
                            doi_final  = doi_raw if doi_raw.lower().startswith(("http://","https://")) else link_google_scholar

                            key = make_record_key(row)
                            if key not in st.session_state["status_map"]:
                                st.session_state["status_map"][key] = False
                            lido = st.session_state["status_map"][key]
                            pill = "<span class='pill pill-ok'>Lido</span>" if lido else "<span class='pill pill-nok'>Não lido</span>"

                            # Layout título + botões Link/DOI
                            col1, col2, col3 = st.columns([5,1,1])
                            col1.markdown(f"**[{id_reg}] {titulo}** {pill}", unsafe_allow_html=True)
                            col2.markdown(f'<a href="{link_final}" target="_blank">Link</a>', unsafe_allow_html=True)
                            col3.markdown(f'<a href="{doi_final}" target="_blank">DOI</a>', unsafe_allow_html=True)

                            # Descrição
                            st.markdown(f"<div class='desc'>{desc}</div>", unsafe_allow_html=True)

                            # Checkbox Lido com atualização imediata
                            st.checkbox(
                                label=f"Marcar como lido (Registro {id_reg})",
                                value=lido,
                                key=f"tgl::{key}",
                                on_change=toggle_lido_callback,
                                args=(key,)
                            )

                        # Botão carregar mais
                        if end < len(records):
                            if st.button("Carregar mais registros", key=f"btn_more_{cat}_{conc}"):
                                st.session_state[f"page_{cat}_{conc}"] = end
                        else:
                            st.session_state[f"page_{cat}_{conc}"] = 0

st.divider()
st.caption("Feito com Streamlit • Arquivo de Experiência • Universidade do Estado de Minas Gerais (UEMG) • 2025")
