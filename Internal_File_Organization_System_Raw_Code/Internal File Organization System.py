import tkinter as tk
from tkinter import ttk, filedialog, messagebox, simpledialog
import os
import json
import hashlib
import subprocess
import threading
import time
import re
import sys
from PIL import Image, ImageTk
import wave  # This is from Python's standard library
from vosk import Model, KaldiRecognizer
import json
import vlc  # Now it will use the correct path
import winreg
import fitz

def get_vlc_instance():
    return vlc.Instance()

def update_vlc_registry_path():
    try:
        # Get the directory where this script is located
        script_dir = os.path.dirname(os.path.abspath(sys.argv[0]))
        
        # Define the VLC folder path (in the same directory as this script)
        VLC_CORRECT_PATH = os.path.join(script_dir, "VLC")
        
        # Verify the VLC folder exists
        if not os.path.exists(VLC_CORRECT_PATH):
            raise FileNotFoundError(f"VLC folder not found at: {VLC_CORRECT_PATH}")

        # Registry key paths
        VLC_REG_KEY = r"SOFTWARE\VideoLAN\VLC"  # For 64-bit Windows
        
        # Open the registry key with write access
        reg_key = winreg.OpenKey(
            winreg.HKEY_LOCAL_MACHINE,
            VLC_REG_KEY,
            0,
            winreg.KEY_SET_VALUE | winreg.KEY_WOW64_64KEY
        )
        
        # Update the InstallDir value
        winreg.SetValueEx(
            reg_key,
            "InstallDir",
            0,
            winreg.REG_SZ,
            VLC_CORRECT_PATH
        )
        
        print(f"✅ Successfully updated VLC registry path to: {VLC_CORRECT_PATH}")
        return True
    
    except FileNotFoundError as e:
        print(f"❌ Error: {e}")
    except PermissionError:
        print("❌ Error: Run this script as Administrator to modify the registry.")
    except Exception as e:
        print(f"❌ Unexpected error: {str(e)}")
    finally:
        if 'reg_key' in locals():
            winreg.CloseKey(reg_key)
    return False


try:
    import fitz  # PyMuPDF for PDF display
    PDF_SUPPORT = True
except ImportError:
    PDF_SUPPORT = False
    print("PyMuPDF not found. PDF display will be limited. Install with: pip install PyMuPDF")

