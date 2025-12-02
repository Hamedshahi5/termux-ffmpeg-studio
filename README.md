Termux FFmpeg Studio 🎬

An interactive, modern CLI tool for Termux that makes working with FFmpeg and subtitles easy and beautiful.  
Built with Python 3.12+, Rich, and Questionary for the best UX.

---

✨ Features
- Burn external .srt subtitles into video (hardsub)
- Add subtitles as a separate track (softsub)
- Burn internal subtitle streams
- Custom font selection, size, and color
- Real-time progress bar with Rich
- Async fixes for Termux Python 3.12+

---

📦 Requirements
- Termux with Python 3.12+
- FFmpeg (pkg install ffmpeg)
- Python libraries:
  `bash
  pip install rich questionary fonttools
  `

---

🚀 Usage
1. Clone the repo:
   `bash
   git clone https://github.com/hamed/termux-ffmpeg-studio.git
   cd termux-ffmpeg-studio
   `
2. Run the script:
   `bash
   python3 studio.py
   `

---

📂 Directories
- Input/ → place your video files
- Subtitles/ → place .srt subtitle files
- Fonts/ → optional custom fonts
- Output/ → processed videos

---

🛡️ .gitignore
This project includes a .gitignore file to keep the repository clean.  
It tells Git which files/folders to ignore so they don’t get uploaded to GitHub.

---

📜 License
MIT License — free to use, modify, and share.
