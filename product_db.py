# product_db.py
# Modul zur Verwaltung der Produktdatenbank (SQLite)
from datetime import datetime

import sqlite3
import pandas as pd
import json
from typing import Dict, List, Optional, Any, Tuple, Union
import traceback
import os

# Datenbankverbindung und Verfügbarkeitsstatus
DB_AVAILABLE = False
get_db_connection_safe_pd = None

try:
    from database import get_db_connection, init_db # init_db wird hier nicht direkt verwendet, aber Import ist ok
    get_db_connection_safe_pd = get_db_connection
    DB_AVAILABLE = True
except ImportError as e:
    def _dummy_get_db_connection_ie(): # type: ignore
        print(f"product_db.py: Importfehler für database.py: {e}. Dummy DB-Verbindung genutzt.")
        return None
    get_db_connection_safe_pd = _dummy_get_db_connection_ie
    print(f"product_db.py: Importfehler für database.py: {e}. Dummy DB Funktionen werden genutzt.")
except Exception as e:
    def _dummy_get_db_connection_ex(): # type: ignore
        print(f"product_db.py: Fehler beim Laden von database.py: {e}. Dummy DB-Verbindung genutzt.")
        return None
    get_db_connection_safe_pd = _dummy_get_db_connection_ex
    print(f"product_db.py: Fehler beim Laden von database.py: {e}. Dummy DB Funktionen werden genutzt.")

