#!/usr/bin/env python3
"""Self-updater for PM Hub skills (stdlib only, Python 3.8+, macOS / Windows / Linux).

Canonical copy: skills/_shared/skill-updater/self_update.py in Product/pm-hub.
Every auto-updating skill ships an identical copy at <skill>/scripts/self_update.py
(CI checks this). Edit the canonical copy, then copy it into each skill.

Usage
  python3 self_update.py --skill-dir <dir> [--check-now]
      Run by the skill's Pre-step. Always exits 0 and prints at most one line:
        SKILL_UPDATE: updated: <message for the PM>
        SKILL_UPDATE: notice: <message for the PM>
      or nothing at all.

  python3 self_update.py --install <skill> [<skill> ...] [--root <skills dir>]
      First install / migration of existing copies. Ignores the throttle and
      prints one human-readable line per skill. Default root: ~/.claude/skills.

How it works (see README.md next to the canonical copy for the full flow)
  - The version lives in SKILL.md frontmatter (version:), the source in
    update_source: <host>/<owner>/<repo>/<path>@<ref>.
  - Checks at most once every 6 hours (state kept in <root>/../.skill-updates/<skill>/).
  - Reads PM Hub through the gh CLI only (GH_HOST is set per call); never reads
    or prints a token, never echoes gh's error output.
  - Downloads into a staging folder, verifies every file against its git blob
    SHA, backs up what it replaces, swaps files in, and rolls back on any error.
  - Only files that exist in the skill's folder in PM Hub are touched. Anything
    else in the install folder belongs to the user and is never modified.

Test-only environment variables
  PMHUB_UPDATER_SOURCE=<host/owner/repo/path@ref>   override update_source
  PMHUB_UPDATER_FAULT=corrupt|fail_mid_swap         inject a failure
  PMHUB_UPDATER_ALLOW_NO_UPDATER=1                  accept a tree without scripts/self_update.py
"""
import base64
import datetime
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import time

try:
    from urllib.parse import quote
except ImportError:  # pragma: no cover
    from urllib import quote

DEFAULT_SOURCE = "github.cyberng.com/Product/pm-hub/skills/{skill}@master"
THROTTLE_SECONDS = 6 * 3600
CALL_TIMEOUT = 8
TOTAL_BUDGET = 30
LOCK_STALE_SECONDS = 120
KEEP_BACKUPS = 3
UPDATER_PATH = "scripts/self_update.py"
END_SENTINEL = "# end of self_update.py"
CLAUDE_VARIANT = "claude-code/SKILL.md"

SEMVER = re.compile(r"^v?(\d+)\.(\d+)\.(\d+)(?:-([0-9A-Za-z.-]+))?$")
SOURCE = re.compile(r"^([A-Za-z0-9.-]+)/([\w.-]+)/([\w.-]+)/([\w./-]+?)@([\w./-]+)$")
# Never installed or overwritten, even if they show up in the repo.
USER_OWNED = re.compile(
    r"(^|/)(__pycache__/|\.stats\.json$|\.last-update$|\.DS_Store$|Thumbs\.db$|[^/]*\.local\.[^/]*$)"
)

REASONS = {
    "gh_missing": "the GitHub CLI (gh) isn't installed",
    "auth": "gh isn't signed in to {host} (run: gh auth login --hostname {host})",
    "offline": "{host} isn't reachable (offline or off VPN?)",
    "unreachable": "the skill couldn't be read from PM Hub",
    "invalid": "the downloaded update was incomplete, so it wasn't applied",
    "apply": "the update couldn't be applied, so your current copy was kept",
}


class Fail(Exception):
    def __init__(self, reason):
        Exception.__init__(self, reason)
        self.reason = reason


# ---------------------------------------------------------------- helpers

def parse_version(text):
    m = SEMVER.match((text or "").strip())
    if not m:
        return None
    major, minor, patch, pre = m.groups()
    # A release sorts after its pre-releases: 1.2.0 > 1.2.0-rc1
    return (int(major), int(minor), int(patch), pre is None, pre or "")


