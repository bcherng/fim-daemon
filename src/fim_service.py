import win32serviceutil
import win32service
import win32event
import servicemanager
import time
import subprocess
import sys
import os

PYTHON_EXE = sys.executable
SCRIPT_PATH = r"C:\Program Files\FimDaemon\fim_daemon.py"

class FIMService(win32serviceutil.ServiceFramework):
    _svc_name_ = "FimDaemon"
    _svc_display_name_ = "File Integrity Monitoring Daemon"
    _svc_description_ = "Monitors filesystem changes and maintains Merkle integrity tree."

    def __init__(self, args):
        win32serviceutil.ServiceFramework.__init__(self, args)
        self.stop_event = win32event.CreateEvent(None, 0, 0, None)
        self.process = None

    def SvcStop(self):
        self.ReportServiceStatus(win32service.SERVICE_STOP_PENDING)
        if self.process:
            self.process.terminate()
        win32event.SetEvent(self.stop_event)
        self.ReportServiceStatus(win32service.SERVICE_STOPPED)

    def SvcDoRun(self):
        servicemanager.LogInfoMsg("FIM Daemon starting...")
        try:
            self.process = subprocess.Popen([PYTHON_EXE, SCRIPT_PATH])
            win32event.WaitForSingleObject(self.stop_event, win32event.INFINITE)
        except Exception as e:
            servicemanager.LogErrorMsg(f"FIM Daemon failed: {e}")

if __name__ == "__main__":
    win32serviceutil.HandleCommandLine(FIMService)
