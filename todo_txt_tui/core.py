import urwid
import re
import sys
import os
import subprocess
import platform
import json
import aiohttp
import threading
import asyncio
from datetime import date, datetime, timedelta
from dateutil.relativedelta import relativedelta


def debug(text):
    with open("debug.txt", "a") as debug_file:
        debug_file.write(f"{text}\n")


# Helper
def is_valid_date(string):
    try:
        datetime.strptime(string, '%Y-%m-%d')
        return True
    except ValueError:
        return False


__version__ = '0.1.8'
__package__ = 'todo-txt-tui'
__sync_refresh_rate__ = 2
__track_focused_task_interval__ = .1
__check_for_updates_interval__ = 1800  # 30 minutes in seconds
__current_search_query__ = ''
__focused_task_index__ = ''
__focused_task_text__ = ''


# Notify user if there's an update available
def check_for_updates(loop, keymap_instance):
    async def fetch():
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(f'https://pypi.org/pypi/{__package__}/json') as response:
                    if response.status != 200:
                        return  # Exit if the response status is not 200 OK
                    latest_version_info = await response.json()
                    latest_version = latest_version_info['info']['version']

            if __version__ != latest_version:
                def keypress(key):
                    if key == 'enter':
                        # subprocess.run(["pip3", "install", "--no-cache-dir", "--upgrade", __package__])

                        # Workaround (install twice) for pip using cache even if told not to
                        subprocess.run(["pip3", "cache", "purge"])
                        subprocess.run(["pip3", "uninstall", "-y", __package__])
                        subprocess.run(["pip3", "install", "--no-cache-dir", __package__])
                        subprocess.run(["pip3", "uninstall", "-y", __package__])
                        subprocess.run(["pip3", "install", "--no-cache-dir", __package__])

                        os.system('clear')
                        sys.exit(
                            f"\nUpdate completed.\nIf the update failed, update manually: pip3 install --upgrade {__package__}")
                    if key in ['esc']:
                        keymap_instance.main_frame.body = keymap_instance.tasklist_decorations

                text_widget = urwid.Text(
                    f"A new version ({latest_version}) is available. Press ENTER to install (ESC to dismiss).\n\nAlternatively, update manually: pip3 install --upgrade {__package__}\n\nChangelog: https://github.com/mdillondc/todo-txt-tui/commits/")
                bordered_layout = urwid.LineBox(text_widget, title="Update available")
                fill = urwid.Filler(bordered_layout, 'middle')
                overlay = urwid.Overlay(fill, keymap_instance.tasklist_decorations, 'center', 80, 'middle', 10)
                keymap_instance.main_frame.body = overlay
                keymap_instance.loop.unhandled_input = keypress
        except aiohttp.ClientConnectorError:
            # If DNS resolution fails or there's no internet connection, fail silently.
            pass
        except Exception as e:
            # If any exception, fail silently
            pass

    def thread_target():
        asyncio.new_event_loop().run_until_complete(fetch())

    # Start a new thread to perform the HTTP request
    threading.Thread(target=thread_target).start()

    # Reschedule the function to run again
    loop.set_alarm_in(__check_for_updates_interval__, check_for_updates, keymap_instance)


# Default theme
PALETTE = [
    ('bold', 'bold', ''),
    ('text', '', ''),  # Default to terminal
    ('priority_a', 'light red', ''),
    ('priority_b', 'brown', ''),
    ('priority_c', 'light green', ''),
    ('priority_d', 'light blue', ''),
    ('priority_e', 'dark magenta', ''),
    ('context', 'light magenta', ''),
    ('project', 'yellow', ''),
    ('is_complete', 'dark gray', ''),
    ('is_danger', 'light red', ''),
    ('is_success', 'light green', ''),
    ('is_link', 'light blue', ''),
    ('heading_overdue', 'light red,italics,bold', ''),
    ('heading_today', 'light green,italics,bold', ''),
    ('heading_future', 'default,italics,bold', ''),
]

# Check if user has defined a custom color palette
os_name = platform.system()

if os_name == 'Linux':
    palette_path = os.path.expanduser("~/.config/todo-txt-tui/palette.conf")
    settings_path = os.path.expanduser("~/.config/todo-txt-tui/settings.conf")
elif os_name == 'Darwin':  # macOS
    palette_path = os.path.expanduser("~/Library/Application Support/todo-txt-tui/palette.conf")
    settings_path = os.path.expanduser("~/Library/Application Support/todo-txt-tui/settings.conf")
else:
    palette_path = None  # For unsupported OS
    settings_path = None

if os.path.exists(palette_path):
    try:
        with open(palette_path, 'r') as f:
            custom_palette = json.load(f)
            if custom_palette:  # Making sure the file is not empty
                PALETTE = custom_palette
    except Exception as e:
        # If error, the default PALETTE will be used
        print(f"An error occurred while reading {palette_path}. Falling back to default palette: {e}")

COLORS = {
    '(A)': 'priority_a',
    '(B)': 'priority_b',
    '(C)': 'priority_c',
    '(D)': 'priority_d',
    '(E)': 'priority_e',
    '(F)': 'priority_f',
    'due:': 'is_complete',
    'rec:': 'is_complete',
    '@': 'context',
    '+': 'project',
    'http': 'is_link',
    'is_danger': 'is_danger',
    'is_success': 'is_success',
    'is_complete': 'is_complete',
}

# Default settings
# ~/.config/todo-txt-tui/settings.conf
SETTINGS = [
    ('enableCompletionAndCreationDates', 'true'),
    ('hideCompletionAndCreationDates', 'true'),
    ('placeCursorBeforeMetadataWhenEditingTasks', 'false')
]

if os.path.exists(settings_path):
    try:
        with open(settings_path, 'r') as f:
            custom_settings = json.load(f)
            if custom_settings:  # Making sure the file is not empty
                SETTINGS = custom_settings
    except Exception as e:
        # If error, the default PALETTE will be used
        print(f"An error occurred while reading {settings_path}. Falling back to default settings: {e}")


# Usage: `if setting_enabled('enableCompletionAndCreationDates'):`
def setting_enabled(setting):
    global SETTINGS
    return any(item for item in SETTINGS if item[0] == setting and item[1].lower() == 'true')


# Constants for regular expressions
STRIP_X_FROM_TASK = r'^x\s'
PRIORITY_REGEX = r'\(([A-Z])\)'
DUE_DATE_REGEX = r'due:(\d{4}-\d{2}-\d{2})'
RECURRENCE_REGEX = r'rec:([+]?[0-9]+[dwmy])'
URLS_REGEX = r'(https?://[^\s\)]+|file://[^\s\)]+)'


