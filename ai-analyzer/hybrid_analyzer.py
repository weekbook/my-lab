import os
import time
import tkinter as tk
from tkinter import filedialog, scrolledtext, messagebox
from tkinter.font import nametofont

# --- GUI 디자인과 드래그앤드롭 라이브러리 ---
import ttkbootstrap as ttk
from ttkbootstrap.constants import *
from tkinterdnd2 import DND_FILES, TkinterDnD

# --- 백엔드 분석 로직 (AI 관련) ---
import google.generativeai as genai
from dotenv import load_dotenv
import threading
import queue

# --- 백엔드 로직: 폴더 분석 ---
def start_folder_analysis_logic(target_directory, log_queue, stop_event):
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
        log_queue.put(f"'{target_directory}' 에서 폴더 전체 분석을 시작합니다...")
        extensions = ['.java', '.jsp', '.js', '.xml']
        all_files = find_project_files(target_directory, extensions)
        
        if not all_files:
            log_queue.put("분석할 파일을 찾지 못했습니다.")
            return

        analysis_units = group_files_by_feature(all_files)
        total_units = len(analysis_units)
        log_queue.put(f"🎉 총 {total_units}개의 기능 단위에 대한 분석을 시작합니다.")

        load_dotenv()
        api_key = os.getenv("GOOGLE_API_KEY")
        if not api_key:
            log_queue.put("오류: GOOGLE_API_KEY를 찾을 수 없습니다.")
            return
        genai.configure(api_key=api_key)

        with open("folder_analysis_report.md", "w", encoding='utf-8') as report_file:
            report_file.write("# AI 코드 분석 보고서 (폴더 전체)\n")
            for i, (feature_name, files_in_unit) in enumerate(analysis_units.items()):
                if stop_event.is_set():
                    log_queue.put("\n!!! 분석이 중지되었습니다 !!!")
                    break
                
                log_queue.put(f"\n[{i+1}/{total_units}] 기능 유닛 '{feature_name}' 분석 중...")
                combined_code = ""
                for file_path in files_in_unit:
                    try:
                        with open(file_path, 'r', encoding='utf-8') as f:
                            combined_code += f"\n\n--- 파일: {os.path.basename(file_path)} ---\n{f.read()}"
                    except Exception: pass
                
                prompt = f"""너는 운영 서버의 심각한 장애를 막기 위해 긴급 투입된 20년차 시니어 아키텍트다. 아래 코드 묶음에서, 오직 운영에 심각한 문제를 일으킬 수 있는 '치명적인 위험'만 찾아내라. [분석 목표]: 1. 치명적인 런타임 오류(NPE 등) 2. 심각한 보안 취약점 3. 대용량 데이터 처리 시 성능 병목. [분석 제외]: 단순 스타일(변수명, 주석, 포맷팅 등)은 절대 언급하지 마라. 결과는 심각도 순서대로 `[심각]`, `[경고]`, `[권장]` 태그를 붙여서 핵심만 요약 보고해라. [분석할 코드 묶음]:\n{combined_code}"""
                
                try:
                    model = genai.GenerativeModel('gemini-2.5-pro')
                    generation_config = genai.types.GenerationConfig(max_output_tokens=8192)
                    response = model.generate_content(prompt, 
                                  generation_config=generation_config,
                                  request_options={"timeout": 600})
                    analysis_result = response.text
                    log_queue.put(f"✅ 분석 완료.")
                except Exception as e:
                    analysis_result = f"오류 발생: {e}"
                    log_queue.put(analysis_result)
                
                report_file.write(f"\n\n---\n\n## 💎 기능 유닛: {feature_name}\n\n{analysis_result}")
                time.sleep(1)

        if not stop_event.is_set():
            log_queue.put("\n\n🎉🎉🎉 폴더 분석 완료! 'folder_analysis_report.md' 파일을 확인하세요! 🎉🎉🎉")

    except Exception as e:
        log_queue.put(f"\n치명적 오류 발생: {e}")
    finally:
        log_queue.put("ANALYSIS_COMPLETE")

