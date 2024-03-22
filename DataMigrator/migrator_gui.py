from __future__ import annotations

import ctypes
import itertools
from os import path, PathLike
from abc import ABC, abstractmethod
from tkinter.constants import LEFT
from typing import Any, Iterable, Literal, Callable, override

import tkinter as tk
from tkinter import ttk, filedialog, messagebox

import DataMigrator.migration_toolkit as mt

def choose_file(entry: ttk.Entry,
                filetypes: Iterable[tuple[str, str | list[str] | tuple[str, ...]]],
                command: Callable | None = None
) -> PathLike:
    """ Choose file and enter the directory to the entry box, and call command function if
        needed, return the path. If no file is chosen, return the content in the entry box.
    """
    filepath: PathLike = filedialog.askopenfilename(filetypes=filetypes)
    if filepath:
        entry.delete(0, tk.END)
        entry.insert(tk.END, filepath)
        if command:
            command()
        return filepath
    else:
        return entry.get()

def choose_save(entry: ttk.Entry,
                filetypes: Iterable[tuple[str, str | list[str] | tuple[str, ...]]],
                command: Callable | None = None
) -> PathLike:
    """ Choose the directory where the file would be saved, and enter the directory to the
        entry box, and call command function if needed, return the path. If no dirctory is
        chosen, return the content in the entry box.
    """
    filepath: PathLike = filedialog.asksaveasfilename(filetypes=filetypes)
    if filepath:
        if not path.splitext(filepath)[1]:
            filepath += filetypes[0][1][-1]
        
        entry.delete(0, tk.END)
        entry.insert(tk.END, filepath)
        if command:
            command()
        return filepath
    else:
        return entry.get()

def choose_dir(entry: ttk.Entry,
               command: Callable | None = None
) -> PathLike:
    """ Choose a directory, enter it to the entry box and call command function if needed.
        Return the chosen dir if something is chosen, otherwise return the context in the
        entry box.
    """
    filepath: PathLike = filedialog.askdirectory()
    if filepath:
        entry.delete(0, tk.END)
        entry.insert(tk.END, filepath)
        if command:
            command()
        return filepath
    else:
        return entry.get()


class FileEntryLine:
    """ Represents one of the lines at the top of the GUI, each line contains some instruction
        text on the left, an entry box for displaying the directory in the mid, and a browse
        button on the right.

        # Attributes
        - parent: the frame of all file entry lines
        - master: the root widget of the GUI
        - label: the label object on the left
        - entry: the entry box object in the mid
        - button: the button object on the right

        # Methods
        - set_row: set which row is the line in
        - set_enabled
        - destroy
        - get_dir
    """
    def __init__(self,
                 frame: FileEntryFrame,
                 master: MigratorUI,
                 row: int,
                 desc: str,
                 save: bool = False,
                 filetypes: Iterable[tuple[str, str | list[str] | tuple[str, ...]]] = ...,
                 enabled: bool = True,
                 on_load: Callable | None = None
    ):
        """ Create a new line on the top for choosing a file/savepath/dir.

            # Args
            - frame: the frame of all file entry lines
            - master: the root widget of the GUI
            - row: which row should the new line be in the frame (do not check if it is
            overlapped which other line)
            - desc: the instruction text on the left
            - save: whether to choose a savefile path or a file path
            - filetypes: specify the extention of the file would be chosen/saved
            - enabled: whether the line is enabled initially
            - on_load: execute when a new directory is loaded, expecting to receive one
            argment - the chosen path
        """
        self.parent: FileEntryFrame = frame
        self.master: MigratorUI = master

        self.label = ttk.Label(frame, text=desc)
        self.entry = ttk.Entry(frame)
        if on_load:
            self.button = ttk.Button(
                frame,
                text = "Browse",
                command = (lambda: on_load(choose_save(self.entry, filetypes))) if save else
                          (lambda: on_load(choose_file(self.entry, filetypes)))
            )
        else:
            self.button = ttk.Button(
                frame,
                text = "Browse",
                command = (lambda: choose_save(self.entry, filetypes)) if save else
                          (lambda: choose_file(self.entry, filetypes))
            )
        
        self.set_row(row)
        self.set_enabled(enabled)

    def set_row(self, row: int) -> None:
        """ Set which row is the line in (do not check if it is overlapped which other line)
        """
        self.label.grid(row = row,
                        column = 0,
                        sticky = tk.W)
        self.entry.grid(row = row,
                        column = 1,
                        sticky = tk.W + tk.E,
                        padx = (5 * self.master.sf, 0))
        self.button.grid(row = row,
                         column = 2,
                         sticky = tk.E,
                         padx = (5 * self.master.sf, 0))
    
    def set_enabled(self, status: bool | Literal["disabled", "normal"]) -> None:
        """ Toggle the enabled status of the whole line. """
        if isinstance(status, bool):
            status = tk.NORMAL if status else tk.DISABLED
        
        self.label.config(state = status)
        self.entry.config(state = status)
        self.button.config(state = status)
    
    def destroy(self) -> None:
        """ Distroy all widgets on the line. """
        self.label.destroy()
        self.entry.destroy()
        self.button.destroy()

    def get_dir(self) -> str:
        """ Get the content in the entry box. """
        dir: str = self.entry.get()
        if dir:
            return dir
        else:
            raise FileNotFoundError()


