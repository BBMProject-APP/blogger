import os
import json
import re
import time
from dotenv import load_dotenv
from google import genai
from google.genai import types
from google.oauth2.credentials import Credentials
from google.auth.transport.requests import Request
from googleapiclient.discovery import build

load_dotenv()

# ---------------------------------------------------------------------------
# CONFIGURATION & INITIALIZATION (MOHO)
# ---------------------------------------------------------------------------
BLOGGER_BLOG_ID = os.getenv("BLOGGER_BLOG_ID", "5691370053604799116")
TARGET_LABEL = "Moho"  # Label baru khusus Moho
JSON_FILE_PATH = "moho_data.json"

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY") or os.getenv("VITE_GEMINI_API_KEY")
if not GEMINI_API_KEY:
    raise ValueError("⚠️ GEMINI_API_KEY tidak ditemukan di Environment Variables!")

client = genai.Client(api_key=GEMINI_API_KEY)

# Fokus khusus Moho (Moho Pro / Lost Marble)
SOFTWARES = [
    "moho-animation"
]

execution_logs = []
generated_contents = []

# ---------------------------------------------------------------------------
# HELPER FUNCTIONS
# ---------------------------------------------------------------------------
def get_blogger_service():
    """Melakukan otentikasi OAuth2 dengan Refresh Token ke Blogger API."""
    client_id = os.getenv("GOOGLE_CLIENT_ID")
    client_secret = os.getenv("GOOGLE_CLIENT_SECRET")
    refresh_token = os.getenv("GOOGLE_REFRESH_TOKEN")

    if not all([client_id, client_secret, refresh_token]):
        print("⚠️ Credentials Google Blogger API tidak lengkap. Skrip berjalan tanpa publikasi ke Blogger.")
        return None

    try:
        creds = Credentials(
            None,
            refresh_token=refresh_token,
            token_uri="https://oauth2.googleapis.com/token",
            client_id=client_id,
            client_secret=client_secret
        )
        
        if creds.expired:
            creds.refresh(Request())

        return build('blogger', 'v3', credentials=creds)
    except Exception as e:
        print(f"⚠️ Gagal menghubungkan Blogger Service: {e}")
        return None

def post_to_blogger(title: str, html_content: str, custom_labels: list = None):
    """Menerbitkan artikel ke Blogger API."""
    service = get_blogger_service()
    if not service:
        return None

    labels = [TARGET_LABEL]
    if custom_labels:
        labels.extend(custom_labels)

    body = {
        "kind": "blogger#post",
        "title": title,
        "content": html_content,
        "labels": list(set(labels))
    }

    try:
        posts = service.posts()
        result = posts.insert(blogId=BLOGGER_BLOG_ID, body=body).execute()
        print(f"   🚀 [BLOGGER POSTED] Berhasil dipublish! URL: {result.get('url')}")
        return result.get('url')
    except Exception as e:
        print(f"   ❌ [BLOGGER ERROR] Gagal publish ke Blogger: {e}")
        return None

def parse_gemini_json(raw_text: str) -> dict:
    cleaned_text = re.sub(r"```json\s*|\s*```", "", raw_text).strip()
    return json.loads(cleaned_text)

def save_to_local_json(new_data: dict):
    existing_data = []
    if os.path.exists(JSON_FILE_PATH):
        try:
            with open(JSON_FILE_PATH, "r", encoding="utf-8") as f:
                existing_data = json.load(f)
        except Exception:
            existing_data = []
            
    existing_data.append(new_data)
    
    with open(JSON_FILE_PATH, "w", encoding="utf-8") as f:
        json.dump(existing_data, f, ensure_ascii=False, indent=4)

def format_html_content(excerpt: str, content: str, source_url: str = "") -> str:
    """Mengubah teks mentah menjadi format HTML yang bersih dan rapi untuk Blogger."""
    html = f"<p><strong><em>{excerpt}</em></strong></p><hr/>"
    
    paragraphs = content.split("\n\n")
    for p in paragraphs:
        p_str = p.strip()
        if p_str:
            if p_str.startswith("### "):
                html += f"<h3>{p_str.replace('### ', '')}</h3>"
            elif p_str.startswith("## "):
                html += f"<h2>{p_str.replace('## ', '')}</h2>"
            elif p_str.startswith("- ") or p_str.startswith("* "):
                items = p_str.split("\n")
                html += "<ul>" + "".join([f"<li>{item.replace('- ', '').replace('* ', '')}</li>" for item in items]) + "</ul>"
            else:
                html += f"<p>{p_str}</p>"
                
    if source_url and source_url != "-":
        html += f'<br/><p><small>Sumber Referensi: <a href="{source_url}" target="_blank" rel="nofollow">{source_url}</a></small></p>'
        
    return html