# --- 백엔드 로직: 개별 파일 분석 ---
def start_file_analysis_logic(file_list, log_queue, stop_event):
    try:
        total_files = len(file_list)
        log_queue.put(f"총 {total_files}개의 개별 파일 분석을 시작합니다...")

        load_dotenv()
        api_key = os.getenv("GOOGLE_API_KEY")
        if not api_key:
            log_queue.put("오류: GOOGLE_API_KEY를 찾을 수 없습니다.")
            return
        genai.configure(api_key=api_key)

        with open("file_analysis_report.md", "w", encoding='utf-8') as report_file:
            report_file.write("# AI 코드 분석 보고서 (개별 파일)\n")
            for i, file_path in enumerate(file_list):
                if stop_event.is_set():
                    log_queue.put("\n!!! 분석이 중지되었습니다 !!!")
                    break

                log_queue.put(f"\n[{i+1}/{total_files}] 파일 '{os.path.basename(file_path)}' 분석 중...")
                
                try:
                    with open(file_path, 'r', encoding='utf-8') as f:
                        code_to_analyze = f.read()
                    
                    prompt = f"""너는 운영 서버의 심각한 장애를 막기 위해 긴급 투입된 20년차 시니어 아키텍트다. 아래 단일 소스코드 파일에서, 오직 운영에 심각한 문제를 일으킬 수 있는 '치명적인 위험'만 찾아내라. [분석 목표]: 1. 치명적인 런타임 오류(NPE 등) 2. 심각한 보안 취약점 3. 대용량 데이터 처리 시 성능 병목. [분석 제외]: 단순 스타일(변수명, 주석, 포맷팅 등)은 절대 언급하지 마라. 결과는 심각도 순서대로 `[심각]`, `[경고]`, `[권장]` 태그를 붙여서 핵심만 요약 보고해라. [분석할 코드]:\n{code_to_analyze}"""
                    
                    model = genai.GenerativeModel('gemini-2.5-pro')
                    response = model.generate_content(prompt, request_options={"timeout": 600})
                    analysis_result = response.text
                    log_queue.put(f"✅ 분석 완료.")
                except Exception as e:
                    analysis_result = f"오류 발생: {e}"
                    log_queue.put(analysis_result)

                report_file.write(f"\n\n---\n\n## 📄 분석 파일: {file_path}\n\n{analysis_result}")
                time.sleep(1)

        if not stop_event.is_set():
            log_queue.put("\n\n🎉🎉🎉 개별 파일 분석 완료! 'file_analysis_report.md' 파일을 확인하세요! 🎉🎉🎉")

    except Exception as e:
        log_queue.put(f"\n치명적 오류 발생: {e}")
    finally:
        log_queue.put("ANALYSIS_COMPLETE")