class CustomCheckBox(urwid.CheckBox):
    """
    CustomCheckBox is a subclass of urwid.CheckBox that includes an additional attribute
    to store the original text of the task. This is useful for keeping track of any
    modifications made to the task text for display purposes, while still retaining
    the original text for operations like edit, complete, delete, etc.
    """

    def __init__(self, label, state=False, original_text=''):
        """
        Initialize a new CustomCheckBox instance.

        Parameters:
        - label (str): The text to display on the checkbox. This could be a modified
                       or simplified version of the original task text.
        - state (bool): The initial state of the checkbox. True for checked, False for unchecked.
        - original_text (str): The original text of the task. This is used to retain
                                the full details of the task that might not be displayed.

        """
        # Initialize the parent urwid.CheckBox class
        super().__init__(label, state=state)

        # Store the original task text
        self.original_text = original_text

    def keypress(self, size, key):
        if key in ('enter', ' '):  # Don't allow space and enter to toggle checkboxes
            return key
        return super().keypress(size, key)  # For other keys, call the superclass method


class Tasks:
    """
    Task manipulation
    Add, edit, delete, etc
    """

    def __init__(self, txt_file):
        self.txt_file = txt_file

    # Reads task lines from the file and returns them as a list
    def read(self):
        with open(self.txt_file, 'r') as f:
            return [line.strip() for line in f.readlines()]

    # Sorts a list of tasks based on due date, priority, and text
    @staticmethod
    def sort(tasks):
        def parse(task_text):
            priority_match = re.search(PRIORITY_REGEX, task_text)
            due_date_match = re.search(DUE_DATE_REGEX, task_text)
            completed = task_text.startswith('x ')
            recurrence_match = re.search(RECURRENCE_REGEX, task_text)

            if completed:
                task_text = task_text[2:]

            return {
                'text': task_text,
                'priority': priority_match.group(1) if priority_match else None,
                'due_date': due_date_match.group(1) if due_date_match else None,
                'completed': completed,
                'recurrence': recurrence_match.group(1) if recurrence_match else None,
            }

        def get_sort_key(task):
            # Convert due_date to a date object for proper sorting, default to a date far in the future if None
            due_date_key = datetime.strptime(task['due_date'], '%Y-%m-%d').date() if task['due_date'] else datetime(
                9999, 12, 31).date()

            sort_text = ''
            words = task['text'].split()

            for index, word in enumerate(words):
                if index == 0 and word == 'x':
                    continue
                elif is_valid_date(word.strip()):
                    continue
                else:
                    sort_text += word + ' '

            # Remove trailing whitespace and convert to lowercase for case-insensitive sorting
            sort_text = sort_text.strip().lower()

            return (due_date_key, sort_text)

        # Parse each task line into a dictionary of its components
        parsed_tasks = [parse(task) for task in tasks]

        # Sort tasks by due date, then by text
        parsed_tasks.sort(key=get_sort_key)

        return parsed_tasks

    # Do not allow adding duplicate tasks
    def task_already_exists(self, task_text):
        existing_tasks = self.read()
        return task_text in existing_tasks

    # Adds a new task to the task file
    def add(self, keymap_instance, new_task):
        # Normalize the new task to remove extra spaces
        normalized_task = self.normalize_task(new_task)

        # Convert NLP dates to actual dates
        normalized_task = self.convert_nlp_to_dates(normalized_task)

        # Check if the file is empty
        file_is_empty = False
        try:
            file_is_empty = os.path.getsize(self.txt_file) == 0
        except FileNotFoundError:
            file_is_empty = True  # File doesn't exist, so consider it as empty

        # Append the new task to the file
        if not self.task_already_exists(normalized_task):
            with open(self.txt_file, 'a') as f:
                if not file_is_empty:
                    f.write('\n')
                f.write(normalized_task)

        keymap_instance.refresh_displayed_tasks()
        keymap_instance.focus_on_specific_task(normalized_task.strip())

    # Edits an existing task in the task file
    def edit(self, old_task, new_task):
        # Normalize both the old and new tasks
        normalized_old_task = self.normalize_task(old_task)
        normalized_new_task = self.normalize_task(new_task)

        # Convert NLP dates to actual dates
        normalized_new_task = self.convert_nlp_to_dates(normalized_new_task)

        # Read all tasks from the file
        with open(self.txt_file, 'r') as f:
            tasks = f.readlines()

        # Find the task to be edited and replace it with the new task
        for i, task in enumerate(tasks):
            if self.normalize_task(task.strip()) == normalized_old_task:
                tasks[i] = normalized_new_task + '\n'
                break

        # Write the updated tasks back to the file
        with open(self.txt_file, 'w') as f:
            f.writelines(tasks)

    def delete(self, task_text):
        # Normalize the task text for consistency
        normalized_task = self.normalize_task(task_text)

        # Read all tasks from the file
        with open(self.txt_file, 'r') as f:
            tasks = f.readlines()

        # Filter out the task to be deleted
        tasks = [task for task in tasks if self.normalize_task(task.strip()) != normalized_task]

        # Write the remaining tasks back to the file
        with open(self.txt_file, 'w') as f:
            f.writelines(tasks)

    # Postpone task to tomorrow
    def postpone_to_tomorrow(self, task_text):
        # Search for the due date in task_text
        due_date_match = re.search(DUE_DATE_REGEX, task_text)
        if not due_date_match:
            return  # Return if no due date is found

        # Convert the found due date to a datetime object
        due_date_str = due_date_match.group(1)
        due_date_dt = datetime.strptime(due_date_str, '%Y-%m-%d')

        # Get today's date
        today_dt = datetime.today().date()

        # Compare today's date with due date and decide on the new due date
        if due_date_dt.date() >= today_dt:
            new_due_date_dt = due_date_dt + timedelta(days=1)
        else:
            new_due_date_dt = datetime.combine(today_dt, datetime.min.time()) + timedelta(days=1)

        # Replace the original due date with the new one
        new_due_date_str = datetime.strftime(new_due_date_dt, '%Y-%m-%d')
        updated_task = re.sub(DUE_DATE_REGEX, f'due:{new_due_date_str}', task_text)

        # Read all tasks from the file
        with open(self.txt_file, 'r') as f:
            tasks = f.readlines()

        # Find the task to be edited and replace it with the new task
        for i, task in enumerate(tasks):
            if task.strip() == task_text:
                tasks[i] = updated_task + '\n'
                break

        # Write the updated tasks back to the file
        with open(self.txt_file, 'w') as f:
            f.writelines(tasks)

        return updated_task

    # Toggle the completion status of a task (and add a new task if rec rule is present)
    def complete(self, task_text):
        # Read the current tasks from the file
        tasks = self.read()

        # Lists to store the modified tasks and recurring tasks
        modified_tasks = []
        recurring_tasks = []

        # Flag to check if a task has been toggled (completed/uncompleted)
        task_toggled = False

        # Current date of completion (today's date)
        completion_date = datetime.now().date()

        for i, task in enumerate(tasks):
            # Remove leading and trailing whitespaces
            text = task.strip()

            # Check if the task is already complete
            is_complete = text.startswith('x ')

            # Check if the modified task text matches the provided task_text
            if text == task_text and not task_toggled:
                # Set the flag to True
                task_toggled = True

                # Toggle the task's completed state
                if is_complete:
                    modified_task = text[2:]  # Slice off "x " to make the task incomplete

                    if setting_enabled('enableCompletionAndCreationDates'):
                        if len(modified_task) >= 14 and is_valid_date(
                                modified_task[4:14]):  # Task has creation date and priority
                            # Remove completion date since the task is no longer marked complete
                            modified_task = modified_task[:4] + modified_task[15:]

                        elif len(modified_task) >= 10 and is_valid_date(
                                modified_task[0:10]):  # Task has creation date but no priority
                            # Remove the completion date from the task
                            modified_task = modified_task[10:]

                else:
                    has_priority = bool(re.match(r'^\([A-Z]\)', text[0:3]))
                    priority = text[0:3]

                    if setting_enabled('enableCompletionAndCreationDates'):
                        if has_priority:
                            modified_task = 'x ' + priority + ' ' + datetime.now().strftime('%Y-%m-%d') + re.sub(
                                r'^\([A-Z]\)', '', text)
                        else:
                            modified_task = 'x ' + datetime.now().strftime('%Y-%m-%d') + ' ' + text
                    else:
                        modified_task = 'x ' + text

                # Remove any extra white spaces
                modified_tasks.append(re.sub(r'\s+', ' ', modified_task).strip())

                # Handle recurring tasks
                if "rec:" in text and not is_complete:
                    # Extract recurrence value
                    recurrence_value = re.search(RECURRENCE_REGEX, text).group(1)

                    # Check if the recurrence is strict (starts with '+')
                    is_strict = recurrence_value.startswith('+')

                    # Extract old due date if present
                    due_date_match = re.search(DUE_DATE_REGEX, text)
                    old_due_date = datetime.strptime(due_date_match.group(1),
                                                     '%Y-%m-%d').date() if due_date_match else None

                    # Calculate new due date based on recurrence
                    base_date = old_due_date if is_strict and old_due_date else completion_date

                    amount = int(re.match(r"\+?(\d+)", recurrence_value).group(1))
                    unit = recurrence_value[-1]
                    unit_mapping = {'d': 'days', 'w': 'weeks', 'm': 'months', 'y': 'years'}
                    unit_full = unit_mapping.get(unit, unit)
                    delta = relativedelta(**{unit_full: amount})
                    new_due_date = base_date + delta
                    new_due_date_str = new_due_date.strftime('%Y-%m-%d')

                    # Create new task with updated due date
                    new_task = re.sub(DUE_DATE_REGEX, f'due:{new_due_date_str}',
                                      text) if old_due_date else text + f' due:{new_due_date_str}'

                    has_priority = False

                    # Remove old creation date if present (for tasks without priority)
                    if len(modified_task) >= 10 and is_valid_date(new_task[0:10]):
                        new_task = new_task[11:]  # strip creation date from new task text

                    # Remove old creation date if present (for tasks with priority)
                    if len(modified_task) >= 14 and is_valid_date(new_task[4:14]):
                        new_task = new_task[:3] + new_task[14:]  # strip creation date from new task text
                        has_priority = True

                    # Add new creation date if setting is enabled
                    if setting_enabled('enableCompletionAndCreationDates'):
                        if not has_priority:
                            new_task = datetime.now().strftime('%Y-%m-%d') + ' ' + new_task
                        else:
                            priority = new_task[:4]
                            text = new_task[3:]
                            new_task = priority + datetime.now().strftime('%Y-%m-%d') + text

                    # Add the new task to recurring_tasks if it doesn't already exist
                    if not self.task_already_exists(new_task):
                        recurring_tasks.append(new_task)
            else:
                modified_tasks.append(text)

        # Write the updated tasks back to the file
        with open(self.txt_file, 'w') as f:
            f.write('\n'.join(modified_tasks + recurring_tasks))

    # Archives completed tasks to a 'done.txt' file and removes them from the original file
    def archive(self):
        completed_tasks = []
        incomplete_tasks = []

        # Read all tasks from the file
        with open(self.txt_file, 'r') as f:
            tasks = f.readlines()

        # Separate tasks into completed and incomplete lists
        for task in tasks:
            if task.startswith('x '):
                completed_tasks.append(task.strip())
            else:
                incomplete_tasks.append(task.strip())

        # Append completed tasks to 'done.txt'
        done_txt_file = os.path.join(os.path.dirname(self.txt_file), 'done.txt')
        with open(done_txt_file, 'a') as f:
            f.write('\n'.join(completed_tasks) + '\n')

        # Write only incomplete tasks back to the original task file
        with open(self.txt_file, 'w') as f:
            f.write('\n'.join(incomplete_tasks))

    # Format a single task line by splitting the task into its components
    def restructure_task_components(self, task):
        """
        Before: Go +zzzProject to @aContext [YouTube](https://youtube.com) and watch rec:+1d a video. +anotherProject due:2023-01-01 @work
        After: Go to [YouTube](https://youtube.com) and watch a video. +anotherProject +zzzProject @aContext @work due:2023-01-01 rec:+1d
        """

        # Store task components
        task_text_dates = []  # completion/creation date
        task_text = []
        projects = []
        contexts = []
        priority = ""
        due_date = ""
        rec_rule = ""
        complete = False

        words = task.split()

        for index, word in enumerate(words):
            if index == 0 and word == 'x':
                complete = True
                continue
            elif word.startswith('+'):
                projects.append(word)
            elif word.startswith('@'):
                contexts.append(word)
            elif word.startswith('due:'):
                due_date = word
            elif word.startswith('rec:'):
                rec_rule = word
            elif is_valid_date(word.strip()):
                task_text_dates.append(word)
            elif re.match(r'^\([A-Z]\)', word):
                priority = word
            else:
                task_text.append(word)

        # Sort projects and contexts
        projects.sort(key=str.casefold)
        contexts.sort(key=str.casefold)

        # Construct the task in the correct order
        restructured_task_parts = []

        # Add priority if it exists
        if priority:
            restructured_task_parts.append(priority)

        # Add dates if they exist
        if task_text_dates:
            restructured_task_parts.append(' '.join(task_text_dates))

        # Add the main task text
        restructured_task_parts.extend(task_text)

        # Add the projects, contexts, due date, and rec_rule if they exist
        restructured_task_parts.extend(projects)
        restructured_task_parts.extend(contexts)
        if due_date:
            restructured_task_parts.append(due_date)
        if rec_rule:
            restructured_task_parts.append(rec_rule)

        # Join all parts with a single space
        restructured_task = ' '.join(restructured_task_parts)

        # If the task is complete, prepend 'x' to the task
        if complete:
            restructured_task = 'x ' + restructured_task

        return restructured_task.strip()

    # Normalizes a single task by removing extra spaces and restructuring it
    def normalize_task(self, task_text):
        # Remove extra spaces
        task_text = ' '.join(task_text.split())
        # Restructure the task
        return self.restructure_task_components(task_text)

    # Normalizes the entire task file
    def normalize_file(self, body=None):
        # Read all tasks from the file
        with open(self.txt_file, 'r') as f:
            tasks = f.readlines()

        # Remove extra spaces, filter out empty lines, and restructure tasks
        normalized_tasks = [self.restructure_task_components(task.strip()) for task in tasks if task.strip()]

        # Write the normalized tasks back to the file
        with open(self.txt_file, 'w') as f:
            f.write('\n'.join(normalized_tasks))

        # Refresh the task list display if a Body instance is provided
        if body is not None:
            body.refresh_displayed_tasks()

    # Performs a fuzzy search for tasks and updates the UI to display only matching tasks
    @staticmethod
    def search(edit_widget, search_query, txt_file, tasklist_instance):
        global __current_search_query__  # Use the global variable
        __current_search_query__ = search_query  # Update the current search query

        # Create a Tasks instance for the given file path
        tasks = Tasks(txt_file)

        # Read all tasks and filter those that match the search query
        filtered_tasks = [task for task in tasks.read() if search_query.lower() in task.lower()]

        # Update the UI to display only the filtered tasks
        tasklist_instance.body = urwid.SimpleFocusListWalker(
            TaskUI.render_and_display_tasks(tasks.sort(filtered_tasks), PALETTE).widget_list)

        # If 'Enter' was the last key pressed, refocus on the task list in the UI
        if hasattr(tasklist_instance, 'last_key') and tasklist_instance.last_key == 'enter':
            tasklist_instance.main_frame.set_focus('body')
            delattr(tasklist_instance, 'last_key')  # Remove the attribute once it's been used
            tasklist_instance.set_focus(0)  # Focus on the first task in the list

    # Convert natural language like due:tomorrow to actual dates
    def convert_nlp_to_dates(self, task):
        # Regular expression to find "due:" keyword and its value
        due_date_match = re.search(r'due:([a-zA-Z0-9]+)', task)

        if due_date_match:
            nlp_date = due_date_match.group(1).lower()
            today = datetime.now().date()
            weekday_to_number = {
                'mon': 0,
                'tue': 1,
                'wed': 2,
                'thu': 3,
                'fri': 4,
                'sat': 5,
                'sun': 6
            }

            # Convert natural language to standard date
            if nlp_date in ['tod', 'today']:
                new_date = today
            elif nlp_date in ['tom', 'tomorrow']:
                new_date = today + timedelta(days=1)
            elif nlp_date in weekday_to_number.keys():
                target_weekday = weekday_to_number[nlp_date]
                days_until_target = (target_weekday - today.weekday() + 7) % 7
                new_date = today + timedelta(days=days_until_target)
                if days_until_target == 0:
                    new_date += timedelta(days=7)
            elif nlp_date in ['nw', 'nextweek']:
                new_date = today + timedelta((0 - today.weekday() + 7))
            elif nlp_date in ['nm', 'nextmonth']:
                if today.month == 12:
                    new_date = today.replace(year=today.year + 1, month=1, day=1)
                else:
                    new_date = today.replace(month=today.month + 1, day=1)
            elif re.match(r'\d{1,2}[a-zA-Z]{3}(\d{4})?$', nlp_date):
                # For patterns like 11dec, 1dec, or 11dec2027, 1dec2027
                day_match = re.search(r'\d{1,2}', nlp_date)
                month_match = re.search(r'[a-zA-Z]{3}', nlp_date)
                year_match = re.search(r'\d{4}$', nlp_date)

                if day_match and month_match:
                    day = int(day_match.group(0))
                    month_str = month_match.group(0)

                    month_to_number = {
                        'jan': 1, 'feb': 2, 'mar': 3, 'apr': 4, 'may': 5, 'jun': 6,
                        'jul': 7, 'aug': 8, 'sep': 9, 'oct': 10, 'nov': 11, 'dec': 12
                    }
                    month = month_to_number.get(month_str.lower())
                    if month is None:
                        return task  # Return original if month is invalid

                    year = int(year_match.group(0)) if year_match else today.year
                    if month < today.month or (month == today.month and day < today.day):
                        year += 1  # Increment year if date has already passed
                    new_date = datetime(year, month, day).date()
            else:
                return task  # If it doesn't match any of these, return the original task

            # Replace in task
            actual_due_date = f"due:{new_date.strftime('%Y-%m-%d')}"
            task_text_with_actual_date = re.sub(r'due:[a-zA-Z0-9]+', actual_due_date, task)

            return task_text_with_actual_date
        else:
            return task  # Return the original task if "due:" keyword is not found

    # Checks for updates in the task file and refreshes the UI if needed
    def sync(self, loop, user_data):
        global __focused_task_index__
        # Unpack user data to get file path, UI instance, and last modification time
        txt_file, tasklist_instance, last_mod_time = user_data

        # Check if a dialog is currently open in the UI; if so, skip the update
        if isinstance(tasklist_instance.main_frame.body, urwid.Overlay):
            # Reschedule to run this method after 5 seconds
            loop.set_alarm_in(__sync_refresh_rate__, self.sync, user_data)
            return

        # Get the current modification time of the task file
        current_mod_time = os.path.getmtime(txt_file)

        # Check if the task file has been modified since the last check
        if current_mod_time != last_mod_time[0]:
            # Save the currently focused task in the UI
            focused_widget, _ = tasklist_instance.get_focus()
            focused_task_text = None

            # Use the original task text if available
            if hasattr(focused_widget, 'original_widget') and isinstance(focused_widget.original_widget,
                                                                         CustomCheckBox):
                focused_task_text = focused_widget.original_widget.original_text

            # Refresh the task list UI
            tasklist_instance.refresh_displayed_tasks()

            # Refocus on the previously focused task in the UI based on its original text
            if focused_task_text:
                tasklist_instance.focus_on_specific_task(__focused_task_index__)

            # Update the last known modification time
            last_mod_time[0] = current_mod_time

        # Reschedule this method to run again after 5 seconds
        loop.set_alarm_in(__sync_refresh_rate__, self.sync, (txt_file, tasklist_instance, last_mod_time))


