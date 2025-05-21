import os
from prometheus_client import Info
import requests
import random
import time
import re # Dinamik token alımı için eklendi
import sys
import subprocess
from datetime import datetime
from secrets import token_hex
from uuid import uuid4

# --- Otomatik Kurulum Kontrolü ---
def check_and_install_libraries():
    required_libraries = {"requests": "requests", "rich": "rich"}
    missing_libraries = []

    # Standart print ve input kullanarak ilk kontroller
    _print_fallback = lambda *args, **kwargs: print(*args) # Basit print
    _input_fallback = lambda prompt: input(prompt)

    # Check for requests (critical)
    try:
        __import__("requests")
    except ImportError:
        _print_fallback("[!] 'requests' kütüphanesi bulunamadı.")
        install_req = _input_fallback(" 'requests' kütüphanesini kurmak ister misiniz? (e/h): ").lower().strip()
        if install_req == 'e':
            _print_fallback("[*] 'requests' kütüphanesi kuruluyor...")
            try:
                subprocess.check_call([sys.executable, "-m", "pip", "install", "requests"])
                _print_fallback("[✓] 'requests' başarıyla kuruldu. Lütfen scripti yeniden başlatın.")
                exit()
            except Exception as e_install:
                _print_fallback(f"[!] 'requests' kurulurken hata: {e_install}")
                _print_fallback("Lütfen manuel olarak kurun: pip install requests")
                exit()
        else:
            _print_fallback("[!] 'requests' kurulumu atlandı. Script çalışamaz.")
            exit()

    # Check for rich (UI enhancement)
    rich_available = False
    try:
        __import__("rich")
        rich_available = True
    except ImportError:
        _print_fallback("[!] 'rich' kütüphanesi bulunamadı. Gelişmiş kullanıcı arayüzü için kurulması önerilir.")
        install_rich = _input_fallback(" 'rich' kütüphanesini şimdi kurmak ister misiniz? (e/h): ").lower().strip()
        if install_rich == 'e':
            _print_fallback("[*] 'rich' kütüphanesi kuruluyor...")
            try:
                subprocess.check_call([sys.executable, "-m", "pip", "install", "rich"])
                _print_fallback("[✓] 'rich' başarıyla kuruldu. Script yeniden başlatılıyor...")
                # Restart to ensure all rich components are loaded correctly by the script
                os.execv(sys.executable, ['python'] + sys.argv)
            except Exception as e_install:
                _print_fallback(f"[!] 'rich' kurulurken hata: {e_install}")
                _print_fallback("Lütfen manuel olarak kurun: pip install rich. Basit konsol çıktıları kullanılacak.")
        else:
            _print_fallback("[!] 'rich' kurulumu atlandı. Basit konsol çıktıları kullanılacak.")

    global console, Text, Panel, Table, Prompt, IntPrompt
    if rich_available:
        try:
            from rich.console import Console as RichConsole
            from rich.text import Text as RichText
            from rich.panel import Panel as RichPanel
            from rich.table import Table as RichTable
            from rich.prompt import Prompt as RichPrompt, IntPrompt as RichIntPrompt
            console = RichConsole()
            Text, Panel, Table, Prompt, IntPrompt = RichText, RichPanel, RichTable, RichPrompt, RichIntPrompt
        except ImportError: # Should not happen if rich_available is True, but as a safeguard
            rich_available = False # Fallback
            print("[CRITICAL] Rich import edilemedi, fallback kullanılıyor.")

    if not rich_available:
        class FallbackConsole:
            def print(self, *args, **kwargs):
                kwargs.pop('style', None)
                kwargs.pop('justify', None)
                processed_args = [re.sub(r'\[/?[\w\s]+\]', '', str(arg)) for arg in args]
                print(*processed_args)
        console = FallbackConsole()
        # Define fallbacks for other Rich components if necessary, or ensure code handles their absence
        # For simplicity, direct usage of Text, Panel, Table, Prompt will rely on them being Rich objects.
        # If Rich is not there, those specific UI elements might not work as intended without more complex fallbacks.
        # The script relies heavily on Rich, so its absence will significantly degrade UI.
        Text = lambda x, **kwargs: str(x) # Simple fallback
        Panel = lambda x, **kwargs: console.print(str(x)) # Simple fallback
        Table = type('FallbackTable', (), {'add_column': lambda self, *args, **kwargs: None, 'add_row': lambda self, *args, **kwargs: None, '__call__': lambda self, *args, **kwargs: self})
        Prompt = type('FallbackPrompt', (), {'ask': lambda *args, **kwargs: input(args[0] if args else "")})
        IntPrompt = type('FallbackIntPrompt', (), {'ask': lambda *args, **kwargs: int(input(args[0] if args else ""))})


    # Optional: ms4
    try:
        from ms4 import InfoIG
        globals()['InfoIG'] = InfoIG # InfoIG'yi global kapsama ekle
        console.print("[green][✓] 'ms4' kütüphanesi bulundu.[/green]")
    except ImportError:
        console.print("[yellow][!] 'ms4' kütüphanesi bulunamadı. Kullanıcı ID'si otomatik alınamayacak.[/yellow]")
        console.print("[yellow]Kurulum için: pip install ms4[/yellow]")
        globals()['InfoIG'] = None # InfoIG kullanılamaz olarak işaretle

# Initialize console and other Rich components
console, Text, Panel, Table, Prompt, IntPrompt = None, None, None, None, None, None
check_and_install_libraries() # Script başında kütüphaneleri kontrol et

# --- Global Değişkenler ---
current_session_id = None
target_user_id = None
target_username_global = None
global_requests_session = requests.Session()
proxy_list = [] # Proxy listesi
current_proxy = None # Mevcut kullanılan proxy'yi izlemek için

# --- Proxy Fonksiyonları ---
def load_proxies_from_file():
    global proxy_list
    file_path = Prompt.ask("[cyan]Proxy dosyasının yolunu girin (her satırda bir proxy, örn: http://user:pass@host:port)[/cyan]", default="proxies.txt").strip()
    try:
        with open(file_path, 'r') as f:
            loaded_proxies = [line.strip() for line in f if line.strip()]
        if loaded_proxies:
            proxy_list.extend(loaded_proxies)
            # Yinelenenleri kaldır
            proxy_list = sorted(list(set(proxy_list)))
            console.print(f"[green][✓] {len(loaded_proxies)} proxy dosyadan yüklendi. Toplam {len(proxy_list)} proxy mevcut.[/green]")
        else:
            console.print("[yellow][i] Dosyada geçerli proxy bulunamadı veya dosya boş.[/yellow]")
    except FileNotFoundError:
        console.print(f"[bold red][!] Proxy dosyası bulunamadı: {file_path}[/bold red]")
    except Exception as e_proxy_load:
        console.print(f"[bold red][!] Proxy dosyası okunurken hata: {str(e_proxy_load)}[/bold red]")

def add_proxy_manually():
    global proxy_list
    proxy_str = Prompt.ask("[cyan]Eklenecek proxy adresini girin (örn: http://user:pass@host:port veya socks5://host:port)[/cyan]").strip()
    if proxy_str:
        if proxy_str not in proxy_list:
            proxy_list.append(proxy_str)
            console.print(f"[green][✓] Proxy eklendi: {proxy_str}[/green]")
        else:
            console.print("[yellow][i] Bu proxy zaten listede mevcut.[/yellow]")
    else:
        console.print("[bold red][!] Geçersiz proxy formatı.[/bold red]")

