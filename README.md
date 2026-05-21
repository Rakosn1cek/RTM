# RTM (Rich Task Manager) for Arch Linux

A lightweight, terminal-based task manager for Linux. It features a beautiful TUI, recurring tasks, desktop notifications.

![Python](https://img.shields.io/badge/Python-3.10%2B-blue)
![License](https://img.shields.io/badge/License-MIT-green)
![Platform](https://img.shields.io/badge/Platform-Arch%20Linux-1793d1)

## Features

* **Interactive TUI:** Built with `rich` for a modern, responsive terminal interface.
* **Arch Linux Optimized:** Follows XDG standards (`~/.local/share/`) and uses `notify-send`.
* **Recurrence:** Support for daily, weekly, or custom recurring tasks (e.g., `2d`, `3w`).
* **Smart Sorting:** Tasks are sorted by Priority (High/Medium/Low) and Due Date.
* **Automation:** Systemd integration for background notification checks and recurring task generation.

## Dependencies

* `python3`
* `python-rich`
* `libnotify` (for desktop notifications)

**Install on Linux:**
`sudo pacman -S python-rich libnotify`

**Installation**
1. git clone https://github.com/Rakosn1cek/RTM.git ~/path/to/RTM/.

2. **Make executable**:
chmod +x ~/path/to/RTM/rtm.py

3. **Add Alias (Recommended)**: 
Add this to your shell config (~/.bashrc or ~/.zshrc):
`alias rtm="python3 ~/path/to/RTM/rtm.py"`

**Usage**

**Interactive Mode (TUI)**
Simply run the alias or script:

`rtm`

**Keybindings**:

A: Add Task

E: Edit Task

C: Complete Task

D: Delete Task

V: View Archive (Completed Tasks)

I: View Task Info

T: Toggle View (Table/Card)

F: Filter Tasks

Q: Quit

**Command Line Interface (CLI)**
You can manage tasks directly from the terminal without opening the UI:
- rtm -a "Buy Milk" --priority H --due 2024-05-20 ____________ -> Add task
- rtm -l ____________________________________________-> List tasks
- rtm -c 1 __________________________________________-> Complete task ID 1
- rtm -d 2 __________________________________________-> Delete task ID 2

**Automation (Systemd)**
To enable background checks for notifications and recurring tasks:

1. **Create** 

`~/.config/systemd/user/rtm-check.service`

[Unit]

Description=RTM Task Manager Notification Check

[Service]

Type=oneshot

**%h expands to your home directory automatically**

`ExecStart=%h/custom-scripts/RTM/rtm.py -n -k`

2. **Create**

`~/.config/systemd/user/rtm-check.timer`

[Unit]

Description=Run RTM Check hourly

[Timer]

OnBootSec=5min

OnUnitActiveSec=1h

Persistent=true

[Install]

WantedBy=timers.target

3. **Enable it**:

systemctl --user enable --now rtm-check.timer

Data Location
Your tasks are stored securely in JSON format, following XDG standards: 

`~/.local/share/arch_task_manager/tasks.json`
