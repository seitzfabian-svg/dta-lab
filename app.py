import io
import re
from datetime import datetime
import streamlit as st

st.set_page_config(page_title="DTA Lab", layout="wide")

st.title("🚀 DTA Lab – TP4a Prototype (EDIFACT)")

st.write("""
Diese App erzeugt **synthetische EDIFACT-Testdateien** nach den Rahmenregeln aus
**Anlage 4 v63** (UNA optional, UNB/UNZ genau 1×, UNH/UNT pro Nachricht).
""")

st.divider()

# -----------------------------
# Helpers
# -----------------------------
def only_digits(s: str) -> str:
    return re.sub(r"\D+", "", s or "")

def pad5(n: int) -> str:
    """00001..99999 rollover -> 00001"""
    if n <= 0:
        n = 1
    if n > 99999:
        n = 1
    return f"{n:05d}"

def is_valid_ik(ik: str) -> bool:
    ikd = only_digits(ik)
    return len(ikd) == 9

def is_valid_appref(appref: str) -> bool:
    # an..14, aber laut Anlage 4: 11 Stellen Dateiname (z.B. KRHxxxxxxxx)
    # Wir erzwingen 11 Zeichen (A-Z0-9) für V1 (schnell + robust)
    return bool(re.fullmatch(r"[A-Z0-9]{11}", (appref or "").strip().upper()))

def seg(*parts: str) -> str:
    """Build EDIFACT segment with + separators, no empty trimming (keeps ++)."""
    return "+".join(parts) + "'"

def build_interchange(
    include_una: bool,
    sender_ik: str,
    receiver_ik: str,
    interchange_ref_5: str,
    app_ref_11: str,
    msg_ref_5: str,
    msg_type: str,   # e.g. KHIN, ANFM, FEHL ...
    msg_version: str = "16",
    msg_release: str = "000",
    msg_agency: str = "00",
    use_synthetic_payload: bool = True,
) -> str:
    now = datetime.now()
    date_ymd = now.strftime("%y%m%d")   # JJMMTT
    time_hm = now.strftime("%H%M")      # HHMM
    dtm_ccyymmdd = now.strftime("%Y%m%d")

    lines = []

    # (1) UNA optional
    if include_una:
        # UNA:+.? '  -> component=:, element=+, decimal=., release=?, segment='
        lines.append("UNA:+.? '")

    # (2) UNB ... UNZ exactly once
    # UNB+UNOC:3+<sender>+<receiver>+JJMMTT:HHMM+00001++<APPREF>'
    # S005 (password) is optional -> we keep empty: "++"
    unb = seg(
        "UNB",
        "UNOC:3",
        sender_ik,
        receiver_ik,
        f"{date_ymd}:{time_hm}",
        interchange_ref_5,
        "",              # S005 reference/password (leer)
        app_ref_11       # 0026 Anwendungsreferenz (11 Stellen)
    )
    lines.append(unb)

    # (3) One message (V1): UNH ... UNT (one business transaction)
    # UNH+00001+KHIN:16:000:00'
    unh = seg(
        "UNH",
        msg_ref_5,
        f"{msg_type}:{msg_version}:{msg_release}:{msg_agency}"
    )
    lines.append(unh)

    # Minimal payload placeholders (synthetic)
    # These are not the TP4a-specific segments yet; they just make the message non-empty.
    payload_segments = []
    if use_synthetic_payload:
        payload_segments.append(seg("BGM", "00", "SYN-TP4A-0001", "9"))
        payload_segments.append(seg("DTM", f"137:{dtm_ccyymmdd}:102"))

    lines.extend(payload_segments)

    # (UNT) count segments from UNH to UNT inclusive
    # segments included: UNH + payload + UNT
    seg_count = 1 + len(payload_segments) + 1
    unt = seg("UNT", str(seg_count), msg_ref_5)
    lines.append(unt)

    # (UNZ) message count + interchange ref
    unz = seg("UNZ", "1", interchange_ref_5)
    lines.append(unz)

    return "\n".join(lines) + "\n"

# -----------------------------
# UI: Inputs
# -----------------------------
st.subheader("🧪 TP4a – EDIFACT-Testdatei erzeugen")

colA, colB, colC = st.columns(3)
with colA:
    include_una = st.checkbox("UNA am Anfang einfügen (optional)", value=True)
with colB:
    mode = st.selectbox("Verfahren", ["TEST", "ECHT"], index=0)
with colC:
    use_payload = st.checkbox("Minimal-Nutzdatensegmente (BGM/DTM) einfügen", value=True)

col1, col2 = st.columns(2)
with col1:
    sender_ik_in = st.text_input("Absender IK (9-stellig)", value="101234567", max_chars=20)
with col2:
    receiver_ik_in = st.text_input("Empfänger IK (9-stellig)", value="261234567", max_chars=20)

app_ref_in = st.text_input(
    "Anwendungsreferenz (0026) – 11-stelliger Dateiname (z.B. KRHXXXXXXXXX)",
    value="KRHXXXXXXXXX",
    max_chars=14
).strip().upper()

