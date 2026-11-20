import json, threading
from pathlib import Path
import customtkinter as ctk
from tkinter import filedialog, messagebox
from PIL import Image, ImageTk
from io import BytesIO
from .core import acquire, extract_metadata
from .exporters import export_report

class ImageMetaXApp(ctk.CTk):
    def __init__(self):
        super().__init__()
        self.title("ImageMetaX — Image Metadata Extractor")
        self.geometry("1180x790"); self.minsize(820,600)
        ctk.set_appearance_mode("dark"); ctk.set_default_color_theme("blue")
        self.report=None; self.preview_image=None
        self.grid_columnconfigure(0,weight=1); self.grid_rowconfigure(3,weight=1)
        header=ctk.CTkFrame(self,corner_radius=14); header.grid(row=0,column=0,padx=18,pady=(18,10),sticky="ew")
        ctk.CTkLabel(header,text="ImageMetaX",font=ctk.CTkFont(size=28,weight="bold")).pack(anchor="w",padx=18,pady=(12,0))
        ctk.CTkLabel(header,text="Local-first image metadata inspection · CLI + GUI",text_color="gray").pack(anchor="w",padx=18,pady=(0,12))
        source=ctk.CTkFrame(self); source.grid(row=1,column=0,padx=18,pady=8,sticky="ew"); source.grid_columnconfigure(0,weight=1)
        self.url=ctk.CTkEntry(source,placeholder_text="Paste a direct image URL or webpage URL…")
        self.url.grid(row=0,column=0,padx=10,pady=10,sticky="ew")
        ctk.CTkButton(source,text="Analyze URL",command=self.run_url,width=115).grid(row=0,column=1,padx=4,pady=10)
        ctk.CTkButton(source,text="Choose image",command=self.choose_file,width=125).grid(row=0,column=2,padx=4,pady=10)
        ctk.CTkButton(source,text="Batch folder",command=self.batch_folder,width=115).grid(row=0,column=3,padx=10,pady=10)
        bar=ctk.CTkFrame(self,fg_color="transparent"); bar.grid(row=2,column=0,padx=18,pady=4,sticky="ew")
        self.status=ctk.CTkLabel(bar,text="Ready — choose an image or enter a URL.",anchor="w")
        self.status.pack(side="left",fill="x",expand=True)
        self.export_menu=ctk.CTkOptionMenu(bar,values=["JSON","TXT","HTML","PDF","CSV"])
        self.export_menu.pack(side="right",padx=5)
        ctk.CTkButton(bar,text="Export",command=self.export,width=85).pack(side="right",padx=5)
        body=ctk.CTkFrame(self); body.grid(row=3,column=0,padx=18,pady=(5,18),sticky="nsew")
        body.grid_columnconfigure(1,weight=1); body.grid_rowconfigure(0,weight=1)
        self.preview=ctk.CTkFrame(body,width=300); self.preview.grid(row=0,column=0,padx=10,pady=10,sticky="ns")
        self.preview.grid_propagate(False)
        ctk.CTkLabel(self.preview,text="IMAGE PREVIEW",font=ctk.CTkFont(size=12,weight="bold")).pack(pady=10)
        self.preview_label=ctk.CTkLabel(self.preview,text="No image loaded",text_color="gray")
        self.preview_label.pack(expand=True,padx=8,pady=8)
        self.details=ctk.CTkTextbox(body,wrap="word",font=("Consolas",12))
        self.details.grid(row=0,column=1,padx=(0,10),pady=10,sticky="nsew")
        self.details.insert("1.0","Your metadata report will appear here. GPS coordinates, when present, are converted to decimal degrees and include an OpenStreetMap link.")
        self.details.configure(state="disabled")

    def choose_file(self):
        path=filedialog.askopenfilename(filetypes=[("Images","*.jpg *.jpeg *.png *.webp *.tif *.tiff *.bmp *.gif *.heic *.heif"),("All files","*.*")])
        if path: self._start(path,False)

    def run_url(self):
        url=self.url.get().strip()
        if url: self._start(url,True)
        else: messagebox.showinfo("ImageMetaX","Enter an image or webpage URL first.")

    def batch_folder(self):
        folder=filedialog.askdirectory()
        if not folder:return
        self.status.configure(text="Analyzing folder…")
        threading.Thread(target=self._batch_worker,args=(folder,),daemon=True).start()

    def _batch_worker(self,folder):
        results=[]
        for path in Path(folder).rglob("*"):
            if path.is_file():
                try:
                    data,info=acquire(str(path),False)
                    results.append(extract_metadata(data,info))
                except Exception:
                    continue
        report={"tool":"ImageMetaX","batch_count":len(results),"results":results}
        self.after(0,lambda:self._show(report,None))

    def _start(self,source,is_url):
        self.status.configure(text="Analyzing…")
        threading.Thread(target=self._worker,args=(source,is_url),daemon=True).start()

    def _worker(self,source,is_url):
        try:
            data,info=acquire(source,is_url)
            report=extract_metadata(data,info)
            self.after(0,lambda:self._show(report,data))
        except Exception as e:
            self.after(0,lambda:self._error(str(e)))

    def _show(self,report,data):
        self.report=report
        self.details.configure(state="normal"); self.details.delete("1.0","end")
        self.details.insert("1.0",json.dumps(report,indent=2,ensure_ascii=False)); self.details.configure(state="disabled")
        if data:
            try:
                image=Image.open(BytesIO(data)); image.thumbnail((260,560))
                self.preview_image=ImageTk.PhotoImage(image)
                self.preview_label.configure(image=self.preview_image,text="")
            except Exception:
                self.preview_label.configure(image=None,text="Preview unavailable")
        elif "results" in report:
            self.preview_label.configure(image=None,text=f"{report['batch_count']} images analyzed")
        gps=report.get("metadata",{}).get("gps_decimal")
        self.status.configure(text=("Analysis complete." + (f" GPS: {gps['latitude']}, {gps['longitude']}" if gps else "")) if "results" not in report else f"Batch complete: {report['batch_count']} images.")

    def _error(self,message):
        self.status.configure(text="Analysis failed.")
        messagebox.showerror("ImageMetaX",message)

    def export(self):
        if not self.report:
            messagebox.showinfo("ImageMetaX","Analyze an image before exporting."); return
        fmt=self.export_menu.get().lower()
        path=filedialog.asksaveasfilename(defaultextension="."+fmt,filetypes=[(fmt.upper(),"*."+fmt)])
        if not path:return
        try:
            export_report(self.report,path,fmt); messagebox.showinfo("ImageMetaX",f"Report saved to:\n{path}")
        except Exception as e: messagebox.showerror("Export failed",str(e))

def launch():
    ImageMetaXApp().mainloop()
