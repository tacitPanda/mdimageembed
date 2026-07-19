import threading
import queue
import shutil
import tkinter as tk
from tkinter import ttk, filedialog, scrolledtext, messagebox
from pathlib import Path
from datetime import date
import mdimage

LOG_POLL_INTERVAL = 100  # ms


def run_mdimage_worker(params, log_queue):
    try:
        base_dir = mdimage.ROOT

        markdown_path = mdimage.resolve_path(params["markdown_path"], base_dir)
        images_dir_param = params.get("images_dir")
        images_dir = mdimage.resolve_path(images_dir_param, base_dir) if images_dir_param else None
        destination_dir = mdimage.resolve_path(params["destination_dir"], base_dir)
        markdown_output_dir = mdimage.resolve_path(params["markdown_output_dir"], base_dir) if params.get("markdown_output_dir") else None
        current_date = date.today().strftime("%Y-%m-%d")
        link_style = params.get("link_style", "absolute")
        source_mode = params.get("source_mode", "remote")

        destination_dir.mkdir(parents=True, exist_ok=True)

        markdown_files = mdimage.get_markdown_files(markdown_path)
        if not markdown_files:
            log_queue.put(f"No markdown files found at: {markdown_path}\n")
            return

        copied_new = []
        copied_existing = []
        skipped = []
        markdown_copies = []

        for markdown_file in markdown_files:
            if markdown_file.parent == destination_dir:
                continue

            suffix = mdimage.get_destination_suffix(destination_dir, base_dir)
            if suffix and markdown_file.name.startswith(f"{suffix}__"):
                continue

            try:
                text = markdown_file.read_text(encoding="utf-8", errors="ignore")
            except Exception:
                log_queue.put(f"Failed to read: {markdown_file}\n")
                continue

            # Extract title to detect duplicates in the markdown output directory (if provided)
            def extract_title(md_text: str):
                # YAML front matter title
                if md_text.lstrip().startswith("---"):
                    parts = md_text.split("---")
                    if len(parts) >= 3:
                        fm = parts[1]
                        for line in fm.splitlines():
                            if line.strip().lower().startswith("title:"):
                                _, val = line.split(":", 1)
                                return val.strip().strip("\"' ")
                # Fallback: first ATX heading
                for line in md_text.splitlines():
                    lm = line.strip()
                    if lm.startswith("#"):
                        # take the text after leading #'s
                        return lm.lstrip('#').strip().strip("\"' ")
                return None

            title = extract_title(text)
            markdown_copy_parent = mdimage.resolve_path(str(markdown_output_dir), base_dir) if markdown_output_dir else markdown_file.parent

            def title_exists_in_dir(search_dir: Path, title_to_find: str) -> Path:
                if not title_to_find:
                    return None
                try:
                    for f in search_dir.rglob("*.md"):
                        try:
                            c = f.read_text(encoding="utf-8", errors="ignore")
                        except Exception:
                            continue
                        t = extract_title(c)
                        if t and t.strip().lower() == title_to_find.strip().lower():
                            return f
                except Exception:
                    return None
                return None

            if title:
                found = title_exists_in_dir(markdown_copy_parent, title)
                if found:
                    log_queue.put(f"Duplicate title found in {found} — skipping {markdown_file}\n")
                    continue

            copied_for_file = False
            refs = mdimage.extract_image_references(text)
            for reference in refs:
                image_path = mdimage.resolve_image_reference(
                    reference,
                    markdown_file,
                    images_dir,
                    destination_dir,
                    base_dir,
                    current_date,
                    source_mode,
                )
                if image_path is None:
                    log_queue.put(f"Unresolved reference in {markdown_file}: {reference}\n")
                    continue

                if image_path.parent != images_dir and image_path.parent != markdown_file.parent and image_path.parent != destination_dir:
                    log_queue.put(f"Skipping external ref for {markdown_file}: {reference} -> {image_path}\n")
                    continue

                copied_for_file = True
                dest = destination_dir / image_path.name
                if image_path.parent == destination_dir:
                    copied_existing.append((mdimage.display_path(markdown_file, base_dir), image_path.name))
                    log_queue.put(f"Already in destination (no action): {image_path.name} (from {markdown_file})\n")
                    continue

                if dest.exists():
                    skipped.append((mdimage.display_path(markdown_file, base_dir), image_path.name, "already_exists"))
                    log_queue.put(f"Skipped (exists): {image_path.name} (from {markdown_file})\n")
                    continue

                try:
                    shutil.copy2(image_path, dest)
                    copied_new.append((mdimage.display_path(markdown_file, base_dir), image_path.name))
                    log_queue.put(f"Copied: {image_path} -> {dest}\n")
                except Exception as e:
                    log_queue.put(f"Failed to copy {image_path} -> {dest}: {e}\n")

            if copied_for_file:
                markdown_copy_path = mdimage.build_markdown_copy_path(markdown_file, markdown_output_dir, current_date)
                if not markdown_copy_path.exists():
                    rewritten_text = mdimage.rewrite_markdown_copy(
                        text,
                        markdown_file,
                        images_dir,
                        destination_dir,
                        base_dir,
                        link_style,
                        current_date,
                    )
                    markdown_copy_path.parent.mkdir(parents=True, exist_ok=True)
                    try:
                        markdown_copy_path.write_text(rewritten_text, encoding="utf-8")
                        markdown_copies.append((mdimage.display_path(markdown_file, base_dir), markdown_copy_path.name))
                        log_queue.put(f"Wrote markdown copy: {markdown_copy_path}\n")
                    except Exception as e:
                        log_queue.put(f"Failed to write markdown copy {markdown_copy_path}: {e}\n")

        log_queue.put(f"Using markdown path: {markdown_path}\n")
        log_queue.put(f"Current date: {current_date}\n")
        log_queue.put(f"Using images directory: {images_dir}\n")
        log_queue.put(f"Copy destination: {destination_dir}\n")
        log_queue.put(f"Newly copied {len(copied_new)} file(s)\n")

        for source_md, image_name in copied_new[:200]:
            log_queue.put(f"- {source_md} -> {image_name}\n")

        if copied_existing:
            log_queue.put(f"{len(copied_existing)} file(s) already present in destination (no action taken)\n")
            for source_md, image_name in copied_existing[:200]:
                log_queue.put(f"- {source_md} -> {image_name}\n")

        total = len(copied_new) + len(copied_existing)
        if total > 200:
            log_queue.put(f"... and {total - 200} more\n")

        if markdown_copies:
            log_queue.put(f"Created {len(markdown_copies)} markdown copy file(s)\n")
            for source_md, copied_md_name in markdown_copies[:200]:
                log_queue.put(f"- {source_md} -> {copied_md_name}\n")

        if skipped:
            log_queue.put(f"Skipped {len(skipped)} existing or unresolved file(s)\n")

    except Exception as e:
        log_queue.put(f"Unhandled error: {e}\n")
    finally:
        log_queue.put("__DONE__")


