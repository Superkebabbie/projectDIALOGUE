from cx_Freeze import setup, Executable
import os

base = "Win32GUI"    

executables = [Executable("project DIALOGUE.py", base=base)]
packages = ["idna", 'sys', 'os', 'shutil', 're', 'tkinter', 'xml.etree.ElementTree']
options = {
    'build_exe': {    
        'packages':packages,
        'include_files':['logo.ico','header.png','D:\\Support Structure\\Python\\WPy-3661\\python-3.6.6.amd64\\DLLs\\tcl86t.dll','D:\\Support Structure\\Python\\WPy-3661\\python-3.6.6.amd64\\DLLs\\tk86t.dll']
    },    
}


os.environ['TCL_LIBRARY'] = "D:\\Support Structure\\Python\\WPy-3661\\python-3.6.6.amd64\\tcl\\tcl8.6"
os.environ['TK_LIBRARY'] = "D:\\Support Structure\\Python\\WPy-3661\\python-3.6.6.amd64\\tcl\\tk8.6"

setup(
    name = "Project DIALOGUE",
    options = options,
    version = "1.3",
    description = 'Minecraft Interactive Dialogue Generator',
    executables = executables
)