def view_proxies():
    if not proxy_list:
        console.print("[yellow][i] Kullanılabilir proxy bulunmuyor.[/yellow]")
        return
    console.print(f"[cyan]--- Mevcut Proxy Listesi ({len(proxy_list)}) ---[/cyan]")
    for i, p_str in enumerate(proxy_list):
        console.print(f"[white]{i+1}. {p_str}[/white]")
    console.print("[cyan]---------------------------[/cyan]")

def clear_proxies():
    global proxy_list
    if proxy_list:
        confirm_clear = Prompt.ask(f"[yellow]Tüm ({len(proxy_list)}) proxy'yi silmek istediğinizden emin misiniz? (e/h)[/yellow]", choices=["e", "h"], default="h")
        if confirm_clear.lower() == 'e':
            proxy_list = []
            console.print("[green][✓] Tüm proxy'ler silindi.[/green]")
        else:
            console.print("[yellow][i] Proxy silme işlemi iptal edildi.[/yellow]")
    else:
        console.print("[yellow][i] Silinecek proxy bulunmuyor.[/yellow]")

def load_proxies_from_webshare():
    global proxy_list
    # Kullanıcıya API URL'sini sormak yerine doğrudan kullanabiliriz veya konfigüre edilebilir hale getirebiliriz.
    # Şimdilik doğrudan URL'yi kullanalım.
    webshare_api_url = "https://proxy.webshare.io/api/v2/proxy/list/download/utfxkwypexmqhigckkissgpwnbccppsbeprmzwwr/-/any/username/direct/-/"
    console.print(f"[cyan][*] Webshare API'sinden proxy listesi indiriliyor: {webshare_api_url}[/cyan]")
    try:
        response = requests.get(webshare_api_url, timeout=20)
        response.raise_for_status() # HTTP hatalarını kontrol et
        
        # API'den gelen yanıt metin formatında, her satır bir proxy
        loaded_proxies = [line.strip() for line in response.text.splitlines() if line.strip()]
        
        if loaded_proxies:
            # Webshare genellikle user:pass@host:port formatında verir, bu format script için uygun.
            # Eğer farklı bir formatta geliyorsa, burada parse etmek gerekebilir.
            
            # Sadece yeni proxy'leri ekle
            newly_added_count = 0
            for proxy_str in loaded_proxies:
                if proxy_str not in proxy_list:
                    proxy_list.append(proxy_str)
                    newly_added_count +=1
            
            if newly_added_count > 0:
                proxy_list = sorted(list(set(proxy_list))) # Yinelenenleri kaldır ve sırala
                console.print(f"[green][✓] {newly_added_count} yeni proxy Webshare API'sinden eklendi. Toplam {len(proxy_list)} proxy mevcut.[/green]")
            else:
                console.print("[yellow][i] Webshare API'sinden gelen tüm proxy'ler zaten listede mevcut.[/yellow]")
        else:
            console.print("[yellow][i] Webshare API'sinden geçerli proxy alınamadı veya yanıt boş.[/yellow]")
            
    except requests.exceptions.RequestException as e: # Catches Timeout, HTTPError, and other request-related errors
        console.print(f"[bold red][!] Webshare API'sine bağlanırken hata: {str(e)}[/bold red]")
    except Exception as e_general:
        console.print(f"[bold red][!] Webshare proxy'leri işlenirken beklenmedik bir hata oluştu: {str(e_general)}[/bold red]")

def get_random_proxy_dict():
    """Kullanılacak rastgele bir proxy'yi dict formatında döndürür."""
    global current_proxy
    if not proxy_list:
        current_proxy = None
        return None
    
    chosen_proxy_str = random.choice(proxy_list)
    current_proxy = chosen_proxy_str # İzleme için ata
    # Proxy formatını http/https ve socks5 için ayır
    # Basit bir ayrım, daha karmaşık URL'ler için urllib.parse kullanılabilir
    if "socks5" in chosen_proxy_str.lower():
        return {'http': chosen_proxy_str, 'https': chosen_proxy_str} # socks5 için hem http hem https'e aynı proxy
    else: # http/https proxy
        return {'http': chosen_proxy_str, 'https': chosen_proxy_str}


def update_session_proxies(session_obj):
    """Verilen session objesinin proxy ayarlarını günceller."""
    proxy_dict = get_random_proxy_dict()
    if proxy_dict:
        session_obj.proxies.update(proxy_dict)
        # console.print(f"[cyan][i] Session için proxy ayarlandı: {current_proxy}[/cyan]") # Çok fazla log olmaması için kapatıldı
    elif session_obj.proxies: # Proxy listesi boşaldıysa session'daki proxy'leri temizle
        session_obj.proxies.clear() # Proxy yoksa temizle
        current_proxy = None # current_proxy'yi de temizle

# --- Başlık ve Banner Fonksiyonları ---
def display_main_title():
    title_text = """
██████╗ ██╗███████╗ ██████╗ ████████╗████████╗ ██████╗ ██████╗ ████████╗
██╔══██╗██║██╔════╝██╔═══██╗╚══██╔══╝╚══██╔══╝██╔═══██╗██╔══██╗╚══██╔══╝
██████╔╝██║███████╗██║   ██║   ██║      ██║   ██║   ██║██████╔╝   ██║   
██╔══██╗██║╚════██║██║   ██║   ██║      ██║   ██║   ██║██╔══██╗   ██║   
██████╔╝██║███████║╚██████╔╝   ██║      ██║   ╚██████╔╝██║  ██║   ██║   
╚═════╝ ╚═╝╚══════╝ ╚═════╝    ╚═╝      ╚═╝    ╚═════╝ ╚═╝  ╚═╝   ╚═╝   
    """
    console.print(Panel(Text(title_text, style="bold magenta"), title="[bold red] Gelişmiş Instagram Report Aracı [/bold red]", border_style="red"))
    console.print(f"[cyan]Geliştirici: [white]@poutyuf[/white] | Versiyon: [white]1.2.0 (Proxy Destekli)[/white][/cyan]", justify="center")
    console.print(f"[yellow]{'='*70}[/yellow]\n", justify="center")

def clear_screen():
    os.system("cls" if os.name == "nt" else "clear")