class FileEntryFrame(ttk.Frame):
    """ The frame on the top of the GUI, may have many line to choose different files/paths.

        # Attributes
        - master: the root widget of the GUI
        - config_loader: the first file entry line to choose the .rjson config file, would be
        always enabled
        - source_loaders: a list contains one or more file entry lines to choose the source
        excel file, the number depends on how much file specified in the .rjson config file.
        - outdir_selector: the last file entry line to choose the save path of the exported
        excel file.

        # Methods
        - set_enabled
        - clear
        - additional_input
        - on_load_config
        - get_src_dirs
        - get_tgt_dir
    """
    def __init__(self, master: MigratorUI) -> None:
        """ Init the frame to load it in the main GUI. """
        ttk.Frame.__init__(self, master)
        
        self.pack(fill = tk.X,
                  padx = 20 * master.sf,
                  pady = 10 * master.sf)
        self.grid_columnconfigure(1, weight=1)
        
        self.master: MigratorUI = master
        
        self.config_loader = FileEntryLine(
            self, master, 0, "Config File Path:",
            filetypes = [("Data Migration Config File", "rjson")],
            enabled = True,
            on_load = self.on_load_config
        )
        self.source_loaders: list[FileEntryLine] = [
            FileEntryLine(
                self, master, 1, "Source File Path:",
                filetypes = [("Microsoft Excel", (".xls", ".xlsx"))],
                enabled = False
            )
        ]
        self.outdir_selector = FileEntryLine(
            self, master, 2, "Export to:",
            filetypes = [("Microsoft Excel", (".xls", ".xlsx"))],
            save = True, enabled = False
        )
    
    def set_enabled(self, status: bool) -> None:
        """ Toggle the enabled status of all widgets in the frame (except the first line) """
        if status:
            for source_loader in self.source_loaders:
                source_loader.set_enabled(True)
            self.outdir_selector.set_enabled(True)
        else:
            for source_loader in self.source_loaders:
                source_loader.set_enabled(False)
            self.outdir_selector.set_enabled(False)
    
    def clear(self) -> None:
        """ Clear all additional source loader lines in the frame, only remain one config
            loader line, one source loader line and one out dir selector line. The last two
            lines would be disabled.
        """
        for i in range(len(self.source_loaders)-1, 0, -1):
            self.source_loaders[i].destroy()
            del self.source_loaders[i]
        self.source_loaders[0].set_enabled(False)
        self.outdir_selector.set_enabled(False)

    def additional_input(self, num: int) -> None:
        """ Add additional source loader lines. """
        self.outdir_selector.set_row(num + 2)
        for _ in range(num):
            row_index = len(self.source_loaders) + 1
            self.source_loaders.append(
                FileEntryLine(
                    self, self.master, row_index, f"Source File Path{row_index}:",
                    filetypes = [("Microsoft Excel", (".xls", ".xlsx"))],
                    enabled = True
                )
            )

    def on_load_config(self, config_path: PathLike) -> None:
        """ Called when the config is loaded. Try to parse the config and save it to mconfig
            attribute in master. Pop up an error box when failed to parse it.
        """
        self.clear()
        self.master.args_entry_frame.clear()
        self.master.button_run.config(state=tk.DISABLED)

        if config_path:

            try:
                self.master.mconfig = mt.parse_migration_config(config_path, "UTF-8")
            except Exception as e:
                messagebox.showerror(f"{type(e).__name__} Occored when Loading Config", e)
                return
            
            if "additional_input" in self.master.mconfig:
                additional_input_num: int = int(self.master.mconfig["additional_input"])
                if additional_input_num > 0:
                    self.additional_input(additional_input_num)
            self.set_enabled(True)
            self.master.args_entry_frame.set_enabled(True)
            self.master.button_run.config(state=tk.NORMAL)
    
    def get_src_dirs(self) -> tuple[str, list[str]]:
        """ Return a list of every source file path. """
        return self.source_loaders[0].get_dir(), \
               [sl.get_dir() for sl in self.source_loaders[1:]]
    
    def get_tgt_dir(self) -> str:
        """ Return the path to save the exported file. """
        return self.outdir_selector.get_dir()