class TaskUI:
    """
    Handle UI components like displaying the actual task list and the add/edit dialog and so on
    """

    # Display the list of tasks inside the "Tasks" area
    @staticmethod
    def render_and_display_tasks(tasks, palette):
        """
        Renders and displays tasks in the terminal UI.

        Parameters:
        tasks (list)
        palette (dict): A dictionary that maps color names to terminal colors.

        Returns:
        urwid.Pile: A urwid Pile widget containing the rendered tasks.
        """

        # Initialize the list to hold UI widgets for each task
        widgets = []

        # Initialize variables to keep track of the current due date section and whether it's the first heading
        current_due_date = ''
        first_heading = True

        # Get today's date for comparison with task due dates
        today = datetime.today().date()

        # Loop through each task
        for task in tasks:

            # Skip tasks that don't match the current search query
            if __current_search_query__ and __current_search_query__.lower() not in task['text'].lower():
                continue

            # Extract the due date from the current task
            due_date = task['due_date']

            # Check if we're entering a new due date section
            if due_date != current_due_date:
                current_due_date = due_date
                due_date_obj = datetime.strptime(due_date, '%Y-%m-%d') if due_date else None

                # Create section heading based on due date
                if due_date_obj:
                    day_name = due_date_obj.strftime("%A")
                    heading_str = f"{due_date}: {day_name}"
                else:
                    heading_str = 'No due date'

                # Color the heading based on its relation to today's date
                if due_date_obj and due_date_obj.date() < today:
                    heading_text = urwid.Text(('heading_overdue', heading_str + ' (Overdue)'))
                elif due_date_obj and due_date_obj.date() == today:
                    heading_text = urwid.Text(('heading_today', heading_str + ' (Today)'))
                else:
                    heading_text = urwid.Text(('heading_future', heading_str))

                # Add a divider between sections (skipped for the first heading)
                if not first_heading:
                    widgets.append(urwid.Divider(' '))

                # Add the heading to the list of widgets
                widgets.append(heading_text)
                first_heading = False

            # Prepare the task line for display
            task_line = task['text'].strip()
            is_task_complete = task['completed']  # Determine if the task is complete
            display_text = []

            # Handle Markdown links and replace them with placeholders
            md_links = re.findall(r'\[(.*?)\]\((https?://\S+|file://\S+)\)', task_line)
            total_md_links = len(md_links)
            for i, (text, url) in enumerate(md_links):
                placeholder = f"MDLINK{i}"
                task_line = task_line.replace(f"[{text}]({url})", placeholder)

            # Count the number of plain text links
            total_plain_links = len(re.findall(r'(https?://\S+|file://\S+)', task_line))

            # Decide if we should count links based on the total number of Markdown and plain text links
            should_count_links = (total_md_links + total_plain_links) > 1

            # Split the task text into words
            task_words = task_line.split()
            link_counter = 0  # Initialize the link counter for each task

            # Loop through each word to apply color-coding logic
            for index, word in enumerate(task_words):
                color = 'is_complete' if is_task_complete else 'text'

                if setting_enabled('hideCompletionAndCreationDates'):
                    if index == 0 and is_valid_date(word):
                        continue

                    if index == 1 and is_valid_date(word):
                        continue

                    if index == 2 and is_valid_date(word):
                        continue

                # Apply color-coding based on the word's prefix or content
                if not is_task_complete:
                    if word.startswith('@'):
                        color = 'context'
                    elif word.startswith('+'):
                        color = 'project'
                    elif word in COLORS:
                        color = COLORS[word]
                    elif re.match(r'(https?://\S+|file://\S+)', word):
                        color = 'is_link'
                        if should_count_links:
                            link_counter += 1
                            word = f"{word}({link_counter})"
                    elif any(word.startswith(keyword) for keyword in COLORS):
                        color = COLORS.get(word[:4], 'text')
                    elif is_valid_date(word):
                        color = 'is_complete'

                # Restore Markdown links and count if necessary
                if word.startswith("MDLINK"):
                    i = int(word.replace("MDLINK", ""))
                    text, url = md_links[i]
                    if not is_task_complete:
                        color = 'is_link'
                    if should_count_links:
                        link_counter += 1
                        word = f"{text}({link_counter})"
                    else:
                        word = text  # If only one link, no need for a counter

                display_text.append((color, word))
                display_text.append(('text', ' '))

            # Remove the trailing space from the colored text
            display_text = display_text[:-1]

            # Create a custom checkbox for the task and apply the color scheme
            original_text = 'x ' + task['text'].strip() if task['completed'] else task['text'].strip()
            checkbox = CustomCheckBox(display_text, state=task['completed'], original_text=original_text)

            wrapped_checkbox = urwid.AttrMap(checkbox, None, focus_map='bold')

            # Add the checkbox to the list of widgets
            widgets.append(wrapped_checkbox)

        # Return a Pile widget containing all the task widgets
        return urwid.Pile(widgets)

    def open_task_add_edit_dialog(keymap_instance, size, default_text=None):
        """
        Opens a dialog for adding or editing a task.

        Parameters:
        keymap_instance: Instance of the Keymap class, which handles key mapping and UI updates.
        size: Size of the dialog (not used in this function but kept for consistency).
        default_text: Default text to populate the edit field with, used for editing existing tasks.

        Returns:
        None: This function manipulates the UI but does not return a value.
        """

        # Initialize Tasks instance
        tasks = Tasks(keymap_instance.txt_file)

        # Function to handle the entered text
        def on_ask(text):
            if not text.strip():  # Exit if text is empty
                return

            if default_text:  # Edit existing task
                tasks.edit(default_text, text)
                keymap_instance.refresh_displayed_tasks()
                keymap_instance.focus_on_specific_task(__focused_task_index__)
            else:  # Add a new task
                if setting_enabled('enableCompletionAndCreationDates'):
                    text = datetime.now().strftime('%Y-%m-%d') + ' ' + text

                tasks.add(keymap_instance, text)

        # Initialize urwid Edit widget
        ask = urwid.Edit()

        def find_task_text_end(task_text):
            # Identifiers for project, context, due date, and recurrence
            identifiers = [' +', ' @', ' due:', ' rec:']
            # Find the first occurrence of any identifier
            first_identifier_pos = min([task_text.find(idf) for idf in identifiers if task_text.find(idf) != -1],
                                       default=len(task_text))
            return first_identifier_pos

        # If default_text is provided, pre-fill the Edit widget
        if default_text:
            if setting_enabled('placeCursorBeforeMetadataWhenEditingTasks'):
                cursor_pos = find_task_text_end(default_text)
                # Insert a space before the cursor position
                default_text_with_space = default_text[:cursor_pos] + ' ' + default_text[cursor_pos:]
                ask.set_edit_text(default_text_with_space)
                # Set the cursor position to one after the inserted space
                ask.set_edit_pos(cursor_pos + 1)
            else:
                ask.set_edit_text(default_text)
                # Place the cursor at the end of the text
                ask.set_edit_pos(len(default_text))

        # Create BoxAdapter to hold suggestions with a height of 1
        suggestions_box_adapter = urwid.BoxAdapter(keymap_instance.auto_suggestions.dialog, height=1)

        # Apply text color to suggestions_box_adapter
        colored_suggestions_box = urwid.AttrMap(suggestions_box_adapter, 'context')

        # Create Pile widget to hold the Edit and Suggestions widgets
        layout = urwid.Pile([('pack', ask), ('pack', colored_suggestions_box)])

        # Add a border and title around the layout
        bordered_layout = urwid.LineBox(layout, title="Edit Task" if default_text else "Add Task")

        # Center the bordered layout
        fill = urwid.Filler(bordered_layout, 'middle')
        overlay = urwid.Overlay(fill, keymap_instance.tasklist_decorations, 'center', 80, 'middle', 5)

        # Function to handle key presses in the dialog
        def keypress(key):
            if key == 'enter':
                on_ask(ask.get_edit_text())
                urwid.ExitMainLoop()
                tasks.normalize_file()
            elif key == 'esc':
                keymap_instance.main_frame.body = keymap_instance.tasklist_decorations
            elif key == 'tab':  # Autocomplete logic for projects/contexts
                first_suggestion = None
                if keymap_instance.auto_suggestions.dialog.body:
                    first_suggestion_widget, _ = keymap_instance.auto_suggestions.dialog.body.get_focus()
                    if first_suggestion_widget:
                        all_suggestions = first_suggestion_widget.get_text()[0]
                        first_suggestion = all_suggestions.split(", ")[0] if all_suggestions else None
                if first_suggestion:
                    cursor_position = ask.edit_pos
                    existing_text = ask.get_edit_text()
                    start_of_word = existing_text.rfind(' ', 0, cursor_position) + 1
                    end_of_word = existing_text.find(' ', cursor_position)
                    if end_of_word == -1:
                        end_of_word = len(existing_text)
                    new_text = existing_text[:start_of_word] + first_suggestion + ' ' + existing_text[end_of_word:]
                    ask.set_edit_text(new_text)
                    ask.set_edit_pos(start_of_word + len(first_suggestion) + 1)

        # Function to update suggestions as text changes
        def on_text_change(edit, new_edit_text):
            cursor_position = edit.edit_pos
            text = new_edit_text
            start_of_word = text.rfind(' ', 0, cursor_position) + 1
            end_of_word = text.find(' ', cursor_position)
            if end_of_word == -1:
                current_word = text[start_of_word:]
            else:
                current_word = text[start_of_word:end_of_word]
            keymap_instance.auto_suggestions.update_suggestions(current_word)

        # Connect the on_text_change function to the Edit widget
        urwid.connect_signal(ask, 'change', on_text_change)

        # Update the UI to show the dialog
        keymap_instance.main_frame.body = overlay
        keymap_instance.loop.unhandled_input = keypress


