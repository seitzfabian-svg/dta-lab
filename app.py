import io
import re
import zipfile
import random
import string
from datetime import datetime, timedelta, date
import streamlit as st

# -----------------------------
# EDIFACT basics (Anlage 4 / Anlage 1)
# -----------------------------
SEG_TERM = "'"
ELEM = "+"
COMP = ":"

ALL_MSG_TYPES = [
    "AUFN", "VERL", "MBEG", "KHIN", "KANT", "RECH", "ENTL", "AMBO", "ZGUT", "KOUB",
    "ANFM", "ZAHL", "ZAAO", "SAMU", "INKA", "KAIN", "FEHL"
]

# UNH S009 Beispiel: 'AUFN:16:000:00' (Anlage 4) :contentReference[oaicite:2]{index=2}
MSG_VERSION = "16"
MSG_RELEASE = "000"
MSG_AGENCY = "00"

st.set_page_config(page_title="DTA Lab – TP4a EDIFACT Generator", layout="wide")
st.title("🚀 DTA Lab – TP4a EDIFACT Generator (V3)")
st.caption("AUFN ist jetzt inhaltlich nach Anlage 1 befüllt (synthetisch). Alle anderen Typen bleiben vorerst generisch/Platzhalter.")

st.divider()

# -----------------------------
# Helpers
# -----------------------------
def only_digits(s: str) -> str:
    return re.sub(r"\D+", "", s or "")

def pad5(n: int) -> str:
    n = int(n)
    if n <= 0:
        n = 1
    if n > 99999:
        n = 1
    return f"{n:05d}"

def pad2(n: int) -> str:
    n = int(n)
    if n <= 0:
        n = 1
    if n > 99:
        n = 1
    return f"{n:02d}"

def seg(*parts: str) -> str:
    return ELEM.join(parts) + SEG_TERM

def yymmdd_hhmm(now: datetime):
    return now.strftime("%y%m%d"), now.strftime("%H%M")

def rand_digits(n: int) -> str:
    return "".join(random.choice(string.digits) for _ in range(n))

def rand_upper(n: int) -> str:
    return "".join(random.choice(string.ascii_uppercase) for _ in range(n))

def rand_upper_alnum(n: int) -> str:
    alphabet = string.ascii_uppercase + string.digits
    return "".join(random.choice(alphabet) for _ in range(n))

def rand_date(start: date, end: date) -> date:
    delta = (end - start).days
    return start + timedelta(days=random.randint(0, max(delta, 0)))

def make_appref_11(prefix="KRH") -> str:
    # Anlage 4: 0026 Anwendungsreferenz = 11 Stellen Dateiname (Beispiel KRHxxxxxxxx) :contentReference[oaicite:3]{index=3}
    return (prefix + rand_upper_alnum(8))[:11].upper()

def rand_gender() -> str:
    return random.choice(["m", "w", "d"])

def rand_icd10() -> str:
    # synthetische ICD-ähnliche Diagnose, z.B. M50.8 (wie Beispiel) :contentReference[oaicite:4]{index=4}
    letter = random.choice(string.ascii_uppercase)
    return f"{letter}{random.randint(0,99):02d}.{random.randint(0,9)}"

# -----------------------------
# AUFN (Anlage 1) – Segment Builder
# Reihenfolge im Beispiel: FKT, INV, NAD, DPV, AUF, EAD :contentReference[oaicite:5]{index=5}
# -----------------------------
def build_fkt(process_code: str, laufnr2: str, sender_ik: str, receiver_ik: str) -> str:
    # FKT+10+01+123456789+987654321' :contentReference[oaicite:6]{index=6}
    return seg("FKT", process_code, laufnr2, sender_ik, receiver_ik)

def build_inv_aufn(kvnr12: str, versichertenart: str, besonderer_personenkreis: str, dmp: str, gueltigkeit_kk: str, kh_kennz: str) -> str:
    # INV+123456789012+1+04+01+2312+A95-12345' :contentReference[oaicite:7]{index=7}
    return seg("INV", kvnr12, versichertenart, besonderer_personenkreis, dmp, gueltigkeit_kk, kh_kennz)

