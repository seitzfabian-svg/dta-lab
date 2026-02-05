import streamlit as st

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
- 🧪 einen Generator für synthetische Testdateien
""")

st.divider()

st.subheader("Was funktioniert schon?")
st.markdown("""
- ✔️ Streamlit startet im Browser  
- ✔️ GitHub ist angebunden  
- ✔️ Basis für alles Weitere steht  
""")

st.info("Im nächsten Schritt verbinden wir dieses Repo mit Streamlit Cloud.")
