#!/usr/bin/env python3
import json
import os
import sys
import argparse
import subprocess
import shutil
from pathlib import Path
from datetime import datetime, timedelta
from rich.console import Console, Group
from rich.table import Table
from rich.panel import Panel
from rich.text import Text
from rich.style import Style
from rich.align import Align
import re

# --- Constants and Configuration ---

APP_NAME = "arch_task_manager"
DATA_DIR = Path.home() / ".local" / "share" / APP_NAME
DATA_DIR.mkdir(parents=True, exist_ok=True)
TASK_FILE = DATA_DIR / "tasks.json"

DATE_FORMAT = "%Y-%m-%d"
VERSION = "v1.9.0-full-feature" 

NOTIFY_CMD = shutil.which("notify-send")

PRIORITY_MAP = {
    'H': Style(color="red", bold=True),
    'M': Style(color="yellow", bold=True),
    'L': Style(color="green", bold=True),
    'High': Style(color="red", bold=True),
    'Medium': Style(color="yellow", bold=True),
    'Low': Style(color="green", bold=True),
}

PRIORITY_BORDER_COLOR_MAP = {
    'H': "hot_pink", 
    'M': "orange1", 
    'L': "cyan",     
}

TASK_TITLE_COLOR_MAP = {
    'H': "bold red", 
    'M': "bold orange1",
    'L': "bold cyan",
}

# --- Utility Functions ---

def is_notification_daemon_available():
    return NOTIFY_CMD is not None

def parse_interval(interval_str):
    interval_str = interval_str.strip().lower()
    match = re.match(r'(\d+)([dwm])', interval_str)
    if match:
        count = int(match.group(1))
        unit = match.group(2)
        if unit == 'd': return (timedelta(days=count), f"every {count} day(s)")
        elif unit == 'w': return (timedelta(weeks=count), f"every {count} week(s)")
        elif unit == 'm': return (timedelta(days=30 * count), f"every {count} month(s)")

    if interval_str == 'daily': return (timedelta(days=1), "Daily")
    elif interval_str == 'weekly': return (timedelta(weeks=1), "Weekly")
    elif interval_str == 'monthly': return (None, "Monthly") 
    return (None, None)

def calculate_next_due_date(last_due_date_str, interval_str):
    try:
        last_due_date = datetime.strptime(last_due_date_str, DATE_FORMAT)
    except (TypeError, ValueError):
        return None

    interval_str = interval_str.lower()
    interval_data, _ = parse_interval(interval_str)

    if interval_data:
        next_due_date = last_due_date + interval_data
        return next_due_date.strftime(DATE_FORMAT)
    
    elif interval_str == 'monthly':
        current_year = last_due_date.year
        current_month = last_due_date.month
        current_day = last_due_date.day
        if current_month == 12:
            next_month = 1
            next_year = current_year + 1
        else:
            next_month = current_month + 1
            next_year = current_year
        try:
            next_due_date = datetime(next_year, next_month, current_day)
        except ValueError:
            if next_month == 2:
                if next_year % 4 == 0 and (next_year % 100 != 0 or next_year % 400 == 0):
                    next_due_date = datetime(next_year, next_month, 29)
                else:
                    next_due_date = datetime(next_year, next_month, 28)
            elif next_month in [4, 6, 9, 11]:
                next_due_date = datetime(next_year, next_month, 30)
            else:
                 return None
        return next_due_date.strftime(DATE_FORMAT)
    return None

# --- CLI Argument Parsing ---

