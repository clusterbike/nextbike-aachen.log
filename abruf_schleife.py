"""Nextbike Aachen: fragt den GBFS-Feed einen Lauf lang regelmäßig ab.

- Pro Lauf eine eigene Status-Datei (data/roh/), damit sich überlappende Läufe
  nie in die Quere kommen. Spalten wie bisher:
  zeitstempel, station_id, raeder, freie_plaetze
- Gespeichert wird höchstens ein Snapshot pro 5-Minuten-Fenster (BUCKET_S),
  gemessen am last_updated des Feeds. Überlappende Läufe speichern dadurch
  dieselben Zeitstempel, die sich später sauber zusammenführen lassen.
- Diagnose (data/diagnose/): pro Abfrage Abrufzeit, last_updated, ttl,
  ob neu, ob gespeichert, ob Fehler. Damit lässt sich klären, ob Lücken am
  Feed oder an GitHub liegen.
"""
import csv
import json
import os
import time
from datetime import datetime, timezone

import requests

BASIS = os.environ.get("NEXTBIKE_BASIS",
                       "https://gbfs.nextbike.net/maps/gbfs/v2/nextbike_an/de/")
DAUER_MIN = float(os.environ.get("DAUER_MIN", "50"))     # Länge eines Laufs
INTERVALL_S = float(os.environ.get("INTERVALL_S", "60")) # Abstand der Abfragen
BUCKET_S = int(os.environ.get("BUCKET_S", "300"))        # 1 Snapshot je 5 min

ORDNER = "data"
ROH = os.path.join(ORDNER, "roh")
DIAG = os.path.join(ORDNER, "diagnose")


def laden(name):
    antwort = requests.get(BASIS + name, timeout=30)
    antwort.raise_for_status()
    return antwort.json()


def main():
    os.makedirs(ROH, exist_ok=True)
    os.makedirs(DIAG, exist_ok=True)

    lauf = os.environ.get("GITHUB_RUN_ID", "lokal")
    stempel = datetime.now(timezone.utc).strftime("%Y-%m-%d_%H%M")
    status_pfad = os.path.join(ROH, f"status_{stempel}_{lauf}.csv")
    diag_pfad = os.path.join(DIAG, f"diag_{stempel}_{lauf}.csv")

    # Stationsliste einmal pro Lauf (enthält auch Stationen, die in Stammdaten fehlen)
    try:
        info = laden("station_information.json")
        with open(os.path.join(ORDNER, "station_information.json"), "w",
                  encoding="utf-8") as f:
            json.dump(info["data"], f, ensure_ascii=False, indent=1, sort_keys=True)
    except Exception as e:
        print("station_information fehlgeschlagen:", e)

    ende = time.time() + DAUER_MIN * 60
    letzte_gesehen = None
    letzter_bucket = None

    with open(status_pfad, "w", newline="", encoding="utf-8") as fs, \
         open(diag_pfad, "w", newline="", encoding="utf-8") as fd:
        status_w = csv.writer(fs)
        diag_w = csv.writer(fd)
        status_w.writerow(["zeitstempel", "station_id", "raeder", "freie_plaetze"])
        diag_w.writerow(["abruf_utc", "last_updated", "ttl", "neu", "gespeichert", "fehler"])

        while True:
            abruf = datetime.now(timezone.utc).isoformat(timespec="seconds")
            try:
                status = laden("station_status.json")
                zeit = status["last_updated"]
                ttl = status.get("ttl", "")
                neu = zeit != letzte_gesehen
                bucket = int(zeit // BUCKET_S)
                speichern = neu and bucket != letzter_bucket
                if neu:
                    letzte_gesehen = zeit
                if speichern:
                    for s in status["data"]["stations"]:
                        status_w.writerow([zeit, s["station_id"],
                                           s["num_bikes_available"],
                                           s["num_docks_available"]])
                    letzter_bucket = bucket
                diag_w.writerow([abruf, zeit, ttl, int(neu), int(speichern), ""])
                print(abruf, "last_updated", zeit, "neu" if neu else "-",
                      "gespeichert" if speichern else "")
            except Exception as e:
                diag_w.writerow([abruf, "", "", 0, 0, type(e).__name__])
                print(abruf, "Fehler:", e)
            fs.flush()
            fd.flush()

            if time.time() + INTERVALL_S > ende:
                break
            time.sleep(INTERVALL_S)


if __name__ == "__main__":
    main()
