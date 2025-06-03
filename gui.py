# gui.py
"""Haupt-GUI für Ömer’s Solar-App – kompakte, FUNKTIONSFÄHIGE Version (Mai 2025)."""

from __future__ import annotations # MUSS DIE ALLERERSTE CODE-ZEILE SEIN

import importlib
import traceback
from typing import Any, Callable, Dict, List, Optional, IO, Union
import io
import math
import pandas as pd
import streamlit as st
import sys
import os
import json

# Import streamlit_shadcn_ui with fallback
try:
    import streamlit_shadcn_ui as sui
    SUI_AVAILABLE = True
except ImportError:
    SUI_AVAILABLE = False
    sui = None


# Globale Importfehlerliste
import_errors: List[str] = []

# Initialtexte laden
_texts_initial: Dict[str, str] = {}
try:
    _temp_base_dir = os.path.dirname(os.path.abspath(__file__))
    _temp_file_path = os.path.join(_temp_base_dir, 'de.json')
    if os.path.exists(_temp_file_path):
        with open(_temp_file_path, 'r', encoding='utf-8') as f:
            loaded_texts = json.load(f)
            if isinstance(loaded_texts, dict) and loaded_texts:
                _texts_initial = loaded_texts
            else:
                # print(f"GUI WARNUNG: de.json ist leer oder hat ein ungültiges Format. Inhalt: {loaded_texts}") # Für Konsole belassen oder in App-Log überführen
                _texts_initial = {"app_title": "Solar App (Fallback - de.json leer)"}
    else:
        # print(f"GUI WARNUNG: de.json nicht gefunden unter {_temp_file_path}. Nutze interne Fallback-Texte.") # Für Konsole belassen
        raise FileNotFoundError("de.json nicht gefunden.")
except (FileNotFoundError, ValueError, json.JSONDecodeError) as e_json_load_specific:
    # print(f"GUI WARNUNG: Konnte de.json nicht korrekt laden ({e_json_load_specific}). Nutze interne Fallback-Texte.") # Für Konsole belassen
    _texts_initial = {
        "app_title": "Solar App KKM (Fallback)", "menu_item_input": "Eingabe (A)",
        "menu_item_analysis": "Analyse (A.5)", "menu_item_quick_calc": "Schnellkalkulation (B)",
        "menu_item_crm": "Kunden (CRM - C)", "menu_item_info_platform": "Info (D)",
        "menu_item_options": "Optionen (E)", "menu_item_admin": "Admin (F)",
        "menu_item_doc_output": "PDF (G)", "sidebar_navigation_title": "Navigation",
        "sidebar_select_area": "Bereich:", "import_errors_title": "⚠️ Ladefehler",
        "db_init_error": "DB Init Fehler:", "module_unavailable": "⚠ Modul fehlt",
        "module_unavailable_details": "Funktion nicht da.", "pdf_creation_no_data_info": "PDF: Bitte zuerst Daten eingeben & berechnen.",
        "gui_critical_error_no_db": "Kritischer Fehler! Datenbankmodul nicht geladen.",
        "gui_critical_error": "Ein kritischer Fehler ist in der Anwendung aufgetreten!"
    }
except Exception as e_json_load_general:
    # print(f"GUI WARNUNG: Unerwarteter Fehler beim Laden von de.json ({e_json_load_general}). Nutze interne Fallback-Texte.") # Für Konsole belassen
    _texts_initial = { "app_title": "Solar App KKM (Fallback General Error)" }

TEXTS: Dict[str, str] = {}


def import_module_with_fallback(module_name: str, import_errors_list: List[str]):
    try:
        module = importlib.import_module(module_name)
        # print(f"GUI INFO: Modul '{module_name}' erfolgreich geladen.") # Konsole-Info OK
        return module
    except ImportError as e:
        error_message = f"Import-Fehler Modul '{module_name}': {e}"
        import_errors_list.append(error_message)
        # print(error_message) # Konsole-Info OK
        return None
    except Exception as e_general_import:
        error_message = f"Allg. Import-Fehler Modul '{module_name}': {e_general_import}"
        import_errors_list.append(error_message)
        # print(error_message); traceback.print_exc() # Konsole-Info OK
        return None