def build_nad(nachname: str, vorname: str, geschlecht: str, gebdat_yyyymmdd: str) -> str:
    # NAD+Meier+Hugo+m+20030101' :contentReference[oaicite:8]{index=8}
    return seg("NAD", nachname, vorname, geschlecht, gebdat_yyyymmdd)

def build_dpv(jahr: str) -> str:
    # DPV+2023' :contentReference[oaicite:9]{index=9}
    return seg("DPV", jahr)

def build_auf(aufnahmedatum: str, aufnahmezeit_hhmm: str, aufnahmegrund: str, fachabteilung: str, vorauss_entlass: str, einweiser_ik: str) -> str:
    # Beispiel aus Anlage 1:
    # AUF+20231001+1120+0101+0700+20231009+++123456789' :contentReference[oaicite:10]{index=10}
    # Wir bilden die Struktur so nach, inkl. der drei leeren Elemente vor der letzten IK ( "+++" ).
    return seg("AUF", aufnahmedatum, aufnahmezeit_hhmm, aufnahmegrund, fachabteilung, vorauss_entlass, "", "", einweiser_ik)

def build_ead(aufnahmediagnose: str) -> str:
    # EAD+M50.8:' :contentReference[oaicite:11]{index=11}
    return seg("EAD", f"{aufnahmediagnose}:")

# -----------------------------
# Generic placeholder payload (für alle außer AUFN erstmal)
# -----------------------------
def build_generic_payload(msg_type: str, sender_ik: str, receiver_ik: str, process_code: str, laufnr2: str) -> list[str]:
    now = datetime.now()
    dtm_ccyymmdd = now.strftime("%Y%m%d")
    business_ref = f"SYN-{msg_type}-{rand_upper_alnum(6)}"
    case_no = f"FALL-{rand_digits(5)}"
    kvnr = rand_digits(12)

    payload = []
    payload.append(build_fkt(process_code, laufnr2, sender_ik, receiver_ik))
    payload.append(seg("BGM", "00", business_ref, "9"))
    payload.append(seg("DTM", f"137:{dtm_ccyymmdd}:102"))
    payload.append(seg("ZSG", msg_type, sender_ik, receiver_ik, case_no, kvnr))  # Platzhalter
    return payload

def build_aufn_payload(sender_ik: str, receiver_ik: str, process_code: str, laufnr2: str) -> list[str]:
    # Synthetische, plausible Inhalte – ohne reale Daten
    today = date.today()
    geb = rand_date(date(today.year - 80, 1, 1), date(today.year - 1, 12, 31))
    aufnahme = rand_date(date(today.year - 1, 1, 1), today)
    entlass = aufnahme + timedelta(days=random.randint(1, 14))

    kvnr12 = rand_digits(12)
    versichertenart = "1"
    besonderer_personenkreis = random.choice(["00", "04", "09"])
    dmp = random.choice(["00", "01", "02"])
    gueltigkeit_kk = f"{random.randint(1,12):02d}{str(today.year)[-2:]}"  # MMJJ wie 2312 im Beispiel
    kh_kennz = f"{random.choice(['A','B','C'])}{random.randint(10,99)}-{rand_digits(5)}"

    nachname = random.choice(["Meier", "Müller", "Schmidt", "Wagner", "Fischer"])
    vorname = random.choice(["Hugo", "Lena", "Mia", "Paul", "Noah"])
    geschlecht = rand_gender()
    gebdat = geb.strftime("%Y%m%d")

    dpv_jahr = str(today.year)

    aufnahmezeit = f"{random.randint(0,23):02d}{random.randint(0,59):02d}"
    aufnahmegrund = "0101"
    fachabteilung = random.choice(["0700", "0100", "0200", "1100"])
    vorauss_entlass = entlass.strftime("%Y%m%d")
    einweiser_ik = sender_ik  # synthetisch: wir nehmen Sender-IK

    diag = rand_icd10()

    payload = [
        build_fkt(process_code, laufnr2, sender_ik, receiver_ik),
        build_inv_aufn(kvnr12, versichertenart, besonderer_personenkreis, dmp, gueltigkeit_kk, kh_kennz),
        build_nad(nachname, vorname, geschlecht, gebdat),
        build_dpv(dpv_jahr),
        build_auf(aufnahme.strftime("%Y%m%d"), aufnahmezeit, aufnahmegrund, fachabteilung, vorauss_entlass, einweiser_ik),
        build_ead(diag),
    ]
    return payload

