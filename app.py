import io
import re
import zipfile
import random
import string
from datetime import datetime, timedelta, date
import streamlit as st

# ============================================================
# EDIFACT GRUNDLAGEN (Anlage 4 v63)
# ============================================================
SEG_TERM = "'"
ELEM = "+"
COMP = ":"

MSG_VERSION = "16"
MSG_RELEASE = "000"
MSG_AGENCY = "00"

ALL_MSG_TYPES = [
    "AUFN", "VERL", "MBEG", "KHIN", "KANT", "RECH", "ENTL", "AMBO",
    "ZGUT", "KOUB", "ANFM", "ZAHL", "ZAAO", "SAMU", "INKA", "KAIN", "FEHL"
]

# ============================================================
# HILFSFUNKTIONEN
# ============================================================
def seg(*parts):
    return ELEM.join(parts) + SEG_TERM

def only_digits(s):
    return re.sub(r"\D+", "", s or "")

def pad5(n):
    n = int(n)
    return f"{((n - 1) % 99999) + 1:05d}"

def pad2(n):
    n = int(n)
    return f"{((n - 1) % 99) + 1:02d}"

def rand_digits(n):
    return "".join(random.choice(string.digits) for _ in range(n))

def rand_upper(n):
    return "".join(random.choice(string.ascii_uppercase) for _ in range(n))

def rand_gender():
    return random.choice(["m", "w", "d"])

def rand_icd10():
    return f"{random.choice(string.ascii_uppercase)}{random.randint(0,99):02d}.{random.randint(0,9)}"

def make_appref():
    return f"KRH{rand_upper(8)}"[:11]

# ============================================================
# FEHLERSZENARIEN
# ============================================================
def apply_error_scenarios(seed, scenarios):
    s = dict(seed)

    if "KVNR_UNGUELTIG" in scenarios:
        s["kvnr"] = "ABC123"

    if "ENTLASS_VOR_AUFNAHME" in scenarios:
        a = datetime.strptime(s["aufnahme"], "%Y%m%d").date()
        s["entlass"] = (a - timedelta(days=1)).strftime("%Y%m%d")

    if "FACHABT_LEER" in scenarios:
        s["fachabteilung"] = ""

    if "DIAG_UNGUELTIG" in scenarios:
        s["diag"] = "1234"

    if "AUFNAHMEZEIT_UNGUELTIG" in scenarios:
        s["aufnahmezeit"] = "2965"

    return s

# ============================================================
# AUFN – NUTZDATENSEGMENTE (ANLAGE 1)
# ============================================================
def build_aufn_payload(sender_ik, receiver_ik, process_code, laufnr, scenarios):
    today = date.today()
    geb = date(today.year - random.randint(18,80), random.randint(1,12), random.randint(1,28))
    aufnahme = today - timedelta(days=random.randint(0,30))
    entlass = aufnahme + timedelta(days=random.randint(1,10))

    seed = {
        "kvnr": rand_digits(12),
        "versichertenart": "1",
        "bpk": "00",
        "dmp": "01",
        "kk_gueltig": f"{random.randint(1,12):02d}{str(today.year)[-2:]}",
        "kh_kennz": f"A{random.randint(10,99)}-{rand_digits(5)}",
        "nachname": random.choice(["Meier", "Schmidt", "Müller"]),
        "vorname": random.choice(["Hugo", "Lena", "Paul"]),
        "geschlecht": rand_gender(),
        "gebdat": geb.strftime("%Y%m%d"),
        "dpv": str(today.year),
        "aufnahme": aufnahme.strftime("%Y%m%d"),
        "aufnahmezeit": f"{random.randint(0,23):02d}{random.randint(0,59):02d}",
        "aufnahmegrund": "0101",
        "fachabteilung": random.choice(["0700","0100","0200"]),
        "entlass": entlass.strftime("%Y%m%d"),
        "einweiser": sender_ik,
        "diag": rand_icd10()
    }

    seed = apply_error_scenarios(seed, scenarios)

    payload = [
        seg("FKT", process_code, laufnr, sender_ik, receiver_ik),
        seg("INV", seed["kvnr"], seed["versichertenart"], seed["bpk"], seed["dmp"], seed["kk_gueltig"], seed["kh_kennz"]),
        seg("NAD", seed["nachname"], seed["vorname"], seed["geschlecht"], seed["gebdat"]),
        seg("DPV", seed["dpv"]),
        seg("AUF", seed["aufnahme"], seed["aufnahmezeit"], seed["aufnahmegrund"],
            seed["fachabteilung"], seed["entlass"], "", "", seed["einweiser"]),
        seg("EAD", f"{seed['diag']}:")
    ]
    return payload

# ============================================================
# EDIFACT DATEI
# ============================================================
def build_edifact(msg_type, scenarios, start_ref, msg_ref, laufnr, sender_ik, receiver_ik, include_una):
    now = datetime.now()
    date6 = now.strftime("%y%m%d")
    time4 = now.strftime("%H%M")
    appref = make_appref()
    ref5 = pad5(start_ref)

    lines = []
    if include_una:
        lines.append("UNA:+.? '")

    lines.append(seg("UNB", "UNOC:3", sender_ik, receiver_ik, f"{date6}:{time4}", ref5, "", appref))
    lines.append(seg("UNH", msg_ref, f"{msg_type}:{MSG_VERSION}:{MSG_RELEASE}:{MSG_AGENCY}"))

    if msg_type == "AUFN":
        payload = build_aufn_payload(sender_ik, receiver_ik, "10", laufnr, scenarios)
    else:
        payload = [
            seg("FKT", "10", laufnr, sender_ik, receiver_ik),
            seg("ZSG", msg_type, "SYNTHETISCH")
        ]

    lines.extend(payload)
    lines.append(seg("UNT", str(len(payload)+2), msg_ref))
    lines.append(seg("UNZ", "1", ref5))

    return "\n".join(lines)

# ============================================================
# STREAMLIT UI
# ============================================================
st.set_page_config(page_title="DTA Lab – AUFN Generator", layout="wide")
st.title("🚀 DTA Lab – AUFN Testdatei Generator (vollständig)")

sender_ik = only_digits(st.text_input("Absender IK", "123456789"))
receiver_ik = only_digits(st.text_input("Empfänger IK", "987654321"))

msg_type = st.selectbox("Nachrichtentyp", ALL_MSG_TYPES, index=0)
include_una = st.checkbox("UNA verwenden", value=True)

st.subheader("Fehlerszenarien")
error_scenarios = st.multiselect(
    "Gezielt Fehler erzeugen:",
    [
        "KVNR_UNGUELTIG",
        "ENTLASS_VOR_AUFNAHME",
        "FACHABT_LEER",
        "DIAG_UNGUELTIG",
        "AUFNAHMEZEIT_UNGUELTIG"
    ]
)

st.subheader("Testdaten (Batch)")
batch = st.number_input("Anzahl Dateien", 1, 100, 1)

if st.button("🗂️ ZIP erzeugen"):
    zipbuf = io.BytesIO()
    with zipfile.ZipFile(zipbuf, "w") as z:
        for i in range(batch):
            edi = build_edifact(
                msg_type,
                error_scenarios,
                i+1,
                pad5(i+1),
                pad2(i+1),
                sender_ik,
                receiver_ik,
                include_una
            )
            z.writestr(f"{msg_type}_{i+1:03d}.edi", edi)

    zipbuf.seek(0)
    st.download_button("⬇️ ZIP herunterladen", zipbuf, file_name="AUFN_Testdaten.zip")
