import os
from pathlib import Path

str_path = str(Path.home())
str_conf_path = str_path + '/app/configurations/settings.ini'  #path to external conf
if os.path.isfile(str_conf_path):
    str_configpath = str_conf_path
else:
    str_configpath = 'app/settings.ini'

