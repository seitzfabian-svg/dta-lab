import io
import re
import zipfile
import random
import string
from datetime import datetime, timedelta, date
import streamlit as st

# -----------------------------
# EDIFACT basics (Anlage 4 v63)
# -----------------------------
SEG_TERM = "'"
ELEM = "+"
COMP = ":"

ALL_MSG_TYPES = [
    "AUFN", "VERL", "MBEG", "KHIN", "KANT", "RECH", "ENTL", "AMBO", "ZGUT", "KOUB",
    "ANFM", "ZAHL", "ZAAO", "SAMU", "INKA", "KAIN", "FEHL"
]

st.set_page_config(page_title="DTA Lab – TP4a EDIFACT Generator", layout="wide")
st.title("🚀 DTA Lab – TP4a EDIFACT Generator (V2)")
st.caption("Rahmen gemäß Anlage 4 v63: UNA optional, UNB/UNZ genau 1×, UNH/UNT je Nachricht, Segmentzählung in UNT.")

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

def seg(*parts: str) -> str:
    # Keep empty elements by passing "" explicitly
    return ELEM.join(parts) + SEG_TERM

def yymmdd_hhmm(now: datetime):
    return now.strftime("%y%m%d"), now.strftime("%H%M")

def rand_digits(n: int) -> str:
    return "".join(random.choice(string.digits) for _ in range(n))

def rand_upper_alnum(n: int) -> str:
    alphabet = string.ascii_uppercase + string.digits
    return "".join(random.choice(alphabet) for _ in range(n))

def rand_date(start: date, end: date) -> date:
    delta = (end - start).days
    return start + timedelta(days=random.randint(0, max(delta, 0)))

def make_appref_11(prefix="KRH") -> str:
    # 11 Zeichen: z.B. KRH + 8 Zeichen
    return (prefix + rand_upper_alnum(8))[:11].upper()

def build_message_segments(msg_type: str, sender_ik: str, receiver_ik: str, seed: dict):
    """
    V2 = generischer synthetischer Payload:
    - minimal: BGM + DTM
    - plus "TP4a Placeholder" Segment je Nachrichtentyp (ZSG)
    Später ersetzen wir diese Liste durch echte Segment-Tabellen aus Anlage 4.
    """
    now = seed["now"]
    dtm_ccyymmdd = now.strftime("%Y%m%d")
    business_ref = seed["business_ref"]

    segments = []
    segments.append(seg("BGM", "00", business_ref, "9"))
    segments.append(seg("DTM", f"137:{dtm_ccyymmdd}:102"))

    # Platzhalter-Segment: ZSG (synthetisch)
    # Enthält msg_type, Sender/Empfänger, Fall/Referenz – rein für Testzwecke
    segments.append(seg("ZSG", msg_type, sender_ik, receiver_ik, seed["case_no"], seed["kvnr"]))

    return segments

def build_edifact_file(
    include_una: bool,
    sender_ik: str,
    receiver_ik: str,
    interchange_ref_5: str,
    app_ref_11: str,
    msg_ref_5: str,
    msg_type: str,
    version="16",
    release="000",
    agency="00",
):
    now = datetime.now()
    d, t = yymmdd_hhmm(now)

    lines = []
    if include_una:
        lines.append("UNA:+.? '")

    # UNB Pflichtfelder gemäß deinem Auszug
    # UNB+UNOC:3+<sender>+<receiver>+JJMMTT:HHMM+00001++<appref>'
    lines.append(seg("UNB", "UNOC:3", sender_ik, receiver_ik, f"{d}:{t}", interchange_ref_5, "", app_ref_11))

    # UNH
    lines.append(seg("UNH", msg_ref_5, f"{msg_type}:{version}:{release}:{agency}"))

    # Payload (synthetisch, V2)
    seed = {
        "now": now,
        "business_ref": f"SYN-{msg_type}-{rand_upper_alnum(6)}",
        "case_no": f"FALL-{rand_digits(5)}",
        "kvnr": rand_digits(12),
    }
    payload = build_message_segments(msg_type, sender_ik, receiver_ik, seed)
    lines.extend(payload)

    # UNT Segment count: UNH + payload + UNT
    seg_count = 1 + len(payload) + 1
    lines.append(seg("UNT", str(seg_count), msg_ref_5))

    # UNZ: 1 Nachricht + gleiche Interchange-Ref wie UNB(0020)
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
    sender_ik_in = st.text_input("Absender IK (9-stellig)", value="101234567", max_chars=20)
