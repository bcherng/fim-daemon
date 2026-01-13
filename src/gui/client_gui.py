#!/usr/bin/env python3
"""
FIM Client GUI
"""
import os
import queue
import threading
from datetime import datetime

import tkinter as tk
from tkinter import ttk, scrolledtext, filedialog, messagebox


class FIMClientGUI:
    """GUI for FIM Client with directory selection"""
    
    def __init__(self, config, state, connection_mgr, admin_verifier):
        self.config = config
        self.state = state
        self.connection_mgr = connection_mgr
        self.admin_verifier = admin_verifier
        self.queue = queue.Queue()
        self.daemon_thread = None
        
        self.root = tk.Tk()
        self.root.title(f"FIM Client - {config.host_id[:16]}")
        self.root.geometry("800x600")
        
        self.setup_ui()
        self.root.protocol("WM_DELETE_WINDOW", self.on_close)
        
        # Check if directory is set
        if not self.state.get_watch_directory():
            self.root.after(500, self.prompt_directory_selection)
        else:
            self.start_monitoring()
    
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
            text="● Disconnected", 
            foreground="red"
        )
        self.status_label.pack(side=tk.RIGHT, padx=5)
        
        # Directory info
        dir_frame = ttk.Frame(self.root)
        dir_frame.pack(fill=tk.X, padx=10, pady=5)
        
        ttk.Label(dir_frame, text="Monitoring:").pack(side=tk.LEFT)
        self.dir_label = ttk.Label(dir_frame, text="Not set", font=("Courier", 9))
        self.dir_label.pack(side=tk.LEFT, padx=5)
        
        ttk.Button(
            dir_frame, 
            text="Change Directory", 
            command=self.change_directory
        ).pack(side=tk.RIGHT)
        
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
        
        # Update directory label
        watch_dir = self.state.get_watch_directory()
        if watch_dir:
            self.dir_label.config(text=watch_dir)
    
    def prompt_directory_selection(self):
        """Show directory selection dialog on first run"""
        result = messagebox.askyesno(
            "Select Monitoring Directory",
            "Would you like to select a directory to monitor?\n\n"
            "FIM will track all file changes in this directory."
        )
        
        if result:
            directory = filedialog.askdirectory(title="Select Directory to Monitor")
            if directory:
                self.set_monitoring_directory(directory)
            else:
                messagebox.showwarning("No Directory", "No directory selected. You can set it later.")
        else:
            messagebox.showinfo("Info", "You can set the monitoring directory later from the GUI.")
    
    def set_monitoring_directory(self, directory):
        """Set the monitoring directory and start monitoring"""
        self.state.set_watch_directory(directory)
        self.dir_label.config(text=directory)
        self.add_log(
            datetime.now().isoformat(), 
            f"Monitoring directory set: {directory}", 
            "success"
        )
        
        # Log directory change event
        self.add_log(datetime.now().isoformat(), "═══ DIRECTORY CHANGE ═══", "info")
        
        # Restart monitoring if already running
        if self.daemon_thread and self.daemon_thread.is_alive():
            self.add_log(datetime.now().isoformat(), "Restarting monitoring...", "warning")
            # TODO: Signal daemon to restart
        else:
            self.start_monitoring()
    
    def change_directory(self):
        """Change monitoring directory with admin verification"""
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
            username = username_entry.get()
            password = password_entry.get()
            
            if self.admin_verifier.verify_credentials(username, password):
                dialog.destroy()
                directory = filedialog.askdirectory(
                    title="Select New Directory to Monitor"
                )
                if directory:
                    old_dir = self.state.get_watch_directory()
                    self.add_log(
                        datetime.now().isoformat(),
                        "═══ DIRECTORY CHANGED ═══",
                        "warning"
                    )
                    self.add_log(
                        datetime.now().isoformat(),
                        f"Old: {old_dir}",
                        "info"
                    )
                    self.add_log(
                        datetime.now().isoformat(),
                        f"New: {directory}",
                        "info"
                    )
                    self.add_log(
                        datetime.now().isoformat(),
                        f"Changed by: {username}",
                        "info"
                    )
                    self.add_log(
                        datetime.now().isoformat(),
                        "═══════════════════════════",
                        "warning"
                    )
                    
                    self.set_monitoring_directory(directory)
            else:
                messagebox.showerror("Authentication Failed", "Invalid credentials")
        
        ttk.Button(
            dialog, 
            text="Verify & Change", 
            command=verify_and_change
        ).pack(pady=10)
    
    def start_monitoring(self):
        """Start the monitoring daemon"""
        if self.daemon_thread and self.daemon_thread.is_alive():
            return
        
        watch_dir = self.state.get_watch_directory()
        if not watch_dir:
            return
        
        from daemon.background import run_daemon_background
        
        self.daemon_thread = threading.Thread(
            target=run_daemon_background,
            args=(
                self.config, 
                self.state, 
                self.connection_mgr, 
                self.queue, 
                watch_dir
            ),
            daemon=True
        )
        self.daemon_thread.start()
        self.add_log(datetime.now().isoformat(), "Monitoring started", "success")
    
    def add_log(self, timestamp, message, status="info"):
        """Add log entry to text widget"""
        self.log_text.config(state='normal')
        time_str = datetime.fromisoformat(timestamp).strftime("%H:%M:%S")
        self.log_text.insert(tk.END, f"[{time_str}] ", "info")
        self.log_text.insert(tk.END, f"{message}\n", status)
        self.log_text.see(tk.END)
        self.log_text.config(state='disabled')
    
    def update_status(self, connected):
        """Update connection status indicator"""
        if connected:
            self.status_label.config(text="● Connected", foreground="green")
        else:
            self.status_label.config(text="● Disconnected", foreground="red")
    
    def update_pending_count(self, count):
        """Update pending events counter"""
        if count > 0:
            self.pending_label.config(text=f"{count} pending events")
        else:
            self.pending_label.config(text="")
    
    def process_queue(self):
        """Process messages from daemon thread"""
        try:
            while True:
                msg = self.queue.get_nowait()
                if msg['type'] == 'log':
                    self.add_log(msg['timestamp'], msg['message'], msg.get('status', 'info'))
                elif msg['type'] == 'status':
                    self.update_status(msg['connected'])
                elif msg['type'] == 'pending':
                    self.update_pending_count(msg['count'])
        except queue.Empty:
            pass
        
        self.root.after(100, self.process_queue)
    
    def on_close(self):
        """Handle window close - minimize to tray"""
        self.root.withdraw()
    
    def run(self):
        """Run the GUI main loop"""
        self.process_queue()
        self.root.mainloop()