class ArgEntry(ABC, ttk.Frame):
    """ The base class of input for all kinds of args required.

        # Attributes
        - row: in which row this arg entry is located

        # Methods
        - get_value (abstract)
        - set_enabled (abstract)
    """
    def __init__(self,
                 frame: ArgsEntryFrame,
                 row: int,
                 side: Literal["left", "right"] = tk.LEFT
    ) -> None:
        """ Create and place a new arg entry in the parent ArgsEntryFrame.

            # Args
            - frame: the parent frame where all arg input aeras are located
            - row: in which row should this arg entry located
            - side: this arg entry is on the left or right of the row
        """
        ttk.Frame.__init__(self, frame)
        self.grid(row = row,
                  column = 0 if side == tk.LEFT else 1,
                  sticky=tk.NW)
        self.row: int = row
    
    @abstractmethod
    def get_value(self) -> Any:
        """ Return the current input (or default) value in the arg entry. """
        ...
        return None
    
    @abstractmethod
    def set_enabled(self, status: bool) -> None:
        """ Toggle the status of this arg entry. """
        ...

class ChoiceArgEntry(ArgEntry):
    """ The arg entry for multiple choice type args.

        # Attributes
        - choice_var: the current choice (the first one by default) value
        - label: the description label widget
        - choice_buttons: a list contains all choice button widgets

        # Methods
        - get_value
        - set_enabled
        - destroy
    """
    def __init__(self,
                 frame: ArgsEntryFrame,
                 row: int,
                 desc: str,
                 choices: list[str],
                 side: Literal["left", "right"] = tk.LEFT
    ) -> None:
        """ Create and place a new choice entry in the parent ArgsEntryFrame.

            # Args
            - frame: the parent frame where all arg input aeras are located
            - row: in which row should this arg entry located
            - desc: the description of this arg entry, will be displayed above the options
            - choices: the choice list to choose from
            - side: this arg entry is on the left or right of the row
        """
        ArgEntry.__init__(self, frame, row, side)
        self.grid_columnconfigure(0, weight=1)

        self.choice_var = tk.StringVar(value=choices[0])

        self.label = ttk.Label(self, text=desc)
        self.label.grid(row=0, column=0, sticky=tk.W)

        self.choice_buttons: list[ttk.Radiobutton] = []
        for i, c in enumerate(choices):
            radio = ttk.Radiobutton(self,
                                    text = choices[i],
                                    variable = self.choice_var,
                                    value = choices[i])
            radio.grid(row=i+1, column=0, sticky=tk.W)
            self.choice_buttons.append(radio)
    
    @override
    def get_value(self) -> str:
        return self.choice_var.get()
    
    @override
    def set_enabled(self, status: bool | Literal["disabled", "normal"]) -> None:
        if isinstance(status, bool):
            status = tk.NORMAL if status else tk.DISABLED
        
        self.label.config(state=status)
        for cb in self.choice_buttons:
            cb.config(state=status)
    
    @override
    def destroy(self) -> None:
        self.label.destroy()
        for cb in self.choice_buttons:
            cb.destroy()
        ttk.Frame.destroy(self)

class TextArgEntry(ArgEntry):
    """ The arg entry for multiple choice type args.

        # Attributes
        - label: the description label widget
        - textbox: the textbox widget for text input

        # Methods
        - get_value
        - set_enabled
        - destroy
    """
    def __init__(self,
                 frame: ArgsEntryLine,
                 row: int,
                 desc: str,
                 side: Literal["left", "right"] = tk.LEFT
    ) -> None:
        """ Create and place a new text entry in the parent ArgsEntryFrame.

            # Args
            - frame: the parent frame where all arg input aeras are located
            - row: in which row should this arg entry located
            - desc: the description of this arg entry, will be displayed above the options
            - side: this arg entry is on the left or right of the row
        """
        ArgEntry.__init__(self, frame, row, side)
        self.grid_columnconfigure(0, weight=1)
        
        self.label = ttk.Label(self, text=desc)
        self.label.grid(row=0, column=0, sticky=tk.W)

        self.textbox = ttk.Entry(self)
        self.textbox.grid(row=1, column=0, sticky=tk.W+tk.E)
    
    @override
    def get_value(self) -> str:
        return self.textbox.get()
    
    @override
    def set_enabled(self, status: bool | Literal["disabled", "normal"]) -> None:
        if isinstance(status, bool):
            status = tk.NORMAL if status else tk.DISABLED
        
        self.label.config(state=status)
        self.textbox.config(state=status)
    
    @override
    def destroy(self) -> None:
        self.label.destroy()
        self.textbox.destroy()
        ttk.Frame.destroy(self)


