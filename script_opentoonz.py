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
# CONFIGURATION & INITIALIZATION
# ---------------------------------------------------------------------------
BLOGGER_BLOG_ID = os.getenv("BLOGGER_BLOG_ID", "5691370053604799116")
TARGET_LABEL = "Opentoonz"
JSON_FILE_PATH = "opentoonz_data.json"

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY") or os.getenv("VITE_GEMINI_API_KEY")
if not GEMINI_API_KEY:
    raise ValueError("⚠️ GEMINI_API_KEY tidak ditemukan di Environment Variables!")

client = genai.Client(api_key=GEMINI_API_KEY)

# Fokus khusus OpenToonz dan Tahoma 2D
SOFTWARES = [
    "opentoonz"
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
        "labels": list(set(labels))  # Hindari label duplikat
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
# MAIN FEEDER FUNCTION
# ---------------------------------------------------------------------------
def feed_tutorials():
    msg = "📚 [TUTORIAL FEEDER] Mencari & Membuat Tutorial OpenToonz (Long-form)..."
    print(f"\n{msg}")
    execution_logs.append(msg)
    
    for sw in SOFTWARES:
        prompt = f"""
Bertindaklah sebagai Senior 2D Animator, Tech Educator, dan Specialist Software {sw} berpengalaman yang ramah, komunikatif, dan pandai menjelaskan teknik animasi serta rigging kompleks secara rinci dan mudah dipahami.

TOLONG BUATKAN 1 PANDUAN TUTORIAL ADVANCE / TINGKAT LANJUT SANGAT DETAIL:
- Topik Utama: Panduan tutorial tingkat lanjut dan mendalam untuk software animasi 2D '{sw}'.
- Fokus Teknik: Pilih 1 fitur unggulan atau alur kerja kompleks paling populer di {sw} (misalnya rigging advanced, efek khusus, cutout animation, frame-by-frame workflow, atau lip-sync automation).
- Target Pembaca: Animator 2D, rigger, ilustrator, Konten Kreator atau pegiat digital yang ingin menguasai {sw} tingkat lanjut.
- Panjang Konten: Wajib berkisar antara 1200 hingga 1700 KATA (Long-form mega tutorial).

ATURAN GAYA PENULISAN & TONE:
1. Panggilan Diri: Gunakan "Saya" atau "Gua" secara konsisten.
2. Panggilan Pembaca: Gunakan "Lu" atau "Sob" / "Bro" agar terasa akrab namun tetap berbobot.
3. Gaya Bahasa: Edukatif, santai, solutif, dan mudah diikuti langkah demi langkah.
4. JANGAN gunakan kata-kata kaku khas AI seperti: "Di era digital yang berkembang pesat ini", "Sangat krusial", "Kesimpulannya", "Dalam dunia animasi yang dinamis".

ATURAN JUDUL & RINGKASAN:
1. Judul: Clickable, to the point, memuat kata kunci spesifik software {sw} (Maksimal 7-12 kata).
2. Excerpt: Ringkasan menarik (2-3 kalimat / 120-150 karakter) yang menjelaskan teknik utama yang akan dipelajari dan manfaat praktisnya.

ATURAN STRUKTUR & FORMAT HTML LENGKAP:
Pada field 'content', wajib menyusun artikel dalam format HTML yang rapi (JANGAN gunakan Markdown raw). Gunakan tag HTML berikut secara tepat:
- Tag <h2> dan <h3> untuk struktur section utama dan sub-fase panduan.
- Tag <p> untuk penjelasan paragraf.
- Tag <ul>, <ol>, dan <li> untuk daftar langkah atau fitur.
- Tag <code> atau <kbd> untuk pintasan keyboard (shortcuts) dan nama tool.
- Tag <blockquote> untuk tips profesional, peringatan penting, atau catatan trik alur kerja.

Struktur Artikel Wajib Memuat:
1. Pendahuluan & Mengapa Teknik Ini Penting (Alasan animator wajib menguasai alur kerja ini di {sw}).
2. Persiapan Workspace & Alat / Toolbox (Setup layer, kanvas, atau persiapan node/vector).
3. Panduan Langkah demi Langkah Detail (Bagi menjadi beberapa fase jelas menggunakan tag <h3>).
4. Tabel / Daftar Pintasan Keyboard (Shortcuts) Penting di {sw}.
5. Troubleshooting / Masalah Umum yang Sering Terjadi + Solusinya.
6. Tips Efisiensi Industri & Penutup.

FORMAT OUTPUT (STRICT JSON HANYA TANPA PEMBUNGKUS TEKS LAIN):
{{
    "title": "Judul Panduan Lengkap dan Menarik di {sw}",
    "softwareId": "{sw}",
    "category": "Advance Tutorial",
    "excerpt": "Ringkasan komprehensif 2-3 kalimat yang menjelaskan teknik mendalam {sw} yang akan dipelajari.",
    "content": "<h2>Pendahuluan</h2><p>Isi panduan lengkap HTML 1200-1700 kata...</p>",
    "source_url": "https://opentoonz.readthedocs.io/"
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
                custom_labels=[sw, "Tutorial Longform", data.get("category", "Tutorial")]
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
    header_msg = f"🚀 === MEMULAI OPENTOONZ & TAHOMA LONG-FORM FEEDER (Waktu: {start_time}) ==="
    print(header_msg)
    execution_logs.append(header_msg)
    execution_logs.append("-" * 60)

    try:
        feed_tutorials()
        
        execution_logs.append("-" * 60)
        footer_msg = "✨ === SELURUH PROSES LONG-FORM FEEDING DISELESAIKAN! ==="
        print(f"\n{footer_msg}")
        execution_logs.append(footer_msg)

    except Exception as e:
        error_msg = f"💥 [CRITICAL ERROR] Terjadi kegagalan sistem: {e}"
        print(f"\n{error_msg}")
        execution_logs.append(error_msg)