# --- GUI 애플리케이션 클래스 ---
class App:
    def __init__(self, root):
        self.root = root
        self.root.title("하이브리드 AI 코드 분석기 v6.0 (Final)")
        self.root.geometry("850x750")

        self.thread = None
        self.stop_event = threading.Event()

        main_frame = ttk.Frame(root, padding=15)
        main_frame.pack(expand=True, fill=BOTH)

        self.notebook = ttk.Notebook(main_frame)
        self.notebook.pack(expand=True, fill=BOTH)

        self.folder_tab = ttk.Frame(self.notebook, padding=10)
        self.notebook.add(self.folder_tab, text="📁 폴더 전체 분석")
        self.create_folder_tab_widgets()

        self.file_tab = ttk.Frame(self.notebook, padding=10)
        self.notebook.add(self.file_tab, text="📄 개별 파일 분석")
        self.create_file_tab_widgets()

        self.file_listbox.drop_target_register(DND_FILES)
        self.file_listbox.dnd_bind('<<Drop>>', self.drop_files)

        self.stop_button = ttk.Button(main_frame, text="⏹️ 분석 중지", command=self.stop_analysis, bootstyle=(DANGER, OUTLINE), state=DISABLED)
        self.stop_button.pack(pady=(10, 0), ipady=5)

        log_frame = ttk.Labelframe(main_frame, text="분석 로그", padding=10)
        log_frame.pack(expand=True, fill=BOTH, pady=10)
        
        self.log_area = scrolledtext.ScrolledText(log_frame, wrap=tk.WORD, state=DISABLED)
        self.log_area.configure(bg="#2a2a2a", fg="#cccccc", insertbackground="white", relief="flat", font=("Malgun Gothic", 9))
        self.log_area.pack(expand=True, fill=BOTH)

        self.log_queue = queue.Queue()
        self.root.after(100, self.process_queue)

    def create_folder_tab_widgets(self):
        frame = self.folder_tab
        ttk.Label(frame, text="\n프로젝트 전체를 기능 단위로 묶어 심층 분석합니다.\n", font=("Malgun Gothic", 11, "bold")).pack(pady=5)
        
        path_frame = ttk.Frame(frame)
        path_frame.pack(fill=X, pady=10)
        
        ttk.Label(path_frame, text="프로젝트 폴더:").pack(side=LEFT, padx=(0, 5))
        self.folder_path_var = tk.StringVar()
        ttk.Entry(path_frame, textvariable=self.folder_path_var, width=60).pack(side=LEFT, expand=True, fill=X)
        
        # 유니코드 기호를 아이콘으로 사용
        ttk.Button(path_frame, text="📂 찾아보기", command=self.browse_folder, bootstyle=SECONDARY).pack(side=LEFT, padx=(5, 0))

        self.start_folder_button = ttk.Button(frame, text="▶️ 폴더 분석 시작", command=self.start_folder_analysis, bootstyle=PRIMARY)
        self.start_folder_button.pack(pady=20, ipady=10, ipadx=20)

    def create_file_tab_widgets(self):
        frame = self.file_tab
        ttk.Label(frame, text="\n분석하고 싶은 개별 파일들을 선택하여 분석합니다.\n", font=("Malgun Gothic", 11, "bold")).pack(pady=5)

        list_frame = ttk.Frame(frame)
        list_frame.pack(expand=True, fill=BOTH, pady=10)

        self.file_listbox = tk.Listbox(list_frame, selectmode=tk.EXTENDED)
        self.file_listbox.configure(bg="#333333", fg="white", selectbackground="#0d6efd", selectforeground="white", relief="flat", highlightthickness=0, font=("Malgun Gothic", 9))
        self.file_listbox.pack(side=LEFT, expand=True, fill=BOTH)
        
        self.file_listbox.insert(tk.END, "이곳에 파일을 드래그 앤 드롭 하거나,")
        self.file_listbox.insert(tk.END, "'파일 추가' 버튼을 눌러 선택하세요.")
        self.file_listbox.config(fg="grey")

        list_button_frame = ttk.Frame(list_frame)
        list_button_frame.pack(side=LEFT, fill=Y, padx=10)
        
        # 유니코드 기호를 아이콘으로 사용
        ttk.Button(list_button_frame, text="➕ 파일 추가", command=self.add_files, bootstyle=INFO).pack(pady=5, fill=X, ipady=3)
        ttk.Button(list_button_frame, text="🗑️ 선택 삭제", command=self.remove_files, bootstyle=(DANGER, OUTLINE)).pack(pady=5, fill=X, ipady=3)
        ttk.Button(list_button_frame, text="❌ 전체 삭제", command=self.clear_file_list, bootstyle=(SECONDARY, OUTLINE)).pack(pady=5, fill=X, ipady=3)
        
        self.start_files_button = ttk.Button(frame, text="▶️ 선택 파일 분석 시작", command=self.start_file_analysis, bootstyle=SUCCESS)
        self.start_files_button.pack(pady=20, ipady=10, ipadx=20)

    def browse_folder(self):
        directory = filedialog.askdirectory()
        if directory:
            self.folder_path_var.set(directory)
            
    def drop_files(self, event):
        """파일을 드래그 앤 드롭했을 때 실행되는 함수"""
        # 안내 문구가 있다면 먼저 삭제
        if "이곳에 파일을" in self.file_listbox.get(0):
            self.file_listbox.delete(0, tk.END)
            self.file_listbox.config(fg="black") # 글자색을 다시 검은색으로
            
        # event.data는 '{C:/.../file1.java} {C:/.../file2.js}' 와 같은 형식의 문자열
        files_to_add = self.root.tk.splitlist(event.data)
        for file in files_to_add:
            if file not in self.file_listbox.get(0, tk.END):
                self.file_listbox.insert(tk.END, file)

    def add_files(self):
        files = filedialog.askopenfilenames(title="분석할 파일을 선택하세요")
        for file in files:
            if file not in self.file_listbox.get(0, tk.END):
                self.file_listbox.insert(tk.END, file)

    def remove_files(self):
        selected_indices = self.file_listbox.curselection()
        for i in sorted(selected_indices, reverse=True):
            self.file_listbox.delete(i)
    
    def clear_file_list(self):
        """파일 목록을 모두 지우고 안내 문구를 다시 표시합니다."""
        self.file_listbox.delete(0, tk.END)
        self.file_listbox.insert(tk.END, "이곳에 파일을 드래그 앤 드롭 하거나,")
        self.file_listbox.insert(tk.END, "'파일 추가' 버튼을 눌러 선택하세요.")
        self.file_listbox.config(fg="grey")

    def start_folder_analysis(self):
        target_path = self.folder_path_var.get()
        if not target_path or not os.path.isdir(target_path):
            messagebox.showerror("오류", "유효한 폴더 경로를 선택해주세요.")
            return
        
        self.disable_ui() # UI 비활성화 함수 호출

        # 분석 스레드 직접 시작
        self.stop_event.clear()
        self.thread = threading.Thread(target=start_folder_analysis_logic, args=(target_path, self.log_queue, self.stop_event))
        self.thread.start()

    def start_file_analysis(self):
        # 목록에 있는 모든 항목을 일단 가져옵니다.
        all_items = self.file_listbox.get(0, tk.END)
        
        # 안내 문구를 제외한 실제 파일 경로만 필터링하여 새로운 리스트를 만듭니다.
        files_to_analyze = [
            item for item in all_items 
            if "이곳에 파일을" not in item and "'파일 추가' 버튼을" not in item
        ]

        # 실제 분석할 파일이 있는지 다시 한번 확인합니다.
        if not files_to_analyze:
            messagebox.showerror("오류", "분석할 파일을 하나 이상 추가해주세요.")
            return

        self.disable_ui()
        
        # 필터링된, 진짜 파일 목록만 분석 스레드로 전달합니다.
        self.stop_event.clear()
        self.thread = threading.Thread(target=start_file_analysis_logic, args=(files_to_analyze, self.log_queue, self.stop_event))
        self.thread.start()

    def disable_ui(self):
        """분석 시작 시 UI 컨트롤들을 비활성화합니다."""
        # 각 탭을 순회하며 비활성화
        for i in range(len(self.notebook.tabs())):
            self.notebook.tab(i, state="disabled")
        
        self.stop_button.config(state=tk.NORMAL)
        self.log_area.config(state=tk.NORMAL)
        self.log_area.delete('1.0', tk.END)

    def enable_ui(self):
        """분석 종료 시 UI 컨트롤들을 다시 활성화합니다."""
        # 각 탭을 순회하며 활성화
        for i in range(len(self.notebook.tabs())):
            self.notebook.tab(i, state="normal")
        
        self.stop_button.config(state=tk.DISABLED)

    def stop_analysis(self):
        if self.thread and self.thread.is_alive():
            self.stop_event.set()
            self.stop_button.config(state=tk.DISABLED)

    def process_queue(self):
        try:
            while True:
                message = self.log_queue.get_nowait()
                if message == "ANALYSIS_COMPLETE":
                    self.enable_ui() # UI 활성화 함수 호출
                else:
                    self.log_area.config(state=tk.NORMAL)
                    self.log_area.insert(tk.END, message + "\n")
                    self.log_area.see(tk.END)
                    self.log_area.config(state=tk.DISABLED)
        except queue.Empty:
            pass
        finally:
            self.root.after(100, self.process_queue)

if __name__ == "__main__":
    root = TkinterDnD.Tk()
    style = ttk.Style(theme="darkly")

    # --- 애플리케이션 기본 폰트 설정 ---
    default_font = nametofont("TkDefaultFont")
    default_font.configure(family="Malgun Gothic", size=10)
    root.option_add("*Font", default_font)

    app = App(root)
    root.mainloop()
