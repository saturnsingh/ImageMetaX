import argparse, json, sys
from pathlib import Path
from .core import acquire, extract_metadata
from .exporters import export_report

def _analyze_one(source, is_url):
    data, info = acquire(str(source), is_url=is_url)
    return extract_metadata(data, info)

def main(argv=None):
    p=argparse.ArgumentParser(prog="imagemetax", description="Extract metadata from local images, direct URLs, webpages, or batches.")
    group=p.add_mutually_exclusive_group()
    group.add_argument("--url", help="Direct image URL or webpage URL containing an image")
    group.add_argument("--file", help="Local image path")
    group.add_argument("--gui", action="store_true", help="Launch desktop GUI")
    group.add_argument("--batch", nargs="+", help="Analyze multiple local image paths")
    p.add_argument("--recursive", action="store_true", help="Include subdirectories when --batch contains directories")
    p.add_argument("--output", "-o", help="Output path; extension selects json/txt/html/pdf/csv")
    p.add_argument("--pretty", action="store_true", help="Print formatted JSON")
    args=p.parse_args(argv)
    if args.gui:
        from .gui import launch
        launch(); return 0
    if not (args.url or args.file or args.batch):
        p.print_help(); return 0
    try:
        if args.batch:
            paths=[]
            for item in args.batch:
                candidate=Path(item).expanduser()
                if candidate.is_dir():
                    iterator=candidate.rglob("*") if args.recursive else candidate.glob("*")
                    paths.extend(x for x in iterator if x.is_file())
                elif candidate.is_file():
                    paths.append(candidate)
                else:
                    print(f"[!] Skipping missing path: {item}", file=sys.stderr)
            reports=[]
            for path in paths:
                try:
                    reports.append(_analyze_one(path, False))
                    print(f"[+] Analyzed: {path}")
                except Exception as e:
                    reports.append({"source": str(path), "error": str(e)})
                    print(f"[!] Failed: {path}: {e}", file=sys.stderr)
            report={"tool":"ImageMetaX","batch_count":len(reports),"results":reports}
        else:
            report=_analyze_one(args.url or args.file, bool(args.url))
        if args.output:
            fmt=Path(args.output).suffix.lower().lstrip(".")
            if fmt not in ("json","txt","html","pdf","csv"):
                raise ValueError("Output extension must be .json, .txt, .html, .pdf, or .csv")
            export_report(report,args.output,fmt)
            print(f"[+] Report saved: {args.output}")
        if args.pretty or not args.output:
            print(json.dumps(report,indent=2 if args.pretty else None,ensure_ascii=False))
        return 0
    except Exception as e:
        print(f"[!] {e}",file=sys.stderr); return 2
