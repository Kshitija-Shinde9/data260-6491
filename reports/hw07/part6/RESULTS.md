# Part 6 results — file tools and safety gate

The six file tools, `SAFE_PREFIXES`, `confirm_bash`, and `is_destructive` are in `code/hw07_part4/tools.py`.

## Integration test

The sandbox has `notes_a.py`, `notes_b.py`, and `notes_c.py`. One chain finds the file that contains DEBUG:

1. `glob_files("*.py")` lists the three files.
2. `search_in_files("DEBUG", file_pattern="*.py")` returns `notes_b.py`.
3. `read_file("notes_b.py", max_lines=5)` shows `DEBUG = True`.

`edit_file` returns a short diff. A write outside the sandbox is rejected.

## Safety-gate test

5 commands are allowed and 5 are blocked.

| Command | Result |
| --- | --- |
| `pwd` | allow: command matches SAFE_PREFIXES (pwd) |
| `ls` | allow: command matches SAFE_PREFIXES (ls) |
| `echo hello` | allow: command matches SAFE_PREFIXES (echo) |
| `python3 -c "print(1)"` | allow: command matches SAFE_PREFIXES (python3) |
| `git status` | allow: command matches SAFE_PREFIXES (git status) |
| `rm -rf notes_b.py` | block: destructive command requires confirmation: recursive deletion |
| `sudo python3 -c "print(1)"` | block: destructive command requires confirmation: privilege escalation |
| `chmod 777 notes_a.py` | block: destructive command requires confirmation: permission or ownership change |
| `dd if=/dev/zero of=/dev/disk0` | block: destructive command requires confirmation: raw-device write |
| `echo hello > /etc/passwd` | block: destructive command requires confirmation: redirection to a root path |

## False allow that was fixed

`echo hello > /etc/passwd` starts with `echo`, which is on `SAFE_PREFIXES`. An allow-list by itself would let it through. `is_destructive` flags the redirect to `/etc/passwd`, and `confirm_bash` blocks it unless confirmation is supplied. The blocked command is not executed.

Full output is in `reports/hw07/part6/RUN_LOG.txt`.