# --- Agent Oluşturma (Script 1'den) ---
class Agent: # Agent sınıfı aynı kalabilir
    @staticmethod
    def generate_user_agent():
        ii = ["273.0.0.17.129", "274.0.0.23.115", "275.0.0.24.117", "276.1.0.25.123", "293.0.0.30.110", "301.0.0.33.110", "312.0.0.35.109"]
        aa = {
            "28/9": ["720dpi", "1080dpi", "1440dpi"], "29/10": ["720dpi", "1080dpi", "1440dpi", "2160dpi"],
            "30/11": ["1080dpi", "1440dpi", "2160dpi"], "31/12": ["1440dpi", "2160dpi"],
            "32/13": ["1080dpi", "1440dpi", "2160dpi", "3072dpi"], "33/14": ["1080dpi", "1440dpi", "2160dpi", "4000dpi"],
            "34/15": ["1440dpi", "2160dpi", "4000dpi"] # Örnek yeni Android sürümü
        }
        ss = { # Çözünürlükler
            "720dpi": ["1280x720", "1920x1080"], "1080dpi": ["1920x1080", "2560x1440", "3840x2160"],
            "1440dpi": ["2560x1440", "3840x2160"], "2160dpi": ["3840x2160", "7680x4320"],
            "3072dpi": ["3072x2048", "4096x2304"], "4000dpi": ["4000x3000", "5120x2880", "6016x3384"]
        }
        dd = { # Cihazlar
            "samsung": ["SM-G998B", "SM-S908E", "SM-S918B", "SM-F936B", "SM-S928B"], 
            "google": ["Pixel 6 Pro", "Pixel 7 Pro", "Pixel 8 Pro", "Pixel Fold", "Pixel 9 Pro"],
            "xiaomi": ["Mi 11 Ultra", "Xiaomi 13 Ultra", "Redmi Note 13 Pro+", "Xiaomi 14 Pro"], 
            "oneplus": ["OnePlus 10 Pro", "OnePlus 11", "OnePlus Open", "OnePlus 12"],
            "oppo": ["Find X5 Pro", "Find X6 Pro", "Find X7 Ultra"], "vivo": ["X80 Pro", "X90 Pro+", "X100 Pro"]
        }
        cc = ["qcom", "exynos", "mediatek", "snapdragon", "tensor", "bionic", "dimensity"] # Chipsetler
        lan = ["en_US", "es_ES", "fr_FR", "de_DE", "it_IT", "pt_BR", "ru_RU", "tr_TR", "ja_JP", "ko_KR", "zh_CN", "ar_AE", "hi_IN"] # Diller
        dp = ["phone", "tablet"]
        arm = ["arm64-v8a", "armeabi-v7a"]

        android_version_code = random.choice(list(aa.keys()))
        dpi_choice = random.choice(aa[android_version_code])
        screen_resolution = random.choice(ss[dpi_choice])
        manufacturer = random.choice(list(dd.keys()))
        model = random.choice(dd.get(manufacturer, ["Generic Model"]))
        architecture = random.choice(arm)
        device_type = random.choice(dp)
        language = random.choice(lan)
        chipset = random.choice(cc)
        instagram_version = random.choice(ii)

        return (f"Instagram {instagram_version} Android "
                f"({android_version_code}; {dpi_choice}; {screen_resolution}; {manufacturer}; {model}; "
                f"{architecture}; {device_type}; {language}; {chipset})")

# --- CSRF Token Alma ---
def get_csrftoken(session): # Proxy kullanacak şekilde güncellendi
    update_session_proxies(session) # Session için proxy ayarla
    try:
        session.headers.update({'User-Agent': Agent.generate_user_agent()})
        response = session.get("https://www.instagram.com/", timeout=15) # Timeout artırıldı
        response.raise_for_status()
        csrftoken = session.cookies.get_dict().get('csrftoken')
        if csrftoken:
            console.print(f"[green][i] CSRF Token başarıyla alındı[/green] [white](Proxy: {current_proxy or 'Yok'}).[/white]")
            return csrftoken
        else: # Cookie'de yoksa
            match = re.search(r'"csrf_token":"(.*?)"', response.text)
            if match and match.group(1):
                csrftoken = match.group(1)
                console.print(f"[green][i] CSRF Token sayfa içeriğinden alındı[/green] [white](Proxy: {current_proxy or 'Yok'}).[/white]")
                return csrftoken
            console.print(f"[bold red][!] CSRF Token alınamadı (Cookie/Sayfa).[/bold red] [white](Proxy: {current_proxy or 'Yok'}).[/white]")
            return None # Fallback
    except requests.exceptions.Timeout:
        console.print(f"[bold red][!] CSRF Token alınırken zaman aşımı[/bold red] [white](Proxy: {current_proxy or 'Yok'}).[/white]")
    except requests.exceptions.RequestException as e:
        console.print(f"[bold red][!] CSRF Token alınırken hata: {str(e)}[/bold red] [white](Proxy: {current_proxy or 'Yok'}).[/white]")
    return None # Fallback

