import os
import time
import google.generativeai as genai
from dotenv import load_dotenv

# --- 1단계: 프로젝트 설정 ---
TARGET_DIRECTORY = r"D:\workspace_ifez\ifez\web-user\src\main\java\com\pentachord\ctrl\commissioner" # 사용자님의 실제 경로
TARGET_EXTENSIONS = ['.java', '.jsp', '.js', '.xml']

# --- 2단계: 프로젝트 파일 스캔 ---
def find_project_files(target_dir, extensions):
    # (이 부분은 이전과 동일하므로 생략)
    found_files = []
    for root, dirs, files in os.walk(target_dir):
        for file in files:
            if file.endswith(tuple(extensions)):
                full_path = os.path.join(root, file)
                found_files.append(full_path)
    return found_files

# --- 3단계: 기능 단위 그룹핑 ---
def group_files_by_feature(file_list):
    # (이 부분은 이전과 동일하므로 생략)
    feature_groups = {}
    for file_path in file_list:
        base_name = os.path.basename(file_path).split('.')[0]
        feature_name = base_name.replace('Controller', '').replace('Service', '').replace('Mapper', '')
        if feature_name not in feature_groups:
            feature_groups[feature_name] = []
        feature_groups[feature_name].append(file_path)
    return feature_groups

# --- 4단계: AI 분석 설정 ---
load_dotenv()
api_key = os.getenv("GOOGLE_API_KEY")
if not api_key:
    print("오류: GOOGLE_API_KEY를 찾을 수 없습니다.")
    exit()
genai.configure(api_key=api_key)

# --- 5단계: 메인 실행 로직 ---
if __name__ == "__main__":
    print(f"'{TARGET_DIRECTORY}' 에서 파일 스캔을 시작합니다...")
    all_files = find_project_files(TARGET_DIRECTORY, TARGET_EXTENSIONS)
    
    if not all_files:
        print("분석할 파일을 찾지 못했습니다.")
        exit()

    print(f"총 {len(all_files)}개의 파일을 찾았습니다. 기능 단위로 그룹핑합니다...")
    analysis_units = group_files_by_feature(all_files)
    total_units = len(analysis_units)
    print(f"🎉 총 {total_units}개의 기능 단위에 대한 '핵심 위험 분석'을 시작합니다.")

    # 새로운 리포트 파일 이름
    with open("critical_issues_report.md", "w", encoding='utf-8') as report_file:
        
        for i, (feature_name, files_in_unit) in enumerate(analysis_units.items()):
            print(f"\n[{i+1}/{total_units}] 기능 유닛 '{feature_name}' 분석 중...")
            
            combined_code = ""
            for file_path in files_in_unit:
                try:
                    with open(file_path, 'r', encoding='utf-8') as f:
                        file_content = f.read()
                    combined_code += f"\n\n--- 파일: {os.path.basename(file_path)} ---\n"
                    combined_code += file_content
                except Exception as e:
                    pass # 오류가 나는 파일은 일단 무시

            # ***** 여기가 핵심! 프롬프트를 완전히 교체했습니다 *****
            prompt = f"""
            너는 지금 운영 서버의 심각한 장애를 막기 위해 긴급 투입된 20년차 시니어 아키텍트다.
            아래 코드 묶음에서, **오직 운영에 심각한 문제를 일으킬 수 있는 '치명적인 위험'만** 찾아내야 한다.
            
            [분석할 코드 묶음]
            {combined_code}
            ---

            [분석 목표 - 이것만 찾아라]
            1.  **치명적인 런타임 오류:** NullPointerException(NPE), 배열 인덱스 오류, 잘못된 형 변환 등 프로그램 중단을 유발할 수 있는 코드.
            2.  **심각한 보안 취약점:** SQL Injection, 크로스 사이트 스크립팅(XSS), CSRF 등 외부 공격에 직접적인 빌미를 제공하는 코드.
            3.  **대용량 데이터 처리 시 성능 병목:** 데이터가 수만 건 이상으로 늘어났을 때 속도가 급격히 저하될 것이 명백한 쿼리(Full Scan 등)나 비효율적인 루프 로직.
            
            [분석 제외 - 이것은 절대 언급하지 마라]
            -   단순 변수명, 메서드명 등 네이밍 스타일
            -   주석 관련 스타일
            -   코드 포맷팅 및 줄 바꿈 스타일
            -   사소한 성능 개선 (예: String '+' 대신 StringBuilder 사용 등)

            결과는 심각도 순서대로 `[심각]`, `[경고]`, `[권장]` 태그를 붙여서 핵심만 요약 보고해라.
            """

            try:
                model = genai.GenerativeModel('gemini-2.5-pro') # 성공했던 모델명 사용
                response = model.generate_content(prompt)
                analysis_result = response.text
                print(f"✅ 분석 완료. 위험 요소를 리포트에 추가합니다.")

            except Exception as e:
                analysis_result = f"오류 발생: '{feature_name}' 유닛 분석 중 문제 발생 - {e}"
                print(analysis_result)
            
            report_file.write(f"\n\n---\n\n## 💎 기능 유닛: {feature_name}\n\n{analysis_result}")
            time.sleep(1) # 1초 휴식

    print("\n\n🎉🎉🎉 핵심 위험 분석 완료! 'critical_issues_report.md' 파일을 확인하세요! 🎉🎉🎉")