def get_text_gui(key: str, default_text: Optional[str] = None) -> str:
    base_texts = TEXTS if TEXTS else _texts_initial
    if default_text is None:
        default_text = _texts_initial.get(key, key.replace("_", " ").title() + " (Fallback GUI Text)")
    return base_texts.get(key, default_text)


locales_module: Optional[Any] = None
database_module: Optional[Any] = None
product_db_module: Optional[Any] = None
data_input_module: Optional[Any] = None
calculations_module: Optional[Any] = None
analysis_module: Optional[Any] = None
crm_module: Optional[Any] = None
admin_panel_module: Optional[Any] = None
doc_output_module: Optional[Any] = None # Wird pdf_ui.py sein
quick_calc_module: Optional[Any] = None
info_platform_module: Optional[Any] = None
options_module: Optional[Any] = None
pv_visuals_module: Optional[Any] = None # Hinzugefügt für pv_visuals.py

_parse_price_matrix_csv_from_calculations: Optional[Callable[[Union[str, io.StringIO], List[str]], Optional[pd.DataFrame]]] = None
_parse_price_matrix_excel_from_calculations: Optional[Callable[[Optional[bytes], List[str]], Optional[pd.DataFrame]]] = None # Korrigierter Name


def initialize_database_once():
    if database_module and callable(getattr(database_module, 'init_db', None)):
        try:
            # print("gui.py: Rufe database_module.init_db() auf...") # Konsole-Info OK
            database_module.init_db() # type: ignore
            # print("gui.py: Datenbank erfolgreich initialisiert via database_module.init_db().") # Konsole-Info OK
        except Exception as e_init_db:
            error_msg_db = get_text_gui("db_init_error", "Fehler bei DB-Initialisierung:") + f" {e_init_db}"
            import_errors.append(error_msg_db)
            # print(f"gui.py: FEHLER in database_module.init_db(): {e_init_db}"); traceback.print_exc() # Konsole-Info OK
    else:
        error_msg_db_mod_missing = get_text_gui("db_init_error", "Fehler bei DB-Initialisierung:") + " database_module oder init_db Funktion nicht verfügbar."
        import_errors.append(error_msg_db_mod_missing)
        # print("gui.py: database_module oder init_db Funktion nicht verfügbar für Initialisierung.") # Konsole-Info OK

def main():
    
    
    TEXTS: Dict[str, str] = {} # Sicherstellen, dass TEXTS initial ein Dict ist
    loaded_translations: Any = None # Any, da der Typ von locales_module unbekannt ist

    if locales_module and callable(getattr(locales_module, 'load_translations', None)):
        try:
            loaded_translations = locales_module.load_translations('de')
        except Exception as e_load_loc:
            print(f"GUI FEHLER: locales_module.load_translations('de') ist fehlgeschlagen: {e_load_loc}")
            # import_errors ist eine globale Liste in gui.py, wie in Ihrem Code definiert
            if 'import_errors' in globals() and isinstance(globals()['import_errors'], list):
                globals()['import_errors'].append(f"Fehler beim Laden der Übersetzungen: {e_load_loc}")
            loaded_translations = None # Sicherstellen, dass es None ist bei Fehler

