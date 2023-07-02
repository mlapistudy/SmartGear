# Readme

This folder contains the code and source file of our tool


## Folder content
1. `./solution`: our implementation of our tool
   1. `./solution/sample_tests.py` contains two examples.
   2. `./solution/sample_functions.py` contains the function definition for `./sample_tests.py`.
   3. `./solution/test_data/` contains an image for testing `find_dessert`.
   4. `./solution/src/` contains the run-time diagnosis part of our tool.
   5. `./solution/control_flow_analysis/` contains static analysis code. Please check `./solution/control_flow_analysis/readme.md` for details.
   6. `./solution/execution_logs/` contains the cached result of `./control_flow_analysis`.
2. `./files`: some files containing metadata of Google Cloud APIs

## How to run
```bash
cd solution/
python ./sample_tests.py` 
```

It will execute the `find_dessert` example, which contains a non-stop-fail failure caused by mismatch.



## Install

### Python
The tool is implemented in Python3. Following are the Python packages we used:

google-auth-httplib2==0.0.4
google-auth-oauthlib==0.4.6
google-cloud-language==1.3.0
google-cloud-vision==1.0.0 
google-cloud-speech==2.0.0
google-cloud-videointelligence==2.7.0
numpy==1.19.5
pillow==8.3.0
bs4==0.0.1
Wikidata==0.7.0
jedi==0.17.0
wikipedia===1.4.0
anytree==2.5.0
moviepy== 1.0.3
imageio-ffmpeg==0.4.7
levenshtein==0.18.1

### Google Cloud AI Credentials

Google Cloud AI Services require some set up before using, including installing libs, enabling APIs in Google account and creating credentials. Following are the Google official document for setting up:

1. Vision: https://cloud.google.com/vision/docs/setup
2. Speech-to-Text: https://cloud.google.com/speech-to-text/docs/quickstart-client-libraries
3. Language: https://cloud.google.com/natural-language/docs/setup
4. Video: https://cloud.google.com/video-intelligence/docs/quickstarts

Please make specify the certification by 

```bash
export GOOGLE_APPLICATION_CREDENTIALS=/path/to/your/certification.json
```


### Others
In `./control_flow_analysis/`(static analysis), We also uses a [CVC (v1.6) constraint solver](https://github.com/cvc5/cvc5/tree/1.6.x).
Please specify CVC path before execution, e.g:
```bash
export PYTHONPATH=/usr/local/share/pyshared/
```

Install instructions are at `https://github.com/CVC5/CVC5/issues/1533`. The compiling might take over 10 minutes. Specifically,

On Linux,
```bash
git clone https://github.com/CVC5/CVC5.git CVC5_python
cd CVC5_python
git checkout 1.6.x
export LC_ALL="en_US.UTF-8"
export LC_CTYPE="en_US.UTF-8"
export PYTHON_CONFIG=/usr/bin/python3.8-config   # Not needed in conda env
export PYTHON_VERSION=3.8                        # Not needed in conda env
contrib/get-antlr-3.4
./autogen.sh
./configure ANTLR=`pwd`/antlr-3.4/bin/antlr3 --enable-language-bindings=python --prefix `pwd`/out_dir
echo "python_cpp_SWIGFLAGS = -py3" >> src/bindings/Makefile.am
autoreconf
make && make install
cd out_dir/share/pyshared/
ln -s ../../lib/pyshared/CVC5.so _CVC5.so

cd /path/to/CVC5/CVC5_python
export PYTHONPATH=/path/to/CVC5/CVC5_python/out_dir/share/pyshared/
# a test to see wether the install is sucess or not
# please go back to folder CVC5_python
python3.8 examples/SimpleVC.py
```


On Mac
```bash
brew update
brew install wget
brew install autoconf
brew install automake
brew install libtool
brew install boost
brew install gmp
brew install gcc
brew install swig
brew install coreutils

git clone https://github.com/CVC5/CVC5.git CVC5_python
cd CVC5_python
git checkout 1.6.x
export PYTHON_CONFIG=/usr/local/bin/python3.8-config
export PYTHON_VERSION=3.8
contrib/get-antlr-3.4
brew install autoconf
brew install automake
./autogen.sh
./configure --enable-optimized --with-antlr-dir=`pwd`/antlr-3.4 ANTLR=`pwd`/antlr-3.4/bin/antlr3 --enable-language-bindings=python
echo "python_cpp_SWIGFLAGS = -py3" >> src/bindings/Makefile.am
autoreconf
make && make install
export PYTHONPATH=/usr/local/share/pyshared/
cd /usr/local/share/pyshared/
ln -s ../../lib/pyshared/CVC5.so _CVC5.so
# a test to see wether the install is sucess or not
# please go back to folder CVC5_python
python3.8 examples/SimpleVC.py
```
