import os
import sys
import subprocess
import ctypes
from pathlib import Path

def is_admin():
    """Проверка прав администратора"""
    try:
        return ctypes.windll.shell32.IsUserAnAdmin()
    except:
        return False

def create_shortcut():
    """Создание ярлыка на рабочем столе"""
    
    # Путь к BAT файлу
    bat_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "start_server.bat")
    
    # Путь для ярлыка
    desktop = Path.home() / "Desktop"
    shortcut_path = desktop / "Расписание Колледжа.lnk"
    
    # Создаем BAT файл для ярлыка (если не существует)
    if not os.path.exists(bat_path):
        with open(bat_path, 'w', encoding='utf-8') as f:
            f.write('''@echo off
cd /d "%~dp0"
python app.py
pause''')
    
    # Команда для создания ярлыка через PowerShell
    ps_script = f'''
$WshShell = New-Object -comObject WScript.Shell
$Shortcut = $WshShell.CreateShortcut("{shortcut_path}")
$Shortcut.TargetPath = "{bat_path}"
$Shortcut.WorkingDirectory = "{os.path.dirname(bat_path)}"
$Shortcut.IconLocation = "C:\\Windows\\System32\\SHELL32.dll,15"
$Shortcut.Description = "Запуск системы расписания колледжа"
$Shortcut.Save()
'''
    
    try:
        # Запускаем PowerShell для создания ярлыка
        result = subprocess.run(['powershell', '-Command', ps_script], 
                              capture_output=True, text=True)
        
        if result.returncode == 0:
            print(f"✅ Ярлык создан: {shortcut_path}")
            
            # Создаем иконку для ярлыка (опционально)
            create_icon()
            
        else:
            print(f"❌ Ошибка создания ярлыка: {result.stderr}")
            
    except Exception as e:
        print(f"❌ Ошибка: {e}")

def create_icon():
    """Создание иконки для ярлыка"""
    icon_script = '''
Add-Type -AssemblyName System.Drawing
$iconPath = Join-Path (Get-Location) "icon.ico"
if (Test-Path $iconPath) { return }

$bitmap = New-Object System.Drawing.Bitmap 256, 256
$graphics = [System.Drawing.Graphics]::FromImage($bitmap)
$graphics.Clear([System.Drawing.Color]::FromArgb(52, 152, 219))

$font = New-Object System.Drawing.Font("Arial", 100, [System.Drawing.FontStyle]::Bold)
$brush = New-Object System.Drawing.SolidBrush([System.Drawing.Color]::White)
$format = New-Object System.Drawing.StringFormat
$format.Alignment = [System.Drawing.StringAlignment]::Center
$format.LineAlignment = [System.Drawing.StringAlignment]::Center

$graphics.DrawString("📚", $font, $brush, [System.Drawing.Rectangle]::new(0, 0, 256, 256), $format)
$graphics.Dispose()

$bitmap.Save($iconPath, [System.Drawing.Imaging.ImageFormat]::Icon)
$bitmap.Dispose()
'''
    
    try:
        subprocess.run(['powershell', '-Command', icon_script], 
                      capture_output=True, text=True)
        print("✅ Иконка создана")
    except:
        print("⚠️  Не удалось создать иконку")

if __name__ == "__main__":
    print("=" * 50)
    print("Создание ярлыка для системы расписания")
    print("=" * 50)
    
    # Проверяем права администратора
    if not is_admin():
        print("⚠️  Запустите программу от имени администратора")
        input("Нажмите Enter для выхода...")
        sys.exit(1)
    
    create_shortcut()
    print("\n✅ Готово! Ярлык создан на рабочем столе")
    input("Нажмите Enter для выхода...")