with col5:
    receiver_ik_in = st.text_input("Empfänger IK (9-stellig)", value="261234567", max_chars=20)

st.caption("Hinweis: IK wird hier synthetisch/technisch geprüft (9-stellig numerisch).")

col6, col7 = st.columns(2)
with col6:
    app_ref_in = st.text_input("Anwendungsreferenz (0026) – 11-stellig (z. B. KRHXXXXXXXXX)", value="KRHXXXXXXXXX", max_chars=14).strip().upper()
with col7:
    auto_appref = st.checkbox("Anwendungsreferenz automatisch generieren", value=False)

st.divider()
st.subheader("2) Testdaten-Generator (Batch)")

colA, colB, colC = st.columns(3)
with colA:
    batch_n = st.number_input("Anzahl Dateien", min_value=1, max_value=500, value=10, step=1)
with colB:
    start_ref = st.number_input("Start Dateinummer (00001..99999)", min_value=1, max_value=99999, value=1, step=1)
with colC:
    msg_ref_start = st.number_input("Start Nachrichtenref (00001..99999)", min_value=1, max_value=99999, value=1, step=1)

# Basic validation
errors = []
sender_ik = only_digits(sender_ik_in)
receiver_ik = only_digits(receiver_ik_in)
if len(sender_ik) != 9:
    errors.append("Absender IK muss 9-stellig numerisch sein.")
if len(receiver_ik) != 9:
    errors.append("Empfänger IK muss 9-stellig numerisch sein.")
if not auto_appref and not re.fullmatch(r"[A-Z0-9]{11}", app_ref_in or ""):
    errors.append("Anwendungsreferenz muss 11 Zeichen A-Z/0-9 sein (oder Auto aktivieren).")
if msg_type not in ALL_MSG_TYPES:
    errors.append("Unbekannter Nachrichtentyp.")

if errors:
    st.error("Bitte korrigiere:\n- " + "\n- ".join(errors))

st.divider()
st.subheader("3) Erzeugen & Download")

colX, colY = st.columns(2)

with colX:
    if st.button("📄 Einzeldatei erzeugen", type="primary", disabled=bool(errors)):
        interchange_ref_5 = pad5(start_ref)
        msg_ref_5 = pad5(msg_ref_start)
        app_ref_11 = make_appref_11() if auto_appref else app_ref_in

        edi = build_edifact_file(
            include_una=include_una,
            sender_ik=sender_ik,
            receiver_ik=receiver_ik,
            interchange_ref_5=interchange_ref_5,
            app_ref_11=app_ref_11,
            msg_ref_5=msg_ref_5,
            msg_type=msg_type
        )

        st.success("Einzeldatei erzeugt.")
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
                app_ref_11 = make_appref_11() if auto_appref else app_ref_in

                edi = build_edifact_file(
                    include_una=include_una,
                    sender_ik=sender_ik,
                    receiver_ik=receiver_ik,
                    interchange_ref_5=interchange_ref_5,
                    app_ref_11=app_ref_11,
                    msg_ref_5=msg_ref_5,
                    msg_type=msg_type
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
Nächster Schritt für „wirklich korrekt“ pro Nachrichtentyp:
Bitte gib mir aus Anlage 4 v63 **für 1 Nachrichtentyp** (z. B. AUFN) die Segmentliste + Pflichtfelder (Tabelle/Abschnitt).
Dann ersetzen wir das Platzhalter-Segment ZSG durch die echten Nutzdatensegmente.
""")
