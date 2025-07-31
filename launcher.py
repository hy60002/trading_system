import sys
import os
import subprocess
import time
import psutil
from PyQt6.QtWidgets import QApplication, QWidget, QVBoxLayout, QPushButton, QLabel, QTextEdit
from PyQt6.QtGui import QFont, QPalette, QColor
from PyQt6.QtCore import Qt, QTimer

# Matplotlib 임베딩
from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg as FigureCanvas
from matplotlib.figure import Figure
import sys
import os
import matplotlib.pyplot as plt
import matplotlib.font_manager as fm  # 🔹 추가된 코드

# ✅ 한글 폰트 설정
plt.rcParams['font.family'] = 'Malgun Gothic'
plt.rcParams['axes.unicode_minus'] = False

# 기존 코드...

import pandas as pd

LOG_FILE = "gpt_log.txt"
TRADE_LOG_FILE = "trade_log.csv"

def check_process_running(script_name):
    """특정 프로세스가 실행 중인지 확인하는 함수"""
    for process in psutil.process_iter(attrs=['pid', 'name', 'cmdline']):
        try:
            cmdline = " ".join(process.info['cmdline']) if process.info['cmdline'] else ""
            if script_name in cmdline:
                return True
        except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
            continue
    return False

def get_trading_status():
    return "✅ ai_auto_trading.py 실행 중" if check_process_running("ai_auto_trading") else "❌ ai_auto_trading.py 중지"

def get_gpt_status():
    return "✅ gpt_analysis.py 실행 중" if check_process_running("gpt_analysis") else "❌ gpt_analysis.py 중지"

def load_gpt_log():
    """GPT 로그 파일에서 최신 분석 결과를 읽어오는 함수"""
    if not os.path.exists(LOG_FILE):
        return "⚠️ No GPT report available."
    try:
        with open(LOG_FILE, "r", encoding="utf-8") as f:
            logs = f.readlines()
            logs = [line.strip() for line in logs if line.strip()]
            return "\n".join(logs[-5:]) if logs else "⚠️ No recent GPT report available."
    except Exception as e:
        return f"🚨 로그 파일 읽기 오류: {e}"

def run_program(script_name):
    """특정 Python 스크립트를 실행하는 함수 (중복 실행 방지)"""
    if check_process_running(script_name):
        print(f"⚠️ 이미 실행 중: {script_name}")
        return None
    process = subprocess.Popen([sys.executable, script_name], creationflags=subprocess.CREATE_NEW_CONSOLE)
    time.sleep(1)
    print(f"✅ 실행됨: {script_name}")
    return process

def kill_process_tree(pid):
    """psutil을 사용하여 프로세스 트리 전체를 종료하는 함수"""
    try:
        parent = psutil.Process(pid)
        children = parent.children(recursive=True)
        for child in children:
            child.kill()
        parent.kill()
    except Exception as e:
        print(f"Error terminating process tree for PID {pid}: {e}")

class TradingChart(FigureCanvas):
    """Matplotlib 차트를 포함한 위젯: 실시간 가격 차트 및 매매 내역 표시"""
    def __init__(self, parent=None, width=7, height=4, dpi=100):
        self.fig = Figure(figsize=(width, height), dpi=dpi)
        self.ax = self.fig.add_subplot(111)
        super().__init__(self.fig)
        self.setParent(parent)
        self.plot_initial()

    def plot_initial(self):
        self.ax.clear()
        self.ax.text(0.5, 0.5, "실시간 매매 내역 없음", 
                     horizontalalignment='center', verticalalignment='center',
                     transform=self.ax.transAxes, fontsize=12)
        self.draw()

    def update_chart(self):
        self.ax.clear()
        if not os.path.exists(TRADE_LOG_FILE):
            self.ax.text(0.5, 0.5, "trade_log.csv 파일이 없습니다.", 
                         horizontalalignment='center', verticalalignment='center',
                         transform=self.ax.transAxes, fontsize=12)
        else:
            try:
                df = pd.read_csv(TRADE_LOG_FILE)
                if df.empty:
                    self.ax.text(0.5, 0.5, "매매 내역이 없습니다.", 
                                 horizontalalignment='center', verticalalignment='center',
                                 transform=self.ax.transAxes, fontsize=12)
                else:
                    # trade_log.csv에는 timestamp, entry_price, exit_price, return_pct, size 등이 있다고 가정
                    df['timestamp'] = pd.to_datetime(df['timestamp'])
                    df.sort_values('timestamp', inplace=True)
                    self.ax.plot(df['timestamp'], df['entry_price'], 'go-', label='Entry Price')
                    self.ax.plot(df['timestamp'], df['exit_price'], 'ro-', label='Exit Price')
                    self.ax.set_title("실시간 매매 내역")
                    self.ax.set_xlabel("시간")
                    self.ax.set_ylabel("가격")
                    self.ax.legend()
            except Exception as e:
                self.ax.text(0.5, 0.5, f"차트 업데이트 오류: {e}",
                             horizontalalignment='center', verticalalignment='center',
                             transform=self.ax.transAxes, fontsize=12)
        self.draw()

