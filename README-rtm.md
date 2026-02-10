# RTM (Rich Task Manager) for Arch Linux

A lightweight, terminal-based task manager optimized for Arch Linux and Hyprland/Sway workflows. It features a beautiful TUI, recurring tasks, desktop notifications, and native Waybar integration.

![Python](https://img.shields.io/badge/Python-3.10%2B-blue)
![License](https://img.shields.io/badge/License-MIT-green)
![Platform](https://img.shields.io/badge/Platform-Arch%20Linux-1793d1)

## Features

* **Interactive TUI:** Built with `rich` for a modern, responsive terminal interface.
* **Arch Linux Optimized:** Follows XDG standards (`~/.local/share/`) and uses `notify-send`.
* **Waybar Integration:** Live task counter and hover tooltips showing pending tasks with priority colors.
* **Recurrence:** Support for daily, weekly, or custom recurring tasks (e.g., `2d`, `3w`).
* **Smart Sorting:** Tasks are sorted by Priority (High/Medium/Low) and Due Date.
* **Automation:** Systemd integration for background notification checks and recurring task generation.

## Dependencies

* `python`
* `python-rich`
* `libnotify` (for desktop notifications)

**Install on Arch:**
```bash
sudo pacman -S python-rich libnotify

Installation
1. Clone/Copy script: Save rtm.py to ~/custom-scripts/RTM/.

2. Make executable:
chmod +x ~/custom-scripts/RTM/rtm.py

3. Add Alias (Recommended): 
Add this to your shell config (~/.bashrc or ~/.zshrc):

Usage
Interactive Mode (TUI)
Simply run the alias or script:
rtm

Keybindings:

A: Add Task

E: Edit Task

C: Complete Task

D: Delete Task

V: View Archive (Completed Tasks)

I: View Task Info

T: Toggle View (Table/Card)

F: Filter Tasks

Q: Quit

Command Line Interface (CLI)
You can manage tasks directly from the terminal without opening the UI (useful for scripts/rofi):
rtm -a "Buy Milk" --priority H --due 2024-05-20  # Add task
rtm -l                                         # List tasks
rtm -c 1                                       # Complete task ID 1
rtm -d 2                                       # Delete task ID 2

Automation (Systemd)
To enable background checks for notifications and recurring tasks:

1. Create ~/.config/systemd/user/rtm-check.service:
[Unit]
Description=RTM Task Manager Notification Check

[Service]
Type=oneshot
# %h expands to your home directory automatically
ExecStart=%h/custom-scripts/RTM/rtm.py -n -k

2. Create ~/.config/systemd/user/rtm-check.timer:
[Unit]
Description=Run RTM Check hourly

[Timer]
OnBootSec=5min
OnUnitActiveSec=1h
Persistent=true

[Install]
WantedBy=timers.target

3. Enable it:
systemctl --user enable --now rtm-check.timer

Waybar Integration
Add a live task counter to your Waybar configuration.

1. Add module to ~/.config/waybar/config (or .jsonc): Note: Replace kitty -e with your preferred terminal emulator.
"custom/rtm": {
    "format": "  {}",
    "return-type": "json",
    "exec": "~/custom-scripts/RTM/rtm.py --waybar",
    "on-click": "kitty -e rtm",
    "on-click-right": "~/custom-scripts/RTM/rtm.py -n",
    "interval": 10,
    "tooltip": true
}

2. Add style to ~/.config/waybar/style.css:
#custom-rtm {
    padding: 0 10px;
    color: #cdd6f4;
}
#custom-rtm.pending {
    background-color: #313244;
    border-bottom: 2px solid #fab387; /* Orange underline for pending */
}
#custom-rtm.empty {
    color: #a6adc8;
    border-bottom: 2px solid #a6e3a1; /* Green underline for empty */
}

Data Location
Your tasks are stored securely in JSON format, following XDG standards: ~/.local/share/arch_task_manager/tasks.json