class AutoSuggestions:
    """
    Handle auto suggesting projects and contexts.
    """

    def __init__(self, txt_file):
        """
        Initializes the AutoSuggestions instance.

        :param txt_file: Path to the todo.txt file.
        """
        self.txt_file = txt_file  # Set the file path
        self.contexts = self.fetch_contexts()  # Fetch and set the contexts
        self.projects = self.fetch_projects()  # Fetch and set the projects
        self.dialog = urwid.ListBox(urwid.SimpleFocusListWalker([]))  # Create an empty ListBox for suggestions

    def fetch_contexts(self):
        """
        Fetches unique context tags from the todo.txt file.

        :returns: A list of unique context tags.
        """
        contexts = set()  # Create an empty set to store unique context tags
        tasks = Tasks(self.txt_file)  # Initialize Tasks
        for task in tasks.read():  # Loop through all tasks
            # Regex to find context tags, making sure they are properly bounded
            for match in re.finditer(r'(^| )@(\w+)( |$)', task):
                contexts.add(match.group(2))  # Add the context to the set
        return list(contexts)  # Convert set to list and return

    def fetch_projects(self):
        """
        Fetches unique project tags from the todo.txt file.

        :returns: A list of unique project tags.
        """
        projects = set()  # Create an empty set to store unique project tags
        tasks = Tasks(self.txt_file)  # Initialize Tasks
        for task in tasks.read():  # Loop through all tasks
            # Regex to find project tags, making sure they are properly bounded
            for match in re.finditer(r'(^| )\+(\w+)( |$)', task):
                projects.add(match.group(2))  # Add the project to the set
        return list(projects)  # Convert set to list and return

    def update_suggestions(self, current_word):
        """
        Updates the suggestion dialog based on the current word being typed.

        :param current_word: The current word being typed by the user.
        """
        # Refresh the contexts and projects each time this method is called
        self.contexts = self.fetch_contexts()
        self.projects = self.fetch_projects()

        filtered = []  # Initialize empty list to store filtered suggestions
        color = ''  # Initialize color to empty string

        # If the current word starts with '@', suggest contexts
        if current_word.startswith("@"):
            filtered = [item for item in self.contexts if item.lower().startswith(current_word[1:].lower())]
            symbol = "@"  # Symbol to prepend to each suggestion
            color = 'context'  # Color for context suggestions

        # If the current word starts with '+', suggest projects
        elif current_word.startswith("+"):
            filtered = [item for item in self.projects if item.lower().startswith(current_word[1:].lower())]
            symbol = "+"  # Symbol to prepend to each suggestion
            color = 'project'  # Color for project suggestions

        # Sort the filtered list alphabetically (case-insensitive)
        filtered.sort(key=str.lower)

        # Create a comma-separated string of suggestions with the appropriate symbol prepended
        suggestions_str = ', '.join([symbol + item for item in filtered])

        # Create a Text widget for the suggestions and set its color
        suggestions_widget = urwid.Text((color, suggestions_str))

        # Update the dialog body with the new suggestions
        self.dialog.body = urwid.SimpleFocusListWalker([suggestions_widget])

        # Invalidate the layout so that it gets redrawn
        self.dialog._invalidate()


