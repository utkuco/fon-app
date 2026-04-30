#!/usr/bin/env python3
"""
Preflight: fixes undetected_chromedriver ARM64 issue on Apple Silicon Macs.
Patches Patcher.patch_exe() to skip download when a custom binary already exists.

Run BEFORE tefas_scraper.py
"""
import sys, os, zipfile, urllib.request, shutil

UNDETECTED_CD_PATH = os.path.expanduser("~/Library/Application Support/undetected_chromedriver/undetected_chromedriver")
CHROMEDRIVER_URL = "https://storage.googleapis.com/chrome-for-testing-public/147.0.7727.117/mac-arm64/chromedriver-mac-arm64.zip"

def get_arch(path):
    with open(path, "rb") as f:
        magic = f.read(4)
    # ARM64 Mach-O magic (little-endian 0xFEEDFACE)
    if magic == b"\xcf\xfa\xed\xfe": return "arm64"
    # x86_64 Mach-O magic (little-endian 0xCFFAEDFE)
    if magic == b"\xfe\xed\xfa\xcf": return "x86_64"
    return "unknown"

def ensure_undetected_chromedriver_arm64():
    """Ensure undetected_chromedriver has ARM64 chromedriver binary."""
    needs_fix = True
    try:
        arch = get_arch(UNDETECTED_CD_PATH)
        print(f"[preflight] Current chromedriver arch: {arch}")
        needs_fix = (arch != "arm64")
    except FileNotFoundError:
        print("[preflight] No chromedriver found — will download")

    if needs_fix:
        print("[preflight] Downloading ARM64 chromedriver...")
        zip_path = "/tmp/cd_preflight.zip"
        urllib.request.urlretrieve(CHROMEDRIVER_URL, zip_path)
        extract_dir = "/tmp/cd_preflight"
        if os.path.exists(extract_dir):
            shutil.rmtree(extract_dir)
        with zipfile.ZipFile(zip_path, "r") as z:
            z.extractall(extract_dir)
        src = os.path.join(extract_dir, "chromedriver-mac-arm64", "chromedriver")
        os.chmod(src, 0o755)

        # Inject marker so is_binary_patched() returns True
        with open(src, "rb") as f:
            data = f.read()
        if b"undetected chromedriver" not in data:
            data += b"undetected chromedriver\x00"
            with open(src, "wb") as f:
                f.write(data)
            print("[preflight] Injected 'undetected chromedriver' marker")
        else:
            print("[preflight] Marker already present")

        shutil.copy2(src, UNDETECTED_CD_PATH)
        print(f"[preflight] Copied ARM64 chromedriver to {UNDETECTED_CD_PATH}")

        new_arch = get_arch(UNDETECTED_CD_PATH)
        print(f"[preflight] Verified arch: {new_arch}")
    else:
        print("[preflight] ARM64 chromedriver already in place — no action needed")

def patch_undetected_chromedriver():
    """Patch Patcher to always use existing binary and never re-download x86."""
    import undetected_chromedriver.patcher as patcher_module

    orig_init = patcher_module.Patcher.__init__

    def patched_init(self, *args, **kwargs):
        orig_init(self, *args, **kwargs)
        # Force custom_exe_path True so auto() skips download
        self._custom_exe_path = True
        # Also force executable_path to the ChromeDriverManager ARM64 path
        from pathlib import Path
        wdm_path = Path.home() / ".wdm" / "drivers" / "chromedriver" / "mac64"
        if wdm_path.exists():
            # Find the most recent ARM64 chromedriver
            for rev_dir in sorted(wdm_path.glob("*/chromedriver-mac-arm64/chromedriver"), reverse=True):
                import subprocess
                result = subprocess.run(["file", rev_dir], capture_output=True, text=True)
                if "arm64" in result.stdout:
                    self.executable_path = str(rev_dir)
                    print(f"[preflight] Using ChromeDriverManager ARM64: {rev_dir}")
                    break

    patcher_module.Patcher.__init__ = patched_init
    print("[preflight] Patcher.__init__ patched to force ARM64 chromedriver from ChromeDriverManager")

if __name__ == "__main__":
    ensure_undetected_chromedriver_arm64()
    patch_undetected_chromedriver()
    print("[preflight] Done. Run tefas_scraper.py now.")
