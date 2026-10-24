"""로컬 API 호출과 Bearer 헤더를 한 곳에서 관리합니다."""
import requests
import re

API_URL = "http://127.0.0.1:8000"


class APIError(Exception):
    def __init__(self, message, status_code=None):
        self.detail = message
        text = str(message)
        if any(word in text for word in ('GEMINI_504', 'GEMINI_TIMEOUT')):
            text = '확인 시간이 길어져 중단했어요. 사진은 유지되니 잠시 후 다시 시도해주세요.'
        elif 'GEMINI_503' in text or 'AI 인증 서버에 연결' in text or 'Gemini 서비스를 일시적' in text:
            text = '지금은 사진 확인이 어려워요. 잠시 후 다시 시도해주세요.'
        elif 'API 키' in text or 'API_KEY' in text or 'FastAPI' in text or 'JSON' in text or '스키마' in text:
            text = '서비스 연결을 확인하고 있어요. 잠시 후 다시 시도해주세요.'
        elif any(word in text for word in ('한도', '할당량', '크레딧', '예산')):
            text = '현재 이용 가능한 요청량을 모두 사용했어요. 잠시 후 다시 이용해주세요.'
        elif any(word in text for word in ('Gemini', 'Exa', 'GROQ_')):
            text = '요청을 처리하지 못했어요. 잠시 후 다시 시도해주세요.'
        text = re.sub(r'\s*\((?:GEMINI|EXA|GROQ)_[A-Z0-9_]+\)', '', text)
        text = re.sub(r'\s*\(상태 코드: \d+\)', '', text)
        super().__init__(text)
        self.status_code = status_code


def _request(method, path, data=None, files=None, token=None, timeout=None):
    headers = {"Authorization": f"Bearer {token}"} if token else {}
    options = {"data": data, "files": files} if files else {"json": data}
    try:
        response = requests.request(method, f"{API_URL}{path}", headers=headers,
                                    timeout=timeout or (300 if files else 10), **options)
    except requests.Timeout:
        raise APIError("응답이 지연되었습니다. 구매내역을 확인한 뒤 다시 시도해주세요.") from None
    except requests.RequestException:
        raise APIError("서버에 연결할 수 없습니다. FastAPI 서버를 먼저 실행해주세요.") from None
    try:
        result = response.json()
    except ValueError:
        raise APIError("서버 응답을 읽을 수 없습니다.", response.status_code) from None
    if not response.ok:
        message = result.get("detail") if isinstance(result, dict) else None
        raise APIError(message if isinstance(message, str) else "요청을 처리할 수 없습니다.", response.status_code)
    return result


def register_user(username, password, display_name):
    return _request("POST", "/auth/register", {"username": username, "password": password, "display_name": display_name})


def login_user(username, password):
    return _request("POST", "/auth/login", {"username": username, "password": password})


def logout_user(token):
    return _request("POST", "/auth/logout", token=token)


def get_current_user(token):
    return _request("GET", "/auth/me", token=token)


def get_products():
    return _request("GET", "/products")


def get_product(product_id):
    return _request("GET", f"/products/{product_id}")


def get_my_purchases(token):
    return _request("GET", "/me/purchases", token=token)


def get_my_impact(token):
    return _request("GET", "/me/impact", token=token)


def get_my_impact_history(token):
    return _request("GET", "/me/impact/history", token=token)


def create_verification_challenge(token, product_id):
    return _request("POST", "/verification/challenge", {"product_id": product_id}, token=token)


def create_photo_challenge(token, product_id):
    return _request('POST', '/verification/photo-challenge', {'product_id': product_id}, token=token, timeout=100)


def verify_photo_purchase(token, product_id, challenge_id, photos):
    return _request('POST', '/purchases/verify-photos', {
        'product_id': product_id, 'challenge_id': challenge_id,
    }, token=token, timeout=240, files={
        f'photo_{index}': (f'capture_{index}', photo.getvalue(), photo.type)
        for index, photo in enumerate(photos, 1)
    })


