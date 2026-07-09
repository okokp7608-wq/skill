import os
import re
import json
import xml.etree.ElementTree as ET
import requests
from flask import Flask, request, jsonify, send_file

app = Flask(__name__, static_folder='.', static_url_path='')

# 1. 설정 로드
CONFIG_PATH = os.path.join('config', 'model_config.json')
with open(CONFIG_PATH, 'r', encoding='utf-8') as f:
    model_config = json.load(f)

OLLAMA_BASE_URL = model_config.get('ollama_base_url', 'http://localhost:11434')
RECOMMENDED_MODEL = model_config.get('recommended_model', 'gemma3:1b')

# 2. FAQ XML 로드 및 파싱
FAQ_PATH = os.path.join('data', 'faq_context.xml')
tree = ET.parse(FAQ_PATH)
root = tree.getroot()
faqs = []
for faq in root.findall('faq'):
    faqs.append({
        'id': faq.get('id'),
        'topic': faq.find('topic').text,
        'department': faq.find('department').text,
        'answer': faq.find('answer').text,
        'keywords': [k.strip() for k in faq.find('keywords').text.split(';')] if faq.find('keywords') is not None else []
    })

def extract_keywords(text):
    """
    한국어 조사 및 불용어를 간단히 제거하여 핵심 키워드 리스트를 추출하는 함수
    """
    cleaned = re.sub(r'[^\w\s]', ' ', text)
    words = cleaned.split()
    
    # 대표적인 한국어 조사 목록
    josa_list = ['은', '는', '이', '가', '을', '를', '에', '에서', '에게', '한테', '의', '와', '과', '로', '으로', '하고', '하며', '해서', '해야', '하나요', '인가요', '합니까', '있나요', '없나요']
    
    keywords = []
    for word in words:
        matched = False
        # 단어 끝에서 조사 매칭하여 제거
        for josa in sorted(josa_list, key=len, reverse=True):
            if word.endswith(josa) and len(word) > len(josa):
                cleaned_word = word[:-len(josa)]
                if len(cleaned_word) >= 2:
                    keywords.append(cleaned_word)
                    matched = True
                    break
        if not matched and len(word) >= 2:
            keywords.append(word)
            
    # 원본 단어도 포함하여 매칭 정확도 향상
    for word in words:
        if len(word) >= 2:
            keywords.append(word)
            
    return list(set(keywords))

def find_related_faqs(query_text, faq_list):
    """
    질문 키워드와 각 FAQ 항목의 유사도(토픽, 키워드, 답변)를 계산하여 가장 관련 깊은 FAQ 1~2개 매칭
    """
    query_keywords = extract_keywords(query_text)
    print(f"Extracted Keywords from Query: {query_keywords}")
    scored_faqs = []
    
    for faq in faq_list:
        score = 0
        
        # 1. 토픽 가중치 (3점)
        for kw in query_keywords:
            if kw in faq['topic']:
                score += 3
                
        # 2. 키워드 가중치 (2점)
        for kw in query_keywords:
            for faq_kw in faq['keywords']:
                if kw in faq_kw or faq_kw in kw:
                    score += 2
                    
        # 3. 답변 본문 가중치 (1점)
        for kw in query_keywords:
            if kw in faq['answer']:
                score += 1
                
        if score > 0:
            scored_faqs.append((score, faq))
            
    # 점수 높은 순 정렬, 점수가 같으면 ID 오름차순
    scored_faqs.sort(key=lambda x: (-x[0], x[1]['id']))
    
    # 최대 2개 선택
    selected = [item[1] for item in scored_faqs[:2]]
    return selected

