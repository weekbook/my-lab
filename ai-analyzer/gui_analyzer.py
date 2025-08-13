import os
import time
import google.generativeai as genai
from dotenv import load_dotenv
import tkinter as tk
from tkinter import filedialog, scrolledtext
import threading
import queue

# --- 핵심 분석 로직 (이전 main.py의 기능을 함수 안으로 옮김) ---
def start_analysis_logic(target_directory, log_queue, stop_event):
    """실제 분석을 수행하는 함수. 별도의 스레드에서 실행됩니다."""
    
    def find_project_files(target_dir, extensions):
        found_files = []
        for root, dirs, files in os.walk(target_dir):
            for file in files:
                if file.endswith(tuple(extensions)):
                    full_path = os.path.join(root, file)
                    found_files.append(full_path)
        return found_files

    def group_files_by_feature(file_list):
        feature_groups = {}
        for file_path in file_list:
            base_name = os.path.basename(file_path).split('.')[0]
            feature_name = base_name.replace('Controller', '').replace('Service', '').replace('Mapper', '')
            if feature_name not in feature_groups:
                feature_groups[feature_name] = []
            feature_groups[feature_name].append(file_path)
        return feature_groups
    
    try:
        # --- 1. 파일 스캔 ---
        log_queue.put(f"'{target_directory}' 에서 파일 스캔을 시작합니다...")
        extensions = ['.java', '.jsp', '.js', '.xml']
        all_files = find_project_files(target_directory, extensions)
        
        if not all_files:
            log_queue.put("분석할 파일을 찾지 못했습니다. 경로를 확인해주세요.")
            return

        log_queue.put(f"총 {len(all_files)}개의 파일을 찾았습니다. 기능 단위로 그룹핑합니다...")
        analysis_units = group_files_by_feature(all_files)
        total_units = len(analysis_units)
        log_queue.put(f"🎉 총 {total_units}개의 기능 단위에 대한 '핵심 위험 분석'을 시작합니다.")

        # --- 2. AI 설정 ---
        load_dotenv()
        api_key = os.getenv("GOOGLE_API_KEY")
        if not api_key:
            log_queue.put("오류: GOOGLE_API_KEY를 .env 파일에서 찾을 수 없습니다.")
            return
        genai.configure(api_key=api_key)
        
        # --- 3. 분석 및 리포트 생성 ---
        with open("critical_issues_report.md", "w", encoding='utf-8') as report_file:
            for i, (feature_name, files_in_unit) in enumerate(analysis_units.items()):
                # 중지 신호를 확인하고 루프를 탈출
                if stop_event.is_set():
                    log_queue.put("\n!!! 분석이 사용자에 의해 중지되었습니다 !!!")
                    break

                log_queue.put(f"\n[{i+1}/{total_units}] 기능 유닛 '{feature_name}' 분석 중...")
                
                combined_code = ""
                # (이하 코드 결합 및 프롬프트 생성 로직은 이전과 동일)
                for file_path in files_in_unit:
                    try:
                        with open(file_path, 'r', encoding='utf-8') as f:
                            file_content = f.read()
                        combined_code += f"\n\n--- 파일: {os.path.basename(file_path)} ---\n{file_content}"
                    except Exception:
                        pass
                
                prompt = f"""
                너는 운영 서버의 심각한 장애를 막기 위해 긴급 투입된 20년차 시니어 아키텍트다.
                아래 코드 묶음에서, 오직 운영에 심각한 문제를 일으킬 수 있는 '치명적인 위험'만 찾아내야 한다.
                [분석 목표]: 1. 치명적인 런타임 오류(NPE 등) 2. 심각한 보안 취약점 3. 대용량 데이터 처리 시 성능 병목
                [분석 제외]: 단순 스타일(변수명, 주석, 포맷팅 등)은 절대 언급하지 마라.
                결과는 심각도 순서대로 `[심각]`, `[경고]`, `[권장]` 태그를 붙여서 핵심만 요약 보고해라.
                [분석할 코드 묶음]:\n{combined_code}
                """

                try:
                    model = genai.GenerativeModel('gemini-2.5-pro') # 성공했던 모델명 사용
                    response = model.generate_content(prompt, request_options={"timeout": 600}) # 타임아웃 10분 설정
                    analysis_result = response.text
                    log_queue.put(f"✅ 분석 완료. 결과를 리포트에 추가합니다.")
                except Exception as e:
                    analysis_result = f"오류 발생: '{feature_name}' 유닛 분석 중 문제 발생 - {e}"
                    log_queue.put(analysis_result)
                
                report_file.write(f"\n\n---\n\n## 💎 기능 유닛: {feature_name}\n\n{analysis_result}")
                time.sleep(1) # API 과부하 방지

        if not stop_event.is_set():
            log_queue.put("\n\n🎉🎉🎉 모든 분석 완료! 'critical_issues_report.md' 파일을 확인하세요! 🎉🎉🎉")

    except Exception as e:
        log_queue.put(f"\n치명적 오류 발생: 분석 프로세스를 중단합니다. - {e}")
    finally:
        log_queue.put("ANALYSIS_COMPLETE") # GUI에 종료 신호 전달


