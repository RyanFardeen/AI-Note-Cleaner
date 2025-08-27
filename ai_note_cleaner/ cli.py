import subprocess
import sys
from rich.console import Console
from rich.markdown import Markdown
import markdown
from bs4 import BeautifulSoup
from markdownify import markdownify as md
from tabulate import tabulate
import re
import html

console = Console()


def markdown_to_plain_text(md_text):
    """
    Convert Markdown to clean, readable plain text with:
      - Uppercased headings + underlines
      - Bullet points
      - Nicely formatted tables (tabulate)
      - Checkboxes prettified
      - ANSI codes stripped
      - Stable blank line spacing
    """
    # 1) Markdown -> HTML
    html_str = markdown.markdown(md_text)

    # 2) Parse HTML
    soup = BeautifulSoup(html_str, "html.parser")

    # 3) Lists -> bullets
    for li in soup.find_all("li"):
        # add a bullet before each list item and ensure newline after
        li.insert_before("• ")
        li.insert_after("\n")

    # 4) Headings -> UPPERCASE + underline
    for heading in soup.find_all(["h1", "h2", "h3", "h4", "h5", "h6"]):
        text = heading.get_text(separator=" ", strip=True)
        underline = "-" * len(text)
        heading.string = f"\n{text.upper()}\n{underline}\n"

    # 5) Tables -> tabulate (GitHub style)
    for table in soup.find_all("table"):
        # collect headers
        thead = table.find("thead")
        if thead:
            headers = [th.get_text(strip=True) for th in thead.find_all("th")]
        else:
            # try first row as headers if no thead
            first_row = table.find("tr")
            if first_row:
                headers = [c.get_text(strip=True) for c in first_row.find_all(["th", "td"])]
            else:
                headers = []

        # rows
        rows = []
        trs = table.find_all("tr")
        # skip thead row if present
        start_idx = 1 if (not thead and len(trs) > 0) else 0
        for tr in trs[start_idx:]:
            cells = [td.get_text(strip=True) for td in tr.find_all(["td", "th"])]
            if cells:
                rows.append(cells)

        pretty = tabulate(rows, headers=headers, tablefmt="github")
        table.replace_with("\n" + pretty + "\n")

    # 6) Extract text
    text = soup.get_text()

    # 7) Checkboxes and minor prettifiers
    # If source had markdown checkboxes, normalize them
    text = (text
            .replace("- [ ]", "☐")
            .replace("[ ]", "☐")
            .replace("- [x]", "☑")
            .replace("[x]", "☑"))

    # 8) Strip any ANSI escapes (like [1;44;93m)
    text = re.sub(r"\x1b\[[0-9;]*m", "", text)

    # 9) Compact extra blank lines (keep at most 2)
    text = re.sub(r"\n{3,}", "\n\n", text)

    # 10) Ensure a trailing newline for nicer <pre> rendering
    if not text.endswith("\n"):
        text += "\n"

    return text.strip()


def to_html_preserving_newlines(plain_text):
    """
    Wrap plain text in a <pre> that preserves line breaks and spacing in Apple Notes.
    Also escape HTML entities to avoid accidental tag interpretation.
    """
    escaped = html.escape(plain_text)
    # Use Apple-friendly fonts (optional)
    return (
        '<pre style="white-space: pre-wrap; '
        'font-family: -apple-system, BlinkMacSystemFont, '
        '\'Helvetica Neue\', Helvetica, Arial, sans-serif; '
        'font-size: 14px; line-height: 1.4;">'
        f'{escaped}'
        '</pre>'
    )


def print_banner():
    console.print("="*50, style="bold green")
    console.print("AI Note Cleaner CLI Application - v1.0", style="bold bright_cyan")
    console.print("="*50, style="bold green")
    console.print("Enhance your Apple Notes by summarizing, fixing grammar,", style="italic")
    console.print("adding headings & bullets using Perplexity AI CLI.", style="italic")
    console.print()


def run_applescript(script):
    process = subprocess.run(['osascript', '-e', script], capture_output=True, text=True)
    if process.returncode != 0:
        console.print(f"[red]AppleScript error:[/] {process.stderr}")
        return None
    return process.stdout.strip()


def list_folders():
    script = 'tell application "Notes" to get name of every folder'
    folders = run_applescript(script)
    if folders:
        unique_folders = list(dict.fromkeys(f.strip() for f in folders.split(",") if f.strip()))
        return unique_folders
    return []