class ArgsEntryLine:
    """ Represents one of the lines in the mid of the GUI, each line contains at most two arg
        entries for different types of arg input.

        # Attributes
        - frame: the ArgsEntryFrame of all arg entry lines
        - row: the row index of this line in the frame
        - arg_l: the ArgEntry object on the left
        - arg_r: the ArgEntry object on the right (may not have one)

        # Methods
        - create_arg_entry
        - set_enabled
        - get_args
        _ destroy
    """
    def __init__(self,
                 frame: ArgsEntryFrame,
                 master: MigratorUI,
                 row: int,
                 arg_config_l: dict,
                 arg_config_r: dict | None = None) -> None:
        """ Create and place a new arg entry line in the parent ArgsEntryFrame.

            # Args
            - frame: the parent frame where all arg input aeras are located
            - master: the root widget of the GUI
            - row: in which row should this arg entry located
            - arg_config_l: the config dict of the arg whose input area is on the left
            - arg_config_r: (optional) the config dict of the arg whose input area is on the
            right
        """
        self.frame: ArgsEntryFrame = frame
        self.row: int = row

        self.arg_l: ArgEntry = self.create_arg_entry(arg_config_l, tk.LEFT)
        self.arg_r: ArgEntry | None = self.create_arg_entry(arg_config_r, tk.RIGHT) \
                                      if arg_config_r else None
    
    def create_arg_entry(self,
                         arg_config: dict,
                         side: Literal["left", "right"] = tk.LEFT
    ) -> ArgEntry:
        """ Create an arg entry object form an arg config dict. """
        arg_type: str = arg_config["type"]
        desc: str = arg_config["description"]

        if arg_type == "choice":
            choices: list[str] = arg_config["options"]
            return ChoiceArgEntry(self.frame, self.row, desc, choices, side)
        elif arg_type == "text":
            return TextArgEntry(self.frame, self.row, desc, side)
        else:
            raise Exception(f"Do not support the argment type {arg_type}")
    
    def set_enabled(self, status: bool | Literal["disabled", "normal"]) -> None:
        if isinstance(status, bool):
            status = tk.NORMAL if status else tk.DISABLED
        
        self.arg_l.set_enabled(status)
        if self.arg_r:
            self.arg_r.set_enabled(status)

    def get_args(self) -> tuple:
        if self.arg_r:
            return self.arg_l.get_value(), self.arg_r.get_value()
        else:
            return self.arg_l.get_value(),
    
    def destroy(self) -> None:
        self.arg_l.destroy()
        if self.arg_r:
            self.arg_r.destroy()
        

class ArgsEntryFrame(ttk.Frame):
    def __init__(self, root: MigratorUI) -> None:
        """Construct a frame widget with the parent MASTER.

            Valid resource names: background, bd, bg, borderwidth, class,
            colormap, container, cursor, height, highlightbackground,
            highlightcolor, highlightthickness, relief, takefocus, visual, width.
        """
        self.root: MigratorUI = root
        self.canvas = tk.Canvas(root)
        self.canvas.pack(fill = tk.BOTH,
                         expand = True,
                         padx = 20 * root.sf,
                         pady = 10 * root.sf)
        
        ttk.Frame.__init__(self, self.canvas)
        self.pack(fill=tk.BOTH, side=tk.LEFT, expand=True)

        self.grid_columnconfigure(0, weight=1)
        self.grid_columnconfigure(1, weight=1)

        self.vbar = ttk.Scrollbar(self.canvas, orient=tk.VERTICAL)
        self.vbar.pack(side=tk.RIGHT, fill=tk.Y)
        self.vbar.config(command=self.canvas.yview)

        self.canvas.config(yscrollcommand=self.vbar.set)
        _frame_id: int = self.canvas.create_window((0, 0), window=self, anchor="nw")

        self.bind("<Configure>",
                  lambda event: self.canvas.configure(scrollregion=self.bbox("all")))
        self.canvas.bind("<Configure>",
                         lambda event: self.canvas.itemconfigure(
                                           _frame_id,
                                           width = self.canvas.winfo_width()
                                       ))

        self.arg_entry_lines: list[ArgsEntryLine] = []
    
    def set_enabled(self, status: bool) -> None:
        """ Toggle the status of all widgets in the arg entry frame. """
        if status:
            if self.root.mconfig and "args" in self.root.mconfig:
                args_config: list[dict] = self.root.mconfig["args"]
                for row, ac_batch in enumerate(itertools.batched(args_config, 2)):
                    self.arg_entry_lines.append(ArgsEntryLine(self, self.root, row, *ac_batch))
        else:
            for ael in self.arg_entry_lines:
                ael.set_enabled(False)
    
    def clear(self) -> None:
        """ Clear all arg entries in the frame. """
        for ael in self.arg_entry_lines:
            ael.destroy()
        self.arg_entry_lines.clear()
    
    def get_args(self) -> list:
        """ Return all current input (or default) value in all arg entries. """
        args: list = []
        for ael in self.arg_entry_lines:
            args.extend(ael.get_args())
        return args