def create_product_table(conn: sqlite3.Connection):
    cursor = conn.cursor()
    # Spalte 'added_date' wurde zu 'created_at' geändert für Konsistenz mit Anforderung A.
    # 'last_updated' bleibt für die letzte Modifikation.
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS products (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            category TEXT NOT NULL,
            model_name TEXT NOT NULL UNIQUE,
            brand TEXT,
            price_euro REAL,
            capacity_w REAL,
            storage_power_kw REAL,
            power_kw REAL,
            max_cycles INTEGER,
            warranty_years INTEGER,
            length_m REAL,
            width_m REAL,
            weight_kg REAL,
            efficiency_percent REAL,
            origin_country TEXT,
            description TEXT,
            pros TEXT,
            cons TEXT,
            rating REAL,
            image_base64 TEXT,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP, 
            updated_at TEXT DEFAULT CURRENT_TIMESTAMP, -- Wird als last_updated interpretiert
            datasheet_link_db_path TEXT, 
            additional_cost_netto REAL DEFAULT 0.0 
        )
    """)
    conn.commit()
    _migrate_product_table_columns(conn) # Stellt sicher, dass alle Spalten existieren

def _migrate_product_table_columns(conn: sqlite3.Connection):
    cursor = conn.cursor()
    cursor.execute("PRAGMA table_info(products)")
    existing_columns_info = {row[1]: row for row in cursor.fetchall()}
    existing_columns = list(existing_columns_info.keys())

    # Reihenfolge und Typen gemäß Anforderung A und DB-Schema
    # 'last_updated' wird intern für 'updated_at' verwendet.
    expected_columns_and_types = {
        "id": "INTEGER", "category": "TEXT", "model_name": "TEXT", "brand": "TEXT",
        "price_euro": "REAL", "capacity_w": "REAL", "storage_power_kw": "REAL",
        "power_kw": "REAL", "max_cycles": "INTEGER", "warranty_years": "INTEGER",
        "length_m": "REAL", "width_m": "REAL", "weight_kg": "REAL",
        "efficiency_percent": "REAL", "origin_country": "TEXT", "description": "TEXT",
        "pros": "TEXT", "cons": "TEXT", "rating": "REAL", "image_base64": "TEXT",
        "created_at": "TEXT", "updated_at": "TEXT", # 'updated_at' wird als 'last_updated' in der Logik oft behandelt
        "datasheet_link_db_path": "TEXT",
        "additional_cost_netto": "REAL"
        # Die alte 'last_updated' Spalte wird durch 'updated_at' abgedeckt/ersetzt.
        # Die alte 'added_date' Spalte wird durch 'created_at' abgedeckt/ersetzt.
    }

    # Umbenennung von 'added_date' zu 'created_at', falls nötig
    if 'added_date' in existing_columns and 'created_at' not in existing_columns:
        try:
            # Temporär NOT NULL entfernen, falls es existiert und Probleme macht
            # Dies ist komplex, da SQLite ALTER TABLE eingeschränkt ist. Besser, neue Tabelle erstellen und Daten kopieren.
            # Für diese Korrektur versuchen wir ein einfaches RENAME.
            print("product_db.py: Alte Spalte 'added_date' gefunden, versuche Umbenennung zu 'created_at'.")
            cursor.execute("ALTER TABLE products RENAME COLUMN added_date TO created_at;")
            conn.commit()
            existing_columns.remove('added_date')
            existing_columns.append('created_at')
            print("product_db.py: Spalte 'added_date' zu 'created_at' umbenannt.")
        except sqlite3.OperationalError as e_rename:
            print(f"product_db.py: Fehler beim Umbenennen von 'added_date' zu 'created_at': {e_rename}. Manuelle Migration könnte nötig sein.")

    # Umbenennung von 'last_updated' zu 'updated_at', falls nötig und 'updated_at' noch nicht existiert
    if 'last_updated' in existing_columns and 'updated_at' not in existing_columns:
        try:
            print("product_db.py: Alte Spalte 'last_updated' gefunden, versuche Umbenennung zu 'updated_at'.")
            cursor.execute("ALTER TABLE products RENAME COLUMN last_updated TO updated_at;")
            conn.commit()
            existing_columns.remove('last_updated')
            existing_columns.append('updated_at')
            print("product_db.py: Spalte 'last_updated' zu 'updated_at' umbenannt.")
        except sqlite3.OperationalError as e_rename_lu:
            print(f"product_db.py: Fehler beim Umbenennen von 'last_updated' zu 'updated_at': {e_rename_lu}.")


    for col_name, col_type in expected_columns_and_types.items():
        if col_name not in existing_columns:
            try:
                default_suffix = ""
                if col_name == "created_at" or col_name == "updated_at": default_suffix = " DEFAULT CURRENT_TIMESTAMP"
                elif col_type == "TEXT": default_suffix = " DEFAULT ''"
                elif col_type == "REAL": default_suffix = " DEFAULT 0.0"
                elif col_type == "INTEGER": default_suffix = " DEFAULT 0"

                not_null_stmt = ""
                if col_name in ["category", "model_name"]: not_null_stmt = " NOT NULL"

                # Bei ALTER TABLE für NOT NULL Spalten muss ein DEFAULT angegeben werden,
                # außer die Tabelle ist garantiert leer oder der Default wird manuell behandelt.
                alter_col_type = col_type
                if not_null_stmt and not default_suffix: # Wenn NOT NULL aber kein expliziter Default für ALTER
                     if col_type == "TEXT": default_suffix = " DEFAULT ''" # Minimaler Default für Text
                     elif col_type == "INTEGER": default_suffix = " DEFAULT 0"
                     elif col_type == "REAL": default_suffix = " DEFAULT 0.0"

                cursor.execute(f"ALTER TABLE products ADD COLUMN {col_name} {alter_col_type}{not_null_stmt}{default_suffix}")
                conn.commit()
                print(f"product_db.py: Spalte '{col_name}' ({alter_col_type}{not_null_stmt}{default_suffix}) zur Tabelle 'products' hinzugefügt.")
            except sqlite3.OperationalError as e:
                if "duplicate column name" in str(e).lower():
                    pass # Spalte existiert bereits, was ok ist.
                else:
                    print(f"product_db.py: Fehler beim Hinzufügen von Spalte '{col_name}': {e}")
                    traceback.print_exc()
            except Exception as e_general_add:
                print(f"product_db.py: Allgemeiner Fehler beim Hinzufügen der Spalte '{col_name}': {e_general_add}")
                traceback.print_exc()
    conn.commit()


def add_product(product_data: Dict[str, Any]) -> Optional[int]:
    conn = get_db_connection_safe_pd()
    if conn is None:
        print("product_db.add_product: DB nicht verfügbar.")
        return None

    create_product_table(conn)
    cursor = conn.cursor()
    now_iso = datetime.now().isoformat()

    # Sicherstellen, dass alle Spalten aus expected_columns_and_types in product_data sind oder Defaults haben
    all_db_columns = {
        "id", "category", "model_name", "brand", "price_euro", "capacity_w", "storage_power_kw",
        "power_kw", "max_cycles", "warranty_years", "length_m", "width_m", "weight_kg",
        "efficiency_percent", "origin_country", "description", "pros", "cons", "rating",
        "image_base64", "created_at", "updated_at", "datasheet_link_db_path", "additional_cost_netto"
    }
    
    insert_data: Dict[str, Any] = {}

    # Pflichtfelder prüfen
    if not product_data.get('category'):
        print(f"product_db.add_product: FEHLER - 'category' ist Pflicht. Produkt: {product_data.get('model_name', 'N/A')}")
        if conn: conn.close(); return None
    if not product_data.get('model_name'):
        print(f"product_db.add_product: FEHLER - 'model_name' ist Pflicht. Daten: {product_data}")
        if conn: conn.close(); return None

    # Vorhandensein in DB-Schema prüfen und Daten vorbereiten
    for col_name in all_db_columns:
        if col_name == 'id': continue # ID ist auto-increment

        if col_name in product_data:
            insert_data[col_name] = product_data[col_name]
        else:
            # Defaults für optionale Felder, falls nicht vorhanden
            if col_name == 'created_at' or col_name == 'updated_at':
                insert_data[col_name] = now_iso
            elif col_name in ["price_euro", "capacity_w", "storage_power_kw", "power_kw", "length_m", "width_m", "weight_kg", "efficiency_percent", "rating", "additional_cost_netto"]:
                insert_data[col_name] = 0.0
            elif col_name in ["max_cycles", "warranty_years"]:
                insert_data[col_name] = 0
            else: # TEXT oder BLOB (image_base64, datasheet_link_db_path)
                insert_data[col_name] = None # Lässt SQLite den Default greifen oder bleibt NULL

    # Duplikatprüfung für model_name
    cursor.execute("SELECT id FROM products WHERE model_name = ?", (insert_data['model_name'],))
    if cursor.fetchone():
        print(f"product_db.add_product: Fehler - Produkt mit Modellname '{insert_data['model_name']}' existiert bereits.")
        if conn: conn.close(); return None

    fields = ', '.join(insert_data.keys())
    placeholders = ', '.join(['?'] * len(insert_data))
    
    try:
        cursor.execute(f"INSERT INTO products ({fields}) VALUES ({placeholders})", list(insert_data.values()))
        conn.commit()
        product_id = cursor.lastrowid
        print(f"product_db.add_product: Produkt '{insert_data['model_name']}' erfolgreich mit ID {product_id} hinzugefügt.")
        return product_id
    except sqlite3.Error as e:
        print(f"product_db.add_product: SQLite Fehler bei INSERT von '{insert_data.get('model_name', 'N/A')}': {e}")
        traceback.print_exc()
        if conn: conn.rollback()
        return None
    finally:
        if conn: conn.close()


def update_product(product_id: Union[int, float], product_data: Dict[str, Any]) -> bool:
    conn = get_db_connection_safe_pd()
    if conn is None:
        print("product_db.update_product: DB nicht verfügbar.")
        return False

    create_product_table(conn)
    cursor = conn.cursor()
    now_iso = datetime.now().isoformat()
    
    # Spalte 'last_updated' in den Daten durch 'updated_at' ersetzen, falls vorhanden
    if 'last_updated' in product_data:
        product_data['updated_at'] = product_data.pop('last_updated')
    
    product_data['updated_at'] = now_iso # Immer das aktuelle Datum für die Änderung

    # Alle Spalten aus der DB holen
    cursor.execute("PRAGMA table_info(products)")
    db_columns = [col_info[1] for col_info in cursor.fetchall()]

    # Validierung für Pflichtfelder
    if 'category' in product_data and not product_data['category']:
        print(f"product_db.update_product: FEHLER - 'category' darf nicht leer sein für ID {product_id}.")
        if conn: conn.close(); return False
    if 'model_name' in product_data and not product_data['model_name']:
        print(f"product_db.update_product: FEHLER - 'model_name' darf nicht leer sein für ID {product_id}.")
        if conn: conn.close(); return False

    # Duplikatprüfung, falls model_name geändert wird
    if 'model_name' in product_data:
        cursor.execute("SELECT id FROM products WHERE model_name = ? AND id != ?", (product_data['model_name'], int(product_id)))
        if cursor.fetchone():
            print(f"product_db.update_product: Fehler - Modellname '{product_data['model_name']}' existiert bereits für anderes Produkt.")
            if conn: conn.close(); return False

    update_data = {k: v for k, v in product_data.items() if k in db_columns and k != 'id'}

    if not update_data:
        print(f"product_db.update_product: Keine gültigen Felder zum Aktualisieren für ID {product_id}.")
        if conn: conn.close(); return False # Keine Änderungen, aber kein Fehler

    fields_to_set = [f"{k}=?" for k in update_data.keys()]
    values = list(update_data.values())
    values.append(int(product_id))
    
    try:
        cursor.execute(f"UPDATE products SET {', '.join(fields_to_set)} WHERE id=?", values)
        conn.commit()
        if cursor.rowcount > 0:
            print(f"product_db.update_product: Produkt ID {product_id} erfolgreich aktualisiert.")
            return True
        else: # Produkt-ID nicht gefunden
            print(f"product_db.update_product: Produkt ID {product_id} nicht gefunden.")
            return False
    except sqlite3.Error as e:
        print(f"product_db.update_product: SQLite Fehler für ID {product_id}: {e}")
        traceback.print_exc()
        if conn: conn.rollback()
        return False
    finally:
        if conn: conn.close()


def delete_product(product_id: Union[int, float]) -> bool:
    conn = get_db_connection_safe_pd()
    if conn is None:
        print("product_db.delete_product: DB nicht verfügbar.")
        return False
    create_product_table(conn) # Stellt Tabellenexistenz sicher
    cursor = conn.cursor()
    try:
        cursor.execute("DELETE FROM products WHERE id=?", (int(product_id),))
        conn.commit()
        deleted_count = cursor.rowcount
        if deleted_count > 0:
            print(f"product_db.delete_product: Produkt ID {product_id} erfolgreich gelöscht.")
        else:
            print(f"product_db.delete_product: Produkt ID {product_id} nicht gefunden, nichts gelöscht.")
        return deleted_count > 0
    except sqlite3.Error as e:
        print(f"product_db.delete_product: SQLite Fehler für ID {product_id}: {e}")
        traceback.print_exc()
        if conn: conn.rollback()
        return False
    finally:
        if conn: conn.close()

def list_products(category: Optional[str] = None) -> List[Dict[str, Any]]:
    conn = get_db_connection_safe_pd()
    if conn is None:
        print("product_db.list_products: DB nicht verfügbar.")
        return []
    create_product_table(conn) # Stellt Tabellenexistenz sicher
    cursor = conn.cursor()
    query = "SELECT * FROM products"
    params: List[Any] = [] # Explizit typisieren
    if category:
        query += " WHERE category = ?"
        params.append(category)
    query += " ORDER BY model_name COLLATE NOCASE" # Sortierung für Konsistenz
    try:
        cursor.execute(query, params)
        # Sicherstellen, dass das Ergebnis von cursor.fetchall() korrekt als dict interpretiert wird
        rows = cursor.fetchall()
        return [dict(row) for row in rows] if rows else []
    except sqlite3.Error as e:
        print(f"product_db.list_products: SQLite Fehler: {e}")
        traceback.print_exc()
        return []
    finally:
        if conn: conn.close()


def get_product_by_id(product_id: Union[int, float]) -> Optional[Dict[str, Any]]:
    conn = get_db_connection_safe_pd()
    if conn is None:
        print("product_db.get_product_by_id: DB nicht verfügbar.")
        return None
    create_product_table(conn) # Stellt Tabellenexistenz sicher
    cursor = conn.cursor()
    try:
        cursor.execute("SELECT * FROM products WHERE id=?", (int(product_id),))
        row = cursor.fetchone()
        return dict(row) if row else None
    except sqlite3.Error as e:
        print(f"product_db.get_product_by_id: SQLite Fehler für ID {product_id}: {e}")
        traceback.print_exc()
        return None
    finally:
        if conn: conn.close()

def get_product_by_model_name(model_name: str) -> Optional[Dict[str, Any]]:
    if not model_name or not model_name.strip(): # Zusätzliche Prüfung
        print("product_db.get_product_by_model_name: Modellname darf nicht leer sein.")
        return None
    conn = get_db_connection_safe_pd()
    if conn is None:
        print("product_db.get_product_by_model_name: DB nicht verfügbar.")
        return None
    create_product_table(conn) # Stellt Tabellenexistenz sicher
    cursor = conn.cursor()
    try:
        # Case-insensitive Suche für Modellnamen kann sinnvoll sein, abhängig von Anforderungen
        cursor.execute("SELECT * FROM products WHERE model_name=? COLLATE NOCASE", (model_name.strip(),))
        row = cursor.fetchone()
        return dict(row) if row else None
    except sqlite3.Error as e:
        print(f"product_db.get_product_by_model_name: SQLite Fehler für Modell '{model_name}': {e}")
        traceback.print_exc()
        return None
    finally:
        if conn: conn.close()


def update_product_image(product_id: Union[int, float], image_base64: Optional[str]) -> bool:
    return update_product(int(product_id), {"image_base64": image_base64})


def list_product_categories() -> List[str]:
    conn = get_db_connection_safe_pd()
    if conn is None:
        print("product_db.list_product_categories: DB nicht verfügbar.")
        return []
    create_product_table(conn) # Stellt Tabellenexistenz sicher
    cursor = conn.cursor()
    try:
        cursor.execute("SELECT DISTINCT category FROM products WHERE category IS NOT NULL AND category != '' ORDER BY category COLLATE NOCASE")
        rows = cursor.fetchall()
        return [row['category'] for row in rows] # Direkter Zugriff, da sqlite.Row wie ein Dict ist
    except sqlite3.Error as e:
        print(f"product_db.list_product_categories: SQLite Fehler: {e}")
        traceback.print_exc()
        return []
    finally:
        if conn: conn.close()

if __name__ == "__main__":
    print("--- Testlauf für product_db.py ---")
    # Temporäre In-Memory-Datenbank für den Test
    _original_db_path_pdb = None # Sicherstellen, dass es definiert ist
    # Um eine separate Test-DB zu verwenden, muss DB_PATH in database.py änderbar sein
    # oder hier muss ein Mock für get_db_connection verwendet werden.
    # Für diesen Testlauf wird die Standard-DB (app_data.db) verwendet und danach ggf. bereinigt.

    # Aktuellen Pfad der DB sichern und für den Test eine separate Datei verwenden
    try:
        import database # Importiere das Modul selbst
        _original_db_path_pdb = database.DB_PATH # Greife auf die Variable im Modul zu
        test_db_file = "test_product_db_run.db"
        database.DB_PATH = test_db_file # Ändere den Pfad im Modul
        if os.path.exists(test_db_file):
            os.remove(test_db_file)
        print(f"INFO: Verwende temporäre DB für Test: {test_db_file}")
        # Stelle sicher, dass product_db die neue Verbindung nutzt
        # Dies ist tricky, da get_db_connection_safe_pd beim Import von product_db gesetzt wird.
        # Eine saubere Lösung wäre Dependency Injection für get_db_connection.
        # Workaround: product_db neu laden, nachdem database.DB_PATH geändert wurde (nicht ideal)
        import importlib
        importlib.reload(product_db) # product_db neu laden, damit es die geänderte DB_PATH von database sieht
        get_db_connection_safe_pd = database.get_db_connection # Erneut zuweisen

        conn_test_pdb = get_db_connection_safe_pd()
        if conn_test_pdb:
            create_product_table(conn_test_pdb) # Explizit für die Test-DB aufrufen
            conn_test_pdb.close()
        else:
            print("FEHLER: Konnte keine Test-DB-Verbindung für product_db Test herstellen.")
            exit()

        print("Test-Produktdatenbank initialisiert.")

        # Testdaten
        products_to_add = [
            {"category": "Modul", "model_name": "AlphaSolar 450W", "brand": "AlphaSolar", "price_euro": 180.0, "capacity_w": 450},
            {"category": "Modul", "model_name": "BetaSun 400W", "brand": "BetaSun", "price_euro": 160.0, "capacity_w": 400},
            {"category": "Wechselrichter", "model_name": "PowerMax 5K", "brand": "InvertCorp", "price_euro": 800.0, "power_kw": 5.0},
            {"category": "Batteriespeicher", "model_name": "EnergyCell 10kWh", "brand": "StoreIt", "price_euro": 3500.0, "storage_power_kw": 10.0, "max_cycles": 6000},
            {"category": "Modul", "model_name": "AlphaSolar 450W", "brand": "AlphaSolar", "price_euro": 185.0} # Duplikat Test
        ]

        added_ids = []
        for i, p_data in enumerate(products_to_add):
            print(f"\nVersuche Produkt hinzuzufügen: {p_data.get('model_name')}")
            p_id = product_db.add_product(p_data.copy()) # .copy() um Originaldaten nicht zu verändern
            if p_id:
                added_ids.append(p_id)
                print(f"  -> ERFOLG: ID {p_id}")
            else:
                print(f"  -> FEHLER (oder Duplikat, erwartet für letztes Element)")

        print("\n--- Alle Produkte auflisten ---")
        all_prods = product_db.list_products()
        for p in all_prods: print(f"  ID: {p['id']}, Kat: {p['category']}, Modell: {p['model_name']}, Preis: {p.get('price_euro')}")

        print(f"\n--- Kategorien auflisten ---")
        categories = product_db.list_product_categories()
        print(f"  Gefundene Kategorien: {categories}")

        if added_ids:
            first_id = added_ids[0]
            print(f"\n--- Produkt mit ID {first_id} abrufen ---")
            prod_by_id = product_db.get_product_by_id(first_id)
            if prod_by_id: print(f"  Gefunden: {prod_by_id['model_name']}")
            else: print("  -> NICHT GEFUNDEN")

            print(f"\n--- Produkt 'AlphaSolar 450W' nach Modellname abrufen ---")
            prod_by_name = product_db.get_product_by_model_name("AlphaSolar 450W")
            if prod_by_name: print(f"  Gefunden: ID {prod_by_name['id']}, Marke: {prod_by_name['brand']}")
            else: print("  -> NICHT GEFUNDEN")

            print(f"\n--- Produkt ID {first_id} aktualisieren (Preis und Marke) ---")
            update_data = {"price_euro": 182.50, "brand": "AlphaSolar Inc."}
            success_update = product_db.update_product(first_id, update_data)
            print(f"  Update erfolgreich: {success_update}")
            updated_p = product_db.get_product_by_id(first_id)
            if updated_p: print(f"  Neuer Preis: {updated_p.get('price_euro')}, Neue Marke: {updated_p.get('brand')}")

            print(f"\n--- Produkt ID {first_id} löschen ---")
            success_delete = product_db.delete_product(first_id)
            print(f"  Löschen erfolgreich: {success_delete}")
            deleted_p = product_db.get_product_by_id(first_id)
            if not deleted_p: print(f"  Produkt ID {first_id} nach Löschen nicht mehr gefunden (korrekt).")
            else: print(f"  FEHLER: Produkt ID {first_id} immer noch gefunden!")

    except Exception as e_test_main:
        print(f"Hauptfehler im product_db Testlauf: {e_test_main}")
        traceback.print_exc()
    finally:
        if _original_db_path_pdb and 'database' in locals() : # Zurücksetzen des Pfades im database Modul
             database.DB_PATH = _original_db_path_pdb
             print(f"INFO: DB_PATH im Modul 'database' zurückgesetzt auf: {database.DB_PATH}")
        if 'test_db_file' in locals() and os.path.exists(test_db_file):
            os.remove(test_db_file)
            print(f"INFO: Temporäre Test-DB '{test_db_file}' gelöscht.")
    print("\n--- Testlauf product_db.py beendet ---")