# --- Giriş Fonksiyonları ---
def login_v1_mobile_api(): # Proxy kullanacak şekilde güncellendi
    global current_session_id, global_requests_session
    console.print(Panel(Text("Mobil API ile Instagram Girişi", style="bold yellow"), border_style="yellow", title_align="center"))
    
    username = Prompt.ask(" [white]Instagram Kullanıcı Adınız[/white][yellow]").strip()
    password = Prompt.ask(" [white]Instagram Şifreniz[/white][yellow]", password=True).strip()
    
    if not username or not password:
        console.print("[bold red][!] Kullanıcı adı ve şifre boş bırakılamaz.[/bold red]")
        return False

    console.print(f"[cyan]Giriş yapılıyor: [white]{username}[/white]...[/cyan]", style="italic")
    
    global_requests_session = requests.Session() 
    update_session_proxies(global_requests_session) # Her giriş için yeni proxy dene
    
    csrftoken = get_csrftoken(global_requests_session) # Bu da proxy kullanacak
    if not csrftoken: csrftoken = token_hex(16) 

    phone_id = str(uuid4())
    device_id = f"android-{token_hex(8)}"
    adid = str(uuid4())
    guid = str(uuid4())
    
    login_url = 'https://i.instagram.com/api/v1/accounts/login/'
    # App ID'ler zamanla değişebilir, güncel tutmak önemlidir.
    # Farklı App ID'ler farklı API davranışlarına yol açabilir.
    # Örnekler: '1217981644879628' (Web), '936619743392459' (Genel), '350615882976469' (Lite)
    app_id_mobile = '936619743392459' # Veya daha spesifik bir mobil App ID

    headers = {
        'User-Agent': Agent.generate_user_agent(),
        'X-Ig-App-Id': app_id_mobile, 
        'X-Ig-Connection-Type': 'WIFI',
        'X-Ig-Capabilities': '3brTvw==', # Bu değer de API versiyonuna göre değişebilir
        'Accept-Language': 'en-US', # Veya Agent'tan gelen dil
        'Content-Type': 'application/x-www-form-urlencoded; charset=UTF-8',
        'X-CSRFToken': csrftoken,
        'X-Ig-Device-Id': device_id, # Ekstra header
        'X-Ig-Phone-Id': phone_id,   # Ekstra header
    }
    global_requests_session.headers.update(headers)

    data = {
        'uuid': guid, 'phone_id': phone_id, 'username': username, 'password': password,
        'device_id': device_id, 'guid': guid, 'adid': adid, '_csrftoken': csrftoken,
        'login_attempt_count': '0',
        'device_settings': '{"app_version":"312.0.0.35.109","android_version":33,"android_release":"13","dpi":"480dpi","resolution":"1080x2400","manufacturer":"Google","device":"Pixel 7","model":"panther","cpu":"tensor","version_code":"368769004"}', # Güncel örnek
        'waterfall_id': str(uuid4()), 'fb_device_id': str(uuid4()), 'google_tokens': '[]',
        'ig_sig_key_version': '5', # veya 4, API'ye göre değişir
        'signed_body': f'SIGNATURE.{{"password":"{password}","username":"{username}"}}' # Bu bazen gerekebilir, ama şifreleme gerektirir. Şimdilik basit data.
    }

    try:
        console.print(f"[cyan][i] Giriş isteği gönderiliyor...[/cyan] [white](Proxy: {current_proxy or 'Yok'})[/white]")
        response = global_requests_session.post(login_url, data=data, timeout=25) # Timeout artırıldı
        response_json = response.json()

        if response.status_code == 200 and response_json.get("status") == "ok" and "logged_in_user" in response_json:
            cookies = global_requests_session.cookies.get_dict()
            if 'sessionid' in cookies:
                current_session_id = cookies['sessionid'] # Session ID'yi kaydet
                console.print(f"[green][✓] Başarıyla giriş yapıldı![/green] [white](Proxy: {current_proxy or 'Yok'})[/white]")
                console.print(f"[cyan]Session ID: [white]{current_session_id}[/white]")
                # x-ig-www-claim gibi header'ları session'a kaydet
                if 'x-ig-set-www-claim' in response.headers:
                    global_requests_session.headers['x-ig-www-claim'] = response.headers['x-ig-set-www-claim']
                return True
            else:
                console.print("[bold red][!] Giriş başarılı ancak sessionid alınamadı.[/bold red]")
                console.print(f"[yellow]Yanıt: {response.text[:500]}[/yellow]")
        else: # Hatalı durumlar
            console.print(f"[bold red][!] Giriş başarısız.[/bold red] [white](Proxy: {current_proxy or 'Yok'})[/white]")
            error_message = response_json.get("message", "Bilinmeyen hata.")
            feedback_title = response_json.get("feedback_title")
            if feedback_title: error_message = f"{feedback_title}: {error_message}"

            if "checkpoint_challenge_required" in response.text or "challenge_required" in response.text:
                challenge_url = response_json.get("challenge", {}).get("url")
                console.print(f"[bold red][!] Checkpoint/Challenge gerekli.[/bold red] [white]({error_message})[/white]")
                if challenge_url: console.print(f"[yellow]Challenge URL: {challenge_url}[/yellow]")
            elif "bad_password" in error_message.lower():
                console.print(f"[bold red][!] Hatalı şifre.[/bold red] [white]({error_message})[/white]")
            elif "invalid_user" in error_message.lower() or "user_not_found" in error_message.lower() :
                console.print(f"[bold red][!] Geçersiz kullanıcı adı.[/bold red] [white]({error_message})[/white]")
            elif "two_factor_required" in response.text:
                two_factor_info = response_json.get("two_factor_info", {})
                tf_identifier = two_factor_info.get("two_factor_identifier")
                console.print(f"[bold red][!] İki faktörlü doğrulama gerekli.[/bold red] [white]({error_message})[/white]")
                if tf_identifier: console.print(f"[yellow]İki Faktör ID: {tf_identifier}[/yellow]")
            else:
                console.print(f"[yellow]Yanıt Kodu: {response.status_code}[/yellow]")
                console.print(f"[yellow]Hata: {error_message}[/yellow]")
                console.print(f"[yellow]Tam Yanıt (ilk 500 krk): {response.text[:500]}[/yellow]")
    except requests.exceptions.Timeout:
        console.print(f"[bold red][!] Giriş sırasında zaman aşımı[/bold red] [white](Proxy: {current_proxy or 'Yok'}).[/white]")
    except requests.exceptions.HTTPError as http_err:
        console.print(f"[bold red][!] HTTP Hatası: {http_err}[/bold red] [white](Proxy: {current_proxy or 'Yok'}).[/white]")
        if http_err.response: console.print(f"[yellow]Yanıt: {http_err.response.text[:500]}[/yellow]")
    except requests.exceptions.RequestException as e:
        console.print(f"[bold red][!] Giriş sırasında bağlantı/istek hatası: {str(e)}[/bold red] [white](Proxy: {current_proxy or 'Yok'}).[/white]")
    except ValueError: 
        console.print(f"[bold red][!] Sunucudan geçersiz JSON yanıtı alındı[/bold red] [white](Proxy: {current_proxy or 'Yok'}).[/white]")
        if 'response' in locals() and response: console.print(f"[yellow]Ham Yanıt: {response.text[:500]}[/yellow]")
    return False

def login_v2_web_ajax(): # Proxy kullanacak şekilde güncellendi
    global current_session_id, global_requests_session
    console.print(Panel(Text("Web AJAX ile Instagram Girişi (Yüksek Derecede Deneysel)", style="bold red"), border_style="red", title_align="center"))
    # ... (Bu fonksiyonun içi de proxy kullanacak şekilde güncellenmeli)
    # Ancak enc_password ve diğer JS bağımlı tokenlar ana sorun olmaya devam ediyor.
    # Şimdilik sadece proxy'nin session'a eklendiğini varsayalım.
    
    username = Prompt.ask(" [white]Instagram Kullanıcı Adınız[/white][yellow]").strip()
    password = Prompt.ask(" [white]Instagram Şifreniz (enc_password üretimi için)[/white][yellow]", password=True).strip()
    
    if not username or not password:
        console.print("[bold red][!] Kullanıcı adı ve şifre boş bırakılamaz.[/bold red]")
        return False

    console.print(f"[cyan]Web AJAX ile giriş deneniyor (Deneysel): [white]{username}[/white]...[/cyan]", style="italic")

    global_requests_session = requests.Session()
    update_session_proxies(global_requests_session) # Proxy ayarla
    global_requests_session.headers.update({'User-Agent': Agent.generate_user_agent()})
    
    login_page_url = 'https://www.instagram.com/accounts/login/'
    csrftoken = None
    jazoest = None
    try:
        console.print(f"[cyan][i] Web AJAX için tokenlar alınıyor...[/cyan] [white](Proxy: {current_proxy or 'Yok'})[/white]")
        login_page_res = global_requests_session.get(login_page_url, timeout=15)
        login_page_res.raise_for_status()
        csrftoken = global_requests_session.cookies.get_dict().get('csrftoken')
        if not csrftoken:
             match_csrf_body = re.search(r'"csrf_token":"(.*?)"', login_page_res.text)
             if match_csrf_body: csrftoken = match_csrf_body.group(1)
        
        match_jazoest = re.search(r'name="jazoest" value="(\d+)"', login_page_res.text)
        jazoest = match_jazoest.group(1) if match_jazoest else None

        if not csrftoken or not jazoest:
            console.print("[bold red][!] Web AJAX girişi için gerekli tokenlar (CSRF, Jazoest) alınamadı.[/bold red]")
            return False
        console.print(f"[green][i] Web CSRF: {csrftoken}, Jazoest: {jazoest}[/green]")

    except requests.exceptions.Timeout:
        console.print(f"[bold red][!] Web AJAX token alımında zaman aşımı[/bold red] [white](Proxy: {current_proxy or 'Yok'}).[/white]")
        return False
    except requests.exceptions.RequestException as e:
        console.print(f"[bold red][!] Web AJAX için giriş sayfası tokenlarını alırken hata: {str(e)}[/bold red] [white](Proxy: {current_proxy or 'Yok'}).[/white]")
        return False

    timestamp = str(int(time.time()))
    console.print("[yellow][!] `enc_password` dinamik olarak üretilemiyor. Bu giriş yöntemi başarısız olabilir.[/yellow]")
    enc_password_placeholder = f"#PWD_INSTAGRAM_BROWSER:10:{timestamp}:FAKE_ENC_DATA_NEEDS_REAL_JS_IMPL"

    ajax_login_url = 'https://www.instagram.com/api/v1/web/accounts/login/ajax/'
    # Web App ID'ler: '1217981644879628' veya '936619743392459'
    web_app_id = '936619743392459'

    headers_ajax = {
        'authority': 'www.instagram.com', 'accept': '*/*', 'accept-language': 'en-US,en;q=0.9',
        'content-type': 'application/x-www-form-urlencoded', 'origin': 'https://www.instagram.com',
        'referer': login_page_url, 'sec-ch-ua-mobile': '?0', 
        'x-csrftoken': csrftoken, 'x-ig-app-id': web_app_id,
        'x-instagram-ajax': '1012345678', # Bu değer dinamik olabilir veya sayfa kaynağından alınabilir
        'x-requested-with': 'XMLHttpRequest',
    }
    # User-Agent zaten session'da var
    # global_requests_session.headers.update(headers_ajax) # Gerekirse bazılarını session'a ekle

    data_ajax = {
        'enc_password': enc_password_placeholder, 'username': username,
        'queryParams': '{}', 'optIntoOneTap': 'false',
        'trustedDeviceRecords': '{}', 'jazoest': jazoest,
        '__comet_req': '15' # Bu da dinamik olabilir
    }
    
    try:
        console.print(f"[cyan][i] Web AJAX giriş isteği gönderiliyor...[/cyan] white[/white]")
        response_ajax = global_requests_session.post(ajax_login_url, headers=headers_ajax, data=data_ajax, timeout=20)
        ajax_json = response_ajax.json()

        if response_ajax.status_code == 200 and ajax_json.get("authenticated") is True:
            cookies_ajax = global_requests_session.cookies.get_dict()
            if 'sessionid' in cookies_ajax:
                current_session_id = cookies_ajax['sessionid'] # Session ID'yi kaydet
                console.print(f"[green][✓] Web AJAX ile giriş başarılı (Deneysel)![/green] white[/white]")
                console.print(f"[cyan]Session ID: [white]{current_session_id}[/white]")
                return True
            else:
                console.print("[bold red][!] Web AJAX girişi başarılı ancak sessionid alınamadı.[/bold red]")
        else:
            console.print(f"[bold red][!] Web AJAX girişi başarısız.[/bold red] white[/white]")
            error_msg_ajax = ajax_json.get("message", ajax_json.get("error_message", "Bilinmeyen AJAX hatası."))
            user_facing_msg = ajax_json.get("userFacingMessage", error_msg_ajax)
            console.print(f"[yellow]Hata: {user_facing_msg}[/yellow]")
            if ajax_json.get("two_factor_required"): console.print("[bold red][!] İki faktörlü doğrulama gerekli.[/bold red]")
            if ajax_json.get("checkpoint_url"): console.print(f"[bold red][!] Checkpoint gerekli: {ajax_json.get('checkpoint_url')}[/bold red]")
            if ajax_json.get("error_type"): console.print(f"[yellow]Hata Tipi: {ajax_json.get('error_type')}[/yellow]")

    except requests.exceptions.Timeout:
        console.print(f"[bold red][!] Web AJAX girişinde zaman aşımı[/bold red] white.[/white]")
    except requests.exceptions.RequestException as e_ajax:
        console.print(f"[bold red][!] Web AJAX girişi sırasında hata: {str(e_ajax)}[/bold red] white.[/white]")
    except ValueError: 
        console.print(f"[bold red][!] Web AJAX sunucusundan geçersiz JSON yanıtı alındı[/bold red] white.[/white]")
        if 'response_ajax' in locals() and response_ajax: console.print(f"[yellow]Ham Yanıt: {response_ajax.text[:500]}[/yellow]")
    return False

