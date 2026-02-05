import streamlit as st
import io
from datetime import datetime

st.set_page_config(
    page_title="DTA Lab",
    layout="wide"
)

st.title("🚀 DTA Lab – TP4a Prototype")

st.write("""
Dies ist die erste, lauffähige Web-App für dein Projekt.

Als Nächstes bauen wir hier:
- 📂 einen Dokumenten-Katalog  
- 🔍 eine TP4a-Volltextsuche  
- 🧪 einen Generator für synthetische Testdateien (➡️ HEUTE)  
""")

st.divider()

# ------------------------------
# MODUL: Synthetische Testdatei
# ------------------------------
st.subheader("🧪 TP4a – Synthetische Testdatei erzeugen")

st.write("""
Klicke auf den Button, um eine **synthetische TP4a-Testdatei** zu erzeugen.  
Die Datei ist **fiktiv**, enthält aber realistische Strukturfelder.
""")

if st.button("📄 Testdatei erzeugen"):
    
    today = datetime.now().strftime("%Y-%m-%d")

    # Beispielhafte, synthetische TP4a-Datei (vereinfachtes XML)
    xml_content = f"""<?xml version="1.0" encoding="UTF-8"?>
<TP4a_Testdatei>
  <Metadaten>
    <Erstellungsdatum>{today}</Erstellungsdatum>
    <Quelle>DTA-Lab Prototype</Quelle>
    <Hinweis>Synthetische Beispieldatei</Hinweis>
  </Metadaten>

  <Krankenhaus>
    <IK>999999999</IK>
    <Name>Beispiel Krankenhaus Musterstadt</Name>
  </Krankenhaus>

  <Fall>
    <Fallnummer>FALL-12345</Fallnummer>
    <Aufnahmedatum>2025-02-01</Aufnahmedatum>
    <Entlassdatum>2025-02-05</Entlassdatum>
    <DRG>T01A</DRG>
  </Fall>
</TP4a_Testdatei>
"""

    # Datei als Download bereitstellen
    file_buffer = io.BytesIO()
    file_buffer.write(xml_content.encode("utf-8"))
    file_buffer.seek(0)

    st.download_button(
        label="⬇️ XML-Datei herunterladen",
        data=file_buffer,
        file_name="tp4a_synthetisch.xml",
        mime="application/xml"
    )

    st.success("Datei wurde erzeugt – du kannst sie jetzt herunterladen.")
