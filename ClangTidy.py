import os.path
import sublime
import sublime_plugin
import subprocess

SETTINGS_FILE = "ClangTidy.sublime-settings"


def which(program):
    def is_exe(fpath):
        return os.path.isfile(fpath) and os.access(fpath, os.X_OK)
    fpath, fname = os.path.split(program)
    if fpath:
        if is_exe(program):
            return program
    else:
        for path in os.environ["PATH"].split(os.pathsep):
            path = path.strip('"')
            exe_file = os.path.join(path, program)
            if is_exe(exe_file):
                return exe_file
    return None


class ClangTidyOnSave(sublime_plugin.EventListener):

    def on_post_save(self, view):
        if sublime.load_settings(SETTINGS_FILE).get("run_on_save", False):
            return view.run_command("clang_tidy")
        return


class ClangTidyCommand(sublime_plugin.TextCommand):

    def run(self, edit):
        self.filename = self.view.file_name()
        self.fname = os.path.basename(self.filename)
        self.settings = sublime.load_settings(SETTINGS_FILE)
        if self.is_c_file():
            self.run_format(edit)

    def is_c_file(self):
        ext = [".c", ".cpp", ".h"]
        return self.fname.endswith(tuple(ext))

    def pipe(self, cmd):
        cwd = os.path.dirname(self.filename)
        startupinfo = None
        if os.name == 'nt':
            startupinfo = subprocess.STARTUPINFO()
            startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
        beautifier = subprocess.Popen(
            cmd, cwd=cwd, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
            startupinfo=startupinfo)
        (_, err) = beautifier.communicate()
        return (beautifier.wait(), err.decode('utf8'))

    def run_format(self, edit):
        buffer_region = sublime.Region(0, self.view.size())
        buffer_text = self.view.substr(buffer_region)
        if buffer_text == "":
            return
        clangtidy_bin = which(self.settings.get("clang-tidy", "clang-tidy"))
        if clangtidy_bin is None:
            return sublime.error_message(
                "Clang Tidy: can not find {0} in path.".format(self.settings.get("clang-tidy", "clang-tidy")))
        cmd_list = [clangtidy_bin, "-checks=-*,clang-analyzer-*,cppcoreguidelines-*,-clang-analyzer-cplusplus-*", self.filename, "--", "-std=c++1z", "-g", "-Wall", "-Wextra", "-Wformat", "-Werror", "-pedantic", "-fms-compatibility-version=19"] + self.settings.get("args", [])
        self.save_viewport_state()
        (exit_code, err) = self.pipe(cmd_list)
        if exit_code != 0 or (err != "" and not err.startswith("Using clang-tidy")):
            self.view.replace(edit, buffer_region, buffer_text)
            print("failed: exit_code: {0}\n{1}".format(exit_code, err))
            if sublime.load_settings(SETTINGS_FILE).get("show_errors", True):
                sublime.error_message(
                    "Clang Tidy: clang-tidy process call failed. See log (ctrl + `) for details.")
        self.view.window().run_command("reload_all_files")
        self.reset_viewport_state()

    def save_viewport_state(self):
        self.previous_selection = [(region.a, region.b)
                                   for region in self.view.sel()]
        self.previous_position = self.view.viewport_position()

    def reset_viewport_state(self):
        self.view.set_viewport_position((0, 0,), False)
        self.view.set_viewport_position(self.previous_position, False)
        self.view.sel().clear()
        for a, b in self.previous_selection:
            self.view.sel().add(sublime.Region(a, b))