def verify_purchase_ai(token, product_id, challenge_id, product_image):
    return _request("POST", "/purchases/verify-ai", {
        "product_id": product_id, "challenge_id": challenge_id,
    }, token=token, files={
        "product_image": ("product", product_image.getvalue(), product_image.type),
    })


def create_developer_purchase(token, product_id):
    return _request("POST", "/developer/purchases", {"product_id": product_id}, token=token)


def reset_developer_purchases(token):
    return _request("POST", "/developer/reset", token=token)


def recommend_products(token, query, conditions="", max_price=None):
    return _request("POST", "/recommendations", {"query": query, "conditions": conditions, "max_price": max_price}, token=token, timeout=240)


def get_monthly_ranking(token, month, include_tests=False):
    return _request("GET", f"/rankings/monthly?month={month}&include_tests={str(include_tests).lower()}", token=token)


def set_monthly_revenue(token, month, revenue_won):
    return _request("POST", "/developer/revenue", {"month": month, "revenue_won": revenue_won}, token=token)


def research_purchase_impact(token, purchase_id):
    return _request("POST", f"/me/purchases/{purchase_id}/impact-research", token=token)



def create_verification_kit(token, product_id):
    return _request('POST', '/developer/verification-kit', {'product_id': product_id}, token=token, timeout=30)



def report_product(token, product_id, reason):
    return _request('POST', f'/products/{product_id}/report', {'reason':reason}, token=token)


def get_product_reports(token):
    return _request('GET', '/me/product-reports', token=token)



def get_ai_usage(token):
    return _request('GET', '/developer/ai-usage', token=token)


def submit_reward_evidence(token, month, image):
    return _request('POST','/me/reward-evidence',{'month':month},token=token,
                    files={'image':('evidence',image.getvalue(),image.type)})


def get_reward_evidence(token, month):
    return _request('GET',f'/developer/reward-evidence?month={month}',token=token)


def read_reward_evidence(token, key):
    try:
        response=requests.get(f'{API_URL}/reward-evidence/{key}',headers={'Authorization':f'Bearer {token}'},timeout=20)
        response.raise_for_status()
        return response.content
    except requests.RequestException:
        raise APIError('증빙 파일을 열지 못했습니다.') from None


def review_reward(token,month,user_id,decision,note):
    return _request('POST',f'/developer/reward-reviews/{month}/{user_id}',
                    {'decision':decision,'note':note},token=token)


def get_reward_purchases(token,month,user_id):
    return _request('GET',f'/developer/reward-purchases?month={month}&user_id={user_id}',token=token)


def get_admin_overview(token):
    return _request('GET','/developer/admin/overview',token=token)


def get_admin_purchases(token,user_id=None,status=None,offset=0):
    query=f'offset={offset}'
    if user_id is not None:query+=f'&user_id={user_id}'
    if status:query+=f'&status={status}'
    return _request('GET','/developer/admin/purchases?'+query,token=token)


def get_admin_purchase(token,purchase_id):
    return _request('GET',f'/developer/admin/purchases/{purchase_id}',token=token)


def get_admin_attempts(token,user_id=None,failed_only=False,offset=0):
    query=f'offset={offset}&failed_only={str(failed_only).lower()}'
    if user_id is not None:query+=f'&user_id={user_id}'
    return _request('GET','/developer/admin/attempts?'+query,token=token)


def reset_admin_purchase(token,purchase_id,reason):
    return _request('POST',f'/developer/admin/purchases/{purchase_id}/reset',
                    {'confirm':True,'reason':reason},token=token)


def reset_admin_tests(token,reason):
    return _request('POST','/developer/admin/reset-my-tests',{'confirm':True,'reason':reason},token=token)


def cancel_admin_challenges(token,user_id,product_id,reason):
    return _request('POST','/developer/admin/cancel-challenges',
                    {'confirm':True,'user_id':user_id,'product_id':product_id,'reason':reason},token=token)


def get_admin_actions(token):
    return _request('GET','/developer/admin/actions',token=token)
