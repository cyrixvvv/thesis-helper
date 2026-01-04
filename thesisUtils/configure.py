import configparser
import os
import sys
config = configparser.ConfigParser()
config_path = os.path.join(os.getcwd(), "CONFIG.ini")
try:
    config.read(config_path, encoding="utf-8")
except UnicodeDecodeError:
    config.read(config_path, encoding="gb18030")