# Rigorose Prüfung und Zuweisung zu TEXTS
    if isinstance(loaded_translations, dict) and loaded_translations: # Nur wenn es ein nicht-leeres Dictionary ist
        TEXTS = loaded_translations
    else:
        if loaded_translations is not None: # Es wurde etwas geladen, aber es war kein gültiges Dictionary
            # import_errors ist eine globale Liste in gui.py
            if 'import_errors' in globals() and isinstance(globals()['import_errors'], list):
                globals()['import_errors'].append(f"WARNUNG: Übersetzungsdaten (locales.py) sind kein gültiges Dictionary (Typ: {type(loaded_translations)}). Verwende Fallback-Texte.")
            else: # Fallback, falls import_errors nicht global erreichbar ist
                print(f"GUI WARNUNG: Übersetzungsdaten (locales.py) sind kein gültiges Dictionary (Typ: {type(loaded_translations)}). Verwende Fallback-Texte.")
        
    # Fallback auf _texts_initial (das ist garantiert ein Dict)
        if isinstance(_texts_initial, dict):
            TEXTS = _texts_initial.copy()
        else: # Absoluter Notfall-Fallback, sollte nie passieren, wenn _texts_initial korrekt definiert ist
            TEXTS = {"app_title": "Solar App (Kritischer Text-Fallback)"}
        if 'import_errors' in globals() and isinstance(globals()['import_errors'], list):
            globals()['import_errors'].append("KRITISCH: _texts_initial ist kein Dictionary! Minimale Fallback-Texte verwendet.")
        else:
            print("GUI KRITISCH: _texts_initial ist kein Dictionary! Minimale Fallback-Texte verwendet.")

    
    if locales_module and callable(getattr(locales_module, 'load_translations', None)):
        TEXTS = locales_module.load_translations('de') or {} # type: ignore
        if not TEXTS: TEXTS = _texts_initial.copy()
    else:
        TEXTS = _texts_initial.copy()

    st.set_page_config(page_title=get_text_gui("app_title"), layout="wide")
    # Störende DEBUG-Ausgaben entfernt

    with st.sidebar:
        st.title(get_text_gui("sidebar_navigation_title"))

        page_options = {
            get_text_gui("menu_item_input"): "input",
            get_text_gui("menu_item_analysis"): "analysis",
            get_text_gui("menu_item_quick_calc"): "quick_calc",
            get_text_gui("menu_item_crm"): "crm",
            get_text_gui("menu_item_info_platform"): "info_platform",
            get_text_gui("menu_item_options"): "options",
            get_text_gui("menu_item_admin"): "admin",
            get_text_gui("menu_item_doc_output"): "doc_output",
        }
        page_options_list = list(page_options.items())

        if 'selected_page_key_sui' not in st.session_state:
            st.session_state.selected_page_key_sui = page_options_list[0][1] # Standard auf erste Seite

        for label, key in page_options_list:
            button_variant = "default" if st.session_state.selected_page_key_sui != key else "secondary"

            if SUI_AVAILABLE and sui:
                try:
                    if sui.button(label, key=f"sui_nav_{key}", variant=button_variant, className="w-full justify-start mb-1"):
                        st.session_state.selected_page_key_sui = key
                        st.rerun()
                except AttributeError: # Fallback, falls sui.button nicht funktioniert wie erwartet
                    if st.sidebar.button(label, key=f"st_nav_{key}", use_container_width=True):
                        st.session_state.selected_page_key_sui = key
                        st.rerun()
                    if key == page_options_list[0][1] and "sui_button_fallback_warning" not in st.session_state:
                         st.sidebar.warning("Hinweis: sui.button nicht optimal. Standard-Buttons als Fallback.") # Angepasste Meldung
                         st.session_state.sui_button_fallback_warning = True
            else: # Standard Streamlit Buttons, wenn SUI nicht verfügbar
                if st.sidebar.button(label, key=f"st_nav_{key}", use_container_width=True):
                    st.session_state.selected_page_key_sui = key
                    st.rerun()
                if key == page_options_list[0][1] and "sui_unavailable_warning" not in st.session_state and not SUI_AVAILABLE:
                    st.sidebar.info("Hinweis: streamlit_shadcn_ui nicht verfügbar. Standard-Buttons werden verwendet.")
                    st.session_state.sui_unavailable_warning = True

        selected_page_key = st.session_state.selected_page_key_sui


    if import_errors:
        with st.sidebar:
            st.markdown("---"); st.subheader(get_text_gui("import_errors_title"))
            for error_msg in import_errors: st.error(error_msg)
            st.markdown("---")

    # Seiten-Rendering basierend auf Auswahl
    if selected_page_key == "input":
        st.header(get_text_gui("menu_item_input"))
        if data_input_module and callable(getattr(data_input_module, 'render_data_input', None)):
            project_data = data_input_module.render_data_input(TEXTS) # TEXTS übergeben
            if project_data: st.session_state['project_data'] = project_data
        else:
            st.warning(get_text_gui("module_unavailable_details", get_text_gui("fallback_title_input", "Eingabemodul nicht verfügbar.")))

    elif selected_page_key == "analysis":
        st.header(get_text_gui("menu_item_analysis"))
        if analysis_module and callable(getattr(analysis_module, 'render_analysis', None)):
            try:
                # Stelle sicher, dass pv_visuals an analysis.py übergeben wird, falls es global geladen wurde
                # Dies geschieht typischerweise durch direkten Import in analysis.py oder als Parameter.
                # Hier gehen wir davon aus, dass analysis.py pv_visuals selbst importiert.
                analysis_module.render_analysis(TEXTS, st.session_state.get("calculation_results", {}))
            except Exception as e_render_analysis:
                st.error(f"Fehler beim Rendern des Analyse-Tabs: {e_render_analysis}")
                st.text_area("Traceback Analysis:", traceback.format_exc(), height=200)
        else:
            st.warning(get_text_gui("module_unavailable_details", get_text_gui("fallback_title_analysis", "Analysemodul nicht verfügbar.")))

    elif selected_page_key == "admin":
        st.header(get_text_gui("menu_item_admin"))
        required_modules_for_admin_render = [admin_panel_module, database_module, product_db_module, calculations_module]
        if all(m is not None for m in required_modules_for_admin_render) and callable(getattr(admin_panel_module, 'render_admin_panel', None)):
            admin_kwargs_pass = {
                "texts": TEXTS,
                "get_db_connection_func": getattr(database_module, 'get_db_connection', None),
                "save_admin_setting_func": getattr(database_module, 'save_admin_setting', None),
                "load_admin_setting_func": getattr(database_module, 'load_admin_setting', None),
                "parse_price_matrix_csv_func": _parse_price_matrix_csv_from_calculations, # Globale Variable verwenden
                "parse_price_matrix_excel_func": _parse_price_matrix_excel_from_calculations, # Globale Variable verwenden
                "list_products_func": getattr(product_db_module, 'list_products', None),
                "add_product_func": getattr(product_db_module, 'add_product', None),
                "update_product_func": getattr(product_db_module, 'update_product', None),
                "delete_product_func": getattr(product_db_module, 'delete_product', None),
                "get_product_by_id_func": getattr(product_db_module, 'get_product_by_id', None),
                "get_product_by_model_name_func": getattr(product_db_module, 'get_product_by_model_name', None),
                "list_product_categories_func": getattr(product_db_module, 'list_product_categories', None),
                "db_list_companies_func": getattr(database_module, 'list_companies', None),
                "db_add_company_func": getattr(database_module, 'add_company', None),
                "db_get_company_by_id_func": getattr(database_module, 'get_company', None),
                "db_update_company_func": getattr(database_module, 'update_company', None),
                "db_delete_company_func": getattr(database_module, 'delete_company', None),
                "db_set_default_company_func": getattr(database_module, 'set_default_company', None),
                "db_add_company_document_func": getattr(database_module, 'add_company_document', None),
                "db_list_company_documents_func": getattr(database_module, 'list_company_documents', None),
                "db_delete_company_document_func": getattr(database_module, 'delete_company_document', None)
            }
            # Überprüfung, ob die Parser-Funktionen korrekt zugewiesen wurden
            all_critical_funcs_valid = True
            for func_name_key, func_obj in admin_kwargs_pass.items():
                 if func_name_key.endswith('_func'):
                     is_callable_admin = callable(func_obj)
                     if func_name_key in ["parse_price_matrix_csv_func", "parse_price_matrix_excel_func", "get_db_connection_func", "save_admin_setting_func", "load_admin_setting_func"]:
                         if not is_callable_admin: all_critical_funcs_valid = False; # print(f"GUI WARNUNG: Kritische Admin Funktion '{func_name_key}' ist NICHT callable.") # Konsole-Info OK

            if not all_critical_funcs_valid:
                 st.error("Einige Kernfunktionen für das Admin-Panel (DB-Zugriff oder Parser) konnten nicht geladen werden. Bitte Terminal prüfen.")
            else:
                try: admin_panel_module.render_admin_panel(**admin_kwargs_pass) # type: ignore
                except Exception as e_render_admin:
                    st.error(f"Fehler im Admin-Panel: {e_render_admin}")
                    st.text_area("Traceback Admin:", traceback.format_exc(), height=200)
        else:
            missing_modules_admin_list = [name for name, mod in [("Admin-Panel", admin_panel_module), ("Datenbank", database_module), ("Produkt-DB", product_db_module), ("Berechnungen", calculations_module)] if not mod]
            st.warning(get_text_gui("module_unavailable_details", f"Admin-Panel oder dessen Abhängigkeiten ({', '.join(missing_modules_admin_list)}) nicht verfügbar."))

    elif selected_page_key == "doc_output":
        st.header(get_text_gui("menu_item_doc_output"))
        if doc_output_module and database_module and product_db_module and callable(getattr(doc_output_module, 'render_pdf_ui', None)):
            project_data_doc = st.session_state.get('project_data', {})
            calc_results_doc = st.session_state.get("calculation_results", {})
            if not project_data_doc or not calc_results_doc : # Grundlegende Prüfung
                st.info(get_text_gui("pdf_creation_no_data_info"))
            else:
                pdf_ui_kwargs_pass = {
                    "texts": TEXTS, "project_data": project_data_doc, "analysis_results": calc_results_doc,
                    "load_admin_setting_func": getattr(database_module, 'load_admin_setting', None),
                    "save_admin_setting_func": getattr(database_module, 'save_admin_setting', None), # Durchgereicht, falls PDF UI es braucht
                    "list_products_func": getattr(product_db_module, 'list_products', None), # Für PDF Generator
                    "get_product_by_id_func": getattr(product_db_module, 'get_product_by_id', None), # Für PDF Generator
                    "get_active_company_details_func": getattr(database_module, 'get_active_company', None),
                    "db_list_company_documents_func": getattr(database_module, 'list_company_documents', None)
                }
                # Sicherstellen, dass alle übergebenen Funktionen auch wirklich callable sind
                critical_funcs_for_pdf_check = [ val for key, val in pdf_ui_kwargs_pass.items() if key.endswith("_func") ]
                if not all(f is not None and callable(f) for f in critical_funcs_for_pdf_check):
                     st.error("Einige Kernfunktionen für die PDF-Ausgabe (DB-Zugriff o.ä.) konnten nicht geladen werden oder sind nicht aufrufbar.")
                else:
                    try: doc_output_module.render_pdf_ui(**pdf_ui_kwargs_pass) # type: ignore
                    except Exception as e_render_pdf:
                        st.error(f"Fehler beim Rendern der PDF UI: {e_render_pdf}")
                        st.text_area("Traceback PDF UI:", traceback.format_exc(), height=200)
        else:
            st.warning(get_text_gui("module_unavailable_details", "PDF-Ausgabemodul oder dessen Abhängigkeiten sind nicht verfügbar."))
    
    # Weitere Seiten-Renderings (Platzhalter)
    elif selected_page_key == "quick_calc":
        st.header(get_text_gui("menu_item_quick_calc"))
        if quick_calc_module and callable(getattr(quick_calc_module, 'render_quick_calc', None)):
             quick_calc_module.render_quick_calc(TEXTS, module_name=get_text_gui("menu_item_quick_calc")) # type: ignore
        else: st.warning(get_text_gui("module_unavailable_details", get_text_gui("fallback_title_quick_calc","Schnellkalkulation nicht verfügbar.")))
    elif selected_page_key == "crm":
        st.header(get_text_gui("menu_item_crm"))
        if crm_module and database_module and callable(getattr(crm_module, 'render_crm', None)):
            crm_module.render_crm(TEXTS, getattr(database_module, 'get_db_connection', None)) # type: ignore
        else: st.warning(get_text_gui("module_unavailable_details", get_text_gui("fallback_title_crm","CRM nicht verfügbar.")))
    elif selected_page_key == "info_platform":
        st.header(get_text_gui("menu_item_info_platform"))
        if info_platform_module and callable(getattr(info_platform_module, 'render_info_platform', None)):
            info_platform_module.render_info_platform(TEXTS, module_name=get_text_gui("menu_item_info_platform")) # type: ignore
        else: st.warning(get_text_gui("module_unavailable_details", get_text_gui("fallback_title_info","Info-Plattform nicht verfügbar.")))
    elif selected_page_key == "options":
        st.header(get_text_gui("menu_item_options"))
        if options_module and callable(getattr(options_module, 'render_options', None)):
            options_module.render_options(TEXTS, module_name=get_text_gui("menu_item_options")) # type: ignore
        else: st.warning(get_text_gui("module_unavailable_details", get_text_gui("fallback_title_options","Optionen nicht verfügbar.")))


