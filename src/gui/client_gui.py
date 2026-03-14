#!/usr/bin/env python3
"""
FIM Client GUI — Pure View Layer
Provides a live dashboard of monitoring activity managed by the FIMAdmin service.
No direct access to state.json or monitoring threads; all data comes via IPC.
"""
import os
import queue
import threading
import time
from datetime import datetime

import tkinter as tk
from tkinter import ttk, scrolledtext, filedialog, messagebox


class FIMClientGUI:
    """GUI for FIM Client — Purely a subscriber to the FIMAdmin service."""

    def __init__(self, config):
        self.config = config
        self.queue = queue.Queue()
        self._subscribe_stop = threading.Event()

        self.root = tk.Tk()
        self.root.title(f"FIM Client - {config.host_id[:16]}")
        self.root.geometry("800x600")

        self.setup_ui()
        self.root.protocol("WM_DELETE_WINDOW", self.on_close)

        # Connect to admin daemon log stream immediately
        self.root.after(100, self.start_log_subscriber)

    def setup_ui(self):
        """Setup GUI components"""
        # Header
        header_frame = ttk.Frame(self.root)
        header_frame.pack(fill=tk.X, padx=10, pady=5)

        ttk.Label(
            header_frame,
            text="FIM Client",
            font=("Arial", 14, "bold")
        ).pack(side=tk.LEFT)

        self.status_label = ttk.Label(
            header_frame,
            text="● Connecting...",
            foreground="gray"
        )
        self.status_label.pack(side=tk.RIGHT, padx=5)

        # Directory info
        dir_frame = ttk.Frame(self.root)
        dir_frame.pack(fill=tk.X, padx=10, pady=5)

        ttk.Label(dir_frame, text="Monitoring:").pack(side=tk.LEFT)
        self.dir_label = ttk.Label(dir_frame, text="Pending service sync...", font=("Courier", 9))
        self.dir_label.pack(side=tk.LEFT, padx=5)

        self.change_dir_btn = ttk.Button(
            dir_frame,
            text="Change Directory",
            command=self.change_directory
        )
        self.change_dir_btn.pack(side=tk.RIGHT)

        # Stats bar
        stats_frame = ttk.Frame(self.root)
        stats_frame.pack(fill=tk.X, padx=10, pady=5)

        ttk.Label(stats_frame, text="Machine ID:").pack(side=tk.LEFT)
        ttk.Label(
            stats_frame,
            text=self.config.host_id[:16],
            font=("Courier", 9)
        ).pack(side=tk.LEFT, padx=5)

        self.pending_label = ttk.Label(stats_frame, text="", foreground="orange")
        self.pending_label.pack(side=tk.RIGHT)

        # Log area
        log_frame = ttk.LabelFrame(self.root, text="Activity Log")
        log_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=5)

        self.log_text = scrolledtext.ScrolledText(
            log_frame,
            height=20,
            state='disabled',
            bg='#1e1e1e',
            fg='#d4d4d4',
            insertbackground='white'
        )
        self.log_text.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)

        # Configure tags
        self.log_text.tag_config("success", foreground="#4ec9b0")
        self.log_text.tag_config("warning", foreground="#ce9178")
        self.log_text.tag_config("error", foreground="#f48771")
        self.log_text.tag_config("info", foreground="#9cdcfe")

    def change_directory(self):
        """Change monitoring directory with admin verification via IPC."""
        # Create admin login dialog
        dialog = tk.Toplevel(self.root)
        dialog.title("Admin Verification Required")
        dialog.geometry("350x180")
        dialog.transient(self.root)
        dialog.grab_set()

        ttk.Label(
            dialog,
            text="Enter admin credentials to change directory:",
            font=("Arial", 10)
        ).pack(pady=10)

        ttk.Label(dialog, text="Username:").pack(anchor=tk.W, padx=20)
        username_entry = ttk.Entry(dialog, width=30)
        username_entry.pack(padx=20, pady=5)

        ttk.Label(dialog, text="Password:").pack(anchor=tk.W, padx=20)
        password_entry = ttk.Entry(dialog, show="*", width=30)
        password_entry.pack(padx=20, pady=5)

        def verify_and_change():
            directory = filedialog.askdirectory(title="Select New Directory to Monitor")
            if directory:
                dialog.destroy()
                # Path correction for Windows consistency
                directory = os.path.abspath(directory).replace('\\', '/')
                
                self.add_log(datetime.now().isoformat(), f"Requesting change to: {directory}", "warning")
                
                # IPC call to service (privileged process)
                from core.admin_ipc_client import send_admin_request
                response = send_admin_request('change_directory', None, {'path': directory})
                
                if not response.get('success'):
                    messagebox.showerror("Error", f"Service rejected change: {response.get('error')}")
                else:
                    messagebox.showinfo("Success", f"Request accepted. The service will now scan {directory}")

        ttk.Button(dialog, text="Select Directory & Apply", command=verify_and_change).pack(pady=10)

    def start_log_subscriber(self):
        """Subscribe to the admin daemon's log broadcast channel."""
        from core.admin_ipc_client import subscribe_to_logs
        self._subscribe_stop.clear()
        subscribe_to_logs(self.queue.put, stop_event=self._subscribe_stop)

    def stop_log_subscriber(self):
        """Signal the subscriber thread to exit."""
        self._subscribe_stop.set()

    def add_log(self, timestamp, message, status="info"):
        """Add log entry to text widget"""
        self.log_text.config(state='normal')
        try:
            time_str = datetime.fromisoformat(timestamp).strftime("%H:%M:%S")
        except:
            time_str = datetime.now().strftime("%H:%M:%S")
        self.log_text.insert(tk.END, f"[{time_str}] ", "info")
        self.log_text.insert(tk.END, f"{message}\n", status)
        self.log_text.see(tk.END)
        self.log_text.config(state='disabled')

    def update_status(self, connected, deregistered=False):
        """Update connection status indicator"""
        if deregistered:
            self.status_label.config(text="● Deregistered", foreground="orange")
            self.change_dir_btn.config(state='disabled')
        elif connected:
            self.status_label.config(text="● Connected", foreground="green")
            self.change_dir_btn.config(state='normal')
        else:
            self.status_label.config(text="● Disconnected", foreground="red")
            self.change_dir_btn.config(state='normal')

    def update_pending_count(self, count):
        """Update pending events counter"""
        if count > 0:
            self.pending_label.config(text=f"{count} pending events")
        else:
            self.pending_label.config(text="")

    def process_queue(self):
        """Process messages from daemon log stream"""
        try:
            for _ in range(50):
                msg = self.queue.get_nowait()
                m_type = msg.get('type')
                
                if m_type == 'log':
                    self.add_log(msg['timestamp'], msg['message'], msg.get('status', 'info'))
                elif m_type == 'status':
                    self.update_status(msg['connected'])
                elif m_type == 'pending':
                    self.update_pending_count(msg['count'])
                elif m_type == 'directory':
                    self.dir_label.config(text=msg['directory'])
                elif m_type == 'sync':
                    # Full state sync from service
                    self.dir_label.config(text=msg.get('directory', 'Not set'))
                    self.update_status(msg.get('connected', False), msg.get('deregistered', False))
                    self.update_pending_count(msg.get('pending', 0))
                    if msg.get('deregistered'):
                        self.handle_deregistration()
                elif m_type == 'deregistered':
                    self.handle_deregistration(msg.get('message'))
                elif m_type == 'removal_detected':
                    self.handle_deregistration("Machine removed from server.")

        except queue.Empty:
            pass
        
        self.root.after(100, self.process_queue)

    def handle_deregistration(self, server_message=None):
        """Show deregistration options."""
        if hasattr(self, 'deregistration_handled'): return
        self.deregistration_handled = True
        
        self.status_label.config(text="● Deregistered", foreground="orange")
        self.change_dir_btn.config(state='disabled')

        dialog = tk.Toplevel(self.root)
        dialog.title("Machine Deregistered")
        dialog.geometry("400x350")
        dialog.transient(self.root)
        dialog.grab_set()

        ttk.Label(dialog, text="⚠ Machine Deregistered", font=("Arial", 12, "bold"), foreground="orange").pack(pady=10)
        ttk.Label(dialog, text=server_message or "Deregistered by administrator.", wraplength=350).pack(pady=10, padx=20)

        # Admin creds for reregister/uninstall
        cred_frame = ttk.Frame(dialog)
        cred_frame.pack(pady=10, padx=20, fill=tk.X)
        ttk.Label(cred_frame, text="Username:").grid(row=0, column=0, sticky=tk.W)
        u_entry = ttk.Entry(cred_frame, width=25)
        u_entry.grid(row=0, column=1)
        ttk.Label(cred_frame, text="Password:").grid(row=1, column=0, sticky=tk.W)
        p_entry = ttk.Entry(cred_frame, show="*", width=25)
        p_entry.grid(row=1, column=1)

        def do_reregister():
            from core.admin_ipc_client import send_admin_request
            resp = send_admin_request('reregister', None, {'username': u_entry.get(), 'password': p_entry.get()})
            if resp.get('success'):
                messagebox.showinfo("Success", "Reregistered successfully!")
                dialog.destroy()
                if hasattr(self, 'deregistration_handled'): del self.deregistration_handled
            else:
                messagebox.showerror("Error", f"Failed: {resp.get('error')}")

        def do_uninstall():
            if messagebox.askyesno("Confirm", "Uninstall FIM entirely?"):
                from core.admin_ipc_client import send_admin_request
                resp = send_admin_request('uninstall', None, {})
                if resp.get('success'):
                    messagebox.showinfo("Success", "Uninstallation started.")
                    self.on_close()
                else:
                    messagebox.showerror("Error", f"Uninstall failed: {resp.get('error')}")

        btn_frame = ttk.Frame(dialog)
        btn_frame.pack(pady=20)
        ttk.Button(btn_frame, text="Reregister", command=do_reregister).pack(side=tk.LEFT, padx=5)
        ttk.Button(btn_frame, text="Uninstall", command=do_uninstall).pack(side=tk.LEFT, padx=5)

    def on_close(self):
        """Cleanly exit."""
        import sys
        self.stop_log_subscriber()
        self.root.destroy()
        sys.exit(0)

    def run(self):
        """Run the GUI."""
        self.process_queue()
        self.root.mainloop()