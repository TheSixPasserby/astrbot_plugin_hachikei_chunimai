@echo off
xcopy /E /Y /Q "D:\TheSixPasserby\dev\mai-plugin\astrbot_plugin_hachikei_chunimai\*.py" "C:\Users\Admin\.astrbot\data\plugins\astrbot_plugin_hachikei_chunimai\" >nul
xcopy /E /Y /Q "D:\TheSixPasserby\dev\mai-plugin\astrbot_plugin_hachikei_chunimai\command\*.py" "C:\Users\Admin\.astrbot\data\plugins\astrbot_plugin_hachikei_chunimai\command\" >nul
xcopy /Y /Q "D:\TheSixPasserby\dev\mai-plugin\astrbot_plugin_hachikei_chunimai\_conf_schema.json" "C:\Users\Admin\.astrbot\data\plugins\astrbot_plugin_hachikei_chunimai\" >nul
xcopy /Y /Q "D:\TheSixPasserby\dev\mai-plugin\astrbot_plugin_hachikei_chunimai\metadata.yaml" "C:\Users\Admin\.astrbot\data\plugins\astrbot_plugin_hachikei_chunimai\" >nul
echo Synced to AstrBot plugin directory.
