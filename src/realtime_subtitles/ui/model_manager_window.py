"""
Model Manager Window - UI for managing model downloads.
"""

import customtkinter as ctk
from typing import Optional, Dict
import threading

from ..model_manager import ModelManager, ModelInfo, ModelType, ModelStatus
from ..i18n import t


class ModelRow(ctk.CTkFrame):
    """A single row displaying a model's status and actions."""
    
    def __init__(
        self,
        master,
        model: ModelInfo,
        manager: ModelManager,
        on_status_change: Optional[callable] = None,
    ):
        super().__init__(master, fg_color="transparent")
        
        self.model = model
        self.manager = manager
        self.on_status_change = on_status_change
        
        self._create_ui()
        self._update_status()
    
    def _create_ui(self):
        """Create the row UI."""
        # Status icon
        self.status_label = ctk.CTkLabel(
            self,
            text="⬇️",
            width=30,
            font=ctk.CTkFont(size=16),
        )
        self.status_label.pack(side="left", padx=(5, 5))
        
        # Model info
        info_frame = ctk.CTkFrame(self, fg_color="transparent")
        info_frame.pack(side="left", fill="x", expand=True, padx=5)
        
        self.name_label = ctk.CTkLabel(
            info_frame,
            text=t(self.model.name),  # Translate model name
            font=ctk.CTkFont(size=13, weight="bold"),
            anchor="w",
        )
        self.name_label.pack(anchor="w")
        
        self.desc_label = ctk.CTkLabel(
            info_frame,
            text=t(self.model.description),  # Translate description
            font=ctk.CTkFont(size=11),
            text_color="#888888",
            anchor="w",
        )
        self.desc_label.pack(anchor="w")
        
        # Size label
        self.size_label = ctk.CTkLabel(
            self,
            text=self.model.get_size_display(),
            width=60,
            font=ctk.CTkFont(size=12),
            text_color="#aaaaaa",
        )
        self.size_label.pack(side="left", padx=10)
        
        # Progress bar (hidden by default)
        self.progress_bar = ctk.CTkProgressBar(self, width=100)
        self.progress_bar.set(0)
        # Don't pack yet
        
        # Progress text
        self.progress_text = ctk.CTkLabel(
            self,
            text="",
            width=120,
            font=ctk.CTkFont(size=11),
            text_color="#888888",
        )
        # Don't pack yet
        
        # Action button
        self.action_button = ctk.CTkButton(
            self,
            text=t("download"),
            width=70,
            height=28,
            command=self._on_action,
        )
        self.action_button.pack(side="right", padx=10)
    
    def _update_status(self):
        """Update UI based on model status."""
        try:
            status = self.manager.get_status(self.model)
            
            if status == ModelStatus.DOWNLOADED:
                self.status_label.configure(text="✅")
                self.action_button.configure(text=t("delete"), fg_color="#8B0000", hover_color="#A52A2A", state="normal")
                self.progress_bar.pack_forget()
                self.progress_text.pack_forget()
            elif status == ModelStatus.DOWNLOADING:
                self.status_label.configure(text="⏳")
                self.action_button.configure(text=t("downloading"), state="disabled")
                self.progress_bar.pack(side="left", padx=5)
                self.progress_text.pack(side="left", padx=5)
            else:  # NOT_DOWNLOADED
                self.status_label.configure(text="⬇️")
                self.action_button.configure(
                    text=t("download"),
                    fg_color=["#3B8ED0", "#1F6AA5"],
                    hover_color=["#36719F", "#144870"],
                    state="normal",
                )
                self.progress_bar.pack_forget()
                self.progress_text.pack_forget()
        except Exception:
            pass  # Widget may be destroyed
    
    def _on_action(self):
        """Handle action button click."""
        status = self.manager.get_status(self.model)
        
        if status == ModelStatus.DOWNLOADED:
            # Delete
            if self.manager.delete(self.model):
                self._update_status()
                if self.on_status_change:
                    self.on_status_change()
        elif status == ModelStatus.NOT_DOWNLOADED:
            # Download
            self._start_download()
    
    def _start_download(self):
        """Start downloading the model."""
        self._update_status()  # Show downloading state
        
        def progress_callback(model_id: str, progress: float, status_text: str):
            # Update UI in main thread
            self.after(0, lambda: self._update_progress(progress, status_text))
        
        self.manager.download(self.model, progress_callback)
        self._update_status()
    
    def _update_progress(self, progress: float, status_text: str):
        """Update progress display."""
        try:
            if progress < 0:
                # Error
                self.progress_text.configure(text=status_text, text_color="red")
                self.action_button.configure(state="normal", text=t("retry"))
            elif progress >= 1.0:
                # Complete
                self._update_status()
                if self.on_status_change:
                    self.on_status_change()
            else:
                # In progress
                self.progress_bar.set(progress)
                self.progress_text.configure(text=status_text, text_color="#888888")
        except Exception:
            pass  # Widget may be destroyed