# Nachrichtentypen aus deinem Auszug (UNH 0065)
msg_type = st.selectbox(
    "Nachrichtentyp (UNH 0065)",
    ["AUFN", "VERL", "MBEG", "KHIN", "KANT", "RECH", "ENTL", "AMBO", "ZGUT", "KOUB",
     "ANFM", "ZAHL", "ZAAO", "SAMU", "INKA", "KAIN", "FEHL"],
    index=3
)

st.caption("""
Zählerlogik:
- Datenaustauschreferenz (UNB/UNZ) ist **5-stellig** und wird je Dateiübermittlung **inkrementiert**.
- Zählung für **TEST** und **ECHT** wird getrennt geführt (hier: pro Browser-Session).
""")

# Session state counters (per session, no persistence yet)
if "ctr_test_interchange" not in st.session_state:
    st.session_state.ctr_test_interchange = 1
if "ctr_prod_interchange" not in st.session_state:
    st.session_state.ctr_prod_interchange = 1
if "ctr_msg_ref" not in st.session_state:
    st.session_state.ctr_msg_ref = 1

# Manual override (optional for advanced)
with st.expander("Optional: Zähler manuell setzen (für reproduzierbare Tests)"):
    manual_interchange = st.text_input("Datenaustauschreferenz (5-stellig) override", value="", max_chars=5)
    manual_msg_ref = st.text_input("Nachrichtenreferenz (5-stellig) override", value="", max_chars=5)

def next_interchange_ref() -> str:
    if manual_interchange.strip():
        x = only_digits(manual_interchange)
        return pad5(int(x) if x else 1)

    if mode == "TEST":
        ref = pad5(st.session_state.ctr_test_interchange)
        st.session_state.ctr_test_interchange += 1
        if st.session_state.ctr_test_interchange > 99999:
            st.session_state.ctr_test_interchange = 1
        return ref
    else:
        ref = pad5(st.session_state.ctr_prod_interchange)
        st.session_state.ctr_prod_interchange += 1
        if st.session_state.ctr_prod_interchange > 99999:
            st.session_state.ctr_prod_interchange = 1
        return ref

def next_msg_ref() -> str:
    if manual_msg_ref.strip():
        x = only_digits(manual_msg_ref)
        return pad5(int(x) if x else 1)

    ref = pad5(st.session_state.ctr_msg_ref)
    st.session_state.ctr_msg_ref += 1
    if st.session_state.ctr_msg_ref > 99999:
        st.session_state.ctr_msg_ref = 1
    return ref

# -----------------------------
# Validation (basic)
# -----------------------------
errors = []
sender_ik = only_digits(sender_ik_in)
receiver_ik = only_digits(receiver_ik_in)

if sender_ik_in and not is_valid_ik(sender_ik_in):
    errors.append("Absender IK muss 9-stellig numerisch sein.")
if receiver_ik_in and not is_valid_ik(receiver_ik_in):
    errors.append("Empfänger IK muss 9-stellig numerisch sein.")

if app_ref_in and not is_valid_appref(app_ref_in):
    errors.append("Anwendungsreferenz muss 11 Zeichen A-Z/0-9 sein (z.B. KRHXXXXXXXXX).")

if errors:
    st.error("Bitte korrigiere zuerst:\n- " + "\n- ".join(errors))

# -----------------------------
# Generate
# -----------------------------
if st.button("📄 EDIFACT-Testdatei erzeugen", type="primary", disabled=bool(errors)):
    interchange_ref_5 = next_interchange_ref()
    msg_ref_5 = next_msg_ref()

    edi = build_interchange(
        include_una=include_una,
        sender_ik=sender_ik,
        receiver_ik=receiver_ik,
        interchange_ref_5=interchange_ref_5,
        app_ref_11=app_ref_in,
        msg_ref_5=msg_ref_5,
        msg_type=msg_type,
        use_synthetic_payload=use_payload
    )

    st.success("EDIFACT-Datei erzeugt.")
    st.code(edi, language="text")

    buf = io.BytesIO(edi.encode("utf-8"))
    st.download_button(
        label="⬇️ EDIFACT-Datei herunterladen",
        data=buf,
        file_name=f"TP4a_{mode}_{app_ref_in}_{interchange_ref_5}.edi",
        mime="text/plain"
    )

st.divider()
st.subheader("Status")
st.write(f"TEST-Interchange Zähler (nächster): {pad5(st.session_state.ctr_test_interchange)}")
st.write(f"ECHT-Interchange Zähler (nächster): {pad5(st.session_state.ctr_prod_interchange)}")
st.write(f"Nachrichtenreferenz Zähler (nächster): {pad5(st.session_state.ctr_msg_ref)}")

st.info("""
Nächster Schritt (für „wirklich korrektes TP4a“):
Wir müssen aus Anlage 4 v63 die **TP4a-relevanten Nachrichtentypen** und die **Nutzdatensegmente/Feldinhalte**
für den Geschäftsvorfall übernehmen. Dann ersetzen wir die Platzhalter-Segmente (BGM/DTM) durch die echten.
""")