class MigratorUI(tk.Tk):
    """ The main widget of the DataMigrator GUI.
    
        # Attributes
        - mconfig: the whole config dict load from the .rjson config file
        - sf: the scale factor (1.0 is 100% on windows)
        - file_entry_frame: the frame for inputing files at the top of GUI
        - args_entry_frame: the frame for inputing args in the mid of GUI
        - frame_bottom: the frame for the cancel and run button at the buttom of GUI
        - button_cancel: the cancel buttom at left-buttom corner
        - button_run: the run buttom at right-buttom corner

        # Methods
        - launch: called when run buttom is clicked and start migrating data.
    """
    def __init__(self,
                 screenName: str | None = None,
                 baseName: str | None = None,
                 className: str = "Tk",
                 useTk: bool = True,
                 sync: bool = False,
                 use: str | None = None
    ) -> None:
        """ Create an instance of DataMigration GUI. All args are inherited from tk.Tk and
            are optional.
        """
        tk.Tk.__init__(self, screenName, baseName, className, useTk, sync, use)
        self.title("Migrator")
        self.geometry("600x300")
        self.mconfig: dict | None = None

        ctypes.windll.shcore.SetProcessDpiAwareness(1)
        scale_factor: int = ctypes.windll.shcore.GetScaleFactorForDevice(0)
        self.tk.call("tk", "scaling", scale_factor / 75)
        self.sf: float = scale_factor / 100

        self.file_entry_frame = FileEntryFrame(self)
        self.args_entry_frame = ArgsEntryFrame(self)

        # The cancel and run buttom at the bottom.
        self.frame_bottom = ttk.Frame(self)
        self.frame_bottom.pack(fill=tk.X, padx=20*self.sf, pady=10*self.sf)

        self.button_cancel = ttk.Button(self.frame_bottom, text="Cancel", command=self.destroy)
        self.button_cancel.pack(side=tk.LEFT)

        self.button_run = ttk.Button(self.frame_bottom, text="Run", command=self.launch)
        self.button_run.pack(side=tk.RIGHT)
        self.button_run.config(state=tk.DISABLED)

        self.mainloop()
    
    def launch(self):
        """ Called when run buttom is clicked and start migrating data. """
        self.file_entry_frame.set_enabled(False)
        self.args_entry_frame.set_enabled(False)
        self.button_cancel.config(state=tk.DISABLED)
        self.button_run.config(state=tk.DISABLED)

        try:
            from DataMigrator.database import Database
            src_dir, ex_src_dirs = self.file_entry_frame.get_src_dirs()
            src_db: Database = Database.import_from_xlsx(src_dir)
            ex_src_db: list[Database] = [Database.import_from_xlsx(esd) for esd in ex_src_dirs]

            args: list = self.args_entry_frame.get_args()

            tgt_db: Database = mt.execute_migration(self.mconfig, src_db, ex_src_db, args)
            tgt_db.export_to_xlsx(self.file_entry_frame.get_tgt_dir())

            messagebox.showinfo("Migrate Complete",
                                "Migration Colpleted, export to path " +
                                    self.file_entry_frame.get_tgt_dir())

        except FileNotFoundError:
            messagebox.showwarning("SourceDirError", "Path not specified.")

        self.file_entry_frame.set_enabled(True)
        self.args_entry_frame.set_enabled(True)
        self.button_cancel.config(state=tk.NORMAL)
        self.button_run.config(state=tk.NORMAL)