class ModelManagerWindow(ctk.CTkToplevel):
    """Window for managing model downloads."""
    
    def __init__(self, master=None):
        super().__init__(master)
        
        self.title(t("model_manager_title"))
        self.geometry("650x500")
        self.resizable(True, True)
        
        # Center on screen
        self.update_idletasks()
        x = (self.winfo_screenwidth() - 750) // 2
        y = (self.winfo_screenheight() - 500) // 2
        self.geometry(f"+{x}+{y}")
        
        # Model manager
        self.manager = ModelManager()
        
        # Model rows
        self._model_rows: Dict[str, ModelRow] = {}
        
        self._create_ui()
        
        # Handle window close
        self.protocol("WM_DELETE_WINDOW", self._on_close)
    
    def _on_close(self):
        """Handle window close with confirmation if downloading."""
        # Check if any model is currently downloading
        for model in self.manager.get_all_models():
            if self.manager.get_status(model) == ModelStatus.DOWNLOADING:
                from tkinter import messagebox
                result = messagebox.askyesno(
                    t("download_in_progress"),
                    t("download_cancel_confirm"),
                    parent=self,
                )
                if not result:
                    return  # User chose not to close
                break
        
        try:
            self.grab_release()
        except Exception:
            pass
        self.destroy()
    
    def _create_ui(self):
        """Create the window UI."""
        # Header
        header = ctk.CTkFrame(self, fg_color="transparent")
        header.pack(fill="x", padx=20, pady=(20, 10))
        
        ctk.CTkLabel(
            header,
            text="📦 " + t("model_manager_title"),
            font=ctk.CTkFont(size=20, weight="bold"),
        ).pack(side="left")
        
        # Storage path section
        path_frame = ctk.CTkFrame(self, fg_color="#2a2a2a", corner_radius=8)
        path_frame.pack(fill="x", padx=20, pady=(0, 15))
        
        ctk.CTkLabel(
            path_frame,
            text=t("model_path") + ":",
            font=ctk.CTkFont(size=12),
        ).pack(side="left", padx=(15, 5), pady=10)
        
        self.path_label = ctk.CTkLabel(
            path_frame,
            text=str(self.manager.models_dir),
            font=ctk.CTkFont(size=11),
            text_color="#888888",
            wraplength=350,
        )
        self.path_label.pack(side="left", fill="x", expand=True, padx=5, pady=10)
        
        # Open folder button
        open_btn = ctk.CTkButton(
            path_frame,
            text=t("open_folder"),
            width=70,
            height=28,
            font=ctk.CTkFont(size=12),
            command=self._open_models_folder,
        )
        open_btn.pack(side="right", padx=10, pady=10)
        
        # Scrollable content area
        self.scroll_frame = ctk.CTkScrollableFrame(self, fg_color="transparent")
        self.scroll_frame.pack(fill="both", expand=True, padx=20, pady=(0, 20))
        
        # Model sections
        self._create_model_section(t("recognition_models"), ModelType.WHISPER)
        self._create_model_section(t("realtime_models"), [ModelType.SHERPA, ModelType.VOSK])
        self._create_model_section(t("translation_models"), ModelType.NLLB)
    
    def _create_model_section(self, title: str, model_types):
        """Create a section for a group of models."""
        # Section title
        section_header = ctk.CTkFrame(self.scroll_frame, fg_color="transparent")
        section_header.pack(fill="x", pady=(15, 5))
        
        ctk.CTkLabel(
            section_header,
            text=title,
            font=ctk.CTkFont(size=14, weight="bold"),
            anchor="w",
        ).pack(side="left")
        
        # Model list
        section_frame = ctk.CTkFrame(self.scroll_frame, fg_color="#2a2a2a", corner_radius=8)
        section_frame.pack(fill="x", pady=(0, 5))
        
        # Get models for this section
        if isinstance(model_types, list):
            models = []
            for mt in model_types:
                models.extend(self.manager.get_models_by_type(mt))
        else:
            models = self.manager.get_models_by_type(model_types)
        
        # Create rows
        for i, model in enumerate(models):
            row = ModelRow(
                section_frame,
                model,
                self.manager,
                on_status_change=self._on_status_change,
            )
            row.pack(fill="x", padx=10, pady=(10 if i == 0 else 5, 10 if i == len(models) - 1 else 0))
            self._model_rows[model.id] = row
    
    def _on_status_change(self):
        """Called when any model's status changes."""
        pass
    
    def _open_models_folder(self):
        """Open the models folder in file explorer."""
        import subprocess
        import sys
        
        folder = str(self.manager.models_dir)
        if sys.platform == "win32":
            subprocess.run(["explorer", folder])
        elif sys.platform == "darwin":
            subprocess.run(["open", folder])
        else:
            subprocess.run(["xdg-open", folder])


