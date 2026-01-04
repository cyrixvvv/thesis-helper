import requests, uuid
from googletrans import Translator, utils
from googletrans import Translator, utils
from googletrans.constants import DEFAULT_USER_AGENT
from googletrans import urls
from thesisUtils.configure import config

# --- 辅助类与函数 ---

def get_proxies():
    """从配置文件读取网络代理设置"""
    proxies = None
    if config.has_section('network') and config.getboolean('network', 'proxy_enable'):
        p_type = config.get('network', 'proxy_type', fallback='http')
        p_host = config.get('network', 'proxy_host', fallback='127.0.0.1')
        p_port = config.get('network', 'proxy_port', fallback='7890')
        proxy_url = f"{p_type}://{p_host}:{p_port}"
        proxies = { "http": proxy_url, "https": proxy_url }
    return proxies

# --- 具体的翻译实现 ---

def _do_google_translate(text_input):
    """执行谷歌翻译"""
    google_host = config.get('translation', 'google_host', fallback='translate.google.com')
    proxies = get_proxies()
    
    # Use standard Translator. googletrans 4.0.0rc1 supports proxies and service_urls properly.
    translator = Translator(service_urls=[google_host], proxies=proxies)
    
    # 简单的翻译调用，出错会抛出异常由上层捕获
    result = translator.translate(text_input, dest='zh-cn')
    return result.text

def _do_microsoft_translate(text_input):
    """执行微软翻译"""
    key = config.get('translation', 'microsoft_key', fallback='')
    if not key:
        raise ValueError("Microsoft translation key is missing in CONFIG.ini")

    region = config.get('translation', 'microsoft_region', fallback='global')
    endpoint = 'https://api.cognitive.microsofttranslator.com/translate?api-version=3.0&to=zh-Hans'
    
    headers = {
        'Ocp-Apim-Subscription-Key': key,
        'Ocp-Apim-Subscription-Region': region,
        'Content-type': 'application/json',
        'X-ClientTraceId': str(uuid.uuid4())
    }
    body = [{'text': text_input}]
    
    response = requests.post(endpoint, headers=headers, json=body, proxies=get_proxies(), timeout=10)
    response.raise_for_status() # 如果状态码不是200，抛出异常
    
    result_json = response.json()
    return result_json[0]['translations'][0]['text']

def _do_custom_translate(text_input):
    """执行自定义API翻译"""
    url = config.get('translation', 'custom_api_url', fallback='')
    if not url:
        raise ValueError("Custom API URL is missing in CONFIG.ini")
        
    api_key = config.get('translation', 'custom_api_key', fallback='')
    headers = {'Content-Type': 'application/json'}
    if api_key:
        headers['Authorization'] = f'Bearer {api_key}'
    
    # 这里假设自定义API接受如下格式，需根据实际情况调整
    data = {'text': text_input, 'source_lang': 'auto', 'target_lang': 'zh'}
    
    response = requests.post(url, json=data, headers=headers, proxies=get_proxies(), timeout=10)
    response.raise_for_status()
    
    # 尝试解析常见的返回格式
    try:
        json_resp = response.json()
        # 兼容 { "data": "..." } 或 { "result": "..." } 或 { "translations": ... }
        if 'result' in json_resp: return json_resp['result']
        if 'data' in json_resp: return json_resp['data']
        # 如果是 DeepLX 格式
        if 'translations' in json_resp: return json_resp['translations'][0]['text']
        return response.text
    except:
        return response.text

# --- 统一入口 ---

def get_translation(text_input, language_output="zh-Hans"):
    if not text_input or not text_input.strip():
        return ""

    # 读取优先级配置，默认为 google
    order_str = config.get('translation', 'engine_order', fallback='google')
    engines = [e.strip().lower() for e in order_str.split(',')]

    last_error = None

    for engine in engines:
        try:
            if engine == 'google':
                return _do_google_translate(text_input)
            elif engine == 'microsoft':
                return _do_microsoft_translate(text_input)
            elif engine == 'custom':
                return _do_custom_translate(text_input)
        except Exception as e:
            # 记录错误，尝试下一个引擎
            last_error = e
            print(f"Translation engine '{engine}' failed: {str(e)}. Trying next...")
            continue
    
    # 如果所有引擎都失败了
    return f"Translation Failed. All engines tried. Last Error: {str(last_error)}"

# 保留此函数以兼容旧代码调用（如果有）
def get_translation_by_google(text_input):
    try:
        return _do_google_translate(text_input)
    except Exception as e:
        return f"Google Error: {e}"