def frontmatter(text):
    text = (text or "").lstrip("\ufeff")
    m = re.match(r"^---[ \t]*\r?\n(.*?)\r?\n---[ \t]*(\r?\n|$)", text, re.S)
    meta = {}
    if not m:
        return meta
    for key in ("version", "update_source"):
        km = re.search(r"^%s:[ \t]*(.+?)[ \t]*$" % key, m.group(1), re.M)
        if km:
            meta[key] = km.group(1).strip().strip("'\"")
    return meta


def parse_source(text):
    m = SOURCE.match((text or "").strip())
    if not m:
        return None
    host, owner, repo, path, ref = m.groups()
    if ".." in path.split("/"):
        return None
    return {"host": host, "owner": owner, "repo": repo, "path": path.strip("/"), "ref": ref}


def git_sha(data):
    return hashlib.sha1(b"blob " + str(len(data)).encode() + b"\0" + data).hexdigest()


def read_bytes(path):
    with open(path, "rb") as f:
        return f.read()


def file_sha(path):
    try:
        return git_sha(read_bytes(path))
    except (IOError, OSError):
        return None


def write_bytes(path, data):
    d = os.path.dirname(path)
    if d and not os.path.isdir(d):
        os.makedirs(d)
    with open(path, "wb") as f:
        f.write(data)


def load_json(path):
    try:
        with open(path, encoding="utf-8") as f:
            data = json.load(f)
        return data if isinstance(data, dict) else {}
    except Exception:
        return {}


def save_json(path, data):
    try:
        tmp = path + ".tmp"
        write_bytes(tmp, json.dumps(data, indent=2, sort_keys=True).encode("utf-8"))
        replace_with_retry(tmp, path)
        return True
    except Exception:
        return False


def replace_with_retry(src, dst):
    # Windows: a file open in an editor or antivirus scan can briefly lock dst.
    for attempt in range(4):
        try:
            os.replace(src, dst)
            return
        except PermissionError:
            if attempt == 3:
                raise
            time.sleep(0.3)


def safe_rel(path):
    parts = path.split("/")
    return bool(path) and not path.startswith("/") and ":" not in parts[0] and ".." not in parts


def changelog_summary(text, version):
    lines = (text or "").splitlines()
    for i, line in enumerate(lines):
        m = re.match(r"^##\s+v?(\S+)", line)
        if m and m.group(1) == version:
            for nxt in lines[i + 1:]:
                s = nxt.strip()
                if s.startswith("#"):
                    break
                if s:
                    s = re.sub(r"^[-*]\s+", "", s)
                    return s if len(s) <= 140 else s[:137].rstrip() + "..."
            break
    return "see CHANGELOG.md for details"


# ---------------------------------------------------------------- gh access

class GH(object):
    def __init__(self, host, deadline):
        self.host = host
        self.deadline = deadline
        self.exe = shutil.which("gh")

    def api(self, path):
        if not self.exe:
            raise Fail("gh_missing")
        env = dict(os.environ)
        env.update({"GH_HOST": self.host, "GH_PROMPT_DISABLED": "1", "NO_COLOR": "1",
                    "GH_NO_UPDATE_NOTIFIER": "1"})
        env.pop("GH_DEBUG", None)
        kwargs = {}
        if os.name == "nt":
            kwargs["creationflags"] = 0x08000000  # CREATE_NO_WINDOW
        for attempt in (1, 2):
            remaining = self.deadline - time.time()
            if remaining < 1:
                raise Fail("offline")
            try:
                p = subprocess.run([self.exe, "api", path], env=env, stdin=subprocess.DEVNULL,
                                   stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                                   timeout=min(CALL_TIMEOUT, remaining), **kwargs)
            except subprocess.TimeoutExpired:
                raise Fail("offline")
            except OSError:
                raise Fail("gh_missing")
            if p.returncode == 0:
                break
            reason = classify(p.returncode, p.stderr + p.stdout)
            if reason != "offline" or attempt == 2:
                raise Fail(reason)
            time.sleep(1)  # one quick retry: the enterprise host drops connections now and then
        try:
            return json.loads(p.stdout.decode("utf-8"))
        except ValueError:
            raise Fail("unreachable")


