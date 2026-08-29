import os
import json
import re
import time
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
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
TARGET_LABEL = "Pojok Animasi"
JSON_FILE_PATH = "animation_data.json"

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY") or os.getenv("VITE_GEMINI_API_KEY")
if not GEMINI_API_KEY:
    raise ValueError("⚠️ GEMINI_API_KEY tidak ditemukan di Environment Variables!")
client = genai.Client(api_key=GEMINI_API_KEY)

SOFTWARES = [
    "opentoonz-tahoma",
    "moho",
    "blender",
    "adobe-animate",
    "toonboom"
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
        print("⚠️ Credentials Google Blogger API tidak lengkap. Skrip akan berjalan tanpa publikasi ke Blogger.")
        return None

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
        print(f"  🚀 [BLOGGER POSTED] Berhasil dipublish! URL: {result.get('url')}")
        return result.get('url')
    except Exception as e:
        print(f"  ❌ [BLOGGER ERROR] Gagal publish ke Blogger: {e}")
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
    """Mengubah teks mentah menjadi format HTML yang bersih untuk Blogger."""
    html = f"<p><strong><em>{excerpt}</em></strong></p><hr/>"
    
    paragraphs = content.split("\n\n")
    for p in paragraphs:
        if p.strip():
            if p.startswith("### ") or p.startswith("## "):
                heading_text = p.replace("### ", "").replace("## ", "").strip()
                html += f"<h3>{heading_text}</h3>"
            else:
                html += f"<p>{p.strip()}</p>"
                
    if source_url and source_url != "-":
        html += f'<br/><p><small>Sumber Referensi: <a href="{source_url}" target="_blank" rel="nofollow">{source_url}</a></small></p>'
        
    return html

def send_email_notification(subject: str, summary_logs: list, contents: list):
    sender_email = os.getenv("SENDER_EMAIL")
    sender_password = os.getenv("SENDER_PASSWORD")
    receiver_email = "bromasterwarrior@gmail.com"

    if not sender_email or not sender_password:
        print("⚠️ [EMAIL] SENDER_EMAIL atau SENDER_PASSWORD tidak ditemukan. Email dilewati.")
        return

    body = "========================================================\n"
    body += "📌 RINGKASAN EKSEKUSI ANIMATION TUTORIAL AUTOFEEDER\n"
    body += "========================================================\n"
    body += "\n".join(summary_logs)
    body += "\n\n" + "="*60 + "\n"
    body += "📚 HASIL TUTORIAL LENGKAP YANG DI-GENERATE GEMINI\n"
    body += "="*60 + "\n\n"

    if contents:
        for idx, item in enumerate(contents, start=1):
            body += f"--------------------------------------------------------\n"
            body += f"[{idx}] TIPE: {item.get('type', 'N/A').upper()}\n"
            body += f"📌 JUDUL    : {item.get('title', '-')}\n"
            if "softwareId" in item:
                body += f"🛠 SOFTWARE : {item.get('softwareId')}\n"
            body += f"🏷 KATEGORI : {item.get('category', '-')}\n"
            body += f"🔗 BLOGGER  : {item.get('blogger_url', 'Belum terpublish')}\n"
            body += f"📝 EXCERPT  :\n{item.get('excerpt', '-')}\n\n"
            body += f"📖 KONTEN LENGKAP :\n{item.get('content', '-')}\n"
            body += f"--------------------------------------------------------\n\n"
    else:
        body += "Tidak ada tutorial yang berhasil di-generate.\n"

    msg = MIMEMultipart()
    msg['From'] = f"Animation Feeder Bot <{sender_email}>"
    msg['To'] = receiver_email
    msg['Subject'] = subject
    msg.attach(MIMEText(body, 'plain', 'utf-8'))

    try:
        server = smtplib.SMTP('smtp.gmail.com', 587)
        server.starttls()
        server.login(sender_email, sender_password)
        server.send_message(msg)
        server.quit()
        print(f"📧 [EMAIL] Laporan + Tutorial Lengkap berhasil dikirim ke {receiver_email}")
    except Exception as e:
        print(f"❌ [EMAIL ERROR] Gagal mengirim email: {e}")

# ---------------------------------------------------------------------------
# MAIN FEEDER FUNCTION
# ---------------------------------------------------------------------------
def feed_tutorials():
    msg = "📚 [TUTORIAL FEEDER] Mencari & Membuat Tutorial Asli..."
    print(f"\n{msg}")
    execution_logs.append(msg)
    
    for sw in SOFTWARES:
        prompt = f"""
        Cari di internet tentang teknik produksi animasi yang asli, berkualitas tinggi, dan terbaru untuk '{sw}'.
        Berdasarkan dokumentasi perangkat lunak resmi atau alur kerja industri animasi, tulis 1 tutorial tertulis yang detail.
        
        INSTRUKSI PENTING:
        1. Seluruh isi konten HARUS ditulis sepenuhnya dalam BAHASA INDONESIA yang jelas dan mudah dipahami.
        2. JANGAN mengulang isi ringkasan/excerpt di dalam isi konten utama (body).
        3. Field 'content' harus berupa tutorial langkah-demi-langkah sebanyak 400-600 kata (Prasyarat, Langkah 1, Langkah 2, Tips Profesional). Gunakan penanda '### Heading' untuk judul langkah.
        4. HANYA keluarkan objek JSON mentah. JANGAN dibungkus dengan teks percakapan apa pun.

        Kembalikan JSON yang sesuai persis dengan skema ini:

        {{
            "title": "Judul Aksi yang Jelas (contoh: Rigging Tingkat Lanjut: Pengaturan Smart Bones di Moho)",
            "softwareId": "{sw}",
            "category": "Rigging & Controls",
            "excerpt": "Ringkasan singkat 2 kalimat tentang apa yang akan dicapai oleh animator.",
            "content": "Panduan tutorial langkah-demi-langkah yang berisi instruksi detail, pintasan keyboard (shortcuts), dan pengaturan keyframe.",
            "source_url": "URL sumber atau referensi dokumentasi utama"
        }}
        """
        try:
            response = client.models.generate_content(
                model="gemini-2.5-flash",
                contents=prompt,
                config=types.GenerateContentConfig(
                    tools=[{"google_search": {}}],
                    temperature=0.3
                )
            )

            data = parse_gemini_json(response.text)
            data["createdAt"] = time.strftime("%Y-%m-%d %H:%M:%S")

            # Format ke HTML & Autopost ke Blogger
            html_body = format_html_content(data.get("excerpt", ""), data.get("content", ""), data.get("source_url", ""))
            blogger_url = post_to_blogger(
                title=data.get("title"),
                html_content=html_body,
                custom_labels=[sw, data.get("category", "Tutorial")]
            )
            
            data["blogger_url"] = blogger_url or "-"
            save_to_local_json(data)
            
            content_copy = dict(data)
            content_copy["type"] = f"Tutorial ({sw})"
            generated_contents.append(content_copy)

            log_item = f"  ✅ [SUKSES] Tutorial '{sw}': {data.get('title')}"
            print(log_item)
            execution_logs.append(log_item)

        except Exception as e:
            log_item = f"  ❌ [ERROR] Gagal menambahkan tutorial '{sw}': {e}"
            print(log_item)
            execution_logs.append(log_item)
            
        time.sleep(12)

# ---------------------------------------------------------------------------
# MAIN EXECUTION
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    start_time = time.strftime("%Y-%m-%d %H:%M:%S")
    header_msg = f"🚀 === MEMULAI ANIMATION TUTORIAL AUTOFEEDER BLOGGER (Waktu: {start_time}) ==="
    print(header_msg)
    execution_logs.append(header_msg)
    execution_logs.append("-" * 60)

    try:
        feed_tutorials()
        
        execution_logs.append("-" * 60)
        footer_msg = "✨ === SELURUH PROSES TUTORIAL FEEDING DISELESAIKAN! ==="
        print(f"\n{footer_msg}")
        execution_logs.append(footer_msg)
        
        send_email_notification(
            subject=f"✅ [TUTORIAL REPORT] Blogger Feeder Generated Content - {time.strftime('%Y-%m-%d %H:%M')}",
            summary_logs=execution_logs,
            contents=generated_contents
        )

    except Exception as e:
        error_msg = f"💥 [CRITICAL ERROR] Terjadi kegagalan sistem: {e}"
        print(f"\n{error_msg}")
        execution_logs.append(error_msg)
        
        send_email_notification(
            subject=f"❌ [FAILED] Blogger Feeder Report - {time.strftime('%Y-%m-%d %H:%M')}",
            summary_logs=execution_logs,
            contents=generated_contents
        )