class App:
    def __init__(self, root):
        self.root = root
        root.title("mdimage GUI")
        self.log_queue = queue.Queue()
        self.worker_thread = None

        frm = ttk.Frame(root, padding=8)
        frm.grid(row=0, column=0, sticky="nsew")
        root.columnconfigure(0, weight=1)
        root.rowconfigure(0, weight=1)

        # Inputs
        self.markdown_path_var = tk.StringVar(value=".")
        self.images_dir_var = tk.StringVar(value="Main Images")
        self.destination_dir_var = tk.StringVar(value="TEST")
        self.markdown_output_dir_var = tk.StringVar(value="")
        self.link_style_var = tk.StringVar(value="absolute")
        self.source_mode_var = tk.StringVar(value="remote")

        r = 0
        ttk.Label(frm, text="Markdown file or folder:").grid(row=r, column=0, sticky="w")
        ttk.Entry(frm, textvariable=self.markdown_path_var, width=50).grid(row=r, column=1, sticky="ew")
        ttk.Button(frm, text="Browse...", command=self.browse_markdown).grid(row=r, column=2)

        r += 1
        ttk.Label(frm, text="Images dir:").grid(row=r, column=0, sticky="w")
        self.images_entry = ttk.Entry(frm, textvariable=self.images_dir_var, width=50)
        self.images_entry.grid(row=r, column=1, sticky="ew")
        self.images_browse_btn = ttk.Button(frm, text="Browse...", command=self.browse_images)
        self.images_browse_btn.grid(row=r, column=2)

        r += 1
        ttk.Label(frm, text="Destination dir:").grid(row=r, column=0, sticky="w")
        ttk.Entry(frm, textvariable=self.destination_dir_var, width=50).grid(row=r, column=1, sticky="ew")
        ttk.Button(frm, text="Browse...", command=self.browse_destination).grid(row=r, column=2)

        r += 1
        ttk.Label(frm, text="Markdown output dir (optional):").grid(row=r, column=0, sticky="w")
        ttk.Entry(frm, textvariable=self.markdown_output_dir_var, width=50).grid(row=r, column=1, sticky="ew")
        ttk.Button(frm, text="Browse...", command=self.browse_markdown_output).grid(row=r, column=2)

        r += 1
        ttk.Label(frm, text="Link style:").grid(row=r, column=0, sticky="w")
        link_frame = ttk.Frame(frm)
        link_frame.grid(row=r, column=1, sticky="w")
        ttk.Radiobutton(link_frame, text="Absolute", variable=self.link_style_var, value="absolute").pack(side="left")
        ttk.Radiobutton(link_frame, text="Static (/assets/images)", variable=self.link_style_var, value="static").pack(side="left")

        r += 1
        ttk.Label(frm, text="Source mode:").grid(row=r, column=0, sticky="w")
        src_frame = ttk.Frame(frm)
        src_frame.grid(row=r, column=1, sticky="w")
        ttk.Radiobutton(src_frame, text="Remote", variable=self.source_mode_var, value="remote").pack(side="left")
        ttk.Radiobutton(src_frame, text="Local", variable=self.source_mode_var, value="local").pack(side="left")

        # Disable/enable images dir controls based on source mode
        self.source_mode_var.trace_add('write', lambda *args: self.on_source_mode_change())
        self.on_source_mode_change()

        r += 1
        self.run_button = ttk.Button(frm, text="Run", command=self.start)
        self.run_button.grid(row=r, column=0, sticky="w")
        ttk.Button(frm, text="Clear Log", command=self.clear_log).grid(row=r, column=1, sticky="w")

        r += 1
        self.log = scrolledtext.ScrolledText(frm, width=100, height=20)
        self.log.grid(row=r, column=0, columnspan=3, pady=(8, 0), sticky="nsew")
        frm.rowconfigure(r, weight=1)

        self.root.after(LOG_POLL_INTERVAL, self.poll_log_queue)

    def browse_markdown(self):
        # Prefer directory selection first for easy folder iteration; fallback to file selection
        d = filedialog.askdirectory(title="Select a markdown directory (or Cancel to choose a file)")
        if d:
            self.markdown_path_var.set(d)
            return
        # fallback to file selection
        path = filedialog.askopenfilename(title="Select a markdown file", filetypes=[("Markdown", "*.md" )])
        if path:
            self.markdown_path_var.set(path)

    def browse_images(self):
        d = filedialog.askdirectory(title="Select images directory")
        if d:
            self.images_dir_var.set(d)

    def browse_destination(self):
        d = filedialog.askdirectory(title="Select destination directory")
        if d:
            self.destination_dir_var.set(d)

    def browse_markdown_output(self):
        d = filedialog.askdirectory(title="Select markdown output directory")
        if d:
            self.markdown_output_dir_var.set(d)

    def on_source_mode_change(self):
        """Enable/disable the images directory controls depending on source mode.
        When switching to 'remote', save the current images dir, clear the field and disable controls.
        When switching back to 'local', restore the saved value (or default) and re-enable controls.
        """
        mode = self.source_mode_var.get()
        if mode == "remote":
            # Save the current value so it can be restored when switching back
            try:
                self._saved_images_dir = self.images_dir_var.get()
            except Exception:
                self._saved_images_dir = ""
            try:
                self.images_entry.config(state="disabled")
                self.images_browse_btn.config(state="disabled")
            except Exception:
                pass
            # Clear the visible field to avoid confusion
            try:
                self.images_dir_var.set("")
            except Exception:
                pass
        else:
            # Restore saved value or default
            saved = getattr(self, "_saved_images_dir", "") or "Main Images"
            try:
                self.images_dir_var.set(saved)
            except Exception:
                pass
            try:
                self.images_entry.config(state="normal")
                self.images_browse_btn.config(state="normal")
            except Exception:
                pass

    def start(self):
        if self.worker_thread and self.worker_thread.is_alive():
            messagebox.showinfo("Running", "Worker is already running")
            return

        # If remote mode, do not pass an images_dir (set to None). If local, pass value or default.
        src_mode = self.source_mode_var.get()
        images_dir_val = None if src_mode == "remote" else (self.images_dir_var.get() or "Main Images")

        params = {
            "markdown_path": self.markdown_path_var.get() or ".",
            "images_dir": images_dir_val,
            "destination_dir": self.destination_dir_var.get() or "TEST",
            "markdown_output_dir": self.markdown_output_dir_var.get() or None,
            "link_style": self.link_style_var.get(),
            "source_mode": src_mode,
        }

        self.run_button.config(state="disabled")
        self.log_queue.put("Starting run...\n")
        self.worker_thread = threading.Thread(target=run_mdimage_worker, args=(params, self.log_queue), daemon=True)
        self.worker_thread.start()

    def clear_log(self):
        self.log.delete("1.0", tk.END)

    def poll_log_queue(self):
        try:
            while True:
                msg = self.log_queue.get_nowait()
                if msg == "__DONE__":
                    self.run_button.config(state="normal")
                    continue
                self.log.insert(tk.END, msg)
                self.log.see(tk.END)
        except queue.Empty:
            pass
        self.root.after(LOG_POLL_INTERVAL, self.poll_log_queue)


if __name__ == "__main__":
    root = tk.Tk()
    app = App(root)
    root.mainloop()