def parse_args():
    parser = argparse.ArgumentParser(description="Rich Task Manager")
    parser.add_argument('--tui', action='store_true', help="Force TUI mode.")
    parser.add_argument('-a', '--add', type=str, help="Add task.")
    parser.add_argument('-c', '--complete', type=int, help="Complete task.")
    parser.add_argument('-u', '--uncomplete', type=int, help="Uncomplete task.")
    parser.add_argument('-d', '--delete', type=int, help="Delete task.")
    parser.add_argument('-r', '--report', action='store_true', help="Report.")
    parser.add_argument('-l', '--list', action='store_true', help="List tasks.")
    parser.add_argument('-n', '--notify-check', action='store_true', help="Check notifications.")
    parser.add_argument('-k', '--recurrence-check', action='store_true', help="Process recurrence.")
    parser.add_argument('--waybar', action='store_true', help="Output JSON for Waybar.")

    parser.add_argument('--desc', type=str, default="", help="Description.")
    parser.add_argument('--due', type=str, default=None, help="Due date.")
    parser.add_argument('--priority', type=str, default="M", choices=["H", "M", "L", "h", "m", "l"], help="Priority.")
    parser.add_argument('--repeat', type=str, default=None, help="Recurrence.")

    args = parser.parse_args()
    if args.priority: args.priority = args.priority.upper()
    return args

# --- TaskManager Class ---

