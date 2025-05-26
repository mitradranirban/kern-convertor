# Kerning Convertor

This is a python script to convert kerning data in [AFDKO](https://github.com/adobe-type-tools/afdko) features.fea format to [UFO](https://github.com/unified-font-object/ufo-spec) groups.plist and kerning.plist format.

## usage
* Clone this repository 

`git clone github.com/mitradranirban/kern-convertor`

 * Set up virtual environment

`python3 -m venv venv`
* Activate Virtual environment 

`venv/bin/activate`
* Update pip and install dependencies

```
pip install -U pip
pip install -r requirements.txt
```
* Copy the features.fea file in the directory and run the scripts
```
python3 kern-groups.py features.fea groups.plist
python3 kern-convertor features.fea kerning.plist
```
Now you can copy the .plist files in your ufo directory.