# -----------------------------
# EDIFACT file builder
# -----------------------------
def build_edifact_file(
    include_una: bool,
    sender_ik: str,
    receiver_ik: str,
    interchange_ref_5: str,
    app_ref_11: str,
    msg_ref_5: str,
    msg_type: str,
    process_code: str,
    laufnr2: str,
):
    now = datetime.now()
    d, t = yymmdd_hhmm(now)

    lines = []
    if include_una:
        lines.append("UNA:+.? '")

    # UNB Pflichtfelder (Anlage 4) :contentReference[oaicite:12]{index=12}
    lines.append(seg("UNB", "UNOC:3", sender_ik, receiver_ik, f"{d}:{t}", interchange_ref_5, "", app_ref_11))

    # UNH (Anlage 4) :contentReference[oaicite:13]{index=13}
    lines.append(seg("UNH", msg_ref_5, f"{msg_type}:{MSG_VERSION}:{MSG_RELEASE}:{MSG_AGENCY}"))

    # Payload
    if msg_type == "AUFN":
        payload = build_aufn_payload(sender_ik, receiver_ik, process_code, laufnr2)  # Anlage 1 AUFN :contentReference[oaicite:14]{index=14}
    else:
        payload = build_generic_payload(msg_type, sender_ik, receiver_ik, process_code, laufnr2)

    lines.extend(payload)

    # UNT: Anzahl Segmente von UNH bis UNT inkl. (Anlage 4) :contentReference[oaicite:15]{index=15}
    seg_count = 1 + len(payload) + 1
    lines.append(seg("UNT", str(seg_count), msg_ref_5))

    # UNZ: Anzahl Nachrichten + Ref wie UNB (Anlage 4) :contentReference[oaicite:16]{index=16}
    lines.append(seg("UNZ", "1", interchange_ref_5))

    return "\n".join(lines) + "\n"

# -----------------------------
# UI
# -----------------------------
st.subheader("1) Einstellungen")

col1, col2, col3 = st.columns(3)
with col1:
    include_una = st.checkbox("UNA am Anfang einfügen (optional)", value=True)
with col2:
    mode = st.selectbox("Verfahren", ["TEST", "ECHT"], index=0)
with col3:
    msg_type = st.selectbox("Nachrichtentyp (UNH 0065)", ALL_MSG_TYPES, index=0)

col4, col5 = st.columns(2)
with col4:
    sender_ik_in = st.text_input("Absender IK (9-stellig)", value="123456789", max_chars=20)
with col5:
    receiver_ik_in = st.text_input("Empfänger IK (9-stellig)", value="987654321", max_chars=20)

col6, col7, col8 = st.columns(3)
with col6:
    process_code = st.text_input("FKT Verarbeitungskennzeichen", value="10", max_chars=2)
with col7:
    laufnr_start = st.number_input("FKT lfd. Nr. Start (01..99)", min_value=1, max_value=99, value=1, step=1)
with col8:
    auto_appref = st.checkbox("Dateiname (0026) automatisch generieren", value=True)

app_ref_in = st.text_input("Anwendungsreferenz (0026) – 11-stellig", value="KRHXXXXXXXXX", max_chars=14).strip().upper()

st.divider()
st.subheader("2) Testdaten-Generator (Batch)")

colA, colB, colC = st.columns(3)
with colA:
    batch_n = st.number_input("Anzahl Dateien", min_value=1, max_value=500, value=10, step=1)
with colB:
    start_ref = st.number_input("Start Dateinummer (00001..99999)", min_value=1, max_value=99999, value=1, step=1)
