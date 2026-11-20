# ImageMetaX

**Version 1.1.0** — batch analysis, image preview, and GPS coordinate conversion added.

**ImageMetaX** is a local-first image metadata extractor with a command-line interface (CLI) and a CustomTkinter desktop GUI. It supports Linux, Windows, and Android through Termux (CLI-first).

## Features

- Analyze a local image path or an online URL.
- Accept direct image URLs and webpage URLs; for webpages, it checks Open Graph, Twitter Card, and image tags.
- Extract available image dimensions, format, mode, frames, DPI, EXIF, GPS, file hashes, embedded image info, JPEG APP/COM segment details, and optional ExifTool metadata.
- Export reports as JSON, TXT, HTML, PDF, and CSV.
- Batch-analyze multiple local files or folders from CLI; GUI folder batch mode.
- GUI image preview.
- Convert embedded EXIF GPS DMS coordinates to decimal latitude/longitude and provide an OpenStreetMap link.
- GUI supports URL input, local file picker, report viewer, and export.
- Images are processed on your machine. Online URLs are downloaded to your machine for analysis; files are not uploaded to an ImageMetaX server.

> **Metadata limitations:** “All metadata” means all metadata exposed by the file and the installed parsers. Metadata may be absent, stripped by a platform, encrypted, malformed, or proprietary. Install ExifTool for much broader EXIF MakerNote, IPTC, and XMP support. No tool can recover metadata that is not present in the image.

## Requirements

- Python 3.10+
- Linux, Windows, or Termux
- Internet access only when analyzing online URLs or installing dependencies
- Optional: ExifTool executable for expanded metadata extraction
- Optional: a working graphical desktop for CustomTkinter GUI

## Install

### Linux

```bash
git clone https://github.com/saturnsingh/ImageMetaX.git
cd ImageMetaX
python3 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
pip install -r requirements.txt
```

Install ExifTool using your distribution package manager, for example:

```bash
sudo apt install libimage-exiftool-perl
```

### Windows (PowerShell)

```powershell
git clone https://github.com/saturnsingh/ImageMetaX.git
cd ImageMetaX
py -m venv .venv
.venv\Scripts\Activate.ps1
py -m pip install --upgrade pip
py -m pip install -r requirements.txt
```

Install ExifTool separately from its official distribution and ensure `exiftool` is available on PATH.

### Android Termux (CLI)

```bash
pkg update && pkg upgrade
pkg install python git libjpeg-turbo
termux-setup-storage
git clone https://github.com/saturnsingh/ImageMetaX.git
cd ImageMetaX
python -m pip install --upgrade pip
pip install -r requirements-termux.txt
```

Termux is supported as a CLI environment. A desktop GUI is not included in the Termux dependency set; the GUI requires a graphical display and a compatible Tk environment.

## Usage

### CLI: local file

```bash
python main.py --file "/path/to/photo.jpg" --pretty
```

Termux example:

```bash
python main.py --file "/storage/emulated/0/DCIM/Camera/photo.jpg" --pretty
```

Windows example:

```powershell
py main.py --file "C:\Users\You\Pictures\photo.jpg" --pretty
```

### CLI: direct image URL

```bash
python main.py --url "https://example.com/photo.jpg" --pretty
```

### CLI: webpage URL

```bash
python main.py --url "https://example.com/article-with-image" --pretty
```

ImageMetaX searches common Open Graph and Twitter image metadata, then ordinary image tags. Some sites block automated access, require login, or render images with JavaScript; those pages may not work.

### Batch analysis

```bash
# Analyze several files
python main.py --batch photo1.jpg photo2.png --output batch.json

# Analyze a directory
python main.py --batch ./photos --output batch.csv

# Include subdirectories
python main.py --batch ./photos --recursive --output batch.html
```

The GUI also has a **Batch folder** button. It recursively analyzes files under the selected folder and lets you export one combined report.

### Save a report

The output extension selects the export format:

```bash
python main.py --file photo.jpg --output report.json
python main.py --url "https://example.com/photo.jpg" --output report.html
python main.py --file photo.jpg --output report.pdf
python main.py --file photo.jpg --output report.csv
python main.py --file photo.jpg --output report.txt
```

### Launch GUI

```bash
python main.py --gui
```

Or:

```bash
python gui.py
```

## Supported formats

Pillow supports common formats such as JPEG, PNG, GIF, BMP, TIFF, and WebP. HEIC/HEIF support depends on the optional `pillow-heif` package and platform codec availability. Actual support depends on the installed Pillow build and codecs.

## Privacy and safety

- Local images are read from the specified path and are not transmitted.
- Online images must be downloaded to inspect their bytes; the request goes to the URL you provide.
- URL fetching accepts HTTP/HTTPS only, checks resolved addresses to block private/local IPs, rechecks redirects, limits downloads to 40 MiB, and uses request timeouts.
- Webpage extraction does not execute JavaScript.
- Treat metadata as untrusted input. Do not open suspicious exported HTML reports in privileged contexts.
- Hashes identify the exact downloaded/local file bytes; they do not prove authenticity or ownership.

## Project structure

```text
ImageMetaX/
├── main.py
├── gui.py
├── requirements.txt
├── requirements-termux.txt
├── README.md
├── LICENSE
└── imagemetax/
    ├── __init__.py
    ├── core.py
    ├── cli.py
    ├── gui.py
    └── exporters.py
```

## Known limitations

- “All details” cannot include data that was removed or never embedded.
- Some camera MakerNotes and proprietary tags require ExifTool and may still be undecodable.
- GPS coordinates are reported as stored EXIF values; this initial release does not geocode them into a street address.
- Webpage URLs may have multiple images; this version selects the first usable candidate it can download.
- GUI preview is a lightweight thumbnail preview; this is not a full image editor.

## License

MIT.