def list_notes_in_folder(folder):
    script = f'''
    tell application "Notes"
      set noteNames to name of notes of folder "{folder}"
    end tell
    '''
    result = run_applescript(script)
    if result:
        return [n.strip() for n in result.split(",")]
    return []


def get_note_body(folder, note_name):
    script = f'''
    tell application "Notes"
      set theNotes to notes of folder "{folder}"
      repeat with n in theNotes
        if name of n is "{note_name}" then
          return body of n
        end if
      end repeat
    end tell
    '''
    return run_applescript(script)


def create_note_in_folder_html(folder, note_name, html_body):
    """
    Create a new Apple Note with an HTML body (so line breaks are preserved).
    We escape just the quotes for AppleScript and pass HTML directly.
    """
    html_escaped_for_as = html_body.replace('"', '\\"')
    script = f'''
    tell application "Notes"
      tell folder "{folder}"
        make new note with properties {{name:"{note_name}", body:"{html_escaped_for_as}"}}
      end tell
    end tell
    '''
    return run_applescript(script)


def enhance_text_with_perplexity(text):
    prompt = f'Summarize, fix grammar, add headings and bullet points, and rewrite cleanly:\n{text}'
    try:
        cmd = ['python3', '/Users/ryan/.local/bin/perplexity', prompt]
        process = subprocess.run(cmd, capture_output=True, text=True, timeout=60)
        if process.returncode == 0:
            return process.stdout.strip()
        else:
            console.print(f"[red]Perplexity CLI error:[/] {process.stderr}")
            return None
    except Exception as e:
        console.print(f"[red]Error running Perplexity CLI:[/] {e}")
        return None


def prompt_int(prompt, min_val, max_val):
    while True:
        val = input(prompt).strip()
        if val.isdigit():
            num = int(val)
            if min_val <= num <= max_val:
                return num
        console.print(f"[red]Invalid input! Please enter a number between {min_val} and {max_val}.[/]")


def main():
    print_banner()

    console.print("Fetching Apple Notes folders...\n", style="yellow")
    folders = list_folders()
    if not folders:
        console.print("[red]No folders found in Apple Notes. Please create some folders first.[/]")
        return

    console.print("Available Apple Notes folders:", style="bold cyan")
    for idx, folder in enumerate(folders, 1):
        console.print(f"  {idx}. {folder}")

    src_idx = prompt_int(f"\nEnter source folder number to process (1-{len(folders)}): ", 1, len(folders)) - 1

    dest_folder_name = input("\nEnter destination folder name (existing or new): ").strip()
    if not dest_folder_name:
        console.print("[red]Destination folder name cannot be empty.[/]")
        return

    if dest_folder_name not in folders:
        console.print(f"Destination folder '{dest_folder_name}' does not exist. Creating it...", style="yellow")
        create_script = f'tell application "Notes" to make new folder with properties {{name:"{dest_folder_name}"}}'
        if run_applescript(create_script) is None:
            console.print(f"[red]Failed to create destination folder '{dest_folder_name}'. Exiting.[/]")
            return
        else:
            console.print(f"Folder '{dest_folder_name}' created successfully.", style="green")

    console.print(f"\nProcessing notes from '{folders[src_idx]}' to '{dest_folder_name}'...\n", style="bold green")

    notes = list_notes_in_folder(folders[src_idx])
    if not notes:
        console.print(f"[yellow]No notes found in folder '{folders[src_idx]}'.[/]")
        return

    for note_name in notes:
        console.print(f"Enhancing note: [bold]{note_name}[/] ...")
        original_body = get_note_body(folders[src_idx], note_name)
        if not original_body:
            console.print(f"  [red]Failed to read note '{note_name}'. Skipping.[/]")
            continue

        enhanced_body = enhance_text_with_perplexity(original_body)
        if not enhanced_body:
            console.print(f"  [red]Failed to enhance note '{note_name}'. Skipping.[/]")
            continue

        new_note_name = f"Enhanced - {note_name}"

        # Format for readability (plain text), then wrap in HTML so Notes preserves breaks
        readable_text = markdown_to_plain_text(enhanced_body)
        html_body = to_html_preserving_newlines(readable_text)

        create_note_in_folder_html(dest_folder_name, new_note_name, html_body)
        console.print(f"  Note '{note_name}' enhanced and saved as '{new_note_name}'.\n", style="green")

    console.print("All notes processed. Thank you for using AI Note Cleaner CLI!", style="bold magenta")


if __name__ == "__main__":
    main()