class FileOrganizerApp:
    def __init__(self, root):
        self.root = root
        self.root.title("File Organization System")
        self.root.geometry("1200x800")
        self.root.configure(bg='white')

        # Configure Times New Roman font
        self.font_family = "Times New Roman"
        self.default_font = (self.font_family, 10)
        self.heading_font = (self.font_family, 12, "bold")

        # Data storage
        self.passwords = {}  # Store encrypted passwords for files/folders
        self.temp_passwords = {}  # Store temp lock passwords
        self.unlocked_items = set()  # Track unlocked items
        self.controls_rules = []  # Rules from Controls.txt
        self.current_directory = None
        self.vlc_process = None
        self.custom_root_folder = None  # <-- Move this here
        self.hidden_items = set()  # Track hidden items
        self.interval_var = tk.StringVar(value="30")  # Default interval
        self.vlc_player = None
        self.vlc_instance = None
        self.vlc_canvas = None  # Add this for audio playback
        self.media_playing = False

        # Load saved data
        self.load_passwords()
        self.load_temp_passwords()
        self.load_controls()
        self.load_custom_folder()

        self.setup_ui()
        self.load_initial_directory()

        success = update_vlc_registry_path()
    
        # Verify by importing vlc (optional)
        if success:
            try:
                import vlc
                print("✅ VLC import successful! Registry update worked.")
            except ImportError:
                print("⚠️ VLC import failed. The path might need manual adjustment.")

        self.vlc_player = None
    
        # Setup VLC environment
        vlc_setup_success = self.setup_vlc_environment()
        if not vlc_setup_success:
            print("⚠️ VLC setup failed - media playback may not work")
        
    def setup_ui(self):
        # Create main paned window for resizable sections
        self.main_paned = ttk.PanedWindow(self.root, orient=tk.HORIZONTAL)
        self.main_paned.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
        
        # Left frame for file tree
        self.left_frame = ttk.Frame(self.main_paned)
        self.main_paned.add(self.left_frame, weight=1)
        
        # Right frame for file display
        self.right_frame = ttk.Frame(self.main_paned)
        self.main_paned.add(self.right_frame, weight=2)
        
        self.setup_left_panel()
        self.setup_right_panel()
        
        # Menu bar
        self.setup_menu()
        
    def setup_menu(self):
        menubar = tk.Menu(self.root)
        self.root.config(menu=menubar)
        
        file_menu = tk.Menu(menubar, tearoff=0)
        menubar.add_cascade(label="File", menu=file_menu)
        file_menu.add_command(label="Select Root Directory", command=self.select_directory)
        file_menu.add_command(label="Set Custom Folder", command=self.set_custom_folder)  # NEW
        file_menu.add_command(label="Go to Script Drive", command=self.go_to_script_drive)
        file_menu.add_command(label="Refresh", command=self.refresh_tree)
        file_menu.add_separator()
        file_menu.add_command(label="Exit", command=self.root.quit)
        
    def setup_left_panel(self):
        # Top frame for controls
        top_controls = ttk.Frame(self.left_frame)
        top_controls.pack(fill=tk.X, pady=5)

        # Button to set root folder
        set_root_btn = ttk.Button(top_controls, text="Set Root Folder", command=self.set_custom_folder)
        set_root_btn.pack(side=tk.LEFT, padx=5)

        # Title
        title_label = tk.Label(self.left_frame, text="File Explorer", 
                            font=self.heading_font, bg='white')
        title_label.pack(pady=5)

        # Treeview for file structure
        tree_frame = ttk.Frame(self.left_frame)
        tree_frame.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)

        self.tree = ttk.Treeview(tree_frame)
        self.tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        # Scrollbar for tree
        tree_scrollbar = ttk.Scrollbar(tree_frame, orient=tk.VERTICAL, command=self.tree.yview)
        tree_scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        self.tree.configure(yscrollcommand=tree_scrollbar.set)

        # Bind events
        self.tree.bind('<<TreeviewSelect>>', self.on_tree_select)
        self.tree.bind('<Button-3>', self.show_context_menu)  # Right click

        # Context menu
        self.context_menu = tk.Menu(self.root, tearoff=0)
        self.context_menu.add_command(label="Set Password", command=self.set_password)
        self.context_menu.add_command(label="Unlock", command=self.unlock_item)
        self.context_menu.add_command(label="Hide", command=self.hide_item)
        
    def setup_right_panel(self):
        # Title
        title_label = tk.Label(self.right_frame, text="File Viewer", 
                              font=self.heading_font, bg='white')
        title_label.pack(pady=5)
        
        # Main display area
        self.display_frame = ttk.Frame(self.right_frame)
        self.display_frame.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
        
        # Default message
        self.default_label = tk.Label(self.display_frame, 
                                     text="Select a file to view its contents",
                                     font=self.default_font, bg='white')
        self.default_label.pack(expand=True)
        
        # Video/Audio controls frame
        self.media_controls = ttk.Frame(self.right_frame)
        self.volume_var = tk.DoubleVar(value=50)
        
    def load_initial_directory(self):
        # Check if custom folder is set first
        if self.custom_root_folder and os.path.exists(self.custom_root_folder):
            self.current_directory = self.custom_root_folder
        else:
            # Get the directory where the Python script is located
            script_path = os.path.abspath(__file__)
            script_directory = os.path.dirname(script_path)
            
            # Use the script directory instead of the entire drive
            self.current_directory = script_directory
            
        self.populate_tree(self.current_directory)
        
    def select_directory(self):
        directory = filedialog.askdirectory(title="Select Root Directory")
        if directory:
            self.current_directory = directory
            self.populate_tree(directory)
            
    def populate_tree(self, root_path):
        # Clear existing items
        for item in self.tree.get_children():
            self.tree.delete(item)
            
        if not os.path.exists(root_path):
            return
            
        # Add root directory
        root_node = self.tree.insert('', 'end', text=self.get_display_name(root_path),
                                    values=[root_path], open=True)
        
        self.add_directory_contents(root_node, root_path)
        
    def add_directory_contents(self, parent_node, directory_path):
        try:
            items = os.listdir(directory_path)
            
            # Separate directories and files
            directories = []
            files = []
            
            for item in items:
                if item.startswith('.'):  # Skip hidden files
                    continue
                    
                item_path = os.path.join(directory_path, item)
                
                if os.path.isdir(item_path):
                    directories.append((item, item_path))
                else:
                    files.append((item, item_path))
            
            # Add directories first
            for dir_name, dir_path in sorted(directories):
                if self.is_item_visible(dir_path):
                    dir_node = self.tree.insert(parent_node, 'end', text=self.get_display_name(dir_path),
                                              values=[dir_path])
                    
                    # Check if directory has contents to show expand option
                    try:
                        if any(os.path.isdir(os.path.join(dir_path, f)) or 
                              os.path.isfile(os.path.join(dir_path, f)) 
                              for f in os.listdir(dir_path) if not f.startswith('.')):
                            self.tree.insert(dir_node, 'end', text='Loading...')
                    except PermissionError:
                        pass
            
            # Add files
            for file_name, file_path in sorted(files):
                if self.is_item_visible(file_path):
                    self.tree.insert(parent_node, 'end', text=self.get_display_name(file_path),
                                   values=[file_path])
                                   
        except PermissionError:
            messagebox.showerror("Error", f"Permission denied accessing {directory_path}")
        except Exception as e:
            messagebox.showerror("Error", f"Error loading directory: {str(e)}")
    
    def on_tree_select(self, event):
        selection = self.tree.selection()
        if not selection:
            return

        item = selection[0]
        values = self.tree.item(item, 'values')

        if not values:
            return

        file_path = values[0]

        # If the item is locked, show locked message instead of file contents
        if not self.is_item_unlocked(file_path):
            self.show_not_accessible_message(file_path)
            return

        # Handle directory expansion
        if os.path.isdir(file_path):
            children = self.tree.get_children(item)
            if len(children) == 1 and self.tree.item(children[0], 'text') == 'Loading...':
                self.tree.delete(children[0])
                self.add_directory_contents(item, file_path)
        else:
            # Handle file selection
            self.display_file(file_path)
    
    def display_file(self, file_path):

        if hasattr(self, 'vlc_player') and self.vlc_player:
            self.vlc_player.stop()
            self.vlc_player.release()
            self.vlc_player = None
        
        # Check if file is locked
        if not self.is_item_unlocked(file_path):
            self.show_not_accessible_message(file_path)
            return
            
        # Stop any existing media playback and clean up
        if hasattr(self, 'vlc_player') and self.vlc_player:
            self.vlc_player.stop()
            self.vlc_player.release()
            del self.vlc_player

        # Clear current display
        for widget in self.display_frame.winfo_children():
            widget.destroy()
            
        # Hide media controls initially
        self.media_controls.pack_forget()
        
        file_ext = os.path.splitext(file_path)[1].lower()

        try:
            if file_ext == '.txt':
                self.display_text_file(file_path)
            elif file_ext == '.pdf':
                self.display_pdf_file(file_path)
            elif file_ext == '.csv':
                self.display_csv_file(file_path)
            elif file_ext == '.json':
                self.display_json_file(file_path)
            elif file_ext in ['.mp4', '.avi', '.mkv', '.mov']:
                self.display_video_file(file_path)
            elif file_ext in ['.mp3', '.wav', '.flac', '.m4a']:
                self.display_audio_file(file_path)
            elif file_ext in ['.png', '.jpg', '.jpeg']:
                self.display_image_file(file_path)
            else:
                self.display_unsupported_file(file_path)
                
        except Exception as e:
            # Clean up on error
            if hasattr(self, 'vlc_player') and self.vlc_player:
                self.vlc_player.stop()
                self.vlc_player.release()
                del self.vlc_player
                
            error_frame = ttk.Frame(self.display_frame)
            error_frame.pack(expand=True)
            tk.Label(error_frame, text="Error displaying file", 
                    font=self.heading_font).pack(pady=10)
            tk.Label(error_frame, text=str(e), 
                    font=self.default_font).pack(pady=5)
            ttk.Button(error_frame, text="Try Again", 
                    command=lambda: self.display_file(file_path)).pack(pady=10)

    def display_image_file(self, file_path):
        # Clear any existing image frame
        for widget in self.display_frame.winfo_children():
            widget.destroy()
        
        # Create a container frame with grid layout
        container = ttk.Frame(self.display_frame)
        container.pack(fill=tk.BOTH, expand=True)
        
        # Create canvas with scrollbars
        canvas = tk.Canvas(container, bg='white', highlightthickness=0)
        v_scrollbar = ttk.Scrollbar(container, orient=tk.VERTICAL, command=canvas.yview)
        h_scrollbar = ttk.Scrollbar(container, orient=tk.HORIZONTAL, command=canvas.xview)
        canvas.configure(yscrollcommand=v_scrollbar.set, xscrollcommand=h_scrollbar.set)
        
        # Grid layout for proper resizing
        canvas.grid(row=0, column=0, sticky='nsew')
        v_scrollbar.grid(row=0, column=1, sticky='ns')
        h_scrollbar.grid(row=1, column=0, sticky='ew')
        
        # Configure grid weights
        container.grid_rowconfigure(0, weight=1)
        container.grid_columnconfigure(0, weight=1)
        
        try:
            # Load the image
            self.img = Image.open(file_path)
            self.update_image_display(canvas)
            
            # Bind resize event
            canvas.bind('<Configure>', lambda e: self.update_image_display(canvas))
            
        except Exception as e:
            error_label = tk.Label(container, 
                                text=f"Error loading image: {str(e)}",  # Fixed quote
                                font=self.default_font)
            error_label.grid(row=0, column=0)

    def update_image_display(self, canvas):
        """Update the image display when window is resized"""
        if hasattr(self, 'img') and self.img:
            try:
                # Get canvas size
                canvas.update_idletasks()  # Ensure accurate dimensions
                canvas_width = canvas.winfo_width()
                canvas_height = canvas.winfo_height()
                
                # Skip if canvas is too small
                if canvas_width < 10 or canvas_height < 10:
                    return
                
                # Get original image size
                img_width, img_height = self.img.size
                
                # Calculate ratio to fit while maintaining aspect ratio
                ratio = min(canvas_width/img_width, canvas_height/img_height)
                new_width = int(img_width * ratio)
                new_height = int(img_height * ratio)
                
                # Resize image
                resized_img = self.img.resize((new_width, new_height), Image.LANCZOS)
                self.tk_img = ImageTk.PhotoImage(resized_img)
                
                # Update canvas
                canvas.delete("all")
                canvas.create_image(
                    canvas_width//2, 
                    canvas_height//2,  # Center the image
                    anchor=tk.CENTER, 
                    image=self.tk_img
                )
                
                # Set scroll region to exact image size
                canvas.config(scrollregion=(
                    0, 
                    0, 
                    max(canvas_width, new_width), 
                    max(canvas_height, new_height)
                ))
                
            except Exception as e:
                print(f"Error updating image display: {e}")  # Proper error handling

    def _resize_image(self, canvas):
        """Resize image to fit canvas while maintaining aspect ratio"""
        if hasattr(self, 'img'):
            # Get canvas size
            canvas_width = canvas.winfo_width()
            canvas_height = canvas.winfo_height()
            
            # Get original image size
            img_width, img_height = self.img.size
            
            # Calculate new size maintaining aspect ratio
            ratio = min(canvas_width/img_width, canvas_height/img_height)
            new_width = int(img_width * ratio)
            new_height = int(img_height * ratio)
            
            # Resize image
            resized_img = self.img.resize((new_width, new_height), Image.LANCZOS)
            self.tk_img = ImageTk.PhotoImage(resized_img)
            
            # Update canvas image
            canvas.itemconfig(self.img_id, image=self.tk_img)
            
            # Update scroll region
            canvas.config(scrollregion=canvas.bbox('all'))

    
    def display_text_file(self, file_path):
        text_frame = ttk.Frame(self.display_frame)
        text_frame.pack(fill=tk.BOTH, expand=True)
        
        # Text widget with scrollbar
        text_widget = tk.Text(text_frame, font=self.default_font, wrap=tk.WORD)
        scrollbar = ttk.Scrollbar(text_frame, orient=tk.VERTICAL, command=text_widget.yview)
        text_widget.configure(yscrollcommand=scrollbar.set)
        
        text_widget.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        
        # Load and display text
        try:
            with open(file_path, 'r', encoding='utf-8') as file:
                content = file.read()
                text_widget.insert(tk.END, content)
        except UnicodeDecodeError:
            with open(file_path, 'r', encoding='latin-1') as file:
                content = file.read()
                text_widget.insert(tk.END, content)
        
        text_widget.config(state=tk.DISABLED)
    
    def display_pdf_file(self, file_path):
        if PDF_SUPPORT:
            self.display_pdf_with_pymupdf(file_path)
        else:
             print("PDF display error.")
    
    def display_pdf_with_pymupdf(self, file_path):
        self.pdf_zoom = 1.0  # Default zoom
        self.pdf_file_path = file_path
        self.pdf_scroll_mode = 'vertical'  # 'vertical' or 'horizontal'
        self.pdf_current_page = 0

        pdf_frame = ttk.Frame(self.display_frame)
        pdf_frame.pack(fill=tk.BOTH, expand=True)

        tk.Label(pdf_frame, text="PDF Viewer", font=self.heading_font).pack(side=tk.TOP, anchor=tk.W)

        # Zoom controls
        zoom_frame = ttk.Frame(pdf_frame)
        zoom_frame.pack(fill=tk.X, pady=5)
        ttk.Button(zoom_frame, text="Zoom In", command=lambda: self.change_pdf_zoom(1.25)).pack(side=tk.LEFT, padx=5)
        ttk.Button(zoom_frame, text="Zoom Out", command=lambda: self.change_pdf_zoom(0.8)).pack(side=tk.LEFT, padx=5)
        self.zoom_label = ttk.Label(zoom_frame, text=f"Zoom: {int(self.pdf_zoom * 100)}%")
        self.zoom_label.pack(side=tk.LEFT, padx=10)
        ttk.Label(zoom_frame, text="Use mouse wheel to scroll pages.", font=self.default_font).pack(side=tk.LEFT, padx=10)

        # Page navigation controls
        nav_frame = ttk.Frame(pdf_frame)
        nav_frame.pack(fill=tk.X, pady=5)
        ttk.Label(nav_frame, text="Go to page:").pack(side=tk.LEFT)
        self.page_entry = ttk.Entry(nav_frame, width=5)
        self.page_entry.pack(side=tk.LEFT)
        ttk.Button(nav_frame, text="Go", command=self.go_to_pdf_page).pack(side=tk.LEFT, padx=5)
        self.page_label = ttk.Label(nav_frame, text="Page: 1")
        self.page_label.pack(side=tk.LEFT, padx=10)
        self.scroll_mode_btn = ttk.Button(nav_frame, text="Switch to Horizontal", command=self.toggle_pdf_scroll_mode)
        self.scroll_mode_btn.pack(side=tk.LEFT, padx=10)

        display_area = ttk.Frame(pdf_frame)
        display_area.pack(fill=tk.BOTH, expand=True)

        self.pdf_canvas = tk.Canvas(display_area, bg='white')
        v_scrollbar = ttk.Scrollbar(display_area, orient=tk.VERTICAL, command=self.pdf_canvas.yview)
        h_scrollbar = ttk.Scrollbar(display_area, orient=tk.HORIZONTAL, command=self.pdf_canvas.xview)
        self.pdf_canvas.configure(yscrollcommand=v_scrollbar.set, xscrollcommand=h_scrollbar.set)
        self.pdf_canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        v_scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        h_scrollbar.pack(side=tk.BOTTOM, fill=tk.X)

        # ADD THE BINDING HERE (new code)
        self.pdf_canvas.bind('<Configure>', lambda e: self.render_pdf_pages())

        self.render_pdf_pages()

    def change_pdf_zoom(self, factor):
        self.pdf_zoom *= factor
        self.zoom_label.config(text=f"Zoom: {int(self.pdf_zoom * 100)}%")
        self.render_pdf_pages()

    def go_to_pdf_page(self):
        try:
            page_num = int(self.page_entry.get()) - 1
            doc = fitz.open(self.pdf_file_path)
            if 0 <= page_num < len(doc):
                self.pdf_current_page = page_num
                self.render_pdf_pages()
            else:
                messagebox.showerror("Error", "Page number out of range.")
        except Exception as e:
            messagebox.showerror("Error", f"Invalid page number: {str(e)}")

    def toggle_pdf_scroll_mode(self):
        if self.pdf_scroll_mode == 'vertical':
            self.pdf_scroll_mode = 'horizontal'
            self.scroll_mode_btn.config(text="Switch to Vertical")
        else:
            self.pdf_scroll_mode = 'vertical'
            self.scroll_mode_btn.config(text="Switch to Horizontal")
        self.render_pdf_pages()

    def render_pdf_pages(self):
        self.pdf_canvas.delete("all")
        # Remove previous navigation button frames
        for widget in self.display_frame.winfo_children():
            if isinstance(widget, ttk.Frame):
                children = widget.winfo_children()
                if any(isinstance(child, ttk.Button) and child.cget("text") in ["Previous Page", "Next Page"] for child in children):
                    widget.destroy()
        
        try:
            doc = fitz.open(self.pdf_file_path)
            self.pdf_images = []
            
            if self.pdf_scroll_mode == 'vertical':
                y_offset = 0
                page_offsets = []
                
                for page_num in range(len(doc)):
                    page = doc.load_page(page_num)
                    
                    # Use the user's zoom factor directly without fitting to canvas
                    zoom = self.pdf_zoom
                    mat = fitz.Matrix(zoom, zoom)
                    pix = page.get_pixmap(matrix=mat)
                    img_data = pix.tobytes("ppm")
                    img = tk.PhotoImage(data=img_data)
                    self.pdf_images.append(img)
                    
                    # Center the page horizontally
                    canvas_width = self.pdf_canvas.winfo_width()
                    x_pos = max(0, (canvas_width - img.width()) // 2)
                    self.pdf_canvas.create_image(x_pos, y_offset, anchor=tk.NW, image=img)
                    page_offsets.append(y_offset)
                    y_offset += img.height() + 10  # Add some spacing between pages
                
                # Set scroll region to encompass all pages
                total_height = y_offset - 10  # Remove last spacing
                canvas_width = self.pdf_canvas.winfo_width()
                self.pdf_canvas.configure(scrollregion=(0, 0, canvas_width, total_height))
                self.page_label.config(text=f"Page: {self.pdf_current_page + 1}")
                
                # Scroll to selected page if in vertical mode
                if 0 <= self.pdf_current_page < len(page_offsets):
                    self.pdf_canvas.yview_moveto(page_offsets[self.pdf_current_page] / max(total_height, 1))
            
            else:  # Horizontal scroll mode - keep original fitting behavior
                canvas_height = self.pdf_canvas.winfo_height()
                page = doc.load_page(self.pdf_current_page)
                
                # Calculate zoom to fit page height to canvas height at 100% zoom
                zoom = (canvas_height - 20) / page.rect.height  # -20 for padding
                zoom *= self.pdf_zoom  # Apply user zoom factor
                
                mat = fitz.Matrix(zoom, zoom)
                pix = page.get_pixmap(matrix=mat)
                img_data = pix.tobytes("ppm")
                img = tk.PhotoImage(data=img_data)
                self.pdf_images = [img]
                
                # Center the page vertically
                y_pos = (canvas_height - img.height()) // 2
                self.pdf_canvas.create_image(0, y_pos, anchor=tk.NW, image=img)
                self.pdf_canvas.configure(scrollregion=(0, 0, img.width(), canvas_height))
                self.page_label.config(text=f"Page: {self.pdf_current_page + 1}")

                # Add navigation buttons for horizontal mode
                nav_btn_frame = ttk.Frame(self.display_frame)
                nav_btn_frame.pack(fill=tk.X, pady=5)
                ttk.Button(nav_btn_frame, text="Previous Page", command=self.prev_pdf_page).pack(side=tk.LEFT, padx=5)
                ttk.Button(nav_btn_frame, text="Next Page", command=self.next_pdf_page).pack(side=tk.LEFT, padx=5)
        
        except Exception as e:
            tk.Label(self.display_frame, text=f"Error loading PDF: {str(e)}", font=self.default_font).pack(expand=True)

    def prev_pdf_page(self):
        doc = fitz.open(self.pdf_file_path)
        if self.pdf_current_page > 0:
            self.pdf_current_page -= 1
            self.page_label.config(text=f"Page: {self.pdf_current_page + 1}")
            self.render_pdf_pages()

    def next_pdf_page(self):
        doc = fitz.open(self.pdf_file_path)
        if self.pdf_current_page < len(doc) - 1:
            self.pdf_current_page += 1
            self.page_label.config(text=f"Page: {self.pdf_current_page + 1}")
            self.render_pdf_pages()

    def display_csv_file(self, file_path):
        # Simple CSV display
        csv_frame = ttk.Frame(self.display_frame)
        csv_frame.pack(fill=tk.BOTH, expand=True)
        
        # Create treeview for CSV data
        csv_tree = ttk.Treeview(csv_frame)
        csv_scrollbar_y = ttk.Scrollbar(csv_frame, orient=tk.VERTICAL, command=csv_tree.yview)
        csv_scrollbar_x = ttk.Scrollbar(csv_frame, orient=tk.HORIZONTAL, command=csv_tree.xview)
        
        csv_tree.configure(yscrollcommand=csv_scrollbar_y.set, xscrollcommand=csv_scrollbar_x.set)
        
        csv_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        csv_scrollbar_y.pack(side=tk.RIGHT, fill=tk.Y)
        csv_scrollbar_x.pack(side=tk.BOTTOM, fill=tk.X)
        
        # Load CSV data
        try:
            with open(file_path, 'r', encoding='utf-8') as file:
                lines = file.readlines()
                if lines:
                    # Use first line as headers
                    headers = [col.strip() for col in lines[0].split(',')]
                    csv_tree['columns'] = headers
                    csv_tree['show'] = 'headings'
                    
                    for col in headers:
                        csv_tree.heading(col, text=col)
                        csv_tree.column(col, width=100)
                    
                    # Add data rows
                    for line in lines[1:]:
                        values = [val.strip() for val in line.split(',')]
                        csv_tree.insert('', 'end', values=values)
        except Exception as e:
            tk.Label(csv_frame, text=f"Error loading CSV: {str(e)}", 
                    font=self.default_font).pack(expand=True)
    
    def display_video_file(self, file_path):
        video_frame = ttk.Frame(self.display_frame)
        video_frame.pack(fill=tk.BOTH, expand=True)
        
        # Top section with title and filename
        title_frame = ttk.Frame(video_frame)
        title_frame.pack(fill=tk.X, pady=5)
        tk.Label(title_frame, text="Video File", font=self.heading_font).pack(side=tk.LEFT)
        tk.Label(title_frame, text=os.path.basename(file_path), font=self.default_font).pack(side=tk.LEFT, padx=10)

        # Video canvas with minimum size
        self.vlc_canvas = tk.Canvas(video_frame, width=400, height=300, bg='black')
        self.vlc_canvas.pack(fill=tk.BOTH, expand=True)

        # Control frame with improved layout
        control_frame = ttk.Frame(video_frame)
        control_frame.pack(fill=tk.X, pady=5)
        
        # Play/Pause button only (no separate pause/stop)
        btn_frame = ttk.Frame(control_frame)
        btn_frame.pack(side=tk.LEFT, padx=5, anchor=tk.W)
        
        self.play_btn = ttk.Button(btn_frame, text="Play", width=6, command=self.play_media)
        self.play_btn.pack(side=tk.LEFT, padx=2)

        # Seek bar with time label below
        seek_frame = ttk.Frame(control_frame)
        seek_frame.pack(fill=tk.X, expand=True, padx=5)
        
        self.seek_var = tk.DoubleVar()
        self.seek_slider = ttk.Scale(seek_frame, variable=self.seek_var, from_=0, to=100, 
                                    orient=tk.HORIZONTAL, command=self.on_seek)
        self.seek_slider.pack(fill=tk.X, expand=True)
        
        self.time_label = ttk.Label(seek_frame, text="00:00:00 / 00:00:00")
        self.time_label.pack()

        # Speed and volume controls in a compact grid
        settings_frame = ttk.Frame(control_frame)
        settings_frame.pack(side=tk.RIGHT, padx=5, anchor=tk.E)
        
        # Speed control
        ttk.Label(settings_frame, text="Speed:").grid(row=0, column=0, sticky=tk.W)
        self.speed_var = tk.DoubleVar(value=1.0)
        speed_menu = ttk.OptionMenu(settings_frame, self.speed_var, "1.0", "0.5", "0.75", "1.0", "1.25", "1.5", "2.0",
                                command=self.change_speed)
        speed_menu.grid(row=0, column=1, padx=5)

        # Volume control
        ttk.Label(settings_frame, text="Vol:").grid(row=0, column=2, sticky=tk.W)
        self.volume_var = tk.IntVar(value=50)
        volume_slider = ttk.Scale(settings_frame, variable=self.volume_var, from_=0, to=100, 
                                orient=tk.HORIZONTAL, command=self.change_volume, length=80)
        volume_slider.grid(row=0, column=3)

        # Captions section with improved layout
        caption_frame = ttk.Frame(video_frame)
        caption_frame.pack(fill=tk.X, pady=5)
        
        # Caption controls with proper button sizes
        caption_btn_frame = ttk.Frame(caption_frame)
        caption_btn_frame.pack(fill=tk.X)
        
        ttk.Button(caption_btn_frame, text="Generate", width=8, 
                command=lambda: self.generate_captions(file_path)).pack(side=tk.LEFT, padx=2)
        ttk.Button(caption_btn_frame, text="Download", width=9,  # Increased width to show full text
                command=lambda: self.download_generated_captions()).pack(side=tk.LEFT, padx=2)
        
        interval_frame = ttk.Frame(caption_btn_frame)
        interval_frame.pack(side=tk.LEFT, padx=5)
        ttk.Label(interval_frame, text="Interval:").pack(side=tk.LEFT)
        self.interval_var = tk.StringVar(value="30")
        interval_menu = ttk.OptionMenu(interval_frame, self.interval_var, "30", "10", "30", "60")
        interval_menu.pack(side=tk.LEFT)

        # Text container with scrollbar
        text_container = ttk.Frame(video_frame)
        text_container.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
        
        self.caption_text = tk.Text(text_container, height=5, width=60, wrap=tk.WORD, font=self.default_font)
        scrollbar = ttk.Scrollbar(text_container, orient=tk.VERTICAL, command=self.caption_text.yview)
        self.caption_text.configure(yscrollcommand=scrollbar.set)
        
        self.caption_text.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        
        self.current_media_file = file_path
        self.generated_captions = ""

        # Add this to the end of display_video_file and display_audio_file methods
        # Replace the existing VLC initialization section with:

        try:
            # Initialize VLC instance if not already created
            if not hasattr(self, 'vlc_instance') or self.vlc_instance is None:
                self.vlc_instance = vlc.Instance()
            
            self.vlc_player = self.vlc_instance.media_player_new()
            media = self.vlc_instance.media_new(file_path)
            self.vlc_player.set_media(media)
            
            # Set the display window - use the hidden canvas for audio
            if sys.platform == "win32":
                self.vlc_player.set_hwnd(self.vlc_canvas.winfo_id())
            elif sys.platform == "darwin":
                self.vlc_player.set_nsobject(self.vlc_canvas.winfo_id())
            else:
                self.vlc_player.set_xwindow(self.vlc_canvas.winfo_id())
            
            self.media_playing = False
            self.update_seek_bar()
            
        except Exception as e:
            # Show error message and fallback option
            error_frame = ttk.Frame(video_frame)
            error_frame.pack(fill=tk.BOTH, expand=True)
            
            tk.Label(error_frame, text="VLC Player Error", 
                    font=self.heading_font, fg="red").pack(pady=10)
            tk.Label(error_frame, text=f"Could not initialize VLC player: {str(e)}", 
                    font=self.default_font).pack(pady=5)
            tk.Label(error_frame, text="Try opening with external player:", 
                    font=self.default_font).pack(pady=5)
            
            ttk.Button(error_frame, text="Open with Default Application", 
                    command=lambda: self.open_external_file(file_path)).pack(pady=10)
            
            # Disable all media controls
            for widget in control_frame.winfo_children():
                if hasattr(widget, 'configure'):
                    widget.configure(state='disabled')

    def display_audio_file(self, file_path):
        # Clear existing widgets
        for widget in self.display_frame.winfo_children():
            widget.destroy()
        
        # Create a hidden canvas for audio playback
        self.vlc_canvas = tk.Canvas(self.display_frame, width=1, height=1, bg='white')
        self.vlc_canvas.pack()

        audio_frame = ttk.Frame(self.display_frame)
        audio_frame.pack(fill=tk.BOTH, expand=True)
        
        # Top section with title and filename
        title_frame = ttk.Frame(audio_frame)
        title_frame.pack(fill=tk.X, pady=5)
        tk.Label(title_frame, text="Audio File", font=self.heading_font).pack(side=tk.LEFT)
        tk.Label(title_frame, text=os.path.basename(file_path), font=self.default_font).pack(side=tk.LEFT, padx=10)

        # Control frame with improved layout
        control_frame = ttk.Frame(audio_frame)
        control_frame.pack(fill=tk.X, pady=10)
        
        # Play/Pause button only (no separate pause/stop)
        btn_frame = ttk.Frame(control_frame)
        btn_frame.pack(side=tk.LEFT, padx=5, anchor=tk.W)
        
        self.play_btn = ttk.Button(btn_frame, text="Play", width=6, command=self.play_media)
        self.play_btn.pack(side=tk.LEFT, padx=2)

        # Seek bar with time label below
        seek_frame = ttk.Frame(control_frame)
        seek_frame.pack(fill=tk.X, expand=True, padx=5)
        
        self.seek_var = tk.DoubleVar()
        self.seek_slider = ttk.Scale(seek_frame, variable=self.seek_var, from_=0, to=100, 
                                    orient=tk.HORIZONTAL, command=self.on_seek)
        self.seek_slider.pack(fill=tk.X, expand=True)
        
        self.time_label = ttk.Label(seek_frame, text="00:00:00 / 00:00:00")
        self.time_label.pack()

        # Speed and volume controls in a compact grid
        settings_frame = ttk.Frame(control_frame)
        settings_frame.pack(side=tk.RIGHT, padx=5, anchor=tk.E)
        
        # Speed control
        ttk.Label(settings_frame, text="Speed:").grid(row=0, column=0, sticky=tk.W)
        self.speed_var = tk.DoubleVar(value=1.0)
        speed_menu = ttk.OptionMenu(settings_frame, self.speed_var, "1.0", "0.5", "0.75", "1.0", "1.25", "1.5", "2.0",
                                command=self.change_speed)
        speed_menu.grid(row=0, column=1, padx=5)

        # Volume control
        ttk.Label(settings_frame, text="Vol:").grid(row=0, column=2, sticky=tk.W)
        self.volume_var = tk.IntVar(value=50)
        volume_slider = ttk.Scale(settings_frame, variable=self.volume_var, from_=0, to=100, 
                                orient=tk.HORIZONTAL, command=self.change_volume, length=80)
        volume_slider.grid(row=0, column=3)

        # Captions section with improved layout
        caption_frame = ttk.Frame(audio_frame)
        caption_frame.pack(fill=tk.X, pady=5)
        
        # Caption controls with proper button sizes
        caption_btn_frame = ttk.Frame(caption_frame)
        caption_btn_frame.pack(fill=tk.X)
        
        ttk.Button(caption_btn_frame, text="Generate", width=8, 
                command=lambda: self.generate_captions(file_path)).pack(side=tk.LEFT, padx=2)
        ttk.Button(caption_btn_frame, text="Download", width=9,
                command=lambda: self.download_generated_captions()).pack(side=tk.LEFT, padx=2)
        
        interval_frame = ttk.Frame(caption_btn_frame)
        interval_frame.pack(side=tk.LEFT, padx=5)
        ttk.Label(interval_frame, text="Interval:").pack(side=tk.LEFT)
        self.interval_var = tk.StringVar(value="30")
        interval_menu = ttk.OptionMenu(interval_frame, self.interval_var, "30", "10", "30", "60")
        interval_menu.pack(side=tk.LEFT)

        # Text container with scrollbar
        text_container = ttk.Frame(audio_frame)
        text_container.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
        
        self.caption_text = tk.Text(text_container, height=5, width=60, wrap=tk.WORD, font=self.default_font)
        scrollbar = ttk.Scrollbar(text_container, orient=tk.VERTICAL, command=self.caption_text.yview)
        self.caption_text.configure(yscrollcommand=scrollbar.set)
        
        self.caption_text.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        
        self.current_media_file = file_path
        self.generated_captions = ""

        # Add this to the end of display_video_file and display_audio_file methods
        # Replace the existing VLC initialization section with:

        try:
            # Initialize VLC instance if not already created
            if not hasattr(self, 'vlc_instance') or self.vlc_instance is None:
                self.vlc_instance = vlc.Instance()
            
            self.vlc_player = self.vlc_instance.media_player_new()
            media = self.vlc_instance.media_new(file_path)
            self.vlc_player.set_media(media)
            
            # Set the display window - use the hidden canvas for audio
            if sys.platform == "win32":
                self.vlc_player.set_hwnd(self.vlc_canvas.winfo_id())
            elif sys.platform == "darwin":
                self.vlc_player.set_nsobject(self.vlc_canvas.winfo_id())
            else:
                self.vlc_player.set_xwindow(self.vlc_canvas.winfo_id())
            
            self.media_playing = False
            self.update_seek_bar()

            self.media_playing = False
            self.update_seek_bar()
            
        except Exception as e:
            # Show error message and fallback option
            error_frame = ttk.Frame(audio_frame)
            error_frame.pack(fill=tk.BOTH, expand=True)
            
            tk.Label(error_frame, text="VLC Player Error", 
                    font=self.heading_font, fg="red").pack(pady=10)
            tk.Label(error_frame, text=f"Could not initialize VLC player: {str(e)}", 
                    font=self.default_font).pack(pady=5)
            tk.Label(error_frame, text="Try opening with external player:", 
                    font=self.default_font).pack(pady=5)
            
            ttk.Button(error_frame, text="Open with Default Application", 
                    command=lambda: self.open_external_file(file_path)).pack(pady=10)
            
            # Disable all media controls
            for widget in control_frame.winfo_children():
                if hasattr(widget, 'configure'):
                    widget.configure(state='disabled')

    # Add these new methods to handle media controls
    def play_media(self):
        if self.vlc_player:
            if not self.media_playing:
                self.vlc_player.play()
                self.media_playing = True
                self.play_btn.config(text="Pause")
            else:
                self.vlc_player.pause()
                self.media_playing = False
                self.play_btn.config(text="Play")

    def pause_media(self):
        if self.vlc_player:
            self.vlc_player.pause()
            self.media_playing = False
            self.play_btn.config(text="Play")

    def stop_media(self):
        if self.vlc_player:
            self.vlc_player.stop()
            self.media_playing = False
            self.play_btn.config(text="Play")
            self.seek_var.set(0)
            self.time_label.config(text="00:00:00 / 00:00:00")

    def on_seek(self, value):
        if self.vlc_player and self.vlc_player.is_seekable():
            media_length = self.vlc_player.get_length()
            if media_length > 0:
                seek_pos = float(value) / 100 * media_length
                self.vlc_player.set_time(int(seek_pos))

    def change_speed(self, speed):
        if self.vlc_player:
            self.vlc_player.set_rate(float(speed))

    def change_volume(self, volume):
        if self.vlc_player:
            try:
                # Ensure we're working with an integer
                vol = int(float(volume))  # First convert to float, then to int
                self.vlc_player.audio_set_volume(vol)
            except Exception as e:
                print(f"Error setting volume: {e}")

    def update_seek_bar(self):

        try:
            if not hasattr(self, 'vlc_player') or self.vlc_player is None:
                return

        except Exception as e:
            print(f"Error in update_seek_bar: {e}")
            return

        try:
            # Check if widgets still exist
            if not self.time_label.winfo_exists():
                return
                
            if self.vlc_player:
                media_length = self.vlc_player.get_length()
                media_time = self.vlc_player.get_time()
                
                if media_length > 0 and media_time >= 0:
                    # Update seek bar position
                    position = media_time / media_length * 100
                    self.seek_var.set(position)
                    
                    # Update time labels
                    current_time = self.format_time(media_time)
                    total_time = self.format_time(media_length)
                    self.time_label.config(text=f"{current_time} / {total_time}")
                    
                    # Update play button state
                    state = self.vlc_player.get_state()
                    if state == vlc.State.Playing:
                        self.media_playing = True
                        if self.play_btn.winfo_exists():
                            self.play_btn.config(text="Pause")
                    else:
                        self.media_playing = False
                        if self.play_btn.winfo_exists():
                            self.play_btn.config(text="Play")
        
        except Exception as e:
            print(f"Error in update_seek_bar: {e}")
            return
        

        
        # Schedule next update only if window still exists
        if hasattr(self, 'root') and self.root.winfo_exists():
            self.root.after(500, self.update_seek_bar)

    def format_time(self, milliseconds):
        seconds = milliseconds // 1000
        minutes, seconds = divmod(seconds, 60)
        hours, minutes = divmod(minutes, 60)
        return f"{hours:02d}:{minutes:02d}:{seconds:02d}"

    def display_unsupported_file(self, file_path):
        info_frame = ttk.Frame(self.display_frame)
        info_frame.pack(expand=True)
        
        tk.Label(info_frame, text="Unsupported File Type", 
                font=self.heading_font).pack(pady=10)
        tk.Label(info_frame, text=os.path.basename(file_path), 
                font=self.default_font).pack(pady=5)
        
        ttk.Button(info_frame, text="Open with Default Application", 
                  command=lambda: self.open_external_file(file_path)).pack(pady=10)
    
    def play_with_vlc(self, file_path):
        try:
            script_dir = os.path.dirname(os.path.abspath(__file__))
            vlc_paths = [
                os.path.join(script_dir, "vlc.exe"),
                os.path.join(script_dir, "VLC", "vlc.exe"),
                os.path.join(script_dir, "VLCPortable", "vlc.exe"),
                os.path.join(script_dir, "VLCPortable", "VLCportable.exe"),  # <-- Add this line
                os.path.join(script_dir, "VLCportable.exe"),                 # <-- And this
                "vlc.exe",
                r"C:\Program Files\VideoLAN\VLC\vlc.exe",
                r"C:\Program Files (x86)\VideoLAN\VLC\vlc.exe",
            ]

            vlc_path = None
            for path in vlc_paths:
                if os.path.exists(path):
                    vlc_path = path
                    break

            if not vlc_path:
                messagebox.showerror("Error", 
                    "VLC not found. Please place vlc.exe or VLCportable.exe in the same directory as this Python file, "
                    "or install VLC normally.")
                return

            volume = int(self.volume_var.get() * 2.56)
            self.vlc_process = subprocess.Popen([vlc_path, file_path, f"--volume={volume}"])

        except Exception as e:
            messagebox.showerror("Error", f"Error launching VLC: {str(e)}")
    
    def open_external_file(self, file_path):
        try:
            if os.name == 'nt':  # Windows
                os.startfile(file_path)
            elif os.name == 'posix':  # macOS and Linux
                subprocess.call(['open' if sys.platform == 'darwin' else 'xdg-open', file_path])
        except Exception as e:
            messagebox.showerror("Error", f"Error opening file: {str(e)}")
    
    def load_captions(self, caption_widget):
        caption_file = filedialog.askopenfilename(
            title="Select Caption File",
            filetypes=[("Text files", "*.txt"), ("SRT files", "*.srt"), ("All files", "*.*")]
        )
        
        if caption_file:
            try:
                with open(caption_file, 'r', encoding='utf-8') as file:
                    content = file.read()
                    caption_widget.config(state=tk.NORMAL)
                    caption_widget.delete(1.0, tk.END)
                    caption_widget.config(state=tk.DISABLED)
            except Exception as e:
                messagebox.showerror("Error", f"Error loading captions: {str(e)}")
    
    def download_captions(self, caption_widget):
        save_file = filedialog.asksaveasfilename(
            title="Save Captions As",
            defaultextension=".txt",
            filetypes=[("Text files", "*.txt"), ("All files", "*.*")]
        )
        
        if save_file:
            try:
                content = caption_widget.get(1.0, tk.END)
                with open(save_file, 'w', encoding='utf-8') as file:
                    file.write(content)
                messagebox.showinfo("Success", "Captions saved successfully!")
            except Exception as e:
                messagebox.showerror("Error", f"Error saving captions: {str(e)}")
    
    def show_context_menu(self, event):
        item = self.tree.identify_row(event.y)
        if item:
            self.tree.selection_set(item)
            item_path = self.tree.item(item, 'values')[0]
            norm_path = self.normalize_path(item_path)
            self.context_menu.delete(0, tk.END)
            if norm_path in self.unlocked_items:
                self.context_menu.add_command(label="Relock", command=self.relock_item)
            elif norm_path in self.passwords or norm_path in self.temp_passwords:
                self.context_menu.add_command(label="Unlock", command=self.unlock_item)
                self.context_menu.add_command(label="Hide", command=self.hide_item)
            else:
                self.context_menu.add_command(label="Set Password", command=self.set_password)
                self.context_menu.add_command(label="Set TEMP Lock", command=self.set_temp_password)
                self.context_menu.add_command(label="Hide", command=self.hide_item)
            self.context_menu.post(event.x_root, event.y_root)

    def set_password(self):
        selection = self.tree.selection()
        if not selection:
            return
        item_path = self.normalize_path(self.tree.item(selection[0], 'values')[0])
        password = simpledialog.askstring("Set Password", "Enter password:", show='*')
        if password:
            hashed_password = hashlib.sha256(password.encode()).hexdigest()
            self.passwords[item_path] = hashed_password
            if item_path in self.unlocked_items:
                self.unlocked_items.remove(item_path)
            self.save_passwords()
            messagebox.showinfo("Success", "Password set successfully!")
            self.refresh_tree()

    def set_temp_password(self):
        selection = self.tree.selection()
        if not selection:
            return
        item_path = self.tree.item(selection[0], 'values')[0]
        password = simpledialog.askstring("Set TEMP Lock", "Enter password:", show='*')
        if password:
            hashed_password = hashlib.sha256(password.encode()).hexdigest()
            self.temp_passwords[item_path] = hashed_password
            if item_path in self.unlocked_items:
                self.unlocked_items.remove(item_path)  # <-- Remove from unlocked!
            self.save_temp_passwords()
            messagebox.showinfo("Success", "TEMP Lock set successfully!")
            self.refresh_tree()

    def unlock_item(self):
        selection = self.tree.selection()
        if not selection:
            return
        item_path = self.tree.item(selection[0], 'values')[0]
        norm_path = self.normalize_path(item_path)
        if norm_path in self.passwords:
            password = simpledialog.askstring("Unlock Item", "Enter password:", show='*')
            if password:
                hashed_password = hashlib.sha256(password.encode()).hexdigest()
                if hashed_password == self.passwords[norm_path]:
                    self.unlocked_items.add(norm_path)
                    messagebox.showinfo("Success", "Item unlocked successfully!")
                    self.refresh_tree()
                    # Reselect the item and show its content
                    for item in self.tree.get_children():
                        self._reselect_and_display(item, norm_path)
                    self.apply_control_rules()
                else:
                    messagebox.showerror("Error", "Incorrect password!")
        elif norm_path in self.temp_passwords:
            password = simpledialog.askstring("Unlock TEMP Item", "Enter password:", show='*')
            if password:
                hashed_password = hashlib.sha256(password.encode()).hexdigest()
                if hashed_password == self.temp_passwords[norm_path]:
                    del self.temp_passwords[norm_path]
                    self.save_temp_passwords()
                    messagebox.showinfo("Success", "TEMP lock removed and item unlocked!")
                    self.refresh_tree()
                    for item in self.tree.get_children():
                        self._reselect_and_display(item, norm_path)
                    self.apply_control_rules()
                else:
                    messagebox.showerror("Error", "Incorrect password!")
        else:
            messagebox.showinfo("Info", "This item is not password protected.")

    def _reselect_and_display(self, item, norm_path):
        # Recursively search for the item in the tree and select it
        values = self.tree.item(item, 'values')
        if not values:
            return False  # Skip items with no values (e.g., dummy nodes)
        item_path = values[0]
        if self.normalize_path(item_path) == norm_path:
            self.tree.selection_set(item)
            self.tree.see(item)
            self.display_file(item_path)
            return True
        for child in self.tree.get_children(item):
            if self._reselect_and_display(child, norm_path):
                return True
        return False

    def relock_item(self):
        selection = self.tree.selection()
        if not selection:
            return
        item_path = self.tree.item(selection[0], 'values')[0]
        norm_path = self.normalize_path(item_path)
        if norm_path in self.unlocked_items:
            self.unlocked_items.remove(norm_path)
            messagebox.showinfo("Relocked", "Item has been relocked.")
            self.refresh_tree()
            # Optionally, show the not accessible message if it's a file
            if os.path.isfile(item_path):
                self.show_not_accessible_message(item_path)

    def is_item_unlocked(self, item_path):
        """Check if an item is unlocked by verifying its path and parent directories"""
        norm_path = self.normalize_path(item_path)
        current_path = norm_path
        
        while True:
            # Check if current path is locked
            if current_path in self.passwords and current_path not in self.unlocked_items:
                return False
            if current_path in self.temp_passwords:
                return False
            
            # Move up to parent directory
            parent_path = os.path.dirname(current_path)
            if parent_path == current_path:  # Reached root directory
                break
            current_path = parent_path
        
        return True

    def hide_item(self):
        selection = self.tree.selection()
        if not selection:
            return
        item_path = self.tree.item(selection[0], 'values')[0]
        norm_path = self.normalize_path(item_path)
        self.hidden_items.add(norm_path)
        self.refresh_tree()

    def is_item_visible(self, item_path):
        # Control rules take priority
        control_visible = self.check_control_rules(item_path)
        if control_visible is not None:
            return control_visible
        # If no control rule applies, check if hidden
        norm_path = self.normalize_path(item_path)
        if norm_path in self.hidden_items:
            return False
        return True
    
    def show_locked_message(self, file_path):
        for widget in self.display_frame.winfo_children():
            widget.destroy()
            
        lock_frame = ttk.Frame(self.display_frame)
        lock_frame.pack(expand=True)
        
        tk.Label(lock_frame, text="🔒 Locked File", font=self.heading_font).pack(pady=20)
        tk.Label(lock_frame, text="This file is password protected.", 
                font=self.default_font).pack(pady=5)
        tk.Label(lock_frame, text="Right-click and select 'Unlock' to access.", 
                font=self.default_font).pack(pady=5)
    
    def show_not_accessible_message(self, file_path):
        for widget in self.display_frame.winfo_children():
            widget.destroy()
        lock_frame = ttk.Frame(self.display_frame)
        lock_frame.pack(expand=True)
        tk.Label(lock_frame, text="⛔ Not Accessible", font=self.heading_font).pack(pady=20)
        tk.Label(lock_frame, text="This file/folder is locked and cannot be accessed.", font=self.default_font).pack(pady=5)
        tk.Label(lock_frame, text="Right-click and select 'Unlock' to access.", font=self.default_font).pack(pady=5)

    def load_controls(self):
        controls_file = "statements.txt"
        self.statements_rules = []
        if os.path.exists(controls_file):
            try:
                with open(controls_file, 'r', encoding='utf-8') as file:
                    content = file.read()
                    self.parse_statements_rules(content)
            except Exception as e:
                print(f"Error loading statements: {e}")

    def parse_statements_rules(self, content):
        self.statements_rules = []
        lines = content.split('\n')
        for line in lines:
            line = line.strip()
            if not line:
                continue
            if line.lower().startswith('hide '):
                # HIDE command: hide the specified item
                hide_item = line[5:].strip()
                # Hide both files and folders with this name in the root
                for entry in os.listdir(self.current_directory):
                    if entry == hide_item:
                        hide_path = os.path.join(self.current_directory, entry)
                        self.hidden_items.add(self.normalize_path(hide_path))
            elif line.lower().startswith('if'):
                self.statements_rules.append(line)

    def check_control_rules(self, item_path):
        for rule in getattr(self, 'statements_rules', []):
            m = re.match(
                r'IF (.+?) IS UNLOCKED, SHOW ([^ ]+)(?: IN ([^\.]+))?\.?$', rule, re.IGNORECASE)
            if m:
                required = [x.strip() for x in m.group(1).split('AND')]
                show_item = m.group(2).strip()
                show_folder = m.group(3).strip() if m.group(3) else None

                item_name = os.path.basename(item_path)
                is_file = os.path.isfile(item_path)
                is_folder = os.path.isdir(item_path)

                # Determine folder context robustly
                item_parent = os.path.normcase(os.path.abspath(os.path.dirname(item_path)))
                if show_folder:
                    folder_path = os.path.normcase(os.path.abspath(os.path.join(self.current_directory, show_folder)))
                    in_folder = item_parent == folder_path
                else:
                    root_path = os.path.normcase(os.path.abspath(self.current_directory))
                    in_folder = item_parent == root_path

                # Debug print
                # print(f"Rule: {rule} | Item: {item_name} | is_file: {is_file} | is_folder: {is_folder} | in_folder: {in_folder}")

                match = False
                if is_file and '.' in show_item and item_name == show_item and in_folder:
                    match = True
                elif is_folder and '.' not in show_item and item_name == show_item and in_folder:
                    match = True

                if match:
                    # Check if all required are unlocked
                    all_unlocked = True
                    for req in required:
                        req_path = os.path.join(self.current_directory, req)
                        norm_req_path = self.normalize_path(req_path)
                        if norm_req_path in self.passwords and norm_req_path not in self.unlocked_items:
                            all_unlocked = False
                            break
                    return all_unlocked
        return None
    
    def apply_control_rules(self):
        # Refresh the tree to apply new visibility rules
        self.refresh_tree()
    
    def refresh_tree(self):
        if self.current_directory:
            self.populate_tree(self.current_directory)
    
    def save_passwords(self):
        try:
            with open('passwords.json', 'w') as file:
                json.dump(self.passwords, file)
        except Exception as e:
            print(f"Error saving passwords: {e}")

    def load_passwords(self):
        try:
            if os.path.exists('passwords.json'):
                with open('passwords.json', 'r') as file:
                    self.passwords = json.load(file)
        except Exception as e:
            print(f"Error loading passwords: {e}")
            self.passwords = {}

    def load_temp_passwords(self):
        try:
            if os.path.exists('temp_passwords.json'):
                with open('temp_passwords.json', 'r') as file:
                    self.temp_passwords = json.load(file)
        except Exception as e:
            print(f"Error loading temp passwords: {e}")
            self.temp_passwords = {}

    def save_temp_passwords(self):
        try:
            with open('temp_passwords.json', 'w') as file:
                json.dump(self.temp_passwords, file)
        except Exception as e:
            print(f"Error saving temp passwords: {e}")

    def setup_menu(self):
        menubar = tk.Menu(self.root)
        self.root.config(menu=menubar)
        
        file_menu = tk.Menu(menubar, tearoff=0)
        menubar.add_cascade(label="File", menu=file_menu)
        file_menu.add_command(label="Select Root Directory", command=self.select_directory)
        file_menu.add_command(label="Set Custom Folder", command=self.set_custom_folder)  # NEW
        file_menu.add_command(label="Go to Script Drive", command=self.go_to_script_drive)
        file_menu.add_command(label="Refresh", command=self.refresh_tree)
        file_menu.add_separator()
        file_menu.add_command(label="Exit", command=self.root.quit)

    def load_initial_directory(self):
        # Check if custom folder is set first
        if self.custom_root_folder and os.path.exists(self.custom_root_folder):
            self.current_directory = self.custom_root_folder
        else:
            # Get the directory where the Python script is located
            script_path = os.path.abspath(__file__)
            script_directory = os.path.dirname(script_path)
            
            # Use the script directory instead of the entire drive
            self.current_directory = script_directory
            
        self.populate_tree(self.current_directory)

    def load_custom_folder(self):
        """Load the custom folder setting from file"""
        settings_file = 'settings.json'
        try:
            if os.path.exists(settings_file):
                with open(settings_file, 'r') as file:
                    settings = json.load(file)
                    self.custom_root_folder = settings.get('custom_root_folder', None)
        except Exception as e:
            print(f"Error loading custom folder setting: {e}")
            self.custom_root_folder = None

    # Add this new method
    def set_custom_folder(self):
        folder = filedialog.askdirectory(
            title="Select Custom Root Folder", 
            initialdir=self.current_directory
        )
        if folder:
            self.custom_root_folder = folder
            self.current_directory = folder
            self.populate_tree(folder)
            self.save_custom_folder()

    def go_to_script_drive(self):
            """Set current directory to the drive where the script is located."""
            script_path = os.path.abspath(__file__)
            drive_root = os.path.splitdrive(script_path)[0] + os.sep
            if os.path.exists(drive_root):
                self.current_directory = drive_root
                self.populate_tree(drive_root)

    def save_custom_folder(self):
        settings_file = 'settings.json'
        try:
            with open(settings_file, 'w') as file:
                json.dump({'custom_root_folder': self.custom_root_folder}, file)
        except Exception as e:
            print(f"Error saving custom folder setting: {e}")

    def get_display_name(self, item_path):
        base = os.path.basename(item_path)
        norm_path = self.normalize_path(item_path)
        if norm_path in self.temp_passwords:
            return f"{base} [🔒TEMP]"
        elif norm_path in self.passwords and norm_path not in self.unlocked_items:
            return f"{base} [🔒]"
        elif norm_path in self.passwords and norm_path in self.unlocked_items:
            return f"{base} [🔑]"  # Key symbol for unlocked regular lock
        else:
            return base

    def normalize_path(self, path):
        return os.path.normcase(os.path.abspath(os.path.normpath(path)))
    
    def generate_captions(self, file_path):
        def conversion_thread():
            try:
                # Get the selected interval from GUI
                interval = int(self.interval_var.get())
                
                # 1. Set path to ffmpeg.exe
                ffmpeg_path = os.path.join(
                    os.path.dirname(__file__),
                    "ffmpeg",
                    "bin",
                    "ffmpeg.exe"
                )
                
                # Verify FFmpeg exists
                if not os.path.exists(ffmpeg_path):
                    self.root.after(0, lambda: messagebox.showerror(
                        "Error",
                        "FFmpeg not found at:\n{}\nPlease download from https://ffmpeg.org/".format(ffmpeg_path)
                    ))
                    return

                # 2. Extract audio to WAV
                temp_wav = os.path.join(os.path.dirname(file_path), "temp_audio.wav")
                cmd = [
                    ffmpeg_path,
                    '-i', file_path,
                    '-ac', '1',  # Mono audio
                    '-ar', '16000',  # 16kHz sample rate
                    '-y',  # Overwrite without asking
                    temp_wav
                ]
                
                # Run FFmpeg
                subprocess.run(
                    cmd,
                    check=True,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    creationflags=subprocess.CREATE_NO_WINDOW
                )

                # 3. Load Vosk model
                model_path = os.path.join(
                    os.path.dirname(__file__),
                    "vosk-model",
                    "vosk-model-small-en-us-0.15"
                )
                
                if not os.path.exists(model_path):
                    self.root.after(0, lambda: messagebox.showerror(
                        "Error", 
                        "Vosk model not found at:\n{}\nDownload from https://alphacephei.com/vosk/models".format(model_path)
                    ))
                    return

                model = Model(model_path)
                wf = wave.open(temp_wav, 'rb')
                rec = KaldiRecognizer(model, wf.getframerate())
                rec.SetWords(True)

                # 4. Process audio with dynamic interval grouping
                results = []
                current_segment = []
                current_segment_start = 0
                
                while True:
                    data = wf.readframes(4000)
                    if len(data) == 0:
                        break
                        
                    if rec.AcceptWaveform(data):
                        result = json.loads(rec.Result())
                        if 'result' in result:
                            for word in result['result']:
                                # If this is the first word or we've reached the interval
                                if not current_segment or word['start'] >= current_segment_start + interval:
                                    if current_segment:  # If we have a previous segment, format and add it
                                        timestamp = "{:02d}:{:02d}:{:02d}".format(
                                            int(current_segment_start//3600),
                                            int((current_segment_start%3600)//60),
                                            int(current_segment_start%60)
                                        )
                                        results.append(f"[{timestamp}] {' '.join(current_segment)}\n")
                                        current_segment = []
                                    # Align to the selected interval boundary
                                    current_segment_start = word['start'] - (word['start'] % interval)
                                    
                                current_segment.append(word['word'])

                # Add the final segment if it exists
                if current_segment:
                    timestamp = "{:02d}:{:02d}:{:02d}".format(
                        int(current_segment_start//3600),
                        int((current_segment_start%3600)//60),
                        int(current_segment_start%60)
                    )
                    results.append(f"[{timestamp}] {' '.join(current_segment)}\n")

                # Get any remaining final result
                final_result = json.loads(rec.FinalResult())
                if final_result.get('text'):
                    results.append(final_result['text'])

                # 5. Clean up
                wf.close()
                os.remove(temp_wav)

                # 6. Update UI
                self.generated_captions = "\n".join(results)  # Join with newlines between segments
                self.root.after(0, self.update_caption_display)

            except Exception as err:
                error_message = str(err)  # Capture the error message
                self.root.after(0, lambda: messagebox.showerror(
                    "Error",
                    f"Caption generation failed:\n{error_message}"
                ))

        # Start the thread
        threading.Thread(target=conversion_thread, daemon=True).start()
        messagebox.showinfo(
            "Processing",
            f"Generating captions with {self.interval_var.get()}-second intervals...\nThis may take several minutes for long files."
        )

    def update_caption_display(self):
        self.caption_text.config(state=tk.NORMAL)
        self.caption_text.delete(1.0, tk.END)
        self.caption_text.insert(tk.END, self.generated_captions)
        self.caption_text.config(state=tk.DISABLED)

    def download_generated_captions(self):
        if not self.generated_captions:
            messagebox.showwarning("Warning", "No captions generated yet")
            return
        
        save_file = filedialog.asksaveasfilename(
            title="Save Captions As",
            defaultextension=".txt",
            filetypes=[("Text files", "*.txt"), ("SRT files", "*.srt"), ("All files", "*.*")]
        )
        
        if save_file:
            try:
                with open(save_file, 'w', encoding='utf-8') as f:
                    f.write(self.generated_captions)
                messagebox.showinfo("Success", "Captions saved successfully!")
            except Exception as e:
                messagebox.showerror("Error", f"Failed to save captions: {str(e)}")

    def setup_vlc_environment(self):  # Add self parameter
        """Setup VLC environment for PyInstaller executable"""
        import os
        import sys
        
        if getattr(sys, 'frozen', False):
            # Running as compiled executable
            base_path = sys._MEIPASS
            vlc_path = os.path.join(base_path, "VLC")
        else:
            # Running as script
            vlc_path = os.path.join(os.path.dirname(__file__), "VLC")
        
        if not os.path.exists(vlc_path):
            print(f"VLC path not found: {vlc_path}")
            return False
        
        # Add VLC path to system PATH at the beginning
        current_path = os.environ.get('PATH', '')
        if vlc_path not in current_path:
            os.environ['PATH'] = vlc_path + os.pathsep + current_path
        
        # Set VLC environment variables
        os.environ['VLC_PLUGIN_PATH'] = os.path.join(vlc_path, "plugins")
        os.environ['VLC_DATA_PATH'] = vlc_path
        
        # On Windows, try to preload VLC DLLs
        if sys.platform == "win32":
            try:
                import ctypes
                
                # List of DLLs to try loading in order
                dlls_to_load = [
                    "libvlccore.dll",
                    "libvlc.dll"
                ]
                
                for dll_name in dlls_to_load:
                    dll_path = os.path.join(vlc_path, dll_name)
                    if os.path.exists(dll_path):
                        try:
                            print(f"Loading {dll_name}...")
                            ctypes.CDLL(dll_path)
                            print(f"✅ Successfully loaded {dll_name}")
                        except Exception as e:
                            print(f"❌ Failed to load {dll_name}: {e}")
                    else:
                        print(f"❌ {dll_name} not found at {dll_path}")
                
            except Exception as e:
                print(f"Error setting up VLC DLLs: {e}")
                return False
        
        return True






def main():
    root = tk.Tk()
    app = FileOrganizerApp(root)
    root.mainloop()

if __name__ == "__main__":
    main()