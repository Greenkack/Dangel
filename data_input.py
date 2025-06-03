# data_input.py
# Eingabemasken für Kundendaten, Verbrauchsdaten und Bedarfsanalyse

import streamlit as st
import pandas as pd
import os
import re
from typing import Dict, Any, Optional, List, Callable
import json
import traceback
from datetime import datetime
import requests
import base64

# Import streamlit_shadcn_ui with fallback
try:
    import streamlit_shadcn_ui as sui
    SUI_AVAILABLE = True
except ImportError:
    SUI_AVAILABLE = False
    sui = None

# --- Hilfsfunktion für Texte ---
def get_text_di(texts_dict: Dict[str, str], key: str, fallback_text_value: Optional[str] = None) -> str:
    if fallback_text_value is None:
        fallback_text_value = key.replace("_", " ").title() + " (DI Text fehlt)"
    return str(texts_dict.get(key, fallback_text_value))

# --- Dummies und reale Imports ---
def Dummy_get_db_connection_input(): return None
def Dummy_list_products_input(*args, **kwargs): return []
def Dummy_get_product_by_model_name_input(*args, **kwargs): return None
def Dummy_get_product_by_id_input(*args, **kwargs): return None
def Dummy_load_admin_setting_input(key, default=None):
    if key == 'salutation_options': return ['Herr (D)', 'Frau (D)', 'Familie (D)']
    if key == 'title_options': return ['Dr. (D)', 'Prof. (D)', 'Mag. (D)', 'Ing. (D)', None]
    if key == 'Maps_api_key': return "PLATZHALTER_HIER_IHREN_KEY_EINFUEGEN"
    return default

get_db_connection_safe = Dummy_get_db_connection_input
load_admin_setting_safe = Dummy_load_admin_setting_input
list_products_safe = Dummy_list_products_input
get_product_by_model_name_safe = Dummy_get_product_by_model_name_input
get_product_by_id_safe = Dummy_get_product_by_id_input

try:
    from database import get_db_connection as real_get_db_connection, load_admin_setting as real_load_admin_setting
    from product_db import list_products as real_list_products, get_product_by_model_name as real_get_product_by_model_name, get_product_by_id as real_get_product_by_id
    get_db_connection_safe = real_get_db_connection
    load_admin_setting_safe = real_load_admin_setting
    list_products_safe = real_list_products
    get_product_by_model_name_safe = real_get_product_by_model_name
    get_product_by_id_safe = real_get_product_by_id
except (ImportError, ModuleNotFoundError) as e:
    print(f"data_input.py: FEHLER Import DB/Produkt: {e}. Dummies bleiben aktiv.")
except Exception as e_load_deps:
    print(f"data_input.py: FEHLER Laden DB/Produkt: {e_load_deps}. Dummies bleiben aktiv.")
    traceback.print_exc()

def parse_full_address_string(full_address: str, texts: Dict[str, str]) -> Dict[str, str]:
    parsed_data = {"street": "", "house_number": "", "zip_code": "", "city": ""}
    full_address = full_address.strip()
    # Regex um PLZ und Ort zu finden (auch mit optionalen Länderkürzeln wie D-)
    zip_city_match = re.search(r"(?:[A-Z]{1,2}-)?(\d{4,5})\s+(.+?)(?:,\s*\w+)?$", full_address)
    address_part = full_address

    if zip_city_match:
        parsed_data["zip_code"] = zip_city_match.group(1).strip()
        # Stadt ist alles bis zum nächsten Komma (falls vorhanden, z.B. bei Ortsteil)
        parsed_data["city"] = zip_city_match.group(2).strip().split(',')[0].strip()
        address_part = full_address[:zip_city_match.start()].strip().rstrip(',')
    else:
        # Fallback, wenn PLZ/Ort nicht am Ende stehen oder anders formatiert sind
        parts = full_address.split(',')
        if len(parts) > 1:
            potential_zip_city = parts[-1].strip()
            zip_city_match_comma = re.match(r"^\s*(?:[A-Z]{1,2}-)?(\d{4,5})\s+(.+?)\s*$", potential_zip_city)
            if zip_city_match_comma:
                parsed_data["zip_code"] = zip_city_match_comma.group(1).strip()
                parsed_data["city"] = zip_city_match_comma.group(2).strip()
                address_part = ",".join(parts[:-1]).strip()
            elif not parts[-1].strip().replace("-","").isdigit() and len(parts[-1].strip()) > 2 : # Wenn letzter Teil keine reine Zahl (PLZ) ist und lang genug für Stadt
                parsed_data["city"] = parts[-1].strip()
                address_part = ",".join(parts[:-1]).strip()


    # Regex um Straße und Hausnummer zu trennen (robustere Version)
    # Sucht nach einer Zeichenkette (Straße), gefolgt von einem Leerzeichen,
    # dann einer Ziffer oder einem Buchstaben (für Hausnummern wie 1a, 12-14, Tor B)
    street_hn_match = re.match(r"^(.*?)\s+([\d\w][\d\w\s\-/.]*?)$", address_part.strip())
    if street_hn_match:
        potential_street = street_hn_match.group(1).strip().rstrip(',')
        potential_hn = street_hn_match.group(2).strip()
        # Zusätzliche Prüfung, ob die Straße plausibel ist (mehr als nur ein Wort oder enthält typische Straßenendungen)
        # und die Hausnummer eine Ziffer enthält.
        if len(potential_street.split()) > 0 and re.search(r'\d', potential_hn):
            parsed_data["street"] = potential_street
            parsed_data["house_number"] = potential_hn
        else: # Wenn Trennung nicht eindeutig, setze alles als Straße
            parsed_data["street"] = address_part
            st.warning(get_text_di(texts, "parse_street_hnr_warning_detail", "Straße und Hausnummer konnten nicht eindeutig getrennt werden. Bitte manuell prüfen."))
    elif address_part: # Wenn keine Trennung möglich war, ist alles Straße
        parsed_data["street"] = address_part
        st.warning(get_text_di(texts, "parse_street_hnr_not_found", "Keine Hausnummer in der Adresse gefunden. Bitte manuell prüfen."))
    return parsed_data


