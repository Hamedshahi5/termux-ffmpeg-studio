# ===== TERMUX FFMPEG STUDIO (v6.5 GITHUB FIXED) =====
# Fixes:
# 1. Softsub Logic (Now properly muxes into MP4 using mov_text)
# 2. Audio Codec (Re-encodes to AAC for MP4 compatibility)
# 3. Rich Panic (Escapes filenames containing square brackets)

import os
import re
import sys
import time
import shutil
import asyncio
import textwrap
import subprocess
from pathlib import Path
from typing import Optional, List, Tuple
from dataclasses import dataclass

# ===== DEPENDENCY CHECKER =====
def install_requirements():
    reqs = ["rich", "questionary", "fonttools"]
    missing = []
    for pkg in reqs:
        try:
            __import__(pkg)
        except ImportError:
            missing.append(pkg)
    
    if missing:
        print(f"Installing missing libraries: {', '.join(missing)}...")
        subprocess.check_call([sys.executable, "-m", "pip", "install"] + missing)
        print("Done. Restarting...")
        os.execv(sys.executable, ['python'] + sys.argv)

try:
    from rich.console import Console
    from rich.panel import Panel
    from rich.progress import Progress, SpinnerColumn, BarColumn, TextColumn, TimeRemainingColumn
    from rich.theme import Theme
    from rich.align import Align
    from rich.markup import escape  # <--- FIX 3: IMPORT ESCAPE
    import questionary
    from questionary import Style
    from fontTools.ttLib import TTFont
except ImportError:
    install_requirements()

# ===== CONFIGURATION =====
BASE_PATH = Path.home() / "storage" / "shared" / "FFmpegBot"
DIRECTORIES = {
    "INPUT": BASE_PATH / "Input",
    "SUBTITLES": BASE_PATH / "Subtitles",
    "OUTPUT": BASE_PATH / "Output",
    "FONTS": BASE_PATH / "Fonts",
    "LOGOS": BASE_PATH / "Logos"
}

# ===== THEME & UI CONSTANTS =====
CUSTOM_THEME = Theme({
    "info": "cyan",
    "warning": "yellow",
    "error": "bold red",
    "success": "bold green",
    "header": "bold magenta",
})
console = Console(theme=CUSTOM_THEME)

LOGO_TEXT = """
 [bold magenta]╔╗ ╔╗╔╗  ╔═╗╔═╗╦ ╦[/]
 [bold cyan]╠╩╗╠╣║║  ║ ║║  ╠═╣[/]
 [bold magenta]╚═╝╝╚╚╚═╝╚═╝╚═╝╩ ╩[/]
 [dim]  Studio v6.5 (GitHub Fixes)[/]
"""

Q_STYLE = Style([
    ('qmark', 'fg:#E91E63 bold'),
    ('question', 'fg:#ffffff bold'),
    ('answer', 'fg:#00ffff bold'),
    ('selected', 'fg:#00ff00 bold'),
    ('pointer', 'fg:#ff00ff bold'),
])

# ===== DATA MODELS =====
@dataclass
class JobConfig:
    video_path: Path
    mode: str  # 'hardsub_srt', 'softsub', 'hardsub_internal'
    subtitle_path: Optional[Path] = None
    internal_sub_index: Optional[int] = None
    
    # Text Styling
    font_path: Optional[Path] = None
    font_size: int = 48
    color_hex: str = "FFFF00"
    use_opaque_box: bool = False
    
    # Video Options
    watermark_path: Optional[Path] = None
    watermark_pos: str = "Bottom-Right"
    resolution: str = "Original"  # 'Original', '720p', '480p'
    is_preview: bool = False