def classify(code, output):
    text = output.decode("utf-8", "replace").lower()
    if code == 4 or any(k in text for k in ("auth login", "http 401", "not logged", "authentication",
                                            "bad credentials", "requires authentication")):
        return "auth"
    if any(k in text for k in ("dial tcp", "connection refused", "no such host", "timeout",
                               "timed out", "network is unreachable", "could not resolve",
                               "connection reset", "tls handshake", "eof")):
        return "offline"
    return "unreachable"


class Remote(object):
    def __init__(self, gh, src):
        self.gh = gh
        self.src = src
        self.base = "repos/%s/%s" % (src["owner"], src["repo"])

    def tree_sha(self):
        parent, _, leaf = self.src["path"].rpartition("/")
        url = "%s/contents/%s?ref=%s" % (self.base, quote(parent), quote(self.src["ref"], safe=""))
        listing = self.gh.api(url)
        if isinstance(listing, list):
            for entry in listing:
                if entry.get("name") == leaf and entry.get("type") == "dir" and entry.get("sha"):
                    return entry["sha"]
        raise Fail("unreachable")

    def files(self, tree_sha, claude_host):
        tree = self.gh.api("%s/git/trees/%s?recursive=1" % (self.base, tree_sha))
        if not isinstance(tree, dict) or tree.get("truncated") or not isinstance(tree.get("tree"), list):
            raise Fail("unreachable")
        blobs = {}
        for e in tree["tree"]:
            if e.get("type") == "blob" and e.get("sha") and e.get("path"):
                if not safe_rel(e["path"]):
                    raise Fail("invalid")
                blobs[e["path"]] = e["sha"]
        return map_variant(blobs, claude_host)

    def blob(self, sha):
        j = self.gh.api("%s/git/blobs/%s" % (self.base, sha))
        try:
            return base64.b64decode(j.get("content", ""))
        except Exception:
            raise Fail("invalid")


def map_variant(blobs, claude_host):
    """Map repo paths to install paths. claude-code/SKILL.md (if present) is the
    Claude Code variant and is installed as SKILL.md outside ~/.cursor."""
    has_cc = CLAUDE_VARIANT in blobs
    out = {}
    for path, sha in blobs.items():
        if path.startswith("claude-code/"):
            if claude_host and path == CLAUDE_VARIANT:
                out["SKILL.md"] = sha
            continue
        if path == "SKILL.md" and claude_host and has_cc:
            continue
        if USER_OWNED.search(path):
            continue
        out[path] = sha
    return out


# ---------------------------------------------------------------- lock

