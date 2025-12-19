from flask import Flask, request, jsonify
from flask_cors import CORS
import requests
import re
import urllib.parse
import os

app = Flask(__name__)
# 보안 정책 최적화
CORS(app, resources={r"/*": {"origins": "*"}})

# 직접 입력 대신 서버 시스템에서 값을 가져오도록 설정
NAVER_CLIENT_ID = os.environ.get("NAVER_CLIENT_ID")
NAVER_CLIENT_SECRET = os.environ.get("NAVER_CLIENT_SECRET")

@app.route('/get_lowest_price', methods=['POST', 'OPTIONS'])
def get_lowest_price():
    if request.method == 'OPTIONS':
        return jsonify({"status": "ok"}), 200

    try:
        data = request.get_json()
        product_name = data.get('product_name', '')
        
        # 1. 검색어 정제 (정확도 향상을 위해 수식어 제거)
        clean_name = re.sub(r'\[.*?\]|\(.*?\)|정품|공식판매처|구매대행', '', product_name).strip()
        search_keyword = clean_name[:25]
        
        # 2. 네이버 쇼핑 API 호출: 'sim'(연관도/추천순)으로 10개 요청
        # 이렇게 해야 '부품' 대신 '본체' 위주의 결과가 먼저 나옵니다.
        encoded_query = urllib.parse.quote(search_keyword)
        url = f"https://openapi.naver.com/v1/search/shop.json?query={encoded_query}&display=10&sort=sim"
        
        headers = {
            "X-Naver-Client-Id": NAVER_CLIENT_ID,
            "X-Naver-Client-Secret": NAVER_CLIENT_SECRET
        }
        
        res = requests.get(url, headers=headers)
        res_json = res.json()
        items = res_json.get('items', [])

        if not items:
            return jsonify({"error": "검색 결과가 없습니다."}), 404

        # 3. 추천순 결과 내에서 실제 최저가 찾기
        processed_items = []
        for item in items:
            try:
                # 가격 및 배송비 정수 변환
                price = int(item.get('lprice', 0))
                raw_ship = str(item.get('shippingFee', '0'))
                ship_fee = int(raw_ship) if raw_ship.isdigit() else 0
                
                total_price = price + ship_fee
                
                # 너무 낮은 가격(예: 1만원 이하)은 부품일 확률이 높으므로 제외 (필요시 조정 가능)
                if total_price > 5000:
                    processed_items.append({
                        "title": re.sub(r'<.*?>', '', item['title']),
                        "total_price": total_price,
                        "link": item['link'],
                        "mallName": item.get('mallName', '네이버쇼핑')
                    })
            except:
                continue

        if not processed_items:
            return jsonify({"error": "유효한 상품을 찾지 못했습니다."}), 404

        # 4. 연관 상품 10개 중 합산 가격이 가장 낮은 것 선택
        best_item = min(processed_items, key=lambda x: x['total_price'])
        
        return jsonify({
            "title": best_item['title'],
            "lprice": best_item['total_price'],
            "naver_link": best_item['link'],
            "coupang_link": "https://link.coupang.com/a/dfyI2Y", # 본인의 파트너스 링크
            "mallName": best_item['mallName']
        })

    except Exception as e:
        print(f"🔥 서버 에러: {e}")
        return jsonify({"error": str(e)}), 500

if __name__ == '__main__':
    # 배포 환경을 위한 포트 설정 추가
    port = int(os.environ.get("PORT", 5000))

    app.run(host='0.0.0.0', port=port)