# ===== SUBTITLE ENGINE =====
class AssGenerator:
    """Handles conversion of SRT to ASS with custom styling."""
    
    @staticmethod
    def _hex_to_ass(hex_color: str) -> str:
        h = hex_color.upper().replace('#', '').strip()
        if "YELLOW" in h: return "&H0000FFFF"
        if "WHITE" in h:  return "&H00FFFFFF"
        if "RED" in h:    return "&H000000FF"
        if len(h) != 6: return "&H0000FFFF"
        r, g, b = h[0:2], h[2:4], h[4:6]
        return f"&H00{b}{g}{r}"

    @staticmethod
    def _get_font_name(font_path: Optional[Path]) -> str:
        if not font_path: return "Arial"
        try:
            font = TTFont(str(font_path))
            name = font['name'].getName(1, 3, 1)
            return name.toUnicode() if name else font_path.stem
        except:
            return font_path.stem

    @classmethod
    def create(cls, srt_path: Path, config: JobConfig) -> Path:
        ass_path = DIRECTORIES["OUTPUT"] / f"temp_{int(time.time())}.ass"
        
        font_name = cls._get_font_name(config.font_path)
        primary_color = cls._hex_to_ass(config.color_hex)
        
        if config.use_opaque_box:
            border_style = "3"
            outline, back = "&H00000000", "&H00000000"
            shadow = "0"
        else:
            border_style = "1"
            outline, back = "&H00000000", "&H00000000"
            shadow = "1"

        header = textwrap.dedent(f"""
            [Script Info]
            ScriptType: v4.00+
            PlayResX: 1280
            PlayResY: 720

            [V4+ Styles]
            Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
            Style: Default,{font_name},{config.font_size},{primary_color},&H000000FF,{outline},{back},0,0,0,0,100,100,0,0,{border_style},2,{shadow},2,10,10,25,1

            [Events]
            Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
        """).strip() + "\n"

        regex = re.compile(r'(\d+)\n(\d{2}:\d{2}:\d{2},\d{3}) --> (\d{2}:\d{2}:\d{2},\d{3})\n((?:.+\n?)+)')
        
        try:
            with open(srt_path, 'r', encoding='utf-8-sig', errors='ignore') as f:
                content = f.read()
            
            if not content.strip(): raise ValueError("SRT file is empty")

            with open(ass_path, 'w', encoding='utf-8') as f:
                f.write(header)
                for match in regex.finditer(content):
                    start = match.group(2).replace(',', '.')[:-1]
                    end = match.group(3).replace(',', '.')[:-1]
                    text = re.sub(r'<[^>]+>', '', match.group(4).strip()).replace('\n', '\\N')
                    f.write(f"Dialogue: 0,{start},{end},Default,,0,0,0,,{text}\n")
            
            return ass_path
        except Exception as e:
            console.print(f"[error]Error generating ASS:[/error] {e}")
            raise

