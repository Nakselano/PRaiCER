import os

import streamlit as st
import requests
import json
import streamlit.components.v1 as components
import os


st.set_page_config(page_title="PRaiCER", layout="wide")
API_URL = os.getenv("API_URL", "http://localhost:8000")
hide_streamlit_style = """
<style> 
    footer {visibility: hidden; display: none !important;}
    header {visibility: hidden; display: none !important;}
    div[data-testid="stStatusWidget"] {visibility: hidden; display: none !important;}

    div[data-testid="stChatInput"] {
        position: fixed !important;
        bottom: 0 !important;
        left: 0 !important;
        right: 0 !important;
        margin: 0 !important;
        padding: 20px !important;
        z-index: 1000;
        background-color: 
    }

    div[data-testid="stAppViewContainer"] > section:first-child > div:first-child {
        padding-bottom: 120px !important;
    }

    div[data-testid="stVerticalBlock"] {
        padding-bottom: 0px !important;
    }
</style>
"""
st.markdown(hide_streamlit_style, unsafe_allow_html=True)

def scroll_to_bottom():
    js = """
    <script>
        function scroll() {
            var body = window.parent.document.body;
            var height = body.scrollHeight;
            window.parent.scrollTo(0, height);
        }
        setTimeout(scroll, 200);
        setTimeout(scroll, 500); 
    </script>
    """
    components.html(js, height=0, width=0)



if "messages" not in st.session_state:
    st.session_state.messages = [
        {"role": "assistant",
         "content": "Cześć! Znajdź produkt w zakładce 'Wyszukiwarka', a potem pogadajmy o nim tutaj."}
    ]
if "search_results" not in st.session_state:
    st.session_state.search_results = []
if "active_product_name" not in st.session_state:
    st.session_state.active_product_name = None

with st.sidebar:
    st.title("⚙️ Ustawienia")
    provider = st.selectbox("Wybierz Model AI:", ["auto", "local"],
                            help="'auto' używa Gemini/Groq, 'local' nie działa :P")

def render_ai_message(content):
    if content is None:
        return
    if isinstance(content, str) and '"type": "product_report"' in content:
        try:
            start = content.find('{')
            end = content.rfind('}') + 1
            data = json.loads(content[start:end])
            st.subheader(data.get("name", "Produkt"))
            col1, col2 = st.columns([1, 2])
            with col1:
                if data.get("image"):
                    st.image(data["image"], width='stretch')
                st.metric("Najniższa cena", f"{data.get('price')} zł")
            with col2:
                st.markdown(f"📝 {data.get('summary', '')}")
                if data.get("pros"):
                    st.success(f"**Zalety:**\n{data['pros']}")
                if data.get("cons"):
                    st.error(f"**Wady:**\n{data['cons']}")
            if data.get("offers"):
                st.write("🛒 **Dostępne oferty:**")
                cols = st.columns(len(data["offers"]) if len(data["offers"]) < 4 else 3)
                for i, off in enumerate(data["offers"]):
                    with cols[i % len(cols)]:
                        st.link_button(f"{off.get('store')} - {off.get('price')} zł", off.get('link', '#'))
        except Exception as e:
            st.warning(f"Błąd renderowania karty: {e}")
            st.markdown(content)
    else:
        st.markdown(content)

tab_search, tab_chat = st.tabs(["🔍 Wyszukiwarka Produktów", "💬 Czat z Asystentem"])

with tab_search:
    st.header("Znajdź i Przeanalizuj")
    with st.form(key="search_form", border=False):
        col1, col2 = st.columns([4, 1], vertical_alignment="bottom")
        with col1:
            query = st.text_input("Wpisz nazwę produktu:", placeholder="Np. Słuchawki Sony...")
        with col2:
            search_btn = st.form_submit_button("Szukaj", width='stretch')
    if search_btn and query:
        with st.spinner("Przeszukuję sklepy..."):
            try:
                resp = requests.post(f"{API_URL}/search", json={"query": query})
                if resp.status_code == 200:
                    st.session_state.search_results = resp.json().get("results", [])
                else:
                    st.error("Błąd API.")
            except Exception as e:
                st.error(f"Nie można połączyć z backendem: {e}")
    results = st.session_state.search_results
    if results:
        cols = st.columns(4)
        for i, prod in enumerate(results):
            with cols[i % 4]:
                st.markdown(f"""
                <div class="product-card">
                    <img src="{prod['image_url']}" style="height:150px; object-fit:contain; width:100%">
                    <h4>{prod['name'][:40]}...</h4>
                    <p class="price-tag">{prod['price']} zł</p>
                </div>
                """, unsafe_allow_html=True)
                if st.button(f"Analizuj Opinie", key=f"btn_{i}"):
                    with st.spinner(f"Pobieram opinie dla {prod['name']}..."):
                        payload = {
                            "name": prod['name'],
                            "price": prod['price'],
                            "image_url": prod['image_url'],
                            "link": prod['link']
                        }
                        try:
                            r = requests.post(f"{API_URL}/analyze", json=payload)
                            if r.status_code == 200:
                                st.success("Pobrano dane! Przejdź do zakładki CZAT.")
                                st.session_state.active_product_name = prod['name']
                                st.session_state.messages.append({
                                    "role": "assistant",
                                    "content": f"🕵️ Pobrałem dane o **{prod['name']}**. Możesz teraz pytać o wady, zalety czy raty."
                                })
                        except:
                            st.error("Błąd połączenia.")

with tab_chat:
    st.header("Asystent AI")
    for msg in st.session_state.messages:
        with st.chat_message(msg["role"]):
            if msg["role"] == "assistant":
                render_ai_message(msg["content"])
            else:
                st.markdown(msg["content"])
    st.markdown('<div id="end-of-chat"></div>', unsafe_allow_html=True)
    if user_input := st.chat_input("O co chcesz zapytać?", key="chat_input_main"):
        st.session_state.messages.append({"role": "user", "content": user_input})
        with st.chat_message("user"):
            st.markdown(user_input)
        with st.chat_message("assistant"):
            with st.spinner("AI myśli..."):
                try:
                    payload = {
                        "messages": st.session_state.messages,
                        "provider": provider,
                        "active_product_name": st.session_state.active_product_name
                    }
                    resp = requests.post(f"{API_URL}/chat", json=payload)
                    if resp.status_code == 200:
                        data = resp.json()
                        ai_reply = data.get("response", "Błąd odpowiedzi.")
                        render_ai_message(ai_reply)
                        st.session_state.messages.append({"role": "assistant", "content": ai_reply})
                        scroll_to_bottom()
                    else:
                        st.error(f"Błąd API: {resp.status_code}")
                except Exception as e:
                    st.error(f"Błąd sieci: {e}")

    if len(st.session_state.messages) > 1:
        scroll_to_bottom()