# --- GUI 애플리케이션 클래스 ---
class App:
    def __init__(self, root):
        self.root = root
        self.root.title("AI 코드 위험 분석기 v1.0")
        self.root.geometry("800x600")

        self.thread = None
        self.stop_event = threading.Event()

        # 프레임 설정
        top_frame = tk.Frame(root, padx=10, pady=10)
        top_frame.pack(fill=tk.X)

        # 경로 입력 위젯
        tk.Label(top_frame, text="분석할 폴더 경로:").pack(side=tk.LEFT)
        self.path_var = tk.StringVar()
        self.path_entry = tk.Entry(top_frame, textvariable=self.path_var, width=60)
        self.path_entry.pack(side=tk.LEFT, expand=True, fill=tk.X, padx=5)
        
        self.browse_button = tk.Button(top_frame, text="폴더 찾아보기", command=self.browse_folder)
        self.browse_button.pack(side=tk.LEFT)

        # 실행/중지 버튼
        button_frame = tk.Frame(root, padx=10, pady=5)
        button_frame.pack(fill=tk.X)
        self.start_button = tk.Button(button_frame, text="분석 시작", command=self.start_analysis, bg="lightblue")
        self.start_button.pack(side=tk.LEFT)
        self.stop_button = tk.Button(button_frame, text="분석 중지", command=self.stop_analysis, state=tk.DISABLED, bg="lightcoral")
        self.stop_button.pack(side=tk.LEFT, padx=5)

        # 로그 출력 영역
        log_frame = tk.Frame(root, padx=10, pady=10)
        log_frame.pack(expand=True, fill=tk.BOTH)
        self.log_area = scrolledtext.ScrolledText(log_frame, wrap=tk.WORD, state=tk.DISABLED)
        self.log_area.pack(expand=True, fill=tk.BOTH)

        # 메시지 큐 설정
        self.log_queue = queue.Queue()
        self.root.after(100, self.process_queue)

    def browse_folder(self):
        directory = filedialog.askdirectory()
        if directory:
            self.path_var.set(directory)

    def start_analysis(self):
        target_path = self.path_var.get()
        if not target_path or not os.path.isdir(target_path):
            tk.messagebox.showerror("오류", "유효한 폴더 경로를 선택해주세요.")
            return
        
        self.start_button.config(state=tk.DISABLED)
        self.stop_button.config(state=tk.NORMAL)
        self.log_area.config(state=tk.NORMAL)
        self.log_area.delete('1.0', tk.END)
        
        self.stop_event.clear()
        self.thread = threading.Thread(target=start_analysis_logic, args=(target_path, self.log_queue, self.stop_event))
        self.thread.start()

    def stop_analysis(self):
        if self.thread and self.thread.is_alive():
            self.stop_event.set()
            self.stop_button.config(state=tk.DISABLED)

    def process_queue(self):
        try:
            while True:
                message = self.log_queue.get_nowait()
                if message == "ANALYSIS_COMPLETE":
                    self.start_button.config(state=tk.NORMAL)
                    self.stop_button.config(state=tk.DISABLED)
                else:
                    self.log_area.config(state=tk.NORMAL)
                    self.log_area.insert(tk.END, message + "\n")
                    self.log_area.see(tk.END)
                    self.log_area.config(state=tk.DISABLED)
        except queue.Empty:
            pass
        finally:
            self.root.after(100, self.process_queue)

# --- 애플리케이션 실행 ---
if __name__ == "__main__":
    root = tk.Tk()
    app = App(root)
    root.mainloop()