# --- Raporlama Fonksiyonları ---
def get_target_info(): # Proxy kullanımı try_get_id_alt içinde
    global target_user_id, target_username_global
    
    if Info is None:
        console.print("[yellow][i] 'ms4.InfoIG' kütüphanesi bulunamadığı için kullanıcı ID'si otomatik alınamayacak.[/yellow]")
        target_username_global = Prompt.ask(" [white]Hedef Kullanıcı Adını Girin[/white][yellow]").strip()
        if not target_username_global:
            console.print("[bold red][!] Hedef kullanıcı adı boş bırakılamaz.[/bold red]")
            return False
        target_user_id = Prompt.ask(" [white]Hedef Kullanıcı ID'sini Manuel Girin (API raporlaması için gerekli)[/white][yellow]", default="").strip()
        if not target_user_id:
            console.print("[yellow][!] Kullanıcı ID'si girilmedi. API tabanlı rapor türleri çalışmayabilir.[/yellow]")
        return True

    target_username = Prompt.ask(" [white]Hedef Kullanıcı Adını Girin[/white][yellow]").strip()
    if not target_username:
        console.print("[bold red][!] Hedef kullanıcı adı boş bırakılamaz.[/bold red]")
        return False
    
    target_username_global = target_username
    console.print(f"[cyan]Hedef kullanıcı ID'si alınıyor: [white]{target_username}[/white]...[/cyan]", style="italic")
    try:
        info = Info.Instagram_Info(target_username)
        if isinstance(info, dict) and 'ID' in info and info['ID']:
            target_user_id = str(info['ID']) # ID'yi string olarak kaydet
            console.print(f"[green][✓] Hedef Kullanıcı: [white]{target_username}[/white], ID: [white]{target_user_id}[/white][/green]")
            return True
        else:
            console.print("[bold red][!] Hedef kullanıcı ID'si 'ms4.InfoIG' ile alınamadı veya kullanıcı bulunamadı.[/bold red]")
            console.print(f"[yellow]Alınan bilgi: {str(info)[:300]}[/yellow]")
            # Alternatif ID alma denemesi (eğer ms4 başarısız olursa)
            try_get_id_alt(target_username)
            return bool(target_user_id) # Eğer alternatif yöntem ID bulduysa True döner
    except Exception as e:
        console.print(f"[bold red][!] Kullanıcı bilgisi alınırken hata ('ms4.InfoIG'): {str(e)}[/bold red]")
        try_get_id_alt(target_username) # ms4 hata verirse alternatif dene
        return bool(target_user_id)

def try_get_id_alt(username):
    """ms4 başarısız olursa ID almak için alternatif bir yöntem."""
    global target_user_id
    console.print(f"[cyan][i] Alternatif yöntemle kullanıcı ID'si deneniyor: [white]{username}[/white][/cyan]")
    temp_session_for_id = requests.Session()
    update_session_proxies(temp_session_for_id) # Proxy kullan
    temp_session_for_id.headers.update({'User-Agent': Agent.generate_user_agent()})
    try:
        # Instagram'ın web arayüzünden kullanıcı bilgilerini çekmeye çalış
        # Bu endpoint sıkça değişir: ?__a=1 veya ?__a=1&__d=dis
        # Veya GraphQL endpoint'leri kullanılabilir (daha karmaşık)
        # En basit yöntemlerden biri, sayfa kaynağındaki bir script tag'ındaki JSON verisidir.
        profile_url = f"https://www.instagram.com/{username}/"
        res = temp_session_for_id.get(profile_url, timeout=15)
        res.raise_for_status()
        
        # Sayfa kaynağında "profilePage_" ile başlayan ID'yi ara
        match = re.search(r'"profilePage_(\d+)"', res.text)
        if match:
            target_user_id = str(match.group(1)) # ID'yi string olarak kaydet
            console.print(f"[green][✓] Alternatif yöntemle ID bulundu: [white]{target_user_id}[/white][/green]")
            return True
        else: # GraphQL veya __a=1 denemesi
            try:
                res_a1 = temp_session_for_id.get(f"https://www.instagram.com/{username}/?__a=1&__d=dis", 
                                                 headers={'X-Requested-With': 'XMLHttpRequest'}, timeout=10)
                res_a1.raise_for_status()
                data_a1 = res_a1.json() # ValueError yakala
                if "graphql" in data_a1 and "user" in data_a1["graphql"] and "id" in data_a1["graphql"]["user"] and data_a1["graphql"]["user"]["id"]:
                    target_user_id = str(data_a1["graphql"]["user"]["id"]) # ID'yi string olarak kaydet
                    console.print(f"[green][✓] Alternatif yöntemle (?__a=1) ID bulundu: [white]{target_user_id}[/white][/green]")
                    return True
            except (requests.exceptions.RequestException, ValueError): # ?__a=1 veya JSON parse başarısız olursa
                pass # Hata mesajı verme, sadece sessizce başarısız ol

        console.print("[bold red][!] Alternatif yöntemle kullanıcı ID'si bulunamadı.[/bold red]")
        target_user_id = None # Bulunamadıysa None olarak ayarla
        return False
    except Exception as e_alt:
        console.print(f"[bold red][!] Alternatif ID alma sırasında hata: {str(e_alt)}[/bold red]")
        target_user_id = None # Hata durumunda None olarak ayarla
        return False