class Body(urwid.ListBox):
    """
    The primary frame of the application
    Also responsible for most keybindings
    """

    def __init__(self, txt_file):
        # File path for the task file
        self.txt_file = txt_file
        # Initialize AutoSuggestions object
        self.auto_suggestions = AutoSuggestions(self.txt_file)
        # Will hold the main frame of the UI
        self.main_frame = None
        # Will hold any decorations around the task list
        self.tasklist_decorations = None
        # Reference to the instance itself
        self.tasklist_instance = self
        # Will hold pending URL choices if multiple URLs are present in a task
        self.pending_url_choice = None
        # Initialize Tasks object
        self.tasks = Tasks(txt_file)
        # Helpers to detect double keypresses, e.g. `gg` for go to top
        self.last_key = None
        self.last_key_time = None

        # Another Tasks object to help with initialization
        tasks = Tasks(txt_file)

        # Initialize the ListBox with sorted tasks
        super(Body, self).__init__(urwid.SimpleFocusListWalker(
            TaskUI.render_and_display_tasks(tasks.sort(tasks.read()), PALETTE).widget_list))

    def refresh_displayed_tasks(self):
        # Refresh the displayed tasks by reading and sorting tasks again
        tasks = Tasks(self.txt_file)
        # Update the ListBox body with newly sorted tasks
        self.body = urwid.SimpleFocusListWalker(
            TaskUI.render_and_display_tasks(tasks.sort(tasks.read()), PALETTE).widget_list)
        # Update the main frame body to reflect the new task list
        self.main_frame.body = self.tasklist_decorations

    def focus_on_specific_task(self, task=None):
        """
        Set focus on specific task either based on its index or text content
        """
        # Check if the ListBox is empty
        if len(self.body) == 0:
            return  # Do nothing if the ListBox is empty

        if task is not None:
            if isinstance(task, int):  # If task is an integer, treat it as an index
                try:
                    # Try setting focus to the task at the given index
                    self.set_focus(task)
                except IndexError:
                    # If the index is out of range, do nothing or handle it differently
                    pass
            elif isinstance(task, str):  # If task is a string, treat it as the task text
                for i, widget in enumerate(self.body):
                    if hasattr(widget, 'original_widget') and \
                            isinstance(widget.original_widget, CustomCheckBox) and \
                            widget.original_widget.original_text == task:
                        self.set_focus(i)
                        break
        else:
            # Focus on the topmost task if no task is specified
            self.set_focus(1)

    def track_focused_task(self, loop, user_data):
        """
        Constantly updates the __focused_task_index/text__ global so we know which task is
        in focus at all times for easier task interaction throughout
        """

        focused_widget, focused_position = self.get_focus()
        global __focused_task_index__  # Ensure you're updating the global variable
        __focused_task_index__ = focused_position

        # Check if the focused widget is a CustomCheckBox
        if hasattr(focused_widget, 'original_widget') and isinstance(focused_widget.original_widget, CustomCheckBox):
            original_text = focused_widget.original_widget.original_text
        else:
            original_text = "Not a CustomCheckBox"

        global __focused_task_text__
        __focused_task_text__ = original_text

        loop.set_alarm_in(__track_focused_task_interval__,
                          self.track_focused_task)  # Schedule the next update in 1 second

    def keypress(self, size, key):
        global __focused_task_index__
        global __focused_task_text__

        # Determine the OS type for URL opening
        os_type = platform.system()
        # Get the current time for detecting rapid keypresses
        current_time = datetime.now()

        # Check if a key was pressed recently
        if self.last_key is not None:
            # Calculate the time difference between the last and current keypress
            time_difference = (current_time - self.last_key_time).total_seconds()
            # If two 'g' keys are pressed quickly, go to the top
            if time_difference < .3:
                if self.last_key == 'g' and key == 'g':
                    self.tasklist_instance.set_focus(1)

        # Update state to keep track of double keypresses, e.g. `gg`
        self.last_key = key
        self.last_key_time = current_time

        # Navigate to the bottom of the list
        if key == 'G':
            self.set_focus(len(self.body) - 1)

        # Quit the application
        elif key == 'q':
            raise urwid.ExitMainLoop()

        # Move focus down
        elif key == 'j':
            super(Body, self).keypress(size, 'down')

        # Move focus up
        elif key == 'k':
            return super(Body, self).keypress(size, 'up')

        # Add task
        elif key == 'n':
            TaskUI.open_task_add_edit_dialog(self, size)

        # Edit the currently focused task
        elif key == 'e':
            focused_widget = self.body.get_focus()[0]
            if hasattr(focused_widget, 'original_widget') and isinstance(focused_widget.original_widget,
                                                                         CustomCheckBox):
                task_text = focused_widget.original_widget.original_text  # Get original text from CustomCheckBox
                dialog = TaskUI.open_task_add_edit_dialog(self, "Edit Task", task_text)
                if dialog is not None:
                    self.update_tasks()

        # Archive completed tasks and refresh display
        elif key == 'A':
            self.tasks.archive()
            self.refresh_displayed_tasks()
            self.focus_on_specific_task(__focused_task_index__)

        # Delete the currently focused task
        elif key == 'D':
            self.tasks.delete(__focused_task_text__)
            self.refresh_displayed_tasks()
            self.focus_on_specific_task(__focused_task_index__)

        # Postpone the currently focused task to tomorrow
        elif key == 'P':
            focused_widget = self.body.get_focus()[0]
            if focused_widget is not None:
                task_text = focused_widget.original_widget.original_text
                task_text = Tasks.postpone_to_tomorrow(self, task_text)
                self.refresh_displayed_tasks()
                self.focus_on_specific_task(task_text)

        # Set focus to the search bar
        elif key == 'f':
            self.main_frame.set_focus('header')

        # Refresh the task list and clear the search field
        elif key == 'r':
            self.refresh_displayed_tasks()
            search_widget = self.main_frame.header.original_widget
            search_widget.set_edit_text('')
            self.tasklist_instance.set_focus(1)

        # Toggle task completion for the currently focused task
        elif key == 'x':
            self.tasks.complete(__focused_task_text__)
            self.refresh_displayed_tasks()
            self.focus_on_specific_task(__focused_task_index__)

        # Toggle task completion and archive all completed tasks at the same time
        elif key == 'X':
            self.tasks.complete(__focused_task_text__)
            self.tasks.archive()
            self.refresh_displayed_tasks()
            self.focus_on_specific_task(__focused_task_index__)

        # Open the URLs of the currently focused task
        elif key == 'u':
            focused_widget, _ = self.get_focus()
            if hasattr(focused_widget, 'original_widget') and isinstance(focused_widget.original_widget,
                                                                         urwid.CheckBox):
                task_text_display = focused_widget.original_widget.get_label().strip()
                original_task_line = focused_widget.original_widget.original_text
                urls = re.findall(URLS_REGEX, original_task_line)
                if len(urls) == 1:
                    if os_type == 'Linux':
                        subprocess.run(['xdg-open', urls[0]], stdout=subprocess.DEVNULL, stderr=subprocess.STDOUT)
                    elif os_type == 'Windows':
                        subprocess.run(['start', urls[0]], shell=True, stdout=subprocess.DEVNULL,
                                       stderr=subprocess.STDOUT)
                    elif os_type == 'Darwin':
                        subprocess.run(['open', urls[0]], stdout=subprocess.DEVNULL, stderr=subprocess.STDOUT)
                elif len(urls) > 1:
                    self.pending_url_choice = urls

        # Open a specific URL if a numeric key is pressed following `u` and multiple URLs are present in the task
        elif key in map(str, range(1, 10)) and self.pending_url_choice:
            index = int(key) - 1
            if index < len(self.pending_url_choice):
                if os_type == 'Linux':
                    subprocess.run(['xdg-open', self.pending_url_choice[index]], stdout=subprocess.DEVNULL,
                                   stderr=subprocess.STDOUT)
                elif os_type == 'Windows':
                    subprocess.run(['start', self.pending_url_choice[index]], shell=True, stdout=subprocess.DEVNULL,
                                   stderr=subprocess.STDOUT)
                elif os_type == 'Darwin':
                    subprocess.run(['open', self.pending_url_choice[index]], stdout=subprocess.DEVNULL,
                                   stderr=subprocess.STDOUT)
            self.pending_url_choice = None

        # Open all URLs of the currently focused task
        elif key == 'U':
            focused_widget, _ = self.get_focus()
            if hasattr(focused_widget, 'original_widget') and isinstance(focused_widget.original_widget,
                                                                         urwid.CheckBox):
                task_text_display = focused_widget.original_widget.get_label().strip()
                original_task_line = focused_widget.original_widget.original_text
                urls = re.findall(URLS_REGEX, original_task_line)
                for url in urls:
                    if os_type == 'Linux':
                        subprocess.run(['xdg-open', url], stdout=subprocess.DEVNULL, stderr=subprocess.STDOUT)
                    elif os_type == 'Windows':
                        subprocess.run(['start', url], shell=True, stdout=subprocess.DEVNULL, stderr=subprocess.STDOUT)
                    elif os_type == 'Darwin':
                        subprocess.run(['open', url], stdout=subprocess.DEVNULL, stderr=subprocess.STDOUT)

        # Pass the keypress event to the parent class if no match is found
        else:
            return super(Body, self).keypress(size, key)