def get_coordinates_from_address_google(address: str, city: str, zip_code: str, api_key: Optional[str], texts: Dict[str, str]) -> Optional[Dict[str, float]]:
    if not api_key or api_key == "" or api_key == "PLATZHALTER_HIER_IHREN_KEY_EINFUEGEN":
        # Terminal-Ausgabe ist hier besser, da es eine Konfigurationssache ist
        print(get_text_di(texts, "geocode_google_api_key_missing_or_placeholder_terminal", "FEHLER: Google API Key fehlt oder ist Platzhalter. Geocoding nicht möglich."))
        st.warning(get_text_di(texts, "geocode_google_api_key_missing_or_placeholder_ui", "Google API Key nicht konfiguriert. Geocoding deaktiviert."))
        return None
    if not address or not city:
        st.warning(get_text_di(texts, "geocode_missing_address_city", "Für Geocoding werden Straße und Ort benötigt."))
        return None

    full_query_address = f"{address}, {zip_code} {city}"
    base_url = "https://maps.googleapis.com/maps/api/geocode/json"
    params = {"address": full_query_address, "key": api_key}
    try:
        response = requests.get(base_url, params=params, timeout=10)
        response.raise_for_status() # Fehler bei HTTP-Statuscodes 4xx/5xx
        data = response.json()
        if data.get("status") == "OK" and data.get("results"):
            location = data["results"][0].get("geometry", {}).get("location", {})
            lat, lng = location.get("lat"), location.get("lng")
            if lat is not None and lng is not None:
                st.success(get_text_di(texts, "geolocation_success_google_api", f"Koordinaten via Google API: Lat {lat:.6f}, Lon {lng:.6f}"))
                return {"latitude": float(lat), "longitude": float(lng)}
            else:
                st.warning(get_text_di(texts, "geolocation_google_api_no_coords", "Google API: Keine Koordinaten in der Antwort gefunden."))
        else:
            st.warning(get_text_di(texts, "geolocation_google_api_status_error", f"Google API Fehler: {data.get('status')} - {data.get('error_message', '')}"))
        return None
    except requests.exceptions.Timeout:
        st.error(get_text_di(texts, "geolocation_google_api_timeout", "Google Geocoding API Zeitüberschreitung."))
        return None
    except requests.exceptions.RequestException as e:
        st.error(get_text_di(texts, "geolocation_google_api_request_error", f"Google Geocoding API Anfragefehler: {e}"))
        return None
    except Exception as e:
        st.error(f"{get_text_di(texts, 'geolocation_api_unknown_error', 'Unbekannter Fehler beim Geocoding:')} {e}")
        return None


def get_Maps_satellite_image_url(latitude: float, longitude: float, api_key: Optional[str], texts: Dict[str, str], zoom: int = 20, width: int = 600, height: int = 400) -> Optional[str]:
    if not api_key or api_key == "PLATZHALTER_HIER_IHREN_KEY_EINFUEGEN":
        # Terminal-Ausgabe, da Konfigurationsproblem
        print(get_text_di(texts, "maps_api_key_missing_or_placeholder_terminal", "FEHLER: Google Maps API Key fehlt oder ist Platzhalter. Satellitenbild kann nicht geladen werden."))
        # UI-Warnung, um den Nutzer direkt zu informieren
        st.warning(get_text_di(texts, "maps_api_key_missing_or_placeholder_ui", "Google Maps API Key nicht konfiguriert. Satellitenbild kann nicht geladen werden."))
        return None

    # Prüfung auf Standardkoordinaten (0,0)
    # 'allow_zero_coords_map' könnte eine temporäre Session-State-Variable sein, falls man 0,0 erlauben will (selten)
    if abs(latitude) < 1e-9 and abs(longitude) < 1e-9 and not st.session_state.get("allow_zero_coords_map_di", False):
         st.info(get_text_di(texts, "map_default_coords_info", "Standardkoordinaten (0,0) werden verwendet. Bitte gültige Koordinaten eingeben oder Adresse parsen, um ein spezifisches Satellitenbild zu laden."))
         return None # Kein Bild für (0,0) laden, es sei denn explizit erlaubt

    base_url = "https://maps.googleapis.com/maps/api/staticmap?"
    params = {
        "center": f"{latitude},{longitude}",
        "zoom": str(zoom),
        "size": f"{width}x{height}",
        "maptype": "satellite",
        "key": api_key
    }
    # Erzeuge die URL
    url_parts = [f"{k}={v}" for k, v in params.items()]
    full_url = base_url + "&".join(url_parts)
    return full_url

