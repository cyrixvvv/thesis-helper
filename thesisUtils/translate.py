import requests, uuid
from googletrans import Translator, models
from googletrans import urls, utils
from googletrans.compat import PY3
from googletrans.constants import DEFAULT_USER_AGENT
from thesisUtils.configure import config  # [修改点1] 导入配置对象

# 原有的微软翻译 key (如果不再使用可以忽略)
subscription_key = '32f1cb9c935a4cd4b33825e2869bff0f'

class MyTranslator(Translator):
    def __init__(self, service_urls=None, user_agent=DEFAULT_USER_AGENT,
                 proxies=None, timeout=None):
        super().__init__(service_urls, user_agent, proxies, timeout)

    def _translate(self, text, dest, src):
        if not PY3 and isinstance(text, str):  # pragma: nocover
            text = text.decode('utf-8')

        token = self.token_acquirer.do(text)
        params = utils.build_params(query=text, src=src, dest=dest,
                                    token=token)
        params['client'] = 'webapp'
        url = urls.TRANSLATE.format(host=self._pick_service_url())
        
        # [修改点2] 使用类初始化时传入的 proxies
        r = self.session.get(url, params=params, proxies=self.proxies)

        data = utils.format_json(r.text)
        return data

# [新增功能] 从配置文件读取代理设置
def get_proxies():
    proxies = None
    if config.has_section('network') and config.getboolean('network', 'proxy_enable'):
        p_type = config.get('network', 'proxy_type', fallback='http')
        p_host = config.get('network', 'proxy_host', fallback='127.0.0.1')
        p_port = config.get('network', 'proxy_port', fallback='7890')
        proxy_url = f"{p_type}://{p_host}:{p_port}"
        proxies = {
            "http": proxy_url,
            "https": proxy_url
        }
    return proxies

def get_extra_result_of_single_word(word, translator):
    """
    :param word: single word string contain no space
    :param translator: google translator object
    :return: result string
    """
    # 尝试翻译，处理网络异常
    try:
        translate_res = translator.translate(word, dest='zh-cn')
    except Exception as e:
        return f"Error: {str(e)}"

    extra_data = translate_res.extra_data
    # 增加空值判断防止报错
    if not extra_data:
        return translate_res.text

    all_translations_list = extra_data.get('all-translations')
    result = ''
    if all_translations_list is None:
        result = translate_res.text
    else:
        for translation in all_translations_list:
            word_class = translation[0]
            result += word_class + '\n    '
            word_tsl_list = translation[2]
            for tsl in word_tsl_list:
                tsl_res = tsl[0]
                tsl_src_list = tsl[1]
                tsl_src = ''
                if tsl_src_list is not None:
                    for i in tsl_src_list:
                        tsl_src += i + ' '
                result += '{0} [{1}]\n    '.format(tsl_res, tsl_src)
            result += '\n'
    return result

def get_translation_by_google(text_input):
    # [修改点3] 动态读取Host和代理配置
    google_host = 'translate.google.com'
    if config.has_option('translation', 'google_host'):
        google_host = config.get('translation', 'google_host')
    
    proxies = get_proxies()
    
    # 初始化带代理和新Host的翻译器
    translator = MyTranslator(service_urls=[google_host], proxies=proxies)
    
    try:
        if len(text_input.split()) == 1:
            trans_result = get_extra_result_of_single_word(text_input.split()[0], translator)
        else:
            trans_result = translator.translate(text_input, dest='zh-cn').text
    except Exception as e:
        trans_result = f"Google Translate Error: {str(e)}"
        
    return trans_result

# [新增功能] 自定义API翻译函数
def get_custom_api_translation(text_input):
    if not config.has_section('translation') or not config.getboolean('translation', 'custom_api_enable'):
        return None
        
    url = config.get('translation', 'custom_api_url')
    api_key = config.get('translation', 'custom_api_key', fallback='')
    
    headers = {'Content-Type': 'application/json'}
    if api_key:
        headers['Authorization'] = f'Bearer {api_key}'
        
    data = {'text': text_input, 'source': 'auto', 'target': 'zh'}
    
    try:
        resp = requests.post(url, json=data, headers=headers, proxies=get_proxies(), timeout=10)
        if resp.status_code == 200:
            # 假设返回格式为 {"result": "翻译文本"}，根据实际API调整
            return resp.json().get('result', resp.text)
    except Exception as e:
        return f"Custom API Error: {str(e)}"
    return None

# 原有的微软翻译函数保留，但也加上代理支持
def get_translation(text_input, language_output="zh-Hans"):
    if not text_input:
        return ""
    
    # 优先尝试自定义API (如果启用)
    custom_res = get_custom_api_translation(text_input)
    if custom_res:
        return custom_res

    base_url = 'https://api.cognitive.microsofttranslator.com'
    path = '/translate?api-version=3.0'
    params = '&to=' + language_output
    constructed_url = base_url + path + params

    headers = {
        'Ocp-Apim-Subscription-Key': subscription_key,
        'Ocp-Apim-Subscription-Region': 'global',
        'Content-type': 'application/json',
        'X-ClientTraceId': str(uuid.uuid4())
    }

    body = [{
        'text' : text_input
    }]
    
    try:
        # [修改点4] 增加代理支持
        response = requests.post(constructed_url, headers=headers, json=body, proxies=get_proxies(), timeout=10)
        result = response.json()
        return result[0]['translations'][0]['text']
    except Exception as e:
        # 如果微软API失败，回退到谷歌翻译
        return get_translation_by_google(text_input)