# ---------------------------------------------------------------------------
# MAIN FEEDER FUNCTION (MOHO)
# ---------------------------------------------------------------------------
def feed_tutorials():
    msg = "📚 [TUTORIAL FEEDER] Mencari & Membuat Tutorial Moho Animation (Long-form)..."
    print(f"\n{msg}")
    execution_logs.append(msg)
    
    for sw in SOFTWARES:
        prompt = f"""
        Buatlah 1 panduan tutorial tingkat lanjut yang SANGAT DETAIL dan MENDALAM untuk software animasi 2D 'Moho Pro' (Lost Marble Moho).
        
        SPESIFIKASI KONTEN (PENTING):
        1. Seluruh isi konten HARUS ditulis dalam BAHASA INDONESIA profesional dan mudah dipahami.
        2. Panjang artikel wajib berkisar antara 1200 hingga 1700 KATA (Long-form mega tutorial).
        3. FOKUS FITUR MOHO: Pembahasan harus mendalam terkait fitur khas Moho seperti Smart Bones, Vector Rigging, Vitruvian Bones, Target Bones, Physics, atau Liquid Shapes.
        4. Struktur artikel harus mencakup:
           - Pendahuluan & Mengapa Teknik Ini Penting
           - Persiapan Workspace & Rigging Tools
           - Panduan Langkah demi Langkah Detail (Sub-heading '### Heading' untuk tiap fase)
           - Pintasan Keyboard (Shortcuts) Penting di Moho
           - Troubleshooting / Masalah Rigging & Animasi yang Sering Terjadi
           - Tips Efisiensi Industri & Kesimpulan
        5. HANYA keluarkan objek JSON mentah tanpa teks pembuka/penutup.

        Kembalikan JSON dengan format persis seperti ini:

        {{
            "title": "Judul Panduan Lengkap dan Menarik (contoh: Panduan Komprehensif Smart Bones & Head Turn Rigging di Moho Pro)",
            "softwareId": "Moho Pro",
            "category": "Advance Tutorial",
            "excerpt": "Ringkasan komprehensif 2-3 kalimat yang menjelaskan teknik rigging/animasi Moho yang akan dipelajari.",
            "content": "Isi panduan lengkap 1200-1700 kata dengan pembagian sub-heading '### Heading' dan paragraf yang jelas.",
            "source_url": "https://moho.lostmarble.com/"
        }}
        """
        try:
            response = client.models.generate_content(
                model="gemini-3.6-flash",
                contents=prompt,
                config=types.GenerateContentConfig(
                    temperature=0.4,
                    response_mime_type="application/json"
                )
            )

            data = parse_gemini_json(response.text)
            data["createdAt"] = time.strftime("%Y-%m-%d %H:%M:%S")

            html_body = format_html_content(data.get("excerpt", ""), data.get("content", ""), data.get("source_url", ""))
            blogger_url = post_to_blogger(
                title=data.get("title"),
                html_content=html_body,
                custom_labels=["Moho", "Moho Pro", "Tutorial Longform", data.get("category", "Tutorial")]
            )
            
            data["blogger_url"] = blogger_url or "-"
            save_to_local_json(data)
            
            content_copy = dict(data)
            content_copy["type"] = f"Tutorial Longform ({sw})"
            generated_contents.append(content_copy)

            log_item = f"   ✅ [SUKSES] Mega Tutorial '{sw}': {data.get('title')}"
            print(log_item)
            execution_logs.append(log_item)

        except Exception as e:
            log_item = f"   ❌ [ERROR] Gagal menambahkan tutorial '{sw}': {e}"
            print(log_item)
            execution_logs.append(log_item)
            
        time.sleep(20)

# ---------------------------------------------------------------------------
# MAIN EXECUTION
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    start_time = time.strftime("%Y-%m-%d %H:%M:%S")
    header_msg = f"🚀 === MEMULAI MOHO ANIMATION LONG-FORM FEEDER (Waktu: {start_time}) ==="
    print(header_msg)
    execution_logs.append(header_msg)
    execution_logs.append("-" * 60)

    try:
        feed_tutorials()
        
        execution_logs.append("-" * 60)
        footer_msg = "✨ === SELURUH PROSES MOHO FEEDING DISELESAIKAN! ==="
        print(f"\n{footer_msg}")
        execution_logs.append(footer_msg)

    except Exception as e:
        error_msg = f"💥 [CRITICAL ERROR] Terjadi kegagalan sistem: {e}"
        print(f"\n{error_msg}")
        execution_logs.append(error_msg)