def report_with_sessionid_api(): # Proxy kullanacak şekilde güncellendi
    global current_session_id, target_user_id, target_username_global, global_requests_session

    if not current_session_id:
        console.print("[bold red][!] Raporlama için geçerli bir Session ID bulunmuyor. Lütfen önce giriş yapın.[/bold red]")
        return
    if not global_requests_session: 
        console.print("[bold red][!] Aktif requests session bulunamadı.[/bold red]")
        return

    if not target_user_id: 
        console.print("[bold red][!] API Raporlaması için hedef kullanıcı ID'si gereklidir.[/bold red]")
        if not get_target_info() or not target_user_id: # get_target_info ID bulamazsa
             console.print("[bold red][!] Hedef ID alınamadı, API raporlaması yapılamıyor.[/bold red]")
             return

    console.print(Panel(Text(f"API ile Raporlama: {target_username_global} (ID: {target_user_id})", style="bold cyan"), border_style="cyan", title_align="center"))
    update_session_proxies(global_requests_session) # Her raporlama için yeni proxy dene

    report_reasons = {
        1: {"tag": "spam", "reason_id": 1, "text": "Spam"},
        2: {"tag": "nudity_or_sexual_activity", "reason_id": 2, "text": "Çıplaklık veya Cinsel Aktivite"},
        3: {"tag": "hate_speech_or_symbols", "reason_id": 3, "text": "Nefret Söylemi"},
        4: {"tag": "bullying_or_harassment", "reason_id": 4, "text": "Zorbalık veya Taciz"},
        5: {"tag": "intellectual_property_violation", "reason_id": 5, "text": "Fikri Mülkiyet İhlali"},
        6: {"tag": "self_injury", "reason_id": 8, "text": "Kendine Zarar Verme"},
        7: {"tag": "impersonation", "reason_id": 7, "text": "Taklitçilik (Detaylı akış gerekebilir)"},
        8: {"tag": "sale_of_illegal_or_regulated_goods", "reason_id": 6, "text": "Yasadışı veya Düzenlenmiş Ürün Satışı"},
        9: {"tag": "scam_or_fraud", "reason_id": 10, "text": "Dolandırıcılık veya Sahtekarlık"}, # Yeni eklendi
    }
    
    console.print("[cyan]Mevcut Rapor Sebepleri:[/cyan]")
    for key, value in report_reasons.items(): console.print(f"[white]{key}. [cyan]{value['text']}[/cyan]")
    
    try:
        reason_choice = IntPrompt.ask(" [white]Lütfen bir rapor sebebi seçin (numara)[/white][yellow]", choices=[str(k) for k in report_reasons.keys()])
    except ValueError:
        console.print("[bold red][!] Geçersiz seçim.[/bold red]")
        return

    selected_reason = report_reasons[reason_choice]
    
    csrftoken = global_requests_session.cookies.get_dict().get('csrftoken', token_hex(16))
    report_url_frx_prompt = 'https://www.instagram.com/api/v1/web/reports/get_frx_prompt/'
    
    headers_frx = {
        'authority': 'www.instagram.com', 'accept': '*/*', 'accept-language': 'en-US,en;q=0.9,tr-TR;q=0.8',
        'content-type': 'application/x-www-form-urlencoded', 'origin': 'https://www.instagram.com',
        'referer': f'https://www.instagram.com/{target_username_global}/',
        'user-agent': global_requests_session.headers.get('User-Agent', Agent.generate_user_agent()),
        'x-csrftoken': csrftoken,
        'x-ig-app-id': global_requests_session.headers.get('x-ig-app-id', '936619743392459'), # Session'dan al veya varsayılan
        'x-ig-www-claim': global_requests_session.headers.get('x-ig-www-claim', '0'),
        'x-requested-with': 'XMLHttpRequest',
        # 'x-asbd-id': '129477', # Bu header'ın gerekliliği ve dinamikliği kontrol edilmeli
    }

    data_get_context = {
        'container_module': 'profilePage', 'entry_point': '1', 'location': '2',
        'object_id': target_user_id, 'object_type': 'user', 'frx_prompt_request_type': '1',
    }

    console.print(f"[cyan]Raporlama için context alınıyor ([white]{selected_reason['text']}[/white])...[/cyan] white[/white]", style="italic")
    
    frx_context = None
    response_context_text = ""
    try:
        response_context = global_requests_session.post(report_url_frx_prompt, headers=headers_frx, data=data_get_context, timeout=20)
        response_context_text = response_context.text 
        response_context.raise_for_status()
        context_json = response_context.json()

        if context_json.get("status") == "ok" and 'context' in context_json.get('response', {}):
            frx_context = context_json['response']['context']
            console.print("[green][i] FRX Context başarıyla alındı.[/green]")
        else:
            console.print("[bold red][!] FRX Context alınamadı.[/bold red]")
            console.print(f"[yellow]Yanıt: {str(context_json)[:500]}[/yellow]")
            return

    except requests.exceptions.Timeout:
        console.print(f"[bold red][!] FRX Context alırken zaman aşımı[/bold red] white.[/white]")
        return
    except requests.exceptions.HTTPError as http_err:
        console.print(f"[bold red][!] FRX Context alırken HTTP Hatası: {http_err}[/bold red] white.[/white]")
        if http_err.response: console.print(f"[yellow]Yanıt: {http_err.response.text[:500]}[/yellow]")
        return
    except requests.exceptions.RequestException as e:
        console.print(f"[bold red][!] FRX Context alırken Bağlantı/İstek Hatası: {str(e)}[/bold red] white.[/white]")
        return
    except ValueError: 
        console.print(f"[bold red][!] FRX Context için sunucudan geçersiz JSON yanıtı alındı[/bold red] white.[/white]")
        console.print(f"[yellow]Ham Yanıt: {response_context_text[:500]}[/yellow]")
        return

    if frx_context:
        data_submit_report = {
            'container_module': 'profilePage', 'entry_point': '1', 'location': '2',
            'object_id': target_user_id, 'object_type': 'user', 'context': frx_context,
            'selected_tag_types': f'["{selected_reason["tag"]}"]', 'action_type': '2',
            'frx_prompt_request_type': '2',
        }
        
        console.print(f"[cyan]Rapor gönderiliyor ([white]{selected_reason['text']}[/white])...[/cyan] white[/white]", style="italic")
        time.sleep(random.uniform(3, 7)) # Raporlar arası bekleme

        response_report_text = ""
        try:
            response_report = global_requests_session.post(report_url_frx_prompt, headers=headers_frx, data=data_submit_report, timeout=20)
            response_report_text = response_report.text
            response_report.raise_for_status()
            report_json = response_report.json()

            if report_json.get("status") == "ok" or report_json.get("success") is True:
                console.print(f"[green][✓] {target_username_global} kullanıcısı '[white]{selected_reason['text']}[/white]' sebebiyle başarıyla raporlandı![/green] white[/white]")
                feedback_message = report_json.get("response", {}).get("toast_message", report_json.get("message"))
                if feedback_message: console.print(f"[green][i] Sunucu Mesajı: {feedback_message}[/green]")
            else:
                console.print(f"[bold red][!] Rapor gönderilemedi.[/bold red] white[/white]")
                error_msg_report = report_json.get("message", report_json.get("error_message", "Bilinmeyen raporlama hatası."))
                console.print(f"[yellow]Hata: {error_msg_report}[/yellow]")
                console.print(f"[yellow]Yanıt: {str(report_json)[:500]}[/yellow]")
        except requests.exceptions.Timeout:
            console.print(f"[bold red][!] Rapor gönderirken zaman aşımı[/bold red] white.[/white]")
        except requests.exceptions.HTTPError as http_err_report:
            console.print(f"[bold red][!] Rapor gönderirken HTTP Hatası: {http_err_report}[/bold red] white.[/white]")
            if http_err_report.response: console.print(f"[yellow]Yanıt: {http_err_report.response.text[:500]}[/yellow]")
        except requests.exceptions.RequestException as e_report:
            console.print(f"[bold red][!] Rapor gönderirken Bağlantı/İstek Hatası: {str(e_report)}[/bold red] white.[/white]")
        except ValueError: 
            console.print(f"[bold red][!] Rapor gönderimi için sunucudan geçersiz JSON yanıtı alındı[/bold red] white.[/white]")
            console.print(f"[yellow]Ham Yanıt: {response_report_text[:500]}[/yellow]")