class TaskManager:
    def __init__(self):
        self.console = Console()
        self.tasks = self.load_tasks()
        self.next_id = max((t.get('id', 0) for t in self.tasks), default=0) + 1
        self.view_mode = "auto"
        self.notify_available = is_notification_daemon_available()

    def load_tasks(self):
        if TASK_FILE.exists():
            try:
                with open(TASK_FILE, 'r') as f:
                    return json.load(f)
            except json.JSONDecodeError:
                return []
        return []

    def save_tasks(self):
        for task in self.tasks:
            if task.get('completed', False) and task.get('processed_for_recurrence', False):
                 if 'repeat_interval' not in task or task['repeat_interval'] is None:
                     if 'processed_for_recurrence' in task:
                         del task['processed_for_recurrence']
        with open(TASK_FILE, 'w') as f:
            json.dump(self.tasks, f, indent=4)

    def get_task_by_id(self, task_id):
        try:
            return next((t for t in self.tasks if t['id'] == int(task_id)), None)
        except ValueError:
            return None

    def get_task_index_by_id(self, task_id):
        try:
            task_id = int(task_id)
            for i, task in enumerate(self.tasks):
                if task['id'] == task_id: return i
            return -1
        except ValueError:
            return -1

    def get_sorted_tasks(self, completed=False):
        filtered_tasks = [t for t in self.tasks if t.get('completed', False) == completed]
        def sort_key(task):
            p = task.get('priority', 'L')
            if p in ['High', 'H']: p = 'H'
            elif p in ['Medium', 'M']: p = 'M'
            else: p = 'L'
            priority_order = {'H': 1, 'M': 2, 'L': 3}
            due_date_value = task.get('due_date')
            if due_date_value is None: due_date = datetime.max
            else:
                try:
                    due_date = datetime.strptime(due_date_value, DATE_FORMAT)
                except ValueError:
                    due_date = datetime.max
            return (priority_order.get(p, 3), due_date)
        return sorted(filtered_tasks, key=sort_key)

    # --- Waybar Output Method ---
    def generate_waybar_json(self):
        """Outputs JSON for Waybar."""
        pending_tasks = self.get_sorted_tasks(completed=False)
        count = len(pending_tasks)
        
        text = str(count)
        alt = "pending" if count > 0 else "empty"
        
        if count == 0:
            tooltip = "No pending tasks."
            class_name = "empty"
        else:
            tooltip_lines = []
            tooltip_lines.append(f"<b><span color='#cba6f7'>Pending Tasks ({count})</span></b>")
            
            for task in pending_tasks[:15]:
                prio = task.get('priority', 'M')
                title = task['title'].replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
                
                if prio == 'H': color = "#f38ba8"
                elif prio == 'M': color = "#fab387"
                else: color = "#a6e3a1"
                
                due_info = ""
                if task.get('due_date'):
                    try:
                        due = datetime.strptime(task['due_date'], DATE_FORMAT).date()
                        today = datetime.now().date()
                        if due < today:
                            due_info = " <span color='#ff0000'>(Overdue)</span>"
                        elif due == today:
                            due_info = " <span color='#fab387'>(Today)</span>"
                    except ValueError: pass

                line = f"<span color='{color}'><b>[{prio}]</b></span> {title}{due_info}"
                tooltip_lines.append(line)

            if count > 15:
                tooltip_lines.append(f"<i>...and {count - 15} more</i>")
                
            tooltip = "\n".join(tooltip_lines)
            class_name = "pending"

        output = {
            "text": text,
            "tooltip": tooltip,
            "class": class_name,
            "alt": alt
        }
        print(json.dumps(output))

    # --- TUI ---
    def add_task(self):
        self.console.print("\n[bold cyan]--- Add New Task ---[/bold cyan]")
        while True:
            title = self.console.input("[bold]Title:[/bold] ").strip()
            if title: break
            self.console.print("[red]Required.[/red]")
        description = self.console.input("[bold]Desc:[/bold] ").strip()
        priority = "M"
        while True:
            prio_input = self.console.input("[bold]Priority (H, M, L) [M]:[/bold] ").upper().strip()
            if not prio_input: break 
            if prio_input in ['H', 'M', 'L']:
                priority = prio_input
                break
        due_date_str = None
        while True:
            date_input = self.console.input(f"[bold]Due ({DATE_FORMAT}):[/bold] ").strip()
            if not date_input: break
            try:
                datetime.strptime(date_input, DATE_FORMAT)
                due_date_str = date_input
                break
            except ValueError: self.console.print(f"[red]Use {DATE_FORMAT}.[/red]")
        repeat_interval = None
        if due_date_str:
             while True:
                repeat_input = self.console.input("[bold]Repeat (daily, 2w):[/bold] ").strip()
                if not repeat_input: break
                _, desc = parse_interval(repeat_input)
                if desc:
                    repeat_interval = repeat_input
                    break
                else: self.console.print("[red]Invalid format.[/red]")
        
        self._add_task_internal(title, description, priority, due_date_str, repeat_interval)
        self.console.print(f"\n[bold green]Added![/bold green]")

    def check_and_send_notifications(self):
        if not self.notify_available: return
        today = datetime.now().date()
        overdue_tasks = []
        today_tasks = []
        for task in self.get_sorted_tasks(completed=False):
            due_date_str = task.get('due_date')
            if not due_date_str: continue
            try:
                due_date = datetime.strptime(due_date_str, DATE_FORMAT).date()
                if due_date < today: overdue_tasks.append(task)
                elif due_date == today: today_tasks.append(task)
            except ValueError: continue

        total_relevant = len(overdue_tasks) + len(today_tasks)
        if total_relevant == 0: return

        body_lines = []
        urgency = "normal"
        icon = "appointment-soon"
        if overdue_tasks:
            urgency = "critical"
            body_lines.append(f"🔴 {len(overdue_tasks)} Overdue:")
            for t in overdue_tasks[:3]: body_lines.append(f"- {t['title']}")
        if today_tasks:
            if overdue_tasks: body_lines.append("\n")
            body_lines.append(f"🟡 {len(today_tasks)} Due Today:")
            for t in today_tasks[:3]: body_lines.append(f"- {t['title']}")

        summary = f"Task Manager: {total_relevant} Items Attention"
        body = "\n".join(body_lines)
        subprocess.run([NOTIFY_CMD, '-u', urgency, '-a', 'Task Manager', '-i', icon, summary, body], check=False)

    def check_and_create_recurrence(self):
        today = datetime.now().date()
        newly_created_count = 0
        for task in list(self.tasks): 
            if task.get('completed', False) and task.get('repeat_interval') and not task.get('processed_for_recurrence'):
                last_due_date_str = task.get('due_date')
                interval_str = task['repeat_interval']
                if not last_due_date_str: continue
                next_due_date_str = calculate_next_due_date(last_due_date_str, interval_str)
                if next_due_date_str:
                    try:
                        next_due_date = datetime.strptime(next_due_date_str, DATE_FORMAT).date()
                    except ValueError: continue
                    if next_due_date >= today:
                        new_task = {
                            'id': self.next_id,
                            'title': task['title'],
                            'description': task.get('description', ''),
                            'priority': task.get('priority', 'M'),
                            'due_date': next_due_date_str,
                            'created_at': datetime.now().strftime(DATE_FORMAT),
                            'completed': False,
                            'repeat_interval': interval_str,
                        }
                        self.tasks.append(new_task)
                        self.next_id += 1
                        newly_created_count += 1
                        task['processed_for_recurrence'] = True
        if newly_created_count > 0:
            self.save_tasks()
            return f"[bold green]Created {newly_created_count} tasks.[/bold green]"
        else: return "[dim]No action.[/dim]"

    def _toggle_view(self):
        if self.view_mode == "auto": self.view_mode = "table"
        elif self.view_mode == "table": self.view_mode = "card"
        else: self.view_mode = "auto"

    def _print_banner(self):
        banner = r"""
    ____  ________  ___
   / __ \/_  __/  |/  /
  / /_/ / / / / /|_/ / 
 / _, _/ / / / /  / /  
/_/ |_| /_/ /_/  /_/   
"""
        self.console.print(Align.center(Text(banner, style="bold cyan")))
        self.console.print(Align.center(Text(f"{VERSION} | Linux - CLI", style="dim white")))

    def display_tasks(self, completed=False, tasks_list=None):
        if tasks_list is None: tasks_to_display = self.get_sorted_tasks(completed=completed)
        else: tasks_to_display = sorted(tasks_list, key=lambda t: t.get('id', 0))
        title = "Completed (Archive)" if completed else "Pending Tasks"
        if not tasks_to_display:
            self.console.print(Panel(f"[bold yellow]No {title.lower()} found.[/bold yellow]", title=title, border_style="yellow"))
            return
        width = self.console.width
        if self.view_mode == "auto": is_card_view = width < 90
        else: is_card_view = (self.view_mode == "card")

        self.console.print(f"\n[bold]{title} ({len(tasks_to_display)}) - {self.view_mode.title()}[/bold]")
        if is_card_view:
            self.console.print(Group(*[self._render_task_row(task, True) for task in tasks_to_display]))
        else:
            table = Table(title=title, show_header=True, header_style="bold magenta", padding=(0, 1))
            table.add_column("ID", style="dim", width=4)
            table.add_column("Task", style="bold magenta", min_width=20)
            table.add_column("Description", style="white", overflow="fold", max_width=50)
            table.add_column("Priority", style="dim", width=6)
            table.add_column("Due/Status", style="yellow", min_width=18)
            for task in tasks_to_display: table.add_row(*self._render_task_row(task, False))
            self.console.print(table)

    def show_filtered_tasks(self):
        keyword = self.console.input("[bold]Keyword:[/bold] ").strip().lower()
        if not keyword: return
        filtered = [t for t in self.get_sorted_tasks(False) if keyword in t['title'].lower() or keyword in t.get('description', '').lower()]
        self.console.clear()
        self.console.print(f"\n[yellow]Results for '{keyword}'[/yellow]")
        if filtered: self.display_tasks(tasks_list=filtered)
        else: self.console.print("[red]No matches.[/red]")
        self.console.input("[dim]Enter...[/dim]")

    def delete_task(self, task_id):
        idx = self.get_task_index_by_id(task_id)
        if idx != -1:
            title = self.tasks[idx]['title']
            del self.tasks[idx]
            self.save_tasks()
            return True, f"Deleted '{title}'."
        return False, "Not found."

    def generate_report(self):
        total = len(self.tasks)
        pending = len(self.get_sorted_tasks(False))
        self.console.clear()
        self.console.print(Panel(f"Total: {total}\nPending: {pending}", title="Report", border_style="green"))

    def _render_task_row(self, task, is_card=False):
        tid = str(task['id'])
        
        # Use 'or' to handle None values safely
        prio = task.get('priority') or 'M'
        t_text = task.get('title') or "Untitled"
        desc = task.get('description') or ""
        due = task.get('due_date') or 'N/A'
        
        title_style = "bold green" if task.get('completed') else TASK_TITLE_COLOR_MAP.get(prio, "white")
        title = Text(t_text, style=title_style)
        
        if is_card:
            border = "green" if task.get('completed') else PRIORITY_BORDER_COLOR_MAP.get(prio, "white")
            content = f"ID: {tid}\nTitle: {t_text}\nPrio: {prio}\nDue: {due}\n---\n{desc}"
            return Panel(content, title=f"Task {tid}", border_style=border)
        else:
            # All inputs are guaranteed to be strings
            return [Text(tid), title, Text(desc), Text(prio), Text(due)]

    def _add_task_internal(self, title, description, priority, due_date_str, repeat_interval=None):
        new_task = {
            'id': self.next_id,
            'title': title,
            'description': description,
            'priority': priority.upper(),
            'due_date': due_date_str,
            'created_at': datetime.now().strftime(DATE_FORMAT),
            'completed': False,
            'repeat_interval': repeat_interval,
        }
        self.tasks.append(new_task)
        self.next_id += 1
        self.save_tasks()

    def edit_task(self):
        """Interactive edit mode restored."""
        tid = self.console.input("\n[bold cyan]ID to Edit:[/bold cyan] ").strip()
        idx = self.get_task_index_by_id(tid)
        if idx == -1: return
        
        task = self.tasks[idx]
        self.console.print(f"[yellow]Editing '{task['title']}'[/yellow]")

        new_title = self.console.input(f"[bold]Title ({task['title']}):[/bold] ").strip()
        if new_title: task['title'] = new_title

        new_desc = self.console.input(f"[bold]Desc ({task['description']}):[/bold] ").strip()
        if new_desc: task['description'] = new_desc

        while True:
            new_prio = self.console.input(f"[bold]Priority ({task.get('priority', 'M')}):[/bold] ").upper().strip()
            if not new_prio: break
            if new_prio in ['H', 'M', 'L']:
                task['priority'] = new_prio
                break
        
        while True:
            cur_due = task.get('due_date', 'None')
            self.console.print(f"[bold]Due ({cur_due})[/bold]:")
            new_due = self.console.input("New Due (or 'none'): ").strip()
            if not new_due: break
            if new_due.lower() == 'none':
                task['due_date'] = None
                break
            try:
                datetime.strptime(new_due, DATE_FORMAT)
                task['due_date'] = new_due
                break
            except ValueError: self.console.print("[red]Invalid.[/red]")

        self.save_tasks()
        self.console.print("[green]Saved.[/green]")

    # --- RESTORED FEATURE: Info View ---
    def view_task_info(self):
        tid = self.console.input("\n[bold cyan]Task ID:[/bold cyan] ").strip()
        task = self.get_task_by_id(tid)
        if not task: return

        # Detailed Info Panel
        content = Text()
        content.append(f"ID: {task['id']}\n", style="bold")
        content.append(f"Status: {'Done' if task.get('completed') else 'Pending'}\n", style="green" if task.get('completed') else "yellow")
        content.append(f"Priority: {task.get('priority', 'M')}\n")
        content.append(f"Due: {task.get('due_date', 'None')}\n")
        content.append(f"Repeat: {task.get('repeat_interval', 'None')}\n")
        content.append("-" * 20 + "\n")
        content.append(f"Title: {task['title']}\n", style="bold white")
        content.append(f"Description:\n{task['description']}")

        self.console.print(Panel(content, title="Task Info", border_style="cyan"))
        self.console.input("[dim]Press Enter...[/dim]")

    def complete_task(self, task_id, complete=True):
        task = self.get_task_by_id(task_id)
        if task:
            task['completed'] = complete
            task['completed_at'] = datetime.now().strftime(DATE_FORMAT) if complete else None
            self.save_tasks()
            return True, "Done"
        return False, "Not found"

    def execute_cli_action(self, args):
        if args.add:
            self._add_task_internal(args.add, args.desc, args.priority, args.due, args.repeat)
        elif args.complete:
            success, msg = self.complete_task(args.complete, True)
            print(msg)
        elif args.uncomplete:
            success, msg = self.complete_task(args.uncomplete, False)
            print(msg)
        elif args.delete:
            success, msg = self.delete_task(args.delete)
            print(msg)
        elif args.notify_check:
            self.check_and_send_notifications()
        elif args.recurrence_check:
            print(self.check_and_create_recurrence())
        elif args.list:
            self.display_tasks()
        elif args.report:
            self.generate_report()

    def run(self):
        self.check_and_send_notifications()
        
        while True:
            self.console.clear()
            self._print_banner()
            self.display_tasks(False)
            
            msg = self.check_and_create_recurrence()
            
            self.console.print(Panel(
                Text.from_markup(f"Notifications: {'[green]On[/green]' if self.notify_available else '[red]Off[/red]'}\nAuto-Recurrence: {msg}"),
                title="System", border_style="yellow"
            ))
            
            self.console.print(Panel("[bold]A[/bold]:Add [bold]E[/bold]:Edit [bold]C[/bold]:Done [bold]D[/bold]:Del [bold]V[/bold]:Archive [bold]I[/bold]:Info [bold]F[/bold]:Filter [bold]R[/bold]:Report [bold]T[/bold]:Toggle [bold]Q[/bold]:Quit", title="Menu", border_style="magenta"))
            
            c = self.console.input("Action: ").upper().strip()
            if c == 'Q': break
            elif c == 'A': self.add_task()
            elif c == 'E': self.edit_task()
            elif c == 'C': 
                tid = self.console.input("ID: ")
                self.complete_task(tid, True)
            elif c == 'D': 
                tid = self.console.input("ID: ")
                self.delete_task(tid)
            # RESTORED ARCHIVE SUB-LOOP
            elif c == 'V': 
                while True:
                    self.console.clear()
                    self.display_tasks(True)
                    self.console.print(Panel("[bold]C[/bold]:Uncomplete [bold]D[/bold]:Delete [bold]R[/bold]:Return", title="Archive Menu", border_style="blue"))
                    ac = self.console.input("Archive Action: ").upper().strip()
                    if ac == 'C':
                        tid = self.console.input("ID to Restore: ")
                        self.complete_task(tid, False)
                    elif ac == 'D':
                        tid = self.console.input("ID to Delete: ")
                        self.delete_task(tid)
                    elif ac == 'R': break

            elif c == 'F': self.show_filtered_tasks()
            elif c == 'R': 
                self.generate_report()
                self.console.input("Enter...")
            elif c == 'N': self.check_and_send_notifications()
            elif c == 'T': self._toggle_view()
            # RESTORED INFO VIEW
            elif c == 'I': self.view_task_info()

if __name__ == "__main__":
    args = parse_args()
    mgr = TaskManager()

    if args.waybar:
        mgr.generate_waybar_json()
        sys.exit(0)

    is_action = any([args.add, args.complete, args.uncomplete, args.delete, args.report, args.list, args.notify_check, args.recurrence_check])
    
    try:
        if is_action and not args.tui:
            mgr.execute_cli_action(args)
        elif sys.stdin.isatty() or args.tui:
            mgr.run()
    except KeyboardInterrupt:
        pass