class TradingLauncher(QWidget):
    def __init__(self):
        super().__init__()

        self.setWindowTitle("Automated Trading System")
        self.setGeometry(300, 200, 800, 600)

        palette = QPalette()
        palette.setColor(QPalette.ColorRole.Window, QColor(240, 240, 240))
        self.setPalette(palette)

        layout = QVBoxLayout()

        self.title_label = QLabel("📊 Automated Trading System", self)
        self.title_label.setFont(QFont("Arial", 18, QFont.Weight.Bold))
        self.title_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self.title_label)

        self.trading_status = QLabel(get_trading_status(), self)
        self.trading_status.setFont(QFont("Arial", 14))
        self.trading_status.setAlignment(Qt.AlignmentFlag.AlignLeft)
        layout.addWidget(self.trading_status)

        self.gpt_status = QLabel(get_gpt_status(), self)
        self.gpt_status.setFont(QFont("Arial", 14))
        self.gpt_status.setAlignment(Qt.AlignmentFlag.AlignLeft)
        layout.addWidget(self.gpt_status)

        self.start_button = QPushButton("🚀 Start Trading System", self)
        self.start_button.setFont(QFont("Arial", 14))
        self.start_button.clicked.connect(self.start_all)
        layout.addWidget(self.start_button)

        self.stop_button = QPushButton("⏹ Stop All", self)
        self.stop_button.setFont(QFont("Arial", 14))
        self.stop_button.clicked.connect(self.stop_all)
        layout.addWidget(self.stop_button)

        self.gpt_report = QTextEdit(self)
        self.gpt_report.setReadOnly(True)
        self.gpt_report.setText(load_gpt_log())
        layout.addWidget(self.gpt_report)

        # 실시간 가격 차트 및 매매 내역 표시용 차트 위젯 추가
        self.chart = TradingChart(self, width=7, height=4, dpi=100)
        layout.addWidget(self.chart)

        self.timer = QTimer(self)
        self.timer.timeout.connect(self.update_dashboard)
        self.timer.start(5000)  # 5초마다 실행

        self.chart_timer = QTimer(self)
        self.chart_timer.timeout.connect(self.chart.update_chart)
        self.chart_timer.start(10000)  # 10초마다 차트 업데이트

        self.setLayout(layout)

        self.processes = []

        # 자동 실행 기능: 프로그램 실행 시 자동으로 두 스크립트 실행
        self.start_all()

        self.update_dashboard()

    def start_all(self):
        """자동매매, GPT 분석 실행 (중복 실행 방지)"""
        if not check_process_running("ai_auto_trading.py"):
            process = run_program("ai_auto_trading.py")
            if process:
                self.processes.append(process)
        else:
            print("ai_auto_trading.py 이미 실행 중")
        if not check_process_running("gpt_analysis.py"):
            process = run_program("gpt_analysis.py")
            if process:
                self.processes.append(process)
        else:
            print("gpt_analysis.py 이미 실행 중")
        self.update_dashboard()

    def stop_all(self):
        """실행 중인 모든 프로그램 종료 (하위 프로세스 포함)"""
        for process in self.processes:
            if process is not None:
                try:
                    kill_process_tree(process.pid)
                except Exception as e:
                    print(f"Error stopping process: {e}")
        self.processes.clear()
        self.update_dashboard()

    def update_dashboard(self):
        """자동매매 및 GPT 분석 실행 상태 자동 업데이트 (5초마다 실행)"""
        self.trading_status.setText(get_trading_status())
        self.gpt_status.setText(get_gpt_status())
        self.gpt_report.setText(load_gpt_log())

if __name__ == "__main__":
    app = QApplication(sys.argv)
    launcher = TradingLauncher()
    launcher.show()
    sys.exit(app.exec())