def report_via_help_form(): # Proxy kullanacak şekilde güncellendi
    global target_username_global
    console.print(Panel(Text("Yardım Formu ile Raporlama (Dinamik Token Denemeli)", style="bold yellow"), border_style="yellow", title_align="center"))
    
    if not target_username_global:
        temp_target_user = Prompt.ask(" [white]Hedef Kullanıcı Adını Girin[/white][yellow]").strip()
        if not temp_target_user:
            console.print("[bold red][!] Hedef kullanıcı adı boş bırakılamaz.[/bold red]")
            return
        target_username_global = temp_target_user
    
    target_name_form = Prompt.ask(" [white]Hedef Kullanıcının (Form için) Adı Soyadı (Zorunlu Değil)[/white][yellow]", default="").strip()
    if not target_name_form:
        console.print("[bold red][!] Hedef adı (form için) boş bırakılamaz.[/bold red]")
        return

    console.print(f"[cyan]Yardım formu ile rapor deneniyor: [white]{target_username_global}[/white]...[/cyan]", style="italic")

    form_url = 'https://help.instagram.com/contact/723586364339719' 
    submit_url = 'https://help.instagram.com/ajax/help/contact/submit/page'
    
    form_session = requests.Session()
    update_session_proxies(form_session) # Proxy ayarla
    form_session.headers.update({'User-Agent': Agent.generate_user_agent()})

    lsd_token = "AVq5uabXj48" # Statik fallback
    jazoest_token = "2931"   # Statik fallback
    
    console.print(f"[cyan]Form sayfasından dinamik tokenlar alınıyor...[/cyan] white[/white]")
    try:
        form_page_res = form_session.get(form_url, timeout=20)
        form_page_res.raise_for_status()
        html_content = form_page_res.text

        match_lsd = re.search(r'name="lsd"\s*value="([^"]+)"', html_content)
        if match_lsd: lsd_token = match_lsd.group(1); console.print(f"[green][i] LSD Token: {lsd_token}[/green]")
        else: console.print("[yellow][!] LSD Token bulunamadı, fallback kullanılıyor.[/yellow]")

        match_jazoest = re.search(r'name="jazoest"\s*value="([^"]+)"', html_content)
        if match_jazoest: jazoest_token = match_jazoest.group(1); console.print(f"[green][i] Jazoest Token: {jazoest_token}[/green]")
        else: console.print("[yellow][!] Jazoest Token bulunamadı, fallback kullanılıyor.[/yellow]")
        
    except requests.exceptions.Timeout:
        console.print(f"[bold red][!] Form token alımında zaman aşımı[/bold red] white. Fallback tokenlar kullanılacak.[/white]")
    except requests.exceptions.RequestException as e_form_get:
        console.print(f"[bold red][!] Form sayfasından token alırken hata: {str(e_form_get)}[/bold red] white. Fallback tokenlar kullanılacak.[/white]")

    form_headers = {
        "Host": "help.instagram.com", "X-Fb-Lsd": lsd_token, "X-Asbd-Id": "129477",
        "Content-Type": "application/x-www-form-urlencoded", "Accept": "*/*",
        "Origin": "https://help.instagram.com", "Referer": form_url,
    }
    # User-Agent ve diğer sec-ch-* header'lar session'dan gelir.

    dt_now = datetime.now()
    timestamp_form = str(int(dt_now.timestamp()))
    random_email_chars = "".join(random.choice('abcdefghijklmnopqrstuvwxyz1234567890') for i in range(10)) # Sadece alfanumerik
    email_form = f"{random_email_chars}@example.com"

    form_data_payload = {
        "jazoest": jazoest_token, "lsd": lsd_token,
        "Field258021274378282": target_username_global, 
        "Field735407019826414": target_name_form,      
        "Field506888789421014[year]": "2014", "Field506888789421014[month]": "11", "Field506888789421014[day]": "11",
        "Field294540267362199": "Parent", "inputEmail": email_form,
        "support_form_id": "723586364339719", "support_form_locale_id": "en_US",
        "support_form_hidden_fields": "{}", "support_form_fact_false_fields": "[]",
        "__user": "0", "__a": "1", "__req": str(random.randint(3,9)), 
        "__hs": "19752.BP:DEFAULT.2.0..0.0", "dpr": "1", "__ccg": "GOOD",
        "__rev": str(random.randint(1007900000, 1008900000)), 
        "__s": f"{token_hex(3)}:{token_hex(3)}:{token_hex(3)}", 
        "__hsi": str(random.randint(7200000000000000000, 7300000000000000000)), 
        "__dyn": "7xe6E5aQ1PyUbFuC1swgE98nwgU6C7UW8xi642-7E2vwXw5ux60Vo1upE4W0OE2WxO2O1Vwooa81VohwnU1e42C220qu1Tw40wdq0Ho2ewnE3fw6iw4vwbS1Lw4Cwcq", 
        "__csr": "", "__spin_r": str(random.randint(1007900000, 1008900000)),
        "__spin_b": "trunk", "__spin_t": timestamp_form
    }
    
    console.print(f"[cyan]Form gönderiliyor...[/cyan] white[/white]")
    try:
        response_form_submit = form_session.post(submit_url, headers=form_headers, data=form_data_payload, timeout=25)
        response_form_submit.raise_for_status()
        
        if response_form_submit.status_code == 200:
            try:
                submit_json = response_form_submit.json()
                # Facebook/Instagram form yanıtları genellikle 'for (;;);' ile başlar, bu temizlenmeli
                cleaned_response_text = response_form_submit.text.lstrip('for (;;);')
                submit_json = requests.utils.json.loads(cleaned_response_text) # ValueError yakala


                if submit_json.get("payload", {}).get("success") is True or "success" in submit_json.get("message","").lower() or submit_json.get("error") is None : # Daha geniş başarı kontrolü
                    console.print(f"[green][✓] Yardım formu başarıyla gönderildi![/green] white[/white]")
                    if "message" in submit_json: console.print(f"[green][i] Mesaj: {submit_json['message']}[/green]")
                    elif "payload" in submit_json and "message" in submit_json["payload"]: console.print(f"[green][i] Mesaj: {submit_json['payload']['message']}[/green]")

                elif "errorSummary" in submit_json or "error_message" in submit_json or submit_json.get("error"):
                    error_summary = submit_json.get("errorSummary", submit_json.get("error_message", submit_json.get("error", "Bilinmeyen form hatası.")))
                    console.print(f"[bold red][!] Form gönderiminde hata (Sunucu): {error_summary}[/bold red] white[/white]")
                else: 
                    console.print(f"[yellow][?] Form gönderildi (HTTP 200), ancak sunucu yanıtı belirsiz.[/yellow] white[/white]")
                    console.print(f"[yellow]Yanıt (JSON): {str(submit_json)[:500]}[/yellow]")
            except ValueError: 
                console.print(f"[yellow][?] Form gönderildi (HTTP 200), ancak sunucu JSON yanıt vermedi.[/yellow] white[/white]")
                console.print(f"[yellow]Yanıt (TEXT): {response_form_submit.text[:500]}[/yellow]")
        else: 
            console.print(f"[bold red][!] Form gönderilemedi. HTTP Durum Kodu: {response_form_submit.status_code}[/bold red] white[/white]")
            console.print(f"[yellow]Yanıt: {response_form_submit.text[:500]}[/yellow]")

    except requests.exceptions.Timeout:
        console.print(f"[bold red][!] Form gönderirken zaman aşımı[/bold red] white.[/white]")
    except requests.exceptions.HTTPError as http_err_form:
        console.print(f"[bold red][!] Form gönderirken HTTP Hatası: {http_err_form}[/bold red] white.[/white]")
        if http_err_form.response: console.print(f"[yellow]Yanıt: {http_err_form.response.text[:500]}[/yellow]")
    except requests.exceptions.RequestException as e_form_submit:
        console.print(f"[bold red][!] Form gönderirken Bağlantı/İstek Hatası: {str(e_form_submit)}[/bold red] white.[/white]")
    return

 # --- Ana Menü ---