def get_available_ollama_model(base_url, recommended):
    """
    로컬 Ollama API의 사용 가능한 모델 목록을 조회하여, 
    추천 모델이 존재하면 이를 반환하고 없으면 로컬의 실제 모델로 폴백 처리
    """
    try:
        response = requests.get(f"{base_url}/api/tags", timeout=3)
        if response.status_code == 200:
            models_data = response.json()
            available_models = [m['name'] for m in models_data.get('models', [])]
            print(f"Available local Ollama models: {available_models}")
            
            # 추천 모델이 정확히 있는지 확인
            if recommended in available_models:
                return recommended
            
            # 태그 부분을 떼어내고 모델 계열 이름 매칭 확인
            recommended_base = recommended.split(':')[0]
            for model in available_models:
                if model.split(':')[0] == recommended_base:
                    return model
            
            # 매칭 모델이 없으면 로컬에 있는 첫 번째 모델 사용
            if available_models:
                return available_models[0]
    except Exception as e:
        print(f"Ollama tag API query failed: {e}")
    return recommended

@app.route('/')
def index():
    return send_file('index.html')

@app.route('/api/query', methods=['POST'])
def query_faq():
    data = request.json or {}
    user_query = data.get('query', '').strip()
    
    if not user_query:
        return jsonify({'error': '질문을 입력해 주세요.'}), 400
        
    # 1. 질문과 관련 있는 FAQ 1~2건 검색
    matched_faqs = find_related_faqs(user_query, faqs)
    print(f"Matched FAQs for query '{user_query}': {[f['id'] for f in matched_faqs]}")
    
    # 2. Ollama 프롬프트 구성
    if matched_faqs:
        faq_contexts = "\n".join([
            f"- [{faq['id']}] (토픽: {faq['topic']}): {faq['answer']}"
            for faq in matched_faqs
        ])
    else:
        faq_contexts = "- (일치하는 FAQ 근거가 없습니다.)"
        
    prompt = f"""[시스템 설정]
당신은 공공기관 민원 응답 지원 AI입니다. 아래 제공되는 '참고 FAQ 근거 자료'에 근거하여 질문에 정확하고 간결하게 답변하세요.

[답변 규칙]
1. 반드시 아래의 '참고 FAQ 근거 자료'의 내용을 바탕으로 답변하세요. 근거에 없는 사실을 임의로 상상하거나 유추하여 답변하지 마세요.
2. 답변은 반드시 5문장 이내로 완료된 문장 형태로 정중하게 작성해 주세요.
3. 한국어 문법과 조사를 바르게 사용해 서술형으로 답변해 주세요.

[참고 FAQ 근거 자료]
{faq_contexts}

[민원인 질문]
{user_query}

[답변]
"""

    # 3. 로컬 Ollama 모델 획득 및 API 호출
    target_model = get_available_ollama_model(OLLAMA_BASE_URL, RECOMMENDED_MODEL)
    print(f"Using model for generation: {target_model}")
    
    payload = {
        "model": target_model,
        "prompt": prompt,
        "options": {
            "temperature": model_config.get("temperature", 0.2),
            "num_ctx": model_config.get("num_ctx", 2048),
            "num_predict": model_config.get("num_predict", 160)
        },
        "stream": False
    }
    
    answer_text = ""
    try:
        response = requests.post(f"{OLLAMA_BASE_URL}/api/generate", json=payload, timeout=180)
        if response.status_code == 200:
            answer_text = response.json().get('response', '').strip()
        else:
            answer_text = f"로컬 LLM 응답 오류 (Status Code: {response.status_code})"
    except Exception as e:
        answer_text = f"로컬 LLM 연결 실패: {str(e)}"
        
    # 4. 결과 응답
    result = {
        'answer': answer_text,
        'faqs': [
            {
                'id': faq['id'],
                'topic': faq['topic'],
                'department': faq['department']
            } for faq in matched_faqs
        ],
        'disclaimer': '⚠️ 민감정보 입력 금지 안내: 주민등록번호, 주소, 연락처 등 개인 식별이 가능한 민감정보는 절대 입력하지 마십시오.',
        'used_model': target_model
    }
    
    return jsonify(result)

if __name__ == '__main__':
    app.run(host='127.0.0.1', port=5000, debug=True)