def render_data_input(texts: Dict[str, str]) -> Optional[Dict[str, Any]]:
    if 'project_data' not in st.session_state:
        st.session_state.project_data = {'customer_data': {}, 'project_details': {}, 'economic_data': {}}

    inputs: Dict[str, Any] = st.session_state.project_data
    for key_to_ensure in ['customer_data', 'project_details', 'economic_data']:
        if key_to_ensure not in inputs:
            inputs[key_to_ensure] = {}

    # Sicherstellen, dass alle Komponenten-Schlüssel im Session State und in inputs['project_details'] initialisiert sind
    component_name_keys = [
        'selected_module_name', 'selected_inverter_name', 'selected_storage_name',
        'selected_wallbox_name', 'selected_ems_name', 'selected_optimizer_name',
        'selected_carport_name', 'selected_notstrom_name', 'selected_tierabwehr_name'
    ]
    for comp_key in component_name_keys:
        if comp_key not in st.session_state: # Initialisiere im Session State, falls nicht vorhanden
            st.session_state[comp_key] = inputs['project_details'].get(comp_key) # Hole aus Projekt, falls da
        if comp_key not in inputs['project_details']: # Wenn immer noch nicht in Projekt (z.B. erster Lauf), nimm aus Session State
             inputs['project_details'][comp_key] = st.session_state.get(comp_key)


    please_select_text = get_text_di(texts, "please_select_option", "--- Bitte wählen ---")
    SALUTATION_OPTIONS = load_admin_setting_safe('salutation_options', ['Herr', 'Frau', 'Familie', 'Firma', 'Divers', '']) # 'Firma' hinzugefügt
    TITLE_OPTIONS_RAW = load_admin_setting_safe('title_options', ['Dr.', 'Prof.', 'Mag.', 'Ing.', None])
    TITLE_OPTIONS = [str(t) if t is not None else get_text_di(texts, "none_option", "(Kein)") for t in TITLE_OPTIONS_RAW] # 'None' zu '(Kein)' geändert
    BUNDESLAND_OPTIONS = load_admin_setting_safe('bundesland_options', ['Baden-Württemberg', 'Bayern', 'Berlin', 'Brandenburg', 'Bremen', 'Hamburg', 'Hessen', 'Mecklenburg-Vorpommern', 'Niedersachsen', 'Nordrhein-Westfalen', 'Rheinland-Pfalz', 'Saarland', 'Sachsen', 'Sachsen-Anhalt', 'Schleswig-Holstein', 'Thüringen'])
    DACHART_OPTIONS = load_admin_setting_safe('dachart_options', ['Satteldach', 'Satteldach mit Gaube', 'Pultdach', 'Flachdach', 'Walmdach', 'Krüppelwalmdach', 'Zeltdach', 'Sonstiges'])
    DACHDECKUNG_OPTIONS = load_admin_setting_safe('dachdeckung_options', ['Frankfurter Pfannen', 'Trapezblech', 'Tonziegel', 'Biberschwanz', 'Schiefer', 'Bitumen', 'Eternit', 'Schindeln', 'Sonstiges'])

    MODULE_LIST_MODELS = [p.get('model_name', f"ID:{p.get('id', 'N/A')}") for p in list_products_safe(category='Modul')] or [get_text_di(texts,"no_modules_in_db","Keine Module in DB")]
    INVERTER_LIST_MODELS = [p.get('model_name', f"ID:{p.get('id', 'N/A')}") for p in list_products_safe(category='Wechselrichter')] or [get_text_di(texts,"no_inverters_in_db","Keine WR in DB")]
    STORAGE_LIST_MODELS = [p.get('model_name', f"ID:{p.get('id', 'N/A')}") for p in list_products_safe(category='Batteriespeicher')] or [get_text_di(texts,"no_storages_in_db","Keine Speicher in DB")]
    WALLBOX_LIST_MODELS = [p.get('model_name', f"ID:{p.get('id', 'N/A')}") for p in list_products_safe(category='Wallbox')] or [get_text_di(texts,"no_wallboxes_in_db","Keine Wallboxen in DB")]
    EMS_LIST_MODELS = [p.get('model_name', f"ID:{p.get('id', 'N/A')}") for p in list_products_safe(category='Energiemanagementsystem')] or [get_text_di(texts,"no_ems_in_db","Keine EMS in DB")]
    OPTIMIZER_LIST_MODELS = [p.get('model_name', f"ID:{p.get('id', 'N/A')}") for p in list_products_safe(category='Leistungsoptimierer')] or [get_text_di(texts,"no_optimizers_in_db","Keine Optimierer in DB")]
    CARPORT_LIST_MODELS = [p.get('model_name', f"ID:{p.get('id', 'N/A')}") for p in list_products_safe(category='Carport')] or [get_text_di(texts,"no_carports_in_db","Keine Carports in DB")]
    NOTSTROM_LIST_MODELS = [p.get('model_name', f"ID:{p.get('id', 'N/A')}") for p in list_products_safe(category='Notstromversorgung')] or [get_text_di(texts,"no_notstrom_in_db","Keine Notstrom in DB")]
    TIERABWEHR_LIST_MODELS = [p.get('model_name', f"ID:{p.get('id', 'N/A')}") for p in list_products_safe(category='Tierabwehrschutz')] or [get_text_di(texts,"no_tierabwehr_in_db","Keine Tierabwehr in DB")]

    st.subheader(get_text_di(texts, "customer_data_header", "Kundendaten"))
    with st.expander(get_text_di(texts, "customer_data_header", "Kundendaten"), expanded=st.session_state.get('customer_data_expanded_di', True)): # Eindeutiger Expander-Key
        col1,col2,col3=st.columns(3)
        with col1: inputs['project_details']['anlage_type']=st.selectbox(get_text_di(texts,"anlage_type_label","Anlagentyp"),options=['Neuanlage','Bestandsanlage'],index=['Neuanlage','Bestandsanlage'].index(inputs['project_details'].get('anlage_type','Neuanlage')),key='anlage_type_di_v6_exp') # Eindeutiger Widget-Key
        with col2: inputs['project_details']['feed_in_type']=st.selectbox(get_text_di(texts,"feed_in_type_label","Einspeisetyp"),options=['Teileinspeisung','Volleinspeisung'],index=['Teileinspeisung','Volleinspeisung'].index(inputs['project_details'].get('feed_in_type','Teileinspeisung')),key='feed_in_type_di_v6_exp')
        with col3: inputs['customer_data']['type']=st.selectbox(get_text_di(texts,"customer_type_label","Kundentyp"),options=['Privat','Gewerblich'],index=['Privat','Gewerblich'].index(inputs['customer_data'].get('type','Privat')),key='customer_type_di_v6_exp')

        col4,col5,col6=st.columns(3)
        default_salutation = inputs['customer_data'].get('salutation', SALUTATION_OPTIONS[0] if SALUTATION_OPTIONS else '')
        with col4: inputs['customer_data']['salutation']=st.selectbox(get_text_di(texts,"salutation_label","Anrede"),options=SALUTATION_OPTIONS,index=SALUTATION_OPTIONS.index(default_salutation) if default_salutation in SALUTATION_OPTIONS else 0,key='salutation_di_v6_exp')
        default_title = inputs['customer_data'].get('title', TITLE_OPTIONS[-1] if TITLE_OPTIONS else '')
        with col5: inputs['customer_data']['title']=st.selectbox(get_text_di(texts,"title_label","Titel"),options=TITLE_OPTIONS,index=TITLE_OPTIONS.index(default_title) if default_title in TITLE_OPTIONS else len(TITLE_OPTIONS)-1,key='title_di_v6_exp')
        with col6: inputs['customer_data']['first_name']=st.text_input(get_text_di(texts,"first_name_label","Vorname"),value=str(inputs['customer_data'].get('first_name','')),key='first_name_di_v6_exp')

        col7,col8=st.columns(2)
        with col7: inputs['customer_data']['last_name']=st.text_input(get_text_di(texts,"last_name_label","Nachname"),value=str(inputs['customer_data'].get('last_name','')),key='last_name_di_v6_exp')
        with col8: inputs['customer_data']['num_persons']=st.number_input(get_text_di(texts,"num_persons_label","Anzahl Personen im Haushalt"),min_value=1,value=int(inputs['customer_data'].get('num_persons',1) or 1),key='num_persons_di_v6_exp')

        full_address_input_val=st.text_input(get_text_di(texts,"full_address_label","Komplette Adresse"),value=str(inputs['customer_data'].get('full_address','')),help=get_text_di(texts,"full_address_help","Z.B. Musterweg 18, 12345 Musterstadt"),key='full_address_widget_key_di_v6_exp')
        inputs['customer_data']['full_address']=full_address_input_val

        if st.button(get_text_di(texts,"parse_address_button","Daten aus Adresse übernehmen"),key="parse_address_btn_di_v6_exp"):
            if full_address_input_val:
                parsed_data=parse_full_address_string(full_address_input_val,texts)
                inputs['customer_data']['address']=parsed_data.get("street",inputs['customer_data'].get('address',''))
                inputs['customer_data']['house_number']=parsed_data.get("house_number",inputs['customer_data'].get('house_number',''))
                inputs['customer_data']['zip_code']=parsed_data.get("zip_code",inputs['customer_data'].get('zip_code',''))
                inputs['customer_data']['city']=parsed_data.get("city",inputs['customer_data'].get('city',''))
                if parsed_data.get("zip_code")and parsed_data.get("city"):st.success(get_text_di(texts,"parse_address_success_all","Adresse erfolgreich geparst! Bitte Felder prüfen."))
                else:st.warning(get_text_di(texts,"parse_address_partial_success","Adresse teilweise geparst. Bitte fehlende Felder ergänzen."))
                st.session_state.satellite_image_url_di = None # Zurücksetzen, damit Bild neu geladen wird
                st.rerun()
            else:st.warning(get_text_di(texts,"parse_address_no_input","Bitte geben Sie eine vollständige Adresse ein."))

        col_addr1,col_addr2=st.columns(2);col_addr3,col_addr4=st.columns(2)
        with col_addr1:inputs['customer_data']['address']=st.text_input(get_text_di(texts,"street_label","Straße"),value=str(inputs['customer_data'].get('address','')),key='address_di_manual_v6_exp')
        with col_addr2:inputs['customer_data']['house_number']=st.text_input(get_text_di(texts,"house_number_label","Hausnummer"),value=str(inputs['customer_data'].get('house_number','')),key='house_number_di_manual_v6_exp')
        with col_addr3:inputs['customer_data']['zip_code']=st.text_input(get_text_di(texts,"zip_code_label","PLZ"),value=str(inputs['customer_data'].get('zip_code','')),key='zip_code_di_manual_v6_exp')
        with col_addr4:inputs['customer_data']['city']=st.text_input(get_text_di(texts,"city_label","Ort"),value=str(inputs['customer_data'].get('city','')),key='city_di_manual_v6_exp')

        default_state=inputs['customer_data'].get('state',please_select_text)
        state_options_with_ps=[please_select_text]+BUNDESLAND_OPTIONS
        inputs['customer_data']['state']=st.selectbox(get_text_di(texts,"state_label","Bundesland"),options=state_options_with_ps,key='state_di_v6_exp',index=state_options_with_ps.index(default_state)if default_state in state_options_with_ps else 0)
        if inputs['customer_data']['state']==please_select_text:inputs['customer_data']['state']=None

        st.markdown("---");st.markdown(f"**{get_text_di(texts,'coordinates_header','Koordinaten')}**")

        # --- BEGINN API KEY LOGIK ---
        Maps_API_KEY_FROM_ENV = os.environ.get("Maps_API_KEY")
        EFFECTIVE_GOOGLE_API_KEY = None

        if Maps_API_KEY_FROM_ENV and Maps_API_KEY_FROM_ENV.strip() and Maps_API_KEY_FROM_ENV != "PLATZHALTER_HIER_IHREN_KEY_EINFUEGEN":
            EFFECTIVE_GOOGLE_API_KEY = Maps_API_KEY_FROM_ENV
            # print("DATA_INPUT_DEBUG: Google Maps API Key aus Umgebungsvariable Maps_API_KEY verwendet.")
        else:
            api_key_from_db = load_admin_setting_safe("Maps_api_key", None)
            if api_key_from_db and api_key_from_db.strip() and api_key_from_db != "PLATZHALTER_HIER_IHREN_KEY_EINFUEGEN":
                EFFECTIVE_GOOGLE_API_KEY = api_key_from_db
                # print(f"DATA_INPUT_DEBUG: Google Maps API Key aus Datenbank (Admin-Settings) geladen.")
        # --- ENDE API KEY LOGIK ---


        current_lat = float(inputs['project_details'].get('latitude', 0.0) or 0.0)
        current_lon = float(inputs['project_details'].get('longitude', 0.0) or 0.0)

        col_lat, col_lon, col_geocode_btn = st.columns([2,2,1])
        with col_lat: inputs['project_details']['latitude'] = st.number_input(get_text_di(texts, "latitude_label", "Breitengrad"), value=current_lat, format="%.6f", key="latitude_di_v6_exp", help="Z.B. 48.137154")
        with col_lon: inputs['project_details']['longitude'] = st.number_input(get_text_di(texts, "longitude_label", "Längengrad"), value=current_lon, format="%.6f", key="longitude_di_v6_exp", help="Z.B. 11.575382")
        with col_geocode_btn:
            st.write(""); st.write("")
            if st.button(get_text_di(texts, "get_coordinates_button", "Koordinaten abrufen"), key="geocode_btn_di_v6_exp", disabled=not EFFECTIVE_GOOGLE_API_KEY):
                addr_geo, city_geo, zip_geo = inputs['customer_data'].get('address', ''), inputs['customer_data'].get('city', ''), inputs['customer_data'].get('zip_code', '')
                if addr_geo and city_geo:
                    coords = get_coordinates_from_address_google(addr_geo, city_geo, zip_geo, EFFECTIVE_GOOGLE_API_KEY, texts)
                    if coords:
                        inputs['project_details']['latitude'], inputs['project_details']['longitude'] = coords['latitude'], coords['longitude']
                        st.session_state.satellite_image_url_di = None
                        st.rerun()
                else: st.warning(get_text_di(texts, "geocode_incomplete_address", "Bitte Adresse (Straße, PLZ, Ort) eingeben."))

        if not (abs(current_lat) < 1e-9 and abs(current_lon) < 1e-9):
            st.map(pd.DataFrame({'lat': [current_lat], 'lon': [current_lon]}), zoom=13)
        elif EFFECTIVE_GOOGLE_API_KEY: # Nur Info anzeigen, wenn Key da ist, aber keine Koordinaten
             st.info(get_text_di(texts, "map_no_coordinates_info", "Keine Koordinaten für Kartenanzeige. Bitte Adresse parsen oder Koordinaten manuell eingeben."))


        st.markdown("---"); st.markdown(f"**{get_text_di(texts, 'satellite_image_header', 'Satellitenbild (Google Maps)')}**")
        if 'satellite_image_url_di' not in st.session_state: st.session_state.satellite_image_url_di = None

        if not (abs(current_lat) < 1e-9 and abs(current_lon) < 1e-9) :
            if EFFECTIVE_GOOGLE_API_KEY:
                if st.button(get_text_di(texts, "load_satellite_image_button", "Satellitenbild laden/aktualisieren"), key="load_sat_img_btn_di_v6_final_exp"):
                    st.session_state.satellite_image_url_di = get_Maps_satellite_image_url(current_lat, current_lon, EFFECTIVE_GOOGLE_API_KEY, texts)
                    if st.session_state.satellite_image_url_di:
                        st.success(get_text_di(texts, "satellite_image_url_generated", "URL für Satellitenbild generiert."))
                        inputs['project_details']['satellite_image_base64_data'] = None # Reset Base64, da neue URL
                        inputs['project_details']['satellite_image_for_pdf_url_source'] = st.session_state.satellite_image_url_di # Speichere die Quell-URL
                    else:
                        st.error(get_text_di(texts, "satellite_image_load_failed", "Satellitenbild konnte nicht geladen werden (URL Generierung fehlgeschlagen oder ungültige Koordinaten)."))
                        inputs['project_details']['satellite_image_base64_data'] = None
                        inputs['project_details']['satellite_image_for_pdf_url_source'] = None


            if st.session_state.get('satellite_image_url_di'): # Prüfe auf .get, da es None sein könnte
                st.markdown(f"Generierte Bild-URL (für Vorschau):"); st.code(st.session_state.satellite_image_url_di)
                try:
                    st.image(st.session_state.satellite_image_url_di, caption=get_text_di(texts, "satellite_image_caption", "Satellitenansicht"))
                    default_visualize_satellite = inputs['project_details'].get('visualize_roof_in_pdf_satellite', True)
                    inputs['project_details']['visualize_roof_in_pdf_satellite'] = st.checkbox(
                        get_text_di(texts, "visualize_satellite_in_pdf_label", "Satellitenbild in PDF anzeigen"),
                        value=default_visualize_satellite,
                        key="visualize_satellite_in_pdf_di_val_v6_final_exp"
                    )

                    if inputs['project_details'].get('visualize_roof_in_pdf_satellite') and st.session_state.satellite_image_url_di:
                        # Nur neu laden, wenn Base64 fehlt ODER die Quell-URL sich geändert hat
                        if not inputs['project_details'].get('satellite_image_base64_data') or \
                           inputs['project_details'].get('satellite_image_for_pdf_url_source') != st.session_state.satellite_image_url_di:
                            try:
                                # print(f"DATA_INPUT_DEBUG: Versuche Satellitenbild von URL zu laden für PDF: {st.session_state.satellite_image_url_di}")
                                with st.spinner("Lade Satellitenbild für PDF..."):
                                    response = requests.get(st.session_state.satellite_image_url_di, timeout=15)
                                    response.raise_for_status()
                                    image_bytes = response.content
                                    base64_encoded_image = base64.b64encode(image_bytes).decode('utf-8')
                                    inputs['project_details']['satellite_image_base64_data'] = base64_encoded_image
                                    inputs['project_details']['satellite_image_for_pdf_url_source'] = st.session_state.satellite_image_url_di # Update Quell-URL
                                    print("DATA_INPUT_DEBUG: Satellitenbild erfolgreich heruntergeladen und als Base64 für PDF gespeichert.")
                                    st.success("Satellitenbild für PDF vorbereitet.")
                            except Exception as e_sat_download:
                                st.warning(f"Satellitenbild konnte nicht für PDF heruntergeladen werden: {e_sat_download}")
                                inputs['project_details']['satellite_image_base64_data'] = None
                                inputs['project_details']['satellite_image_for_pdf_url_source'] = None # Quell-URL auch zurücksetzen
                except Exception as e_img:
                    st.error(f"{get_text_di(texts, 'satellite_image_display_error', 'Fehler Anzeige Satellitenbild:')} {e_img}")
                    inputs['project_details']['visualize_roof_in_pdf_satellite'] = False # Im Fehlerfall nicht versuchen zu visualisieren
                    inputs['project_details']['satellite_image_base64_data'] = None
                    inputs['project_details']['satellite_image_for_pdf_url_source'] = None

            elif EFFECTIVE_GOOGLE_API_KEY :
                 st.info(get_text_di(texts, "satellite_image_press_button_info", "Klicken Sie auf 'Satellitenbild laden/aktualisieren', um das Bild anzuzeigen."))
        elif not EFFECTIVE_GOOGLE_API_KEY:
            st.info(get_text_di(texts, "maps_api_key_needed_for_button_info", "Ein gültiger Google Maps API Key wird benötigt, um Satellitenbilder zu laden. Bitte im Admin-Panel konfigurieren."))
        else: # Fall für Koordinaten (0,0)
            st.info(get_text_di(texts, "satellite_image_no_coords_info", "Keine (gültigen) Koordinaten für Satellitenbild. Adresse parsen & Koordinaten abrufen/manuell eingeben."))


        col_contact1,col_contact2,col_contact3=st.columns(3)
        with col_contact1:inputs['customer_data']['email']=st.text_input(get_text_di(texts,"email_label","E-Mail"),value=str(inputs['customer_data'].get('email','')),key='email_di_v6_exp')
        with col_contact2:inputs['customer_data']['phone_landline']=st.text_input(get_text_di(texts,"phone_landline_label","Telefon (Festnetz)"),value=str(inputs['customer_data'].get('phone_landline','')),key='phone_landline_di_v6_exp')
        with col_contact3:inputs['customer_data']['phone_mobile']=st.text_input(get_text_di(texts,"phone_mobile_label","Telefon (Mobil)"),value=str(inputs['customer_data'].get('phone_mobile','')),key='phone_mobile_di_v6_exp')

        inputs['customer_data']['income_tax_rate_percent']=st.number_input(
            label=get_text_di(texts,"income_tax_rate_label","ESt.-Satz (%)"),
            min_value=0.0, max_value=100.0,
            value=float(inputs['customer_data'].get('income_tax_rate_percent',0.0) or 0.0),
            step=0.1,format="%.1f",key='income_tax_rate_percent_di_v6_exp',
            help=get_text_di(texts,"income_tax_rate_help","Grenzsteuersatz für Wirtschaftlichkeitsberechnung (optional)")
        )

    st.subheader(get_text_di(texts,"consumption_analysis_header","Bedarfsanalyse"))
    with st.expander(get_text_di(texts,"consumption_costs_header","Verbräuche und Kosten"),expanded=st.session_state.get('consumption_data_expanded_di',True)): # Eindeutiger Expander-Key
        col_cons_hh,col_cons_heat=st.columns(2)
        inputs['project_details']['annual_consumption_kwh_yr']=col_cons_hh.number_input(label=get_text_di(texts,"annual_consumption_kwh_label","Jahresverbrauch Haushalt (kWh)"),min_value=0,value=int(inputs['project_details'].get('annual_consumption_kwh_yr',3500) or 3500),key='annual_consumption_kwh_yr_di_v6_exp')
        inputs['project_details']['consumption_heating_kwh_yr']=col_cons_heat.number_input(label=get_text_di(texts,"annual_heating_kwh_optional_label","Jahresverbrauch Heizung (kWh, opt.)"),min_value=0,value=int(inputs['project_details'].get('consumption_heating_kwh_yr',0) or 0),key='consumption_heating_kwh_yr_di_v6_exp')

        total_consumption_kwh_yr_display=(inputs['project_details'].get('annual_consumption_kwh_yr',0) or 0)+(inputs['project_details'].get('consumption_heating_kwh_yr',0) or 0)
        st.info(f"{get_text_di(texts,'total_annual_consumption_label','Gesamtjahresverbrauch (Haushalt + Heizung)')}: {total_consumption_kwh_yr_display:.0f} kWh")

        col_price_direct,col_price_calc=st.columns(2)
        default_calc_price=inputs['project_details'].get('calculate_electricity_price',True)
        use_calculated_price=col_price_calc.checkbox(get_text_di(texts,"calculate_electricity_price_checkbox","Strompreis aus Kosten berechnen?"),value=default_calc_price,key="calculate_electricity_price_di_v6_exp")
        inputs['project_details']['calculate_electricity_price']=use_calculated_price

        if use_calculated_price:
            col_costs_hh,col_costs_heat=st.columns(2)
            inputs['project_details']['costs_household_euro_mo']=col_costs_hh.number_input(label=get_text_di(texts,"monthly_costs_household_label","Monatliche Kosten Haushalt (€)"),min_value=0.0,value=float(inputs['project_details'].get('costs_household_euro_mo',80.0) or 80.0),step=0.1,key='costs_household_euro_mo_di_v6_exp')
            inputs['project_details']['costs_heating_euro_mo']=col_costs_heat.number_input(label=get_text_di(texts,"monthly_costs_heating_optional_label","Monatliche Kosten Heizung (€, opt.)"),min_value=0.0,value=float(inputs['project_details'].get('costs_heating_euro_mo',0.0) or 0.0),step=0.1,key='costs_heating_euro_mo_di_v6_exp')
            total_annual_costs_calc=((inputs['project_details'].get('costs_household_euro_mo',0.0) or 0.0)+(inputs['project_details'].get('costs_heating_euro_mo',0.0) or 0.0))*12
            st.info(f"{get_text_di(texts,'total_annual_costs_display_label','Gesamte jährliche Stromkosten (berechnet)')}: {total_annual_costs_calc:.2f} €")
            calculated_price_kwh=(total_annual_costs_calc/total_consumption_kwh_yr_display)if total_consumption_kwh_yr_display>0 else 0.0
            inputs['project_details']['electricity_price_kwh']=calculated_price_kwh
            st.info(f"{get_text_di(texts,'calculated_electricity_price_info','Daraus resultierender Strompreis')}: {calculated_price_kwh:.4f} €/kWh")
        else:
            inputs['project_details']['electricity_price_kwh']=col_price_direct.number_input(label=get_text_di(texts,"electricity_price_manual_label","Strompreis manuell (€/kWh)"),min_value=0.0,value=float(inputs['project_details'].get('electricity_price_kwh',0.30) or 0.30),step=0.001,format="%.4f",key='electricity_price_kwh_di_v6_exp')
            inputs['project_details']['costs_household_euro_mo'],inputs['project_details']['costs_heating_euro_mo']=0.0,0.0 # Sicherstellen, dass diese Null sind, wenn manueller Preis

    st.subheader(get_text_di(texts,"building_data_header","Daten des Gebäudes"))
    with st.expander(get_text_di(texts,"building_data_header","Daten des Gebäudes"),expanded=st.session_state.get('building_data_expanded_di',True)): # Eindeutiger Expander-Key
        col_build1,col_build2=st.columns(2)
        with col_build1:
            inputs['project_details']['build_year']=st.number_input(label=get_text_di(texts,"build_year_label","Baujahr des Hauses"),min_value=1800,max_value=datetime.now().year,value=int(inputs['project_details'].get('build_year',2000) or 2000),step=1,key='build_year_di_v6_exp')
            build_year_val=inputs['project_details']['build_year']
            if build_year_val<1960:st.warning(get_text_di(texts,"build_year_warning_old","❗️ Zählerschrank/Hauselektrik prüfen."))
            elif build_year_val<2000:st.info(get_text_di(texts,"build_year_info_mid","ℹ️ Zählerschrank/Hauselektrik prüfen."))
            else:st.success(get_text_di(texts,"build_year_success_new","✅ Zählerschrank/Hauselektrik OK."))
        with col_build2:
            default_roof_type=inputs['project_details'].get('roof_type',please_select_text)
            roof_type_options_with_ps=[please_select_text]+DACHART_OPTIONS
            inputs['project_details']['roof_type']=st.selectbox(get_text_di(texts,"roof_type_label","Dachart"),options=roof_type_options_with_ps,index=roof_type_options_with_ps.index(default_roof_type)if default_roof_type in roof_type_options_with_ps else 0,key='roof_type_di_v6_exp')
            if inputs['project_details']['roof_type']==please_select_text:inputs['project_details']['roof_type']=None
        col_build3,col_build4=st.columns(2)
        with col_build3:
            default_roof_covering=inputs['project_details'].get('roof_covering_type',please_select_text)
            roof_covering_options_with_ps=[please_select_text]+DACHDECKUNG_OPTIONS
            inputs['project_details']['roof_covering_type']=st.selectbox(get_text_di(texts,"roof_covering_label","Dachdeckungsart"),options=roof_covering_options_with_ps,index=roof_covering_options_with_ps.index(default_roof_covering)if default_roof_covering in roof_covering_options_with_ps else 0,key='roof_covering_type_di_v6_exp')
            if inputs['project_details']['roof_covering_type']==please_select_text:inputs['project_details']['roof_covering_type']=None
            if inputs['project_details']['roof_covering_type']and inputs['project_details']['roof_covering_type']in['Schiefer','Bitumen','Eternit']:st.warning(get_text_di(texts,"roof_covering_warning","❗️ Höhere Montagekosten möglich."))
            elif inputs['project_details']['roof_covering_type']:st.success(get_text_di(texts,"roof_covering_info","✅ Dachbelegung problemlos."))
        with col_build4:inputs['project_details']['free_roof_area_sqm']=st.number_input(label=get_text_di(texts,"free_roof_area_label","Freie Dachfläche (m²)"),min_value=0.0,value=float(inputs['project_details'].get('free_roof_area_sqm',50.0) or 50.0),key='free_roof_area_sqm_di_v6_exp')
        col_build5,col_build6=st.columns(2)
        with col_build5:
            orientation_options=[please_select_text]+['Süd','Südost','Ost','Südwest','West','Nordwest','Nord','Nordost','Flachdach (Süd)','Flachdach (Ost-West)']
            default_orientation=inputs['project_details'].get('roof_orientation',please_select_text)
            inputs['project_details']['roof_orientation']=st.selectbox(get_text_di(texts,"roof_orientation_label","Dachausrichtung"),options=orientation_options,index=orientation_options.index(default_orientation)if default_orientation in orientation_options else 0,key='roof_orientation_di_select_v6_exp')
            if inputs['project_details']['roof_orientation']==please_select_text:inputs['project_details']['roof_orientation']=None
        with col_build6:inputs['project_details']['roof_inclination_deg']=st.number_input(label=get_text_di(texts,"roof_inclination_label","Dachneigung (Grad)"),min_value=0,max_value=90,value=int(inputs['project_details'].get('roof_inclination_deg',30) or 30),key='roof_inclination_deg_di_v6_exp')
        inputs['project_details']['building_height_gt_7m']=st.checkbox(get_text_di(texts,"building_height_gt_7m_label","Gebäudehöhe > 7 Meter (Gerüst erforderlich)"),value=inputs['project_details'].get('building_height_gt_7m',False),key='building_height_gt_7m_di_v6_exp')

    st.markdown("---")
    st.subheader(get_text_di(texts,"future_consumption_header","Zukünftiger Mehrverbrauch"))
    inputs['project_details']['future_ev']=st.checkbox(get_text_di(texts,"future_ev_checkbox_label","Zukünftiges E-Auto einplanen"),value=inputs['project_details'].get('future_ev',False),key='future_ev_di_v6_exp')
    inputs['project_details']['future_hp']=st.checkbox(get_text_di(texts,"future_hp_checkbox_label","Zukünftige Wärmepumpe einplanen"),value=inputs['project_details'].get('future_hp',False),key='future_hp_di_v6_exp')

    st.subheader(get_text_di(texts,"technology_selection_header","Auswahl der Technik"))
    with st.expander(get_text_di(texts,"technology_selection_header","Auswahl der Technik"),expanded=st.session_state.get('tech_selection_expanded_di',True)): # Eindeutiger Expander-Key
        col_tech1,col_tech2=st.columns(2)
        with col_tech1:inputs['project_details']['module_quantity']=st.number_input(label=get_text_di(texts,"module_quantity_label","Anzahl PV Module"),min_value=0,value=int(inputs['project_details'].get('module_quantity',20) or 20),key='module_quantity_di_tech_v6_exp') # Eindeutiger Widget-Key
        with col_tech2:
            current_module_name=inputs['project_details'].get('selected_module_name',please_select_text)
            module_options_tech=[please_select_text]+MODULE_LIST_MODELS
            try:idx_module_tech=module_options_tech.index(current_module_name)
            except ValueError:idx_module_tech=0
            selected_module_name_ui_tech=st.selectbox(get_text_di(texts,"module_model_label","PV Modul Modell"),options=module_options_tech,index=idx_module_tech,key='selected_module_name_di_tech_v6_exp')
            inputs['project_details']['selected_module_name']=selected_module_name_ui_tech if selected_module_name_ui_tech!=please_select_text else None
            st.session_state['selected_module_name'] = inputs['project_details']['selected_module_name'] # Sync mit Session State
            if inputs['project_details']['selected_module_name']:
                module_details=get_product_by_model_name_safe(inputs['project_details']['selected_module_name'])
                if module_details:inputs['project_details']['selected_module_id'],inputs['project_details']['selected_module_capacity_w']=module_details.get('id'),float(module_details.get('capacity_w',0.0)or 0.0)
                else:st.warning(get_text_di(texts,'module_details_not_loaded_warning',f"Details für Modul '{inputs['project_details']['selected_module_name']}' nicht geladen."));inputs['project_details']['selected_module_id'],inputs['project_details']['selected_module_capacity_w']=None,0.0
            else:inputs['project_details']['selected_module_id'],inputs['project_details']['selected_module_capacity_w']=None,0.0
        if inputs['project_details'].get('selected_module_name')and inputs['project_details'].get('selected_module_capacity_w',0.0)>0:
            st.info(f"{get_text_di(texts,'module_capacity_label','Leistung pro Modul (Wp)')}: {inputs['project_details']['selected_module_capacity_w']:.0f} Wp")
        anlage_kwp_calc_tech=((inputs['project_details'].get('module_quantity',0) or 0)*(inputs['project_details'].get('selected_module_capacity_w',0.0) or 0.0))/1000.0
        st.info(f"{get_text_di(texts,'anlage_size_label','Anlagengröße (kWp)')}: {anlage_kwp_calc_tech:.2f} kWp")
        inputs['project_details']['anlage_kwp']=anlage_kwp_calc_tech
        current_inverter_name=inputs['project_details'].get('selected_inverter_name',please_select_text)
        inverter_options_tech=[please_select_text]+INVERTER_LIST_MODELS
        try:idx_inverter_tech=inverter_options_tech.index(current_inverter_name)
        except ValueError:idx_inverter_tech=0
        selected_inverter_name_ui_tech=st.selectbox(get_text_di(texts,"inverter_model_label","Wechselrichter Modell"),options=inverter_options_tech,index=idx_inverter_tech,key='selected_inverter_name_di_tech_v6_exp')
        inputs['project_details']['selected_inverter_name']=selected_inverter_name_ui_tech if selected_inverter_name_ui_tech!=please_select_text else None
        st.session_state['selected_inverter_name'] = inputs['project_details']['selected_inverter_name'] # Sync
        if inputs['project_details']['selected_inverter_name']:
            inverter_details=get_product_by_model_name_safe(inputs['project_details']['selected_inverter_name'])
            if inverter_details:inputs['project_details']['selected_inverter_id'],inputs['project_details']['selected_inverter_power_kw']=inverter_details.get('id'),float(inverter_details.get('power_kw',0.0)or 0.0)
            else:st.warning(get_text_di(texts,'inverter_details_not_loaded_warning',f"Details für WR '{inputs['project_details']['selected_inverter_name']}' nicht geladen."));inputs['project_details']['selected_inverter_id'],inputs['project_details']['selected_inverter_power_kw']=None,0.0
        else:inputs['project_details']['selected_inverter_id'],inputs['project_details']['selected_inverter_power_kw']=None,0.0
        if inputs['project_details'].get('selected_inverter_name')and inputs['project_details'].get('selected_inverter_power_kw',0.0)>0:
            st.info(f"{get_text_di(texts,'inverter_power_label','Leistung WR (kW)')}: {inputs['project_details']['selected_inverter_power_kw']:.2f} kW")
        inputs['project_details']['include_storage']=st.checkbox(get_text_di(texts,"include_storage_label","Batteriespeicher einplanen"),value=inputs['project_details'].get('include_storage',False),key='include_storage_di_tech_v6_exp')
        if inputs['project_details']['include_storage']:
            col_storage_model,col_storage_capacity=st.columns(2)
            with col_storage_model:
                current_storage_name=inputs['project_details'].get('selected_storage_name',please_select_text)
                storage_options_tech=[please_select_text]+STORAGE_LIST_MODELS
                try:idx_storage_tech=storage_options_tech.index(current_storage_name)
                except ValueError:idx_storage_tech=0
                selected_storage_name_ui_tech=st.selectbox(get_text_di(texts,"storage_model_label","Speicher Modell"),options=storage_options_tech,index=idx_storage_tech,key='selected_storage_name_di_tech_v6_exp')
                inputs['project_details']['selected_storage_name']=selected_storage_name_ui_tech if selected_storage_name_ui_tech!=please_select_text else None
                st.session_state['selected_storage_name'] = inputs['project_details']['selected_storage_name'] # Sync
            storage_capacity_from_model_tech=0.0
            if inputs['project_details']['selected_storage_name']:
                storage_details=get_product_by_model_name_safe(inputs['project_details']['selected_storage_name'])
                if storage_details:
                    inputs['project_details']['selected_storage_id']=storage_details.get('id')
                    storage_capacity_from_model_tech=float(storage_details.get('storage_power_kw',0.0)or 0.0)
                    st.info(f"{get_text_di(texts,'storage_capacity_model_label','Kapazität Modell (kWh)')}: {storage_capacity_from_model_tech:.2f} kWh")
                else:st.warning(get_text_di(texts,'storage_details_not_loaded_warning',f"Details für Speicher '{inputs['project_details']['selected_storage_name']}' nicht geladen."));inputs['project_details']['selected_storage_id']=None
            else:inputs['project_details']['selected_storage_id']=None
            with col_storage_capacity:
                default_manual_cap_tech=float(inputs['project_details'].get('selected_storage_storage_power_kw',0.0) or 0.0)
                if default_manual_cap_tech==0.0:default_manual_cap_tech=storage_capacity_from_model_tech if storage_capacity_from_model_tech>0 else 5.0
                inputs['project_details']['selected_storage_storage_power_kw']=st.number_input(label=get_text_di(texts,"storage_capacity_manual_label","Gewünschte Gesamtkapazität (kWh)"),min_value=0.0,value=default_manual_cap_tech,step=0.1,key='selected_storage_storage_power_kw_di_tech_v6_exp')
        else:inputs['project_details']['selected_storage_name'],inputs['project_details']['selected_storage_id'],inputs['project_details']['selected_storage_storage_power_kw']=None,None,0.0

    st.markdown("---")
    st.subheader(get_text_di(texts,"additional_components_header","Zusätzliche Komponenten"))
    inputs['project_details']['include_additional_components']=st.checkbox(get_text_di(texts,"include_additional_components_label","Zusätzliche Komponenten einplanen"),value=inputs['project_details'].get('include_additional_components',False),key='include_additional_components_di_tech_main_cb_v6_exp')
    if inputs['project_details']['include_additional_components']:
        def create_component_selector(component_label_key: str, component_list: List[str], project_details_key_name: str, project_details_key_id: str, widget_key_suffix:str):
            current_value=inputs['project_details'].get(project_details_key_name,please_select_text)
            options=[please_select_text]+component_list
            try:initial_idx=options.index(current_value)
            except ValueError:initial_idx=0
            label_str=get_text_di(texts,component_label_key)
            selected_name=st.selectbox(label_str,options=options,index=initial_idx,key=f"{project_details_key_name}_widget_key_di_add_{widget_key_suffix}_v6_exp") # Eindeutiger Widget-Key
            inputs['project_details'][project_details_key_name]=selected_name if selected_name!=please_select_text else None
            st.session_state[project_details_key_name] = inputs['project_details'][project_details_key_name] # Sync
            if inputs['project_details'][project_details_key_name]:
                comp_details=get_product_by_model_name_safe(inputs['project_details'][project_details_key_name])
                inputs['project_details'][project_details_key_id]=comp_details.get('id')if comp_details else None
            else:inputs['project_details'][project_details_key_id]=None
        create_component_selector("wallbox_model_label",WALLBOX_LIST_MODELS,"selected_wallbox_name","selected_wallbox_id", "wb_v6_exp")
        create_component_selector("ems_model_label",EMS_LIST_MODELS,"selected_ems_name","selected_ems_id", "ems_v6_exp")
        create_component_selector("optimizer_model_label",OPTIMIZER_LIST_MODELS,"selected_optimizer_name","selected_optimizer_id", "opti_v6_exp")
        create_component_selector("carport_model_label",CARPORT_LIST_MODELS,"selected_carport_name","selected_carport_id", "cp_v6_exp")
        create_component_selector("notstrom_model_label",NOTSTROM_LIST_MODELS,"selected_notstrom_name","selected_notstrom_id", "not_v6_exp")
        create_component_selector("tierabwehr_model_label",TIERABWEHR_LIST_MODELS,"selected_tierabwehr_name","selected_tierabwehr_id", "ta_v6_exp")

    st.subheader(get_text_di(texts,"economic_data_header","Wirtschaftliche Parameter"))
    with st.expander(get_text_di(texts,"economic_data_header","Wirtschaftliche Parameter"),expanded=st.session_state.get('economic_data_expanded_di',False)): # Eindeutiger Expander-Key
        inputs['economic_data']['simulation_period_years']=st.number_input(label=get_text_di(texts,"simulation_period_label_short","Simulationsdauer (Jahre)"),min_value=5,max_value=50,value=int(inputs['economic_data'].get('simulation_period_years',20) or 20),key="sim_period_econ_di_v6_exp")
        inputs['economic_data']['electricity_price_increase_annual_percent']=st.number_input(label=get_text_di(texts,"electricity_price_increase_label_short","Strompreissteigerung p.a. (%)"),min_value=0.0,max_value=10.0,value=float(inputs['economic_data'].get('electricity_price_increase_annual_percent',3.0) or 3.0),step=0.1,format="%.1f",key="elec_increase_econ_di_v6_exp")
        inputs['economic_data']['custom_costs_netto']=st.number_input(label=get_text_di(texts,"custom_costs_netto_label","Zusätzliche einmalige Nettokosten (€)"),min_value=0.0,value=float(inputs['economic_data'].get('custom_costs_netto',0.0) or 0.0),step=10.0,key="custom_costs_netto_di_v6_exp")

    st.session_state.project_data = inputs.copy()
    return inputs