class Search(urwid.Edit):
    """
    Extension of urwid.Edit to serve as search field for filtering tasks
    """

    def __init__(self, tasklist_instance, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.tasklist_instance = tasklist_instance

    def keypress(self, size, key):
        if key == 'enter':
            self.tasklist_instance.main_frame.set_focus('body')

            # Set focus on topmost task if search results !empty
            if len(self.tasklist_instance.body) > 0:
                self.tasklist_instance.set_focus(1)
            else:
                # Reset search if no results
                self.set_edit_text('')
                self.tasklist_instance.set_focus(1)
            return

        super().keypress(size, key)


def main():
    """
    Init. and run the actual application
    """

    # Check if there are command-line arguments
    if len(sys.argv) > 1:
        if sys.argv[1] == '--version':
            print(f"Version: {__version__}")
            return
        elif sys.argv[1] == '--help':
            print("Help (keybindings, features, etc): https://github.com/mdillondc/todo-txt-tui")
            return

    # Check if a file path for the todo.txt file is provided as a command-line argument
    if len(sys.argv) < 2:
        print("Please provide the path to the todo.txt file.")
        return

    # Store the path to the todo.txt file
    txt_file = sys.argv[1]

    # Check if the file actually exists
    if not os.path.exists(txt_file):
        print(f"The file '{txt_file}' does not exist. Are you sure you specified the correct path?")
        return

    # Initialize Body as ListBox to serve as layout for tasks and handle tasks related keybindings
    tasklist = Body(txt_file)
    tasklist_decorations = urwid.LineBox(tasklist,
                                         title="Tasks")  # Wrap the Body ListBox in a border and add a title
    tasklist.tasklist_decorations = tasklist_decorations  # Store the tasklist layout back into tasklist for future reference and state management

    # Use Search instead of urwid.Edit for search field
    # Had to use Search instead of a direct urwid.Edit to make general_input work. No idea why.
    search = Search(tasklist_instance=tasklist,
                    caption="Search: ")  # Give the search field an inline title to make its function obviou
    search_decorations = urwid.LineBox(search)  # Wrap the search field in a border (LineBox)
    urwid.connect_signal(  # Filter tasklist based on search query when the text in the search field changes
        search,
        'change',
        lambda edit_widget, search_query: Tasks.search(
            edit_widget, search_query, txt_file, tasklist.tasklist_instance
        )
    )

    # Create a Frame to contain the search field and the tasklist
    tasklist.main_frame = urwid.Frame(tasklist_decorations, header=search_decorations)

    # Initialize Tasks to handle task manipulation
    tasks = Tasks(txt_file)
    tasks.normalize_file(tasklist)

    # Initialize the MainLoop
    tasklist.loop = urwid.MainLoop(tasklist.main_frame, palette=PALETTE, handle_mouse=False)

    # Prepare to update the tasklist if the todo.txt file has changed outside the application
    try:  # Check and store the last modification time of the todo.txt file
        last_mod_time = [os.path.getmtime(txt_file)]  # Note the list
    except FileNotFoundError:
        last_mod_time = [None]  # Note the list

    # Set an alarm to check for file changes every 5 seconds
    tasklist.loop.set_alarm_in(__sync_refresh_rate__, tasks.sync, (txt_file, tasklist, last_mod_time))

    # Set an alarm to update focused task index every 1 second
    tasklist.loop.set_alarm_in(__track_focused_task_interval__, tasklist.track_focused_task)

    # Notify user if a new version is available for install
    tasklist.loop.set_alarm_in(0, check_for_updates, tasklist)

    # Start the MainLoop to display the application
    tasklist.loop.run()


# Start the application
if __name__ == '__main__':
    main()


# Needed to build for pypi because use of for main function await
def entry_point():
    main()
