import csv
import json
import os
from datetime import datetime, timezone

import requests

BASIS = "https://gbfs.nextbike.net/maps/gbfs/v2/nextbike_an/de/"
ORDNER = "data"

os.makedirs(ORDNER, exist_ok=True)


def laden(name):
    antwort = requests.get(BASIS + name, timeout=30)
    antwort.raise_for_status()
    return antwort.json()


# 1) Status der Stationen: Räder und freie Plätze, eine Datei pro Tag (UTC)
status = laden("station_status.json")
zeit = status["last_updated"]
tag = datetime.fromtimestamp(zeit, timezone.utc).strftime("%Y-%m-%d")
datei = os.path.join(ORDNER, f"status_{tag}.csv")

bekannte = set()
if os.path.exists(datei):
    with open(datei, newline="", encoding="utf-8") as f:
        bekannte = {zeile[0] for zeile in csv.reader(f) if zeile}

if str(zeit) in bekannte:
    print("schon vorhanden:", zeit)
else:
    neue_datei = not os.path.exists(datei)
    with open(datei, "a", newline="", encoding="utf-8") as f:
        schreiber = csv.writer(f)
        if neue_datei:
            schreiber.writerow(["zeitstempel", "station_id", "raeder", "freie_plaetze"])
        for s in status["data"]["stations"]:
            schreiber.writerow([zeit, s["station_id"],
                                s["num_bikes_available"], s["num_docks_available"]])
    print("gespeichert:", zeit)

# 2) Stationsliste: ändert sich selten, wird nur bei Änderung neu gespeichert
info = laden("station_information.json")
with open(os.path.join(ORDNER, "station_information.json"), "w", encoding="utf-8") as f:
    json.dump(info["data"], f, ensure_ascii=False, indent=1, sort_keys=True)