def main_menu():
    global current_session_id, target_username_global, target_user_id, global_requests_session, proxy_list, current_proxy
    
    while True:
        clear_screen()
        display_main_title()
        
        console.print(f"[cyan]Aktif Session ID: [white]{current_session_id or 'Yok'}[/white][/cyan]", justify="center")
        console.print(f"[cyan]Hedef Kullanıcı: [white]{target_username_global or 'Seçilmedi'}[/white] (ID: [white]{target_user_id or 'Bilinmiyor'}[/white])[/cyan]", justify="center")
        console.print(f"[cyan]Kullanılan Proxy: [white]{current_proxy or 'Yok'}[/white] | Toplam Proxy: [white]{len(proxy_list)}[/white]\n[/cyan]", justify="center")


        menu_options = {
            1: "Instagram'a Giriş Yap (Mobil API)",
            2: "Instagram'a Giriş Yap (Web AJAX - Deneysel)",
            3: "Hedef Kullanıcı Seç/Değiştir",
            4: "Session ID ile API Üzerinden Raporla",
            5: "Yardım Formu ile Raporla (Deneysel)",
            6: "Proxy Yükle (Dosyadan)",
            7: "Proxy Yükle (Webshare API)", # Yeni seçenek
            8: "Proxy Ekle (Manuel)",
            9: "Proxy'leri Görüntüle",
            10: "Proxy'leri Temizle",
            0: "Çıkış",
        }

        table = Table(title="[bold magenta]Ana Menü[/bold magenta]", show_header=True, header_style="bold magenta")
        table.add_column("Seçenek", style="cyan", width=10)
        table.add_column("Açıklama")

        for key, value in menu_options.items(): table.add_row(str(key), value)
        console.print(table)
        
        try:
            choice = IntPrompt.ask("\n[white]Lütfen bir işlem seçin[/white][yellow]", choices=[str(k) for k in menu_options.keys()])
        except ValueError: 
            console.print("[bold red]Geçersiz giriş. Lütfen menüden bir numara girin.[/bold red]")
            time.sleep(2)
            continue
        except Exception as e_prompt: 
             console.print(f"[bold red]Menü seçimi sırasında bir hata oluştu: {e_prompt}[/bold red]")
             time.sleep(2)
             continue

        if choice == 1: login_v1_mobile_api()
        elif choice == 2: login_v2_web_ajax()
        elif choice == 3: get_target_info()
        elif choice == 4: # API Raporlama
            if not current_session_id: console.print("[bold red][!] Bu işlem için önce giriş yapmalısınız (Seçenek 1).[/bold red]")
            elif not target_username_global or not target_user_id: 
                console.print("[yellow][i] API Raporlaması için önce hedef kullanıcı seçmeli ve ID'si alınmalıdır.[/yellow]")
                if get_target_info() and target_user_id: report_with_sessionid_api()
            else: report_with_sessionid_api()
        elif choice == 5: # Form Raporlama
            if not target_username_global:
                console.print("[yellow][i] Form Raporlaması için önce hedef kullanıcı seçmelisiniz.[/yellow]")
                if get_target_info(): report_via_help_form()
            else: report_via_help_form()
        elif choice == 6: load_proxies_from_file()
        elif choice == 7: load_proxies_from_webshare() # Yeni fonksiyon çağrısı
        elif choice == 8: add_proxy_manually()
        elif choice == 9: view_proxies()
        elif choice == 10: clear_proxies()
        elif choice == 0:
            console.print("[green]Araçtan çıkılıyor... Hoşça kalın, Efendim![/green]")
            break
        
        if choice != 0:
            Prompt.ask("\n[cyan]Devam etmek için Enter'a basın...[/cyan]")

if __name__ == "__main__":
    try:
        main_menu()
    except KeyboardInterrupt:
        clear_screen()
        console.print("\n[yellow]Program kullanıcı tarafından (Ctrl+C) sonlandırıldı.[/yellow]")
    except Exception as e_main:
        clear_screen()
        console.print("\n[bold red]Beklenmedik bir ana hata oluştu. Lütfen geliştiriciye bildirin.[/bold red]")
        console.print(f"[bold red]Hata Detayı: {type(e_main).__name__}: {str(e_main)}[/bold red]")
        # import traceback
        # console.print(f"[bold red]Traceback:\n{traceback.format_exc()}[/bold red]")
