import pyrad
import os

pyrad_path = os.path.dirname(pyrad.__file__)
dictionary_path = os.path.join(pyrad_path, 'dictionaries', 'dictionary')
print("Default dictionary path:", dictionary_path)