# ===== FFMPEG WORKER =====
class MediaProcessor:
    def __init__(self, config: JobConfig):
        self.cfg = config
        prefix = "PREVIEW_" if self.cfg.is_preview else "FINAL_"
        self.output_file = DIRECTORIES["OUTPUT"] / f"{prefix}{self.cfg.video_path.stem}.mp4"
        self.cleanup_files = []

    def _escape_path(self, path: Path) -> str:
        return str(path).replace('\\', '/').replace(':', '\\:').replace("'", "'\\''")

    async def _extract_internal_sub(self) -> Optional[Path]:
        temp_srt = DIRECTORIES["OUTPUT"] / "temp_extract.srt"
        cmd = [
            "ffmpeg", "-y", "-i", str(self.cfg.video_path), 
            "-map", f"0:{self.cfg.internal_sub_index}", 
            str(temp_srt)
        ]
        p = await asyncio.create_subprocess_exec(*cmd, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.STDOUT)
        await p.wait()
        
        if temp_srt.exists() and temp_srt.stat().st_size > 0:
            self.cleanup_files.append(temp_srt)
            return temp_srt
        return None

    async def get_video_duration(self) -> float:
        cmd = ["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "default=noprint_wrappers=1:nokey=1", str(self.cfg.video_path)]
        try:
            p = await asyncio.create_subprocess_exec(*cmd, stdout=asyncio.subprocess.PIPE)
            out, _ = await p.communicate()
            return float(out.decode().strip())
        except: return 0.0

    async def run(self):
        # 1. Prepare Subtitles (Only for Hardsub modes)
        ass_file = None
        if "hardsub" in self.cfg.mode:
            with console.status("[bold magenta]Preparing Hardsub...[/]", spinner="dots"):
                srt_source = self.cfg.subtitle_path
                
                if self.cfg.mode == 'hardsub_internal':
                    srt_source = await self._extract_internal_sub()
                    if not srt_source: return

                if srt_source:
                    try:
                        ass_file = AssGenerator.create(srt_source, self.cfg)
                        self.cleanup_files.append(ass_file)
                    except Exception: return

        # 2. Build FFmpeg Command
        cmd = ["ffmpeg", "-y", "-i", str(self.cfg.video_path)]
        
        # Keep track of input indices
        # Index 0: Video
        watermark_index = -1
        softsub_index = -1
        current_input_idx = 1

        # Add Watermark Input if needed
        if self.cfg.watermark_path:
            cmd.extend(["-i", str(self.cfg.watermark_path)])
            watermark_index = current_input_idx
            current_input_idx += 1
        
        # Add Softsub Input if needed (<-- FIX 1: Softsub Logic)
        if self.cfg.mode == "softsub" and self.cfg.subtitle_path:
            cmd.extend(["-i", str(self.cfg.subtitle_path)])
            softsub_index = current_input_idx
            current_input_idx += 1

        if self.cfg.is_preview:
            cmd.extend(["-ss", "00:00:30", "-t", "15"])

        # Filter Complex Logic
        filters = []
        last_vid = "[0:v]"
        
        # A. Hardsub Burning
        if ass_file:
            fonts_dir = self.cfg.font_path.parent if self.cfg.font_path else DIRECTORIES["FONTS"]
            filters.append(f"{last_vid}subtitles='{self._escape_path(ass_file)}':fontsdir='{self._escape_path(fonts_dir)}'[v_sub]")
            last_vid = "[v_sub]"
        
        # B. Scaling
        if self.cfg.resolution != "Original":
            h = "720" if self.cfg.resolution == "720p" else "480"
            filters.append(f"{last_vid}scale=-2:{h}[v_scale]")
            last_vid = "[v_scale]"
        
        # C. Watermark Overlay
        if watermark_index != -1:
            pos_map = {
                "Top-Left": "20:20", "Top-Right": "main_w-overlay_w-20:20",
                "Bottom-Left": "20:main_h-overlay_h-20", "Bottom-Right": "main_w-overlay_w-20:main_h-overlay_h-20",
                "Center": "(main_w-overlay_w)/2:(main_h-overlay_h)/2"
            }
            xy = pos_map.get(self.cfg.watermark_pos, "20:20")
            filters.append(f"{last_vid}[{watermark_index}:v]overlay={xy}[v_fin]")
            last_vid = "[v_fin]"

        if filters:
            cmd.extend(["-filter_complex", ";".join(filters), "-map", last_vid])
        else:
            cmd.extend(["-map", "0:v"])

        # Audio Settings (<-- FIX 2: Force AAC for MP4)
        cmd.extend(["-map", "0:a?", "-c:a", "aac", "-b:a", "192k"])

        # Softsub Mapping (<-- FIX 1 Continuation)
        if softsub_index != -1:
            cmd.extend(["-map", f"{softsub_index}:0", "-c:s", "mov_text"])

        # Video Encoding
        cmd.extend(["-c:v", "libx264", "-preset", "veryfast", "-crf", "23", "-sn"])
        # Note: -sn prevents copying internal subs from input video if we are doing softsub external
        
        cmd.extend(["-progress", "pipe:1", str(self.output_file)])

        # 3. Execution
        job_type = "PREVIEW (Synced)" if self.cfg.is_preview else "FULL RENDER"
        console.rule(f"[bold cyan]🚀 {job_type}[/]")
        
        total_duration = 15.0 if self.cfg.is_preview else await self.get_video_duration()
        
        # Redirect stderr to stdout to prevent hanging
        process = await asyncio.create_subprocess_exec(
            *cmd, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.STDOUT
        )

        error_logs = []
        with Progress(
            SpinnerColumn("dots", style="cyan"),
            TextColumn("[bold white]{task.description}"),
            BarColumn(bar_width=None, style="magenta", complete_style="bold cyan"),
            TextColumn("{task.percentage:>3.0f}%"),
            TimeRemainingColumn(),
            console=console
        ) as progress:
            task_id = progress.add_task("Processing...", total=100)
            while True:
                line = await process.stdout.readline()
                if not line: break
                line_str = line.decode('utf-8', 'ignore').strip()
                error_logs.append(line_str)
                if len(error_logs) > 20: error_logs.pop(0)

                if line_str.startswith('out_time_us='):
                    try:
                        us = int(line_str.split('=')[1])
                        current_sec = us / 1_000_000
                        percentage = (current_sec / total_duration) * 100
                        progress.update(task_id, completed=percentage)
                    except: pass

        await process.wait()
        for f in self.cleanup_files:
            if f.exists(): os.remove(f)

        if process.returncode == 0:
            console.print(Panel(f"[green]Saved to:[/]\n{self.output_file.name}", border_style="green", title="SUCCESS"))
            if not self.cfg.is_preview and shutil.which("termux-notification"):
                subprocess.run(["termux-notification", "--title", "FFmpeg Studio", "--content", "Render Complete"], check=False)
        else:
            console.print("[bold red]Render Failed![/]")
            console.print(Panel("\n".join(error_logs), title="Error Log", border_style="red"))

# ===== UTILS & UI =====
async def get_streams(video_path: Path) -> List[Tuple[int, str]]:
    cmd = ["ffprobe", "-v", "error", "-select_streams", "s", "-show_entries", "stream=index:stream_tags=language,title", "-of", "csv=p=0", str(video_path)]
    try:
        p = await asyncio.create_subprocess_exec(*cmd, stdout=asyncio.subprocess.PIPE)
        out, _ = await p.communicate()
        streams = []
        for line in out.decode().splitlines():
            parts = line.split(',')
            if parts:
                idx = int(parts[0])
                info = " ".join(parts[1:]).strip()
                streams.append((idx, f"Stream #{idx} ({info or 'Unknown'})"))
        return streams
    except: return []

async def select_file(directory: Path, extensions: tuple, prompt: str) -> Optional[Path]:
    files = sorted([f for f in directory.iterdir() if f.is_file() and f.suffix.lower() in extensions], key=lambda x: x.name)
    if not files: return None
    choices = [f.name for f in files]
    if directory.name == "Fonts": choices.insert(0, "Default System Font")
    sel = await questionary.select(f"{prompt}:", choices=choices, style=Q_STYLE).ask_async()
    if not sel or sel == "Default System Font": return None
    return directory / sel

async def main():
    os.system('cls' if os.name == 'nt' else 'clear')
    for p in DIRECTORIES.values(): p.mkdir(parents=True, exist_ok=True)
    console.print(Panel(Align.center(LOGO_TEXT), border_style="magenta", padding=(0, 2)))

    while True:
        # 1. Video
        video = await select_file(DIRECTORIES["INPUT"], ('.mp4', '.mkv', '.avi'), "Select Video")
        if not video: break
        
        mode_label = await questionary.select("Operation Mode:", choices=["Hardsub (SRT)", "Softsub (Mux)", "Internal Hardsub"], style=Q_STYLE).ask_async()
        mode_map = {"Hardsub (SRT)": "hardsub_srt", "Softsub (Mux)": "softsub", "Internal Hardsub": "hardsub_internal"}
        cfg = JobConfig(video_path=video, mode=mode_map[mode_label])

        # 2. Subtitles
        if cfg.mode in ["hardsub_srt", "softsub"]:
            sub = await select_file(DIRECTORIES["SUBTITLES"], ('.srt',), "Select SRT")
            if not sub: continue
            cfg.subtitle_path = sub
        elif cfg.mode == "hardsub_internal":
            console.print("[dim]Analyzing streams...[/]")
            streams = await get_streams(video)
            if not streams:
                console.print("[yellow]No subtitle streams found![/]")
                time.sleep(2); continue
            s_label = await questionary.select("Select Stream:", choices=[s[1] for s in streams], style=Q_STYLE).ask_async()
            cfg.internal_sub_index = next(s[0] for s in streams if s[1] == s_label)

        # 3. Styling (Hardsub Only)
        if "hardsub" in cfg.mode:
            cfg.font_path = await select_file(DIRECTORIES["FONTS"], ('.ttf', '.otf'), "Font Family")
            clr = await questionary.select("Font Color:", choices=["Yellow", "White", "Custom Hex"], style=Q_STYLE).ask_async()
            if clr == "Custom Hex":
                cfg.color_hex = await questionary.text("Enter Hex:", default="FFFF00").ask_async()
            else:
                cfg.color_hex = clr.upper()
            cfg.use_opaque_box = await questionary.confirm("Add Background Box?", default=False, style=Q_STYLE).ask_async()
            
            size_opts = ["30 (Standard)", "48 (Large)", "60 (Huge)", "Custom"]
            sz_sel = await questionary.select("Font Size:", choices=size_opts, default="48 (Large)", style=Q_STYLE).ask_async()
            if sz_sel == "Custom":
                raw_size = await questionary.text("Enter Size:", default="48").ask_async()
                cfg.font_size = int(raw_size) if raw_size.isdigit() else 48
            else:
                cfg.font_size = int(sz_sel.split(' ')[0])

        # 4. Settings
        cfg.resolution = await questionary.select("Output Resolution:", choices=["Original", "720p", "480p"], default="Original", style=Q_STYLE).ask_async()
        
        logos = list(DIRECTORIES["LOGOS"].glob("*"))
        valid_logos = [f for f in logos if f.suffix.lower() in ('.png', '.jpg')]
        if valid_logos:
            wm_choices = ["None"] + [f.name for f in valid_logos]
            wm_sel = await questionary.select("Add Watermark:", choices=wm_choices, style=Q_STYLE).ask_async()
            if wm_sel != "None":
                cfg.watermark_path = DIRECTORIES["LOGOS"] / wm_sel
                cfg.watermark_pos = await questionary.select("Position:", choices=["Bottom-Right", "Top-Right", "Top-Left", "Bottom-Left", "Center"], style=Q_STYLE).ask_async()

        # 5. Execution
        while True:
            # <--- FIX 3: Safe print using escape()
            summary = (
                f"\n[bold white]Target:[/][cyan] {escape(cfg.video_path.name)}[/]\n"
                f"[bold white]Mode:[/][green] {cfg.mode.upper()}[/] | "
                f"[bold white]Res:[/][cyan] {cfg.resolution}[/]"
            )
            console.print(Panel(summary, title="Job Summary", border_style="cyan"))
            
            action = await questionary.select("Ready?", choices=["👁️  Preview (15s)", "🚀 Start Render", "🔙 Edit Settings"], style=Q_STYLE).ask_async()
            
            if "Preview" in action:
                cfg.is_preview = True
                await MediaProcessor(cfg).run()
                cfg.is_preview = False
                input("\n[Press Enter to continue...]")
            elif "Start Render" in action:
                await MediaProcessor(cfg).run()
                break
            elif "Edit Settings" in action:
                break 
        
        if not await questionary.confirm("Process another video?", default=False, style=Q_STYLE).ask_async():
            break

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        console.print("\n[bold red]Aborted by user.[/]")