with colC:
    msg_ref_start = st.number_input("Start Nachrichtenref (00001..99999)", min_value=1, max_value=99999, value=1, step=1)

# Validation
errors = []
sender_ik = only_digits(sender_ik_in)
receiver_ik = only_digits(receiver_ik_in)
if len(sender_ik) != 9:
    errors.append("Absender IK muss 9-stellig numerisch sein.")
if len(receiver_ik) != 9:
    errors.append("Empfänger IK muss 9-stellig numerisch sein.")
if not re.fullmatch(r"\d{2}", process_code):
    errors.append("FKT Verarbeitungskennzeichen muss 2-stellig sein (z.B. 10).")
if not auto_appref and not re.fullmatch(r"[A-Z0-9]{11}", app_ref_in or ""):
    errors.append("Anwendungsreferenz muss 11 Zeichen A-Z/0-9 sein (oder Auto aktivieren).")

if errors:
    st.error("Bitte korrigiere:\n- " + "\n- ".join(errors))

st.divider()
st.subheader("3) Erzeugen & Download")

colX, colY = st.columns(2)

with colX:
    if st.button("📄 Einzeldatei erzeugen", type="primary", disabled=bool(errors)):
        interchange_ref_5 = pad5(start_ref)
        msg_ref_5 = pad5(msg_ref_start)
        laufnr2 = pad2(laufnr_start)

        app_ref_11 = make_appref_11() if auto_appref else app_ref_in

        edi = build_edifact_file(
            include_una=include_una,
            sender_ik=sender_ik,
            receiver_ik=receiver_ik,
            interchange_ref_5=interchange_ref_5,
            app_ref_11=app_ref_11,
            msg_ref_5=msg_ref_5,
            msg_type=msg_type,
            process_code=process_code,
            laufnr2=laufnr2
        )

        st.success("Datei erzeugt.")
        st.code(edi, language="text")
        st.download_button(
            label="⬇️ Download (.edi)",
            data=edi.encode("utf-8"),
            file_name=f"TP4a_{mode}_{msg_type}_{app_ref_11}_{interchange_ref_5}.edi",
            mime="text/plain"
        )

with colY:
    if st.button("🗂️ Batch erzeugen (ZIP)", disabled=bool(errors)):
        zip_buf = io.BytesIO()
        with zipfile.ZipFile(zip_buf, "w", zipfile.ZIP_DEFLATED) as zf:
            for i in range(int(batch_n)):
                interchange_ref_5 = pad5(int(start_ref) + i)
                msg_ref_5 = pad5(int(msg_ref_start) + i)
                laufnr2 = pad2(int(laufnr_start) + i)

                app_ref_11 = make_appref_11() if auto_appref else app_ref_in

                edi = build_edifact_file(
                    include_una=include_una,
                    sender_ik=sender_ik,
                    receiver_ik=receiver_ik,
                    interchange_ref_5=interchange_ref_5,
                    app_ref_11=app_ref_11,
                    msg_ref_5=msg_ref_5,
                    msg_type=msg_type,
                    process_code=process_code,
                    laufnr2=laufnr2
                )

                fname = f"TP4a_{mode}_{msg_type}_{app_ref_11}_{interchange_ref_5}.edi"
                zf.writestr(fname, edi)

        zip_buf.seek(0)
        st.success(f"Batch erzeugt: {batch_n} Dateien als ZIP.")
        st.download_button(
            label="⬇️ ZIP herunterladen",
            data=zip_buf,
            file_name=f"TP4a_{mode}_{msg_type}_batch_{pad5(start_ref)}_{pad5(int(start_ref)+int(batch_n)-1)}.zip",
            mime="application/zip"
        )

st.divider()
st.info("""
AUFN ist jetzt strukturell nach Anlage 1 umgesetzt (FKT/INV/NAD/DPV/AUF/EAD).
Nächster Schritt: AUFN-Validierung (Pflicht/Kann je Feld) + Fehlerszenarien-Generator.
""")