def acquire_lock(path):
    for _ in range(2):
        try:
            fd = os.open(path, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
            os.write(fd, str(os.getpid()).encode())
            os.close(fd)
            return True
        except FileExistsError:
            try:
                if time.time() - os.path.getmtime(path) <= LOCK_STALE_SECONDS:
                    return False
                os.remove(path)
            except OSError:
                return False
        except OSError:
            return False
    return False


# ---------------------------------------------------------------- core

class Updater(object):
    def __init__(self, skill_dir, mode):
        self.skill_dir = os.path.abspath(os.path.expanduser(skill_dir))
        self.mode = mode  # "check" | "now" | "install"
        self.skill = os.path.basename(self.skill_dir.rstrip("/\\"))
        root_parent = os.path.dirname(os.path.dirname(self.skill_dir))
        self.state_dir = os.path.join(root_parent, ".skill-updates", self.skill)
        self.state_path = os.path.join(self.state_dir, "state.json")
        self.manifest_path = os.path.join(self.state_dir, "manifest.json")
        parts = [p.lower() for p in re.split(r"[/\\]", self.skill_dir)]
        self.claude_host = ".cursor" not in parts
        self.local_label = "your current version"

    def run(self):
        """Returns (kind, message) or None. kind is 'updated' or 'notice'."""
        skill_md_path = os.path.join(self.skill_dir, "SKILL.md")
        if self.mode != "install" and not os.path.isfile(skill_md_path):
            return None  # wrong folder: never create a phantom install
        meta = frontmatter(self._read_text(skill_md_path))
        raw_version = meta.get("version")
        local_version = parse_version(raw_version or "0.0.0")
        if local_version is None:
            return self._quiet_or_say("notice", "Skipped the %s update check: its version (%s) isn't valid."
                                      % (self.skill, raw_version))
        self.local_label = raw_version or "unversioned"
        src_text = (os.environ.get("PMHUB_UPDATER_SOURCE") or meta.get("update_source")
                    or DEFAULT_SOURCE.format(skill=self.skill))
        src = parse_source(src_text)
        if src is None:
            return self._quiet_or_say("notice", "Skipped the %s update check: update_source isn't valid." % self.skill)

        try:
            os.makedirs(self.state_dir, exist_ok=True)
        except OSError:
            return self._quiet_or_say("notice", "Couldn't create %s." % self.state_dir)
        state = load_json(self.state_path)
        now = time.time()
        last = state.get("last_check", 0)
        if (self.mode == "check" and isinstance(last, (int, float))
                and 0 <= now - last < THROTTLE_SECONDS):
            return None
        state["last_check"] = now
        save_json(self.state_path, state)

        lock = os.path.join(self.state_dir, "lock")
        if not acquire_lock(lock):
            return self._quiet_or_say("notice", "Another %s update is already running." % self.skill)
        try:
            try:
                result = self._check_and_apply(src, raw_version, local_version)
            except Fail as f:
                return self._failed(state, f.reason, src["host"])
            except Exception:
                return self._failed(state, "apply", src["host"])
            state = load_json(self.state_path) or state
            state["failure_notified"] = False
            state["last_result"] = "updated" if result else "current"
            save_json(self.state_path, state)
            return result
        finally:
            try:
                os.remove(lock)
            except OSError:
                pass

    # -- internals

    def _read_text(self, path):
        try:
            return read_bytes(path).decode("utf-8", "replace")
        except (IOError, OSError):
            return ""

    def _quiet_or_say(self, kind, message):
        return (kind, message) if self.mode == "install" else None

    def _failed(self, state, reason, host):
        text = REASONS.get(reason, REASONS["unreachable"]).format(host=host)
        if self.mode == "install" and not os.path.isfile(os.path.join(self.skill_dir, "SKILL.md")):
            message = "Couldn't install %s: %s." % (self.skill, text)
        elif reason in ("invalid", "apply"):
            message = "Couldn't update %s: %s. Still using %s." % (self.skill, text, self.local_label)
        else:
            message = "Couldn't check for %s updates: %s. Using %s." % (self.skill, text, self.local_label)
        state = load_json(self.state_path) or state
        state["last_result"] = "failed:" + reason
        if self.mode == "install":
            save_json(self.state_path, state)
            return ("notice", message)
        if state.get("failure_notified"):
            save_json(self.state_path, state)
            return None
        state["failure_notified"] = True
        save_json(self.state_path, state)
        return ("notice", message)

    def _check_and_apply(self, src, raw_version, local_version):
        gh = GH(src["host"], time.time() + TOTAL_BUDGET)
        remote = Remote(gh, src)
        manifest = load_json(self.manifest_path)
        tree_sha = remote.tree_sha()
        if (self.mode != "install" and manifest.get("tree_sha") == tree_sha
                and manifest.get("version") == raw_version):
            return None

        files = remote.files(tree_sha, self.claude_host)
        if "SKILL.md" not in files:
            raise Fail("invalid")
        skill_md = self._fetch(remote, "SKILL.md", files["SKILL.md"])
        remote_raw = frontmatter(skill_md.decode("utf-8", "replace")).get("version")
        remote_version = parse_version(remote_raw)
        if remote_version is None:
            raise Fail("invalid")
        if self.mode != "install" and remote_version <= local_version:
            return None
        return self._apply(remote, files, skill_md, manifest, tree_sha, src, raw_version, remote_raw)

    def _fetch(self, remote, path, sha):
        local = os.path.join(self.skill_dir, *path.split("/"))
        if os.path.isfile(local) and file_sha(local) == sha:
            return read_bytes(local)  # unchanged file: no download needed
        return remote.blob(sha)

    def _apply(self, remote, files, skill_md, manifest, tree_sha, src, old_raw, new_raw):
        fault = os.environ.get("PMHUB_UPDATER_FAULT", "")
        old_files = manifest.get("files") if isinstance(manifest.get("files"), dict) else {}
        have_manifest = bool(old_files)
        staging = tempfile.mkdtemp(prefix="staging-", dir=self.state_dir)
        try:
            # 1. Stage and verify every file
            for path, sha in files.items():
                data = skill_md if path == "SKILL.md" else self._fetch(remote, path, sha)
                if fault == "corrupt" and path == "SKILL.md":
                    data = data[: len(data) // 2]
                if git_sha(data) != sha:
                    raise Fail("invalid")
                write_bytes(os.path.join(staging, *path.split("/")), data)
            staged_md = self._read_text(os.path.join(staging, "SKILL.md"))
            if frontmatter(staged_md).get("version") != new_raw:
                raise Fail("invalid")
            if not os.environ.get("PMHUB_UPDATER_ALLOW_NO_UPDATER"):
                if UPDATER_PATH not in files:
                    raise Fail("invalid")
                if END_SENTINEL not in self._read_text(os.path.join(staging, *UPDATER_PATH.split("/"))):
                    raise Fail("invalid")

            # 2. Work out what changes and what the user edited
            def local_path(p):
                return os.path.join(self.skill_dir, *p.split("/"))

            local_sha = {}
            for p in set(files) | set(old_files):
                local_sha[p] = file_sha(local_path(p))
            to_write = [p for p in files if local_sha[p] != files[p]]
            to_delete = [p for p in old_files if p not in files
                         and local_sha[p] is not None and local_sha[p] == old_files[p]]
            edited = []
            if have_manifest:
                for p, lsha in local_sha.items():
                    if lsha is None or lsha == files.get(p):
                        continue
                    if p in old_files and lsha != old_files[p]:
                        edited.append(p)
                    elif p not in old_files and p in files:
                        edited.append(p)
            touched = [p for p in to_write + to_delete if local_sha[p] is not None]

            # 3. Back up everything we are about to replace or delete
            backup_dir = None
            if touched:
                stamp = datetime.datetime.now().strftime("%Y%m%d-%H%M%S")
                base = os.path.join(self.state_dir, "backups", "%s-%s" % (old_raw or "unversioned", stamp))
                backup_dir, n = base, 1
                while os.path.exists(backup_dir):
                    n += 1
                    backup_dir = "%s-%d" % (base, n)
                for p in touched:
                    dst = os.path.join(backup_dir, *p.split("/"))
                    os.makedirs(os.path.dirname(dst), exist_ok=True)
                    shutil.copy2(local_path(p), dst)

            # 4. Swap in, rolling back on any error
            done_replace, done_add, done_delete = [], [], []
            try:
                for i, p in enumerate(to_write):
                    target = local_path(p)
                    existed = local_sha[p] is not None
                    os.makedirs(os.path.dirname(target), exist_ok=True)
                    replace_with_retry(os.path.join(staging, *p.split("/")), target)
                    (done_replace if existed else done_add).append(p)
                    if fault == "fail_mid_swap" and i == 0:
                        raise RuntimeError("injected failure")
                for p in to_delete:
                    os.remove(local_path(p))
                    done_delete.append(p)
                installed = frontmatter(self._read_text(local_path("SKILL.md"))).get("version")
                if installed != new_raw:
                    raise RuntimeError("post-check failed")
            except Exception:
                self._rollback(backup_dir, done_replace + done_delete, done_add)
                raise Fail("apply")

            # 5. Commit
            save_json(self.manifest_path, {
                "version": new_raw, "tree_sha": tree_sha, "files": files,
                "source": "%s/%s/%s/%s@%s" % (src["host"], src["owner"], src["repo"], src["path"], src["ref"]),
                "updated_at": datetime.datetime.now().isoformat(timespec="seconds"),
            })
            try:
                os.remove(os.path.join(self.skill_dir, ".stats.json"))
            except OSError:
                pass
            self._prune_backups()
        finally:
            shutil.rmtree(staging, ignore_errors=True)

        summary = changelog_summary(self._read_text(local_path("CHANGELOG.md")), new_raw)
        if self.mode == "install" and not touched and old_raw == new_raw:
            return ("updated", "%s %s is installed and up to date." % (self.skill, new_raw))
        if self.mode == "install" and old_raw is None and not touched:
            message = "Installed %s %s." % (self.skill, new_raw)
        else:
            message = "Updated %s %s -> %s: %s" % (self.skill, self.local_label, new_raw, summary.rstrip("."))
            message += "."
        if edited and backup_dir:
            shown = ", ".join(sorted(edited)[:3]) + (" and others" if len(edited) > 3 else "")
            message += " Your local edits to %s were saved in %s" % (shown, backup_dir)
        elif not have_manifest and backup_dir:
            message += " Your previous copy was saved in %s" % backup_dir
        return ("updated", message)

    def _rollback(self, backup_dir, restore, remove):
        for p in remove:
            try:
                os.remove(os.path.join(self.skill_dir, *p.split("/")))
            except OSError:
                pass
        if not backup_dir:
            return
        for p in restore:
            src = os.path.join(backup_dir, *p.split("/"))
            dst = os.path.join(self.skill_dir, *p.split("/"))
            try:
                os.makedirs(os.path.dirname(dst), exist_ok=True)
                shutil.copy2(src, dst)
            except (IOError, OSError):
                pass

    def _prune_backups(self):
        root = os.path.join(self.state_dir, "backups")
        try:
            dirs = [os.path.join(root, d) for d in os.listdir(root)]
            dirs = sorted((d for d in dirs if os.path.isdir(d)), key=os.path.getmtime, reverse=True)
            for d in dirs[KEEP_BACKUPS:]:
                shutil.rmtree(d, ignore_errors=True)
        except OSError:
            pass


# ---------------------------------------------------------------- CLI

def emit(line):
    data = (line + "\n").encode(getattr(sys.stdout, "encoding", None) or "utf-8", "replace")
    try:
        sys.stdout.buffer.write(data)
    except AttributeError:  # pragma: no cover
        sys.stdout.write(data.decode("ascii", "replace"))
    sys.stdout.flush()


def main(argv):
    if "--install" in argv:
        i = argv.index("--install")
        skills, root = [], os.path.join("~", ".claude", "skills")
        rest = argv[i + 1:]
        j = 0
        while j < len(rest):
            if rest[j] == "--root" and j + 1 < len(rest):
                root = rest[j + 1]
                j += 2
                continue
            if not rest[j].startswith("--"):
                skills.append(rest[j])
            j += 1
        if "--root" in argv[:i]:
            k = argv.index("--root")
            root = argv[k + 1] if k + 1 < len(argv) else root
        if not skills:
            emit("Usage: self_update.py --install <skill> [<skill> ...] [--root <skills dir>]")
            return 2
        root = os.path.expanduser(root)
        ok = True
        for skill in skills:
            if not re.match(r"^[\w.-]+$", skill):
                emit("%s: not a valid skill name" % skill)
                ok = False
                continue
            try:
                os.makedirs(os.path.join(root, skill), exist_ok=True)
                result = Updater(os.path.join(root, skill), "install").run()
            except Exception as e:  # pragma: no cover
                result = ("notice", "%s: unexpected error (%s)" % (skill, type(e).__name__))
            kind, message = result or ("notice", "%s: nothing to do." % skill)
            emit(("OK    " if kind == "updated" else "FAIL  ") + message)
            ok = ok and kind == "updated"
        if ok:
            emit("Done. Start a new Claude Code session (VS Code: Developer: Reload Window) to load the skills.")
        return 0 if ok else 1

    skill_dir = None
    if "--skill-dir" in argv:
        k = argv.index("--skill-dir")
        skill_dir = argv[k + 1] if k + 1 < len(argv) else None
    if not skill_dir:
        return 0
    try:
        result = Updater(skill_dir, "now" if "--check-now" in argv else "check").run()
        if result:
            emit("SKILL_UPDATE: %s: %s" % result)
    except BaseException:
        pass  # fail open: never break the skill
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
# end of self_update.py