class ModelDownloadDialog(ctk.CTkToplevel):
    """Dialog for downloading missing models."""
    
    def __init__(self, master, models_to_download: list, on_complete: Optional[callable] = None):
        super().__init__(master)
        
        self.title(t("download_title"))
        self.geometry("450x350")
        self.resizable(False, False)
        
        # Center on screen
        self.update_idletasks()
        x = (self.winfo_screenwidth() - 450) // 2
        y = (self.winfo_screenheight() - 350) // 2
        self.geometry(f"+{x}+{y}")
        
        self.models_to_download = models_to_download
        self.on_complete = on_complete
        self.manager = ModelManager()
        self._completed_count = 0
        self._progress_labels = {}
        self._progress_bars = {}
        self._destroyed = False
        
        self._create_ui()
        self._start_downloads()
        
        # Make modal
        self.grab_set()
        self.focus_set()
        
        # Handle window close
        self.protocol("WM_DELETE_WINDOW", self._on_close)
    
    def _create_ui(self):
        """Create the dialog UI."""
        # Header
        ctk.CTkLabel(
            self,
            text=t("downloading_models"),
            font=ctk.CTkFont(size=18, weight="bold"),
        ).pack(pady=(20, 15))
        
        # Model list
        for model in self.models_to_download:
            frame = ctk.CTkFrame(self, fg_color="#2a2a2a", corner_radius=8)
            frame.pack(fill="x", padx=20, pady=5)
            
            # Model name
            ctk.CTkLabel(
                frame,
                text=f"{t(model.name)} ({model.get_size_display()})",
                font=ctk.CTkFont(size=13, weight="bold"),
            ).pack(anchor="w", padx=15, pady=(10, 5))
            
            # Progress bar
            progress_bar = ctk.CTkProgressBar(frame, width=380)
            progress_bar.set(0)
            progress_bar.pack(padx=15, pady=(0, 5))
            self._progress_bars[model.id] = progress_bar
            
            # Status label
            status_label = ctk.CTkLabel(
                frame,
                text="等待中...",
                font=ctk.CTkFont(size=11),
                text_color="#888888",
            )
            status_label.pack(anchor="w", padx=15, pady=(0, 10))
            self._progress_labels[model.id] = status_label
        
        # Close button (hidden until complete)
        self.close_btn = ctk.CTkButton(
            self,
            text=t("downloading"),
            width=100,
            state="disabled",
            command=self._on_close,
        )
        self.close_btn.pack(pady=(15, 20))
    
    def _start_downloads(self):
        """Start downloading all models."""
        for model in self.models_to_download:
            def make_callback(m):
                return lambda model_id, progress, status_text: self.after(
                    0, lambda: self._update_progress(m.id, progress, status_text)
                )
            
            self.manager.download(model, make_callback(model))
    
    def _update_progress(self, model_id: str, progress: float, status_text: str):
        """Update progress for a model."""
        # Check if dialog is still alive
        if self._destroyed:
            return
        
        try:
            if model_id in self._progress_bars:
                if progress >= 0:
                    self._progress_bars[model_id].set(progress)
                
                self._progress_labels[model_id].configure(
                    text=status_text,
                    text_color="red" if progress < 0 else ("#00AA00" if progress >= 1.0 else "#888888")
                )
                
                # Check if completed
                if progress >= 1.0:
                    self._completed_count += 1
                    self._check_all_complete()
        except Exception:
            pass  # Widget may be destroyed
    
    def _check_all_complete(self):
        """Check if all downloads are complete."""
        if self._destroyed:
            return
        try:
            if self._completed_count >= len(self.models_to_download):
                self.close_btn.configure(text=t("complete"), state="normal")
        except Exception:
            pass
    
    def _on_close(self):
        """Handle dialog close."""
        # Check if any download is still in progress
        if self._completed_count < len(self.models_to_download):
            from tkinter import messagebox
            result = messagebox.askyesno(
                t("download_in_progress"),
                t("download_cancel_confirm"),
                parent=self,
            )
            if not result:
                return  # User chose not to close
            
            # User confirmed cancel - delete partial downloaded models and force quit
            import os
            import shutil
            
            for model in self.models_to_download:
                # Delete from models directory
                model_path = self.manager.get_model_path(model)
                if model_path and model_path.exists():
                    try:
                        if model_path.is_dir():
                            shutil.rmtree(model_path)
                        else:
                            os.remove(model_path)
                    except Exception:
                        pass
                
                # Also try to clear HuggingFace cache for this model
                if model.hf_repo:
                    try:
                        hf_cache = os.path.expanduser("~/.cache/huggingface/hub")
                        repo_name = model.hf_repo.replace("/", "--")
                        for entry in os.listdir(hf_cache):
                            if repo_name in entry:
                                cache_path = os.path.join(hf_cache, entry)
                                if os.path.isdir(cache_path):
                                    shutil.rmtree(cache_path)
                    except Exception:
                        pass
            
            # Force exit - os._exit stops all threads immediately
            os._exit(0)
        
        self._destroyed = True
        try:
            self.grab_release()
        except Exception:
            pass
        self.destroy()
        if self.on_complete:
            self.on_complete()


def show_model_manager(parent=None):
    """Show the model manager window."""
    window = ModelManagerWindow(parent)
    window.grab_set()  # Modal
    window.focus_set()
    return window


def show_download_dialog(parent, models_to_download: list, on_complete=None):
    """Show the download dialog for specific models."""
    dialog = ModelDownloadDialog(parent, models_to_download, on_complete)
    return dialog
