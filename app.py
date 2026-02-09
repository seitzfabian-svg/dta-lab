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

MSG_VERSION = "16"
MSG_RELEASE = "000"
MSG_AGENCY = "00"

st.set_page_config(page_title="DTA Experte – Ausbaustufe 1 (Testdatei Generator)", layout="wide")
st.title("🚀 DTA Experte – Ausbaustufe 1 (Testdatei Generator) ")
st.caption(" TP4a-Dateien können erzeugt werden: AUFN/ENTL/RECH sind synthetisch befüllt und konsistent (gleicher Fall). 
Alle anderen Nachrichtentypen werden leer erzeugt (nur FKT).")
st.divider()

# -----------------------------
# Helpers
# -----------------------------
def only_digits(s: str) -> str:
    return re.sub(r"\D+", "", s or "")

def pad5(n: int) -> str:
    n = int(n)
    if n <= 0 or n > 99999:
        n = 1
    return f"{n:05d}"

def pad2(n: int) -> str:
    n = int(n)
    if n <= 0 or n > 99:
        n = 1
    return f"{n:02d}"

def seg(*parts: str) -> str:
    return ELEM.join(parts) + SEG_TERM

def yymmdd_hhmm(now: datetime):
    return now.strftime("%y%m%d"), now.strftime("%H%M")

def rand_digits(n: int, rnd: random.Random | None = None) -> str:
    r = rnd or random
    return "".join(r.choice(string.digits) for _ in range(n))

def rand_upper_alnum(n: int, rnd: random.Random | None = None) -> str:
    r = rnd or random
    alphabet = string.ascii_uppercase + string.digits
    return "".join(r.choice(alphabet) for _ in range(n))

def rand_date(start: date, end: date, rnd: random.Random | None = None) -> date:
    r = rnd or random
    delta = (end - start).days
    return start + timedelta(days=r.randint(0, max(delta, 0)))

def make_appref_11(prefix="KRH") -> str:
    return (prefix + rand_upper_alnum(8))[:11].upper()

def rand_gender(rnd: random.Random) -> str:
    return rnd.choice(["m", "w", "d"])

def rand_icd10(rnd: random.Random) -> str:
    # synthetische ICD-ähnliche Diagnose z.B. M50.8
    letter = rnd.choice(string.ascii_uppercase)
    return f"{letter}{rnd.randint(0,99):02d}.{rnd.randint(0,9)}"

def fmt_amount(amount: float) -> str:
    # EDIFACT nutzt Dezimalzeichen Komma (Anlage 1 Hinweis)
    s = f"{amount:.2f}".replace(".", ",")
    # Kein Tausender-Trennzeichen
    return s

# -----------------------------
# Case-Model (Single Source of Truth für AUFN/ENTL/RECH)
# -----------------------------
def make_case(seed: int, sender_ik: str, receiver_ik: str) -> dict:
    rnd = random.Random(seed)
    today = date.today()

    geb = rand_date(date(today.year - 80, 1, 1), date(today.year - 1, 12, 31), rnd)
    aufnahme = rand_date(date(today.year - 1, 1, 1), today, rnd)
    entlass = aufnahme + timedelta(days=rnd.randint(1, 14))

    versichertenart = "1"
    besonderer_personenkreis = rnd.choice(["00", "04", "09"])
    dmp = rnd.choice(["00", "01", "02"])
    gueltigkeit_kk = f"{rnd.randint(1,12):02d}{str(today.year)[-2:]}"  # MMJJ
    kh_kennz = f"{rnd.choice(['A','B','C'])}{rnd.randint(10,99)}-{rand_digits(5, rnd)}"

    nachname = rnd.choice(["Meier", "Müller", "Schmidt", "Wagner", "Fischer"])
    vorname = rnd.choice(["Hugo", "Lena", "Mia", "Paul", "Noah"])

    fachabteilung = rnd.choice(["0700", "0100", "0200", "1100"])
    aufnahmezeit = f"{rnd.randint(0,23):02d}{rnd.randint(0,59):02d}"
    entlasszeit = f"{rnd.randint(0,23):02d}{rnd.randint(0,59):02d}"

    # RECH: Entgeltpositionen (ENT) + ggf. Zuzahlung (ZLG)
    ent_positions = []
    n_pos = rnd.randint(1, 3)
    for i in range(n_pos):
        entgeltart = f"{rnd.randint(0, 99999999):08d}"   # Schlüssel 4 (an8) – synthetisch 8-stellig
        einzelbetrag = round(rnd.uniform(150.0, 2500.0), 2)
        anzahl = rnd.randint(1, 5)
        ent_positions.append({
            "entgeltart": entgeltart,
            "einzelbetrag": einzelbetrag,
            "von": aufnahme.strftime("%Y%m%d"),
            "bis": entlass.strftime("%Y%m%d"),
            "anzahl": anzahl,
        })

    # Optional Zuzahlung
    zlg_amount = round(rnd.uniform(0.0, 100.0), 2)
    zlg = {
        "amount": zlg_amount,
        "kennz": rnd.choice(["0", "1"])  # Schlüssel 15 – synthetisch
    } if zlg_amount > 0.0 and rnd.random() < 0.6 else None

    # REC-5 = Summe(ENT-2 * ENT-5) ./. ZLG-1 (Hinweis in Anlage 1)
    rec_sum = sum(p["einzelbetrag"] * p["anzahl"] for p in ent_positions)
    if zlg:
        rec_sum = max(0.0, rec_sum - zlg["amount"])
    rec_sum = round(rec_sum, 2)

    # Rechnung
    rechnungsdatum = entlass + timedelta(days=rnd.randint(0, 5))
    rechnungsnummer = f"R{today.year}{rand_digits(8, rnd)}"[:20]
    rechnungsart = rnd.choice(["01", "02"])  # Schlüssel 11 – synthetisch (z.B. 01/02)
    waehrung = "EUR"  # Schlüssel 18

    return {
        "seed": seed,
        "sender_ik": sender_ik,
        "receiver_ik": receiver_ik,

        # INV / NAD
        "kvnr12": rand_digits(12, rnd),
        "versichertenart": versichertenart,
        "besonderer_personenkreis": besonderer_personenkreis,
        "dmp": dmp,
        "gueltigkeit_kk": gueltigkeit_kk,
        "kh_kennz": kh_kennz,
        "nachname": nachname,
        "vorname": vorname,
        "geschlecht": rand_gender(rnd),
        "gebdat": geb.strftime("%Y%m%d"),

        # Aufenthalt
        "aufnahme_datum": aufnahme.strftime("%Y%m%d"),
        "aufnahme_zeit": aufnahmezeit,
        "entlass_datum": entlass.strftime("%Y%m%d"),
        "entlass_zeit": entlasszeit,
        "fachabteilung": fachabteilung,

        # Diagnose
        "dpv_icd": str(today.year),  # ICD-Version (an..6)
        "aufnahmediag": rand_icd10(rnd),
        "hauptdiag": rand_icd10(rnd),
        "nebendiags": [rand_icd10(rnd) for _ in range(rnd.randint(0, 3))],

        # RECH
        "waehrung": waehrung,
        "rechnungsnummer": rechnungsnummer,
        "rechnungsdatum": rechnungsdatum.strftime("%Y%m%d"),
        "rechnungsart": rechnungsart,
        "ent_positions": ent_positions,
        "zlg": zlg,
        "rechnungsbetrag": rec_sum,
    }

# -----------------------------
# Segment Builder (shared)
# -----------------------------
def build_fkt(process_code: str, laufnr2: str, sender_ik: str, receiver_ik: str) -> str:
    return seg("FKT", process_code, laufnr2, sender_ik, receiver_ik)

def build_inv(case: dict) -> str:
    # INV: für AUFN/ENTL/RECH identisch nutzbar (Mindestfelder + KH-Kennz)
    return seg(
        "INV",
        case["kvnr12"],
        case["versichertenart"],
        case["besonderer_personenkreis"],
        case["dmp"],
        case["gueltigkeit_kk"],
        case["kh_kennz"],
    )

def build_nad(case: dict) -> str:
    return seg("NAD", case["nachname"], case["vorname"], case["geschlecht"], case["gebdat"])

def build_dpv_icd(case: dict) -> str:
    # DPV+2025'
    return seg("DPV", case["dpv_icd"])

def build_sta(case: dict) -> str:
    # STA ist bei ENTL und RECH Muss (99x möglich)
    # Standortnummer an9 – synthetisch "001"
    standortnr = "001"
    ende = case["entlass_datum"]
    ende_time = case["entlass_zeit"]
    return seg("STA", standortnr, ende, ende_time)

# -----------------------------
# AUFN (Anlage 1) – Segment Builder (wie bei dir, aber aus Case)
# -----------------------------
def build_auf(aufnahmedatum: str, aufnahmezeit_hhmm: str, aufnahmegrund: str, fachabteilung: str, vorauss_entlass: str, einweiser_ik: str) -> str:
    # AUF+YYYYMMDD+HHMM+0101+0700+YYYYMMDD+++IK'
    return seg("AUF", aufnahmedatum, aufnahmezeit_hhmm, aufnahmegrund, fachabteilung, vorauss_entlass, "", "", einweiser_ik)

def build_ead(aufnahmediagnose: str) -> str:
    return seg("EAD", f"{aufnahmediagnose}:")

def build_aufn_payload(case: dict, process_code: str, laufnr2: str) -> list[str]:
    payload = [
        build_fkt(process_code, laufnr2, case["sender_ik"], case["receiver_ik"]),
        build_inv(case),
        build_nad(case),
        build_dpv_icd(case),
        build_auf(
            case["aufnahme_datum"],
            case["aufnahme_zeit"],
            "0101",
            case["fachabteilung"],
            case["entlass_datum"],   # vorauss. Entlassung = echte Entlassung im synthetischen Modell
            case["sender_ik"],       # Einweiser IK synthetisch = Sender IK
        ),
        build_ead(case["aufnahmediag"]),
    ]
    return payload

# -----------------------------
# ENTL (Anlage 1) – Minimal fachlich korrekt (FKT, INV, NAD, STA, DPV, DAU, ETL, NDG*)
# -----------------------------
def build_dau(case: dict) -> str:
    # DAU+Aufnahmetag+Entlassungstag'
    return seg("DAU", case["aufnahme_datum"], case["entlass_datum"])

def build_etl(case: dict) -> str:
    # ETL: Tag, Uhrzeit, Grund (an3), Fachabteilung, Hauptdiagnose (Datenelementgruppe -> hier "ICD:")
    grund = "001"  # Schlüssel 5 – synthetisch an3
    return seg("ETL", case["entlass_datum"], case["entlass_zeit"], grund, case["fachabteilung"], f"{case['hauptdiag']}:")

def build_ndg(icd: str) -> str:
    return seg("NDG", f"{icd}:")

def build_entl_payload(case: dict, process_code: str, laufnr2: str) -> list[str]:
    # Minimalregeln
    if case["entlass_datum"] < case["aufnahme_datum"]:
        raise ValueError("ENTL: Entlassdatum < Aufnahmedatum")

    payload = [
        build_fkt(process_code, laufnr2, case["sender_ik"], case["receiver_ik"]),
        build_inv(case),
        build_nad(case),
        build_sta(case),
        build_dpv_icd(case),
        build_dau(case),
        build_etl(case),
    ]
    for nd in case["nebendiags"]:
        payload.append(build_ndg(nd))
    return payload

# -----------------------------
# RECH (Anlage 1) – Minimal fachlich korrekt
# Muss u.a.: FKT, INV, NAD, STA, CUX, REC, FAB (>=1), ENT (>=1)
# REC-5 muss Summe(ENT-2*ENT-5) ./. ZLG-1 sein
# -----------------------------
def build_cux(case: dict) -> str:
    # CUX+EUR'
    return seg("CUX", case["waehrung"])

def build_rec(case: dict) -> str:
    # REC Felder (gemäß Anlage 1):
    # 1 Rechnungsnummer (M)
    # 2 Rechnungsdatum (M)
    # 3 Rechnungsart (M)
    # 4 Aufnahmetag (M)
    # 5 Rechnungsbetrag (M)
    # 6 Debitoren-Kontonr (K) -> leer
    # 7 Referenznummer KH (K) -> leer
    # 8 IK KH Zahlungsweg (K) -> leer
    return seg(
        "REC",
        case["rechnungsnummer"],
        case["rechnungsdatum"],
        case["rechnungsart"],
        case["aufnahme_datum"],
        fmt_amount(case["rechnungsbetrag"]),
    )

def build_zlg(case: dict) -> str:
    # ZLG ist Kann, aber wenn vorhanden: Betrag + Kennzeichen
    z = case["zlg"]
    return seg("ZLG", fmt_amount(z["amount"]), z["kennz"])

def build_fab(case: dict) -> str:
    # FAB+0700'
    return seg("FAB", case["fachabteilung"])

def build_ent(pos: dict) -> str:
    # ENT+Entgeltart+Entgeltbetrag+von+bis+anzahl'
    return seg(
        "ENT",
        pos["entgeltart"],
        fmt_amount(pos["einzelbetrag"]),
        pos["von"],
        pos["bis"],
        str(pos["anzahl"]),
    )

def build_rech_payload(case: dict, process_code: str, laufnr2: str) -> list[str]:
    payload = [
        build_fkt(process_code, laufnr2, case["sender_ik"], case["receiver_ik"]),
        build_inv(case),
        build_nad(case),
        build_sta(case),
        build_cux(case),
        build_rec(case),
    ]
    if case["zlg"]:
        payload.append(build_zlg(case))

    # Muss: mind. 1x FAB und 1x ENT
    payload.append(build_fab(case))
    for p in case["ent_positions"]:
        payload.append(build_ent(p))

    return payload

# -----------------------------
# Empty payload for all other message types (minimal: nur FKT)
# -----------------------------
def build_empty_payload(sender_ik: str, receiver_ik: str, process_code: str, laufnr2: str) -> list[str]:
    return [build_fkt(process_code, laufnr2, sender_ik, receiver_ik)]

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

    lines.append(seg("UNB", "UNOC:3", sender_ik, receiver_ik, f"{d}:{t}", interchange_ref_5, "", app_ref_11))
    lines.append(seg("UNH", msg_ref_5, f"{msg_type}:{MSG_VERSION}:{MSG_RELEASE}:{MSG_AGENCY}"))

    # Case-Seed: sorgt dafür, dass AUFN/ENTL/RECH für dieselbe (Interchange,msg_ref) Kombi konsistent sind
    seed = int(interchange_ref_5) * 100000 + int(msg_ref_5)
    case = make_case(seed, sender_ik, receiver_ik)

    if msg_type == "AUFN":
        payload = build_aufn_payload(case, process_code, laufnr2)
    elif msg_type == "ENTL":
        payload = build_entl_payload(case, process_code, laufnr2)
    elif msg_type == "RECH":
        payload = build_rech_payload(case, process_code, laufnr2)
    else:
        payload = build_empty_payload(sender_ik, receiver_ik, process_code, laufnr2)

    lines.extend(payload)

    seg_count = 1 + len(payload) + 1
    lines.append(seg("UNT", str(seg_count), msg_ref_5))
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
Status:
- AUFN / ENTL / RECH: synthetisch befüllt, fachlich plausibel, konsistent über denselben Case-Seed.
- Alle anderen Nachrichtentypen: leer (nur FKT).
Nächster Ausbau:
- Szenario-Generator (AUFN+ENTL+RECH in einem ZIP pro Fall)
- Validierungs-/Fehler-Flags je Nachricht
- Weitere Verfahren schrittweise nachziehen (Case-first Architektur)
""")