if __name__ == "__main__":
    try:
        # Modulimporte
        locales_module = import_module_with_fallback("locales", import_errors)
        database_module = import_module_with_fallback("database", import_errors)
        product_db_module = import_module_with_fallback("product_db", import_errors) # Für Admin und PDF
        data_input_module = import_module_with_fallback("data_input", import_errors)
        calculations_module = import_module_with_fallback("calculations", import_errors)
        analysis_module = import_module_with_fallback("analysis", import_errors)
        crm_module = import_module_with_fallback("crm", import_errors)
        admin_panel_module = import_module_with_fallback("admin_panel", import_errors)
        doc_output_module = import_module_with_fallback("pdf_ui", import_errors) # Nutze pdf_ui.py als doc_output
        quick_calc_module = import_module_with_fallback("quick_calc", import_errors)
        info_platform_module = import_module_with_fallback("info_platform", import_errors)
        options_module = import_module_with_fallback("options", import_errors)
        pv_visuals_module = import_module_with_fallback("pv_visuals", import_errors) # Importiere pv_visuals

        # Globale Zuweisung der Parser-Funktionen aus calculations_module
        if calculations_module:
            if hasattr(calculations_module, 'parse_module_price_matrix_csv'):
                _parse_price_matrix_csv_from_calculations = calculations_module.parse_module_price_matrix_csv
            if hasattr(calculations_module, 'parse_module_price_matrix_excel'): # Korrekter Funktionsname
                _parse_price_matrix_excel_from_calculations = calculations_module.parse_module_price_matrix_excel

        # Datenbank einmalig initialisieren
        if 'db_initialized' not in st.session_state:
            if database_module: initialize_database_once()
            st.session_state['db_initialized'] = True
            # print("GUI INFO: Datenbank Initialisierungsprozess (einmalig) durchlaufen.") # Konsole-Info OK

        # Hauptanwendung starten
        if database_module: # Kritische Abhängigkeit
            main()
        else:
            # Fallback, falls main() nicht erreicht wird wegen fehlendem DB-Modul
            st.set_page_config(page_title=_texts_initial.get("app_title", "Fehler"), layout="wide")
            st.error(get_text_gui("gui_critical_error_no_db", "Datenbankmodul nicht geladen. Anwendung kann nicht starten."))
            if import_errors:
                with st.sidebar:
                    st.subheader("Ladefehler")
                    for err_msg_display in import_errors: st.error(err_msg_display)

    except Exception as e_global_gui_main_block:
        # print(f"❌ GUI Hauptfehler (im if __name__ == \"__main__\" Block): {e_global_gui_main_block}") # Konsole-Info OK
        # traceback.print_exc() # Konsole-Info OK
        critical_error_text_for_display_main_block = get_text_gui("gui_critical_error", "Ein kritischer Fehler ist in der Anwendung aufgetreten!")
        try:
            # Versuche st.set_page_config hier nur, wenn es noch nicht aufgerufen wurde.
            if not getattr(st, "_is_page_config_allowed", True): # Behelfsmäßige Prüfung
                 st.set_page_config(page_title="Kritischer Fehler", layout="wide")

            st.error(f"{critical_error_text_for_display_main_block}\nDetails: {e_global_gui_main_block}")
            st.text_area("Traceback Global:", traceback.format_exc(), height=300)
        except Exception as e_fallback_display:
            # print(f"Schwerwiegender Fehler auch bei der Fehleranzeige: {e_fallback_display}") # Konsole-Info OK
            pass # Minimal-Fallback, um Absturz zu vermeiden