if __name__ == "__main__":
  st.title("Data Input Modul Test")
  if 'project_data' not in st.session_state:
    st.session_state.project_data = {'customer_data': {}, 'project_details': {}, 'economic_data': {}}
  

    def mock_list_products(category=None):
        if category == 'Modul': return [{'id': 1, 'model_name': 'TestModul 400Wp', 'capacity_w': 400.0}]
        if category == 'Wechselrichter': return [{'id': 2, 'model_name': 'TestWR 5kW', 'power_kw': 5.0}]
        if category == 'Batteriespeicher': return [{'id': 3, 'model_name': 'TestSpeicher 10kWh', 'storage_power_kw': 10.0}]
        return []
    def mock_get_product_by_model_name(model_name):
        if model_name == 'TestModul 400Wp': return {'id': 1, 'model_name': 'TestModul 400Wp', 'capacity_w': 400.0}
        if model_name == 'TestWR 5kW': return {'id': 2, 'model_name': 'TestWR 5kW', 'power_kw': 5.0}
        if model_name == 'TestSpeicher 10kWh': return {'id': 3, 'model_name': 'TestSpeicher 10kWh', 'storage_power_kw': 10.0}
        return None
    def mock_load_admin_setting(key, default=None):
        if key == 'Maps_api_key': return "PLATZHALTER_API_KEY_TEST"
        if key == 'salutation_options': return ['Herr', 'Frau', 'Familie', 'Firma', 'Divers', '']
        if key == 'title_options': return ['Dr.', 'Prof.', 'Mag.', 'Ing.', None]
        return default

    _original_list_products, _temp_list_products_safe = list_products_safe, mock_list_products
    _original_get_product_by_model_name, _temp_get_product_by_model_name_safe = get_product_by_model_name_safe, mock_get_product_by_model_name
    _original_load_admin_setting, _temp_load_admin_setting_safe = load_admin_setting_safe, mock_load_admin_setting
    list_products_safe = _temp_list_products_safe
    get_product_by_model_name_safe = _temp_get_product_by_model_name_safe
    load_admin_setting_safe = _temp_load_admin_setting_safe

    test_texts_di = {key: key.replace("_"," ").title() + " (Test)" for key in [
        "customer_data_header", "anlage_type_label", "feed_in_type_label", "customer_type_label",
        "salutation_label", "title_label", "first_name_label", "last_name_label", "full_address_label",
        "full_address_help", "parse_address_button", "parse_address_success_all", "parse_address_partial_success",
        "parse_address_no_input", "street_label", "house_number_label", "zip_code_label", "city_label",
        "state_label", "coordinates_header", "latitude_label", "longitude_label", "get_coordinates_button",
        "geolocation_success_google_api", "geolocation_google_api_no_coords", "geolocation_google_api_status_error",
        "geolocation_google_api_timeout", "geolocation_google_api_request_error", "geocode_incomplete_address",
        "map_no_coordinates_info", "satellite_image_header", "load_satellite_image_button", "satellite_image_caption",
        "visualize_satellite_in_pdf_label", "satellite_image_load_failed", "satellite_image_display_error",
        "satellite_image_no_coords_info", "maps_api_key_needed_for_button_info", "satellite_image_url_generated",
        "satellite_image_press_button_info", "email_label", "phone_landline_label", "phone_mobile_label",
        "income_tax_rate_label", "income_tax_rate_help", "consumption_analysis_header", "consumption_costs_header",
        "annual_consumption_kwh_label", "annual_heating_kwh_optional_label", "total_annual_consumption_label",
        "calculate_electricity_price_checkbox", "monthly_costs_household_label", "monthly_costs_heating_optional_label",
        "total_annual_costs_display_label", "calculated_electricity_price_info", "electricity_price_manual_label",
        "building_data_header", "build_year_label", "build_year_warning_old", "build_year_info_mid",
        "build_year_success_new", "roof_type_label", "roof_covering_label", "roof_covering_warning",
        "roof_covering_info", "free_roof_area_label", "roof_orientation_label", "roof_inclination_label",
        "building_height_gt_7m_label", "future_consumption_header", "future_ev_checkbox_label",
        "future_hp_checkbox_label", "technology_selection_header", "num_persons_label", "map_default_coords_info",
        "please_select_option", "none_option", "no_modules_in_db", "no_inverters_in_db", "no_storages_in_db",
        "module_capacity_label", "anlage_size_label", "inverter_power_label", "include_storage_label",
        "storage_model_label", "storage_capacity_model_label", "storage_capacity_manual_label",
        "economic_data_header", "simulation_period_label_short", "electricity_price_increase_label_short",
        "custom_costs_netto_label", "additional_components_header", "include_additional_components_label",
        "wallbox_model_label", "no_wallboxes_in_db", "ems_model_label", "no_ems_in_db",
        "optimizer_model_label", "no_optimizers_in_db", "carport_model_label", "no_carports_in_db",
        "notstrom_model_label", "no_notstrom_in_db", "tierabwehr_model_label", "no_tierabwehr_in_db",
        "geocode_google_api_key_missing_or_placeholder_terminal", "geocode_google_api_key_missing_or_placeholder_ui",
        "maps_api_key_missing_or_placeholder_terminal", "maps_api_key_missing_or_placeholder_ui",
        "maps_api_key_NOT_found_error_detailed_terminal", "maps_api_key_NOT_found_error_ui",
        "parse_street_hnr_warning_detail", "parse_street_hnr_not_found", "geocode_missing_address_city",
        "geolocation_api_unknown_error", "module_details_not_loaded_warning",
        "inverter_details_not_loaded_warning", "storage_details_not_loaded_warning"
    ]}
    render_data_input(test_texts_di)
    st.write("Aktueller project_data im session_state:", st.session_state.project_data)

    list_products_safe = _original_list_products
    get_product_by_model_name_safe = _original_get_product_by_model_name
    load_admin_setting_safe = _original_load_admin_setting