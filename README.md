Qwiic_Template_Py
==================
<p align="center">
   <img src="https://cdn.sparkfun.com/assets/custom_pages/2/7/2/qwiic-logo-registered.jpg"  width=200>  
   <img src="https://www.python.org/static/community_logos/python-logo-master-v3-TM.png"  width=240>   
</p>


This is a template repository and associated documentation that outlines how to publish and maintain a python package 
for the SparkFun Qwiic ecosystem.

This repository defines the general structure of a repository and details the role of each file/location in the repository. 
Additionally, the use of ReadTheDocs and PyPi are outlined. 

The general structure implemented follows the guidelines set forth in the python packaging structure and tools. While this document provides a high-level overview of SparkFun's implementation of a python project, details of this process and structure can be found in the [Packaging Python Projects](https://packaging.python.org/tutorials/packaging-projects/) document provided by the Python Foundation. 

For details and example use of the described structure, please review the existing python projects for the Qwiic system. 
Examples Include:
* [Qwiic_CCS811_Py - An example of a repository for a single file, python module](https://github.com/sparkfun/Qwiic_CCS811_Py)
* [Qwiic_Micro_OLED_Py - An example of a python package, that includes resource files](https://github.com/sparkfun/Qwiic_Micro_OLED_Py)
* [Qwiic_Py - the overall package for the Qwiic python system](https://github.com/sparkfun/Qwiic_Py)

Repository Structure
---------------------

The general structure of a Qwiic Python repository is as follows

```
Qwiic_Template_Py/
   +--- docs/
   |       `--- ... files to support automatic documentation creation via readthedocs.org
   |
   +--- examples/
   |       `--- ... example files for the package
   |
   +--- .readthedocs.yml  - configuration file for readthedocs
   +--- DESCRIPTION.rst   - Contains the RST formatted description for the package. Used when building the installer package
   +--- LICENSE           - The license for the package. Currently using MIT
   +--- README.md         - The GitHub markdown formatted readme for the package
   +--- setup.cfg         - Configuration details used when building the installer package.
   +--- setup.py          - The python script used to define and build the python installer package.
   |
   +--- qwiic_<mod>.py.   - If a module (single file implementation), the implementation source code file.
   |
   or
   |
   `--- qwiic_package/    - If a package (directory that contains the implementation) the name of the package
        `---  ... implementation files.
   

```
Implementation
-----------------
To keep the implementation simple and minimize resource needs, there are few design requirements when implementing a new Qwiic I2C driver. Each driver implements a class that encapsulates all interations with the underlying I2C device. This class implements a simple interface that enables the higher-level functionality provided by the overarching [Qwiic package](https://github.com/sparkfun/Qwiic_Py).

The specific implementation requirements are as follows

### Device Class
Each development driver package implements a class that encapsulates all interactions with this device. 

#### Class Name
The class name should be a **CamelCase** version of the package name. This naming schema is used by future automation functionality and follows common python methodologies

```
     qwiic_bme280.          -> QwiicBme280
     qwiic_micro_oled       -> QwiicMicroOled
     qwiic_scmd             -> QwiicScmd
     qwiic_my_super_board.  -> QwiicMySuperBoard
```

An example of a class declaration (note the use and location of the class docstring):
```python
class QwiicScmd(object):
	"""
	QwiicScmd

		:param address: The I2C address to use for the device. 
						If not provided, the default address is used.
		:param i2c_driver: An existing i2c driver object. If not provided 
						a driver object is created. 
		:return: The Serial Control Motor Driver device object.
		:rtype: Object
	"""
```

#### Class Variables
To support the dynamic discovery and enumeration of Qwiic boards by the [Qwiic package](https://github.com/sparkfun/Qwiic_Py), each object implements a set of class variables. This allows the Qwiic package to inspect these values at runtime without having to instantiate an actual object. 

These variables are:

| Class Variable Name| Description|
|----|----|
|**device_name**      |      - Set to the human-readable name of the device|
|**available_addresses**|   - Set to an array of the I2C addresses this device supports. The first address is the default|

These values are set outside of any class method, by convention they are placed right after the class declaration statement. 

Example:
```python
class QwiicScmd(object):
	"""
	QwiicScmd

		:param address: The I2C address to use for the device. 
						If not provided, the default address is used.
		:param i2c_driver: An existing i2c driver object. If not provided 
						a driver object is created. 
		:return: The Serial Control Motor Driver device object.
		:rtype: Object
	"""
	device_name = "Qwiic Serial Control Motor Driver"
	
        # note, the first address is the default I2C address.
	available_addresses = [0x58, 0x59, 0x5A, 0x5C]
```
#### The Constructor 
The Qwiic package expects the constructor of the class to implement the following signature:
```
def __init__(self, address=None, i2c_driver=None):
```
The method supports the following parameters:

|Parameter | Description |
|----|----|
|address| The I2C address to use for the device. If not provided, the default address is used|
|i2c_driver| An existing Qwiic I2C device object. If not provided, the class should create an instance of driver|

The initial body of the constructor handles these parameters - setting the I2C address and constructing a I2C driver if needed. The following object constructor provides a *boilerplate* implementation for this functionality. 

```python
def __init__(self, address=None, i2c_driver=None):


		# Did the user specify an I2C address?
		self.address = address if address != None else self.available_addresses[0]

		# load the I2C driver if one isn't provided

		if i2c_driver == None:
			self._i2c = qwiic_i2c.getI2CDriver()
			if self._i2c == None:
				print("Unable to load I2C driver for this platform.")
				return
		else:
			self._i2c = i2c_driver
```
Note - the docstring for the constructor is actually the docstring for the class.

### Interface Conventions
While not strictly required, the following conventions and patterns are used for qwiic driver implementations

#### Device Constants as Class Attributes
A standard methodology for I2C device implementations is to define constants (#defines in C/C++) for I2C interaction values for a device. For Qwiic python modules these values are defined as capitalized attributes and either placed as file attributes or class attributes on the driver class. 

The convention is to implement any attributes required for user interaction as class attributes. Any internal values are created as file/modules attributes. 

#### is_connected() Method
Each class implements an ```is_connected()``` method that returns True the specific Qwiic device is connect to the system. 

This is a standard method, that often uses the following implementation pattern.
```python
def is_connected(self):
		""" 
			Determine if a SCMD device is connected to the system.

			:return: True if the device is connected, otherwise False.
			:rtype: bool

		"""
		return qwiic_i2c.isDeviceConnected(self.address)
	
# expose as a property
connected = property(is_connected)
```

Additionally, the method is exposed as a read-only attribute on the object. 

#### A begin() Method
Following the pattern set by the Qwiic Arduino libraries, a begin() method is used to perform the actual initialization of the underlying I2C device. 

While each device implements device specific initialization logic, the signature of this method is as follows:
```python
def begin(self):
		""" 
			Initialize the operation of the SCMD module

			:return: Returns true of the initialization was successful, otherwise False.
			:rtype: bool

		"""
```


Implementation Structure
-------------------------
There are two patterns of implementation for a package - a python module or a python package. 

To the end-user a package or module looks the same, but the implementation within the repository is different. 

### Module
A python module is nothing more than a single file that makes up the overall implementaiton for the package. 
This file has the same name as the package being imported by the user. 

For example, if a user imports a module named qwiic_module
```python
import qwiic_module
```
The file name would be ```qwiic_module.py``` and reside in the root of the repository.
```
Qwiic_Module_Py/
   +--- qwiic_module.py
```

### Package
A python package is a folder that contains the implementation of the package. The folder can contain python source files, as well as any other resource needed for the property operation of the package.

The package directory is name is the name of the package. A file named ```__init__.py``` in the root directory of the package defines its entry/operation and lets python know that the directory implements a package.

For example, if the user imports a package named qwiic_package
```python
import qwiic_package
```

The structure of this implementation would be under a directory called ```qwiic_package``` in the repository

```
Qwiic_Package_Py
   +--- qwiic_package/
           +--- __init__.py       - the entry point for the package implementation
           |
           +---  ... Any other file, directory or resource that makes up the package
```

Note: The souce of the implementation must be contain the [license attribution statement](#source-code-license-attribution).

The LICENSE File
----------------
The file named [LICENSE](https://github.com/sparkfun/Qwiic_Template_Py/blob/master/LICENSE) contains the license for the repository. The name of the file, LICENSE, is used by other systems to identify which license the repository implements.

For example, in GitHub, when the contents of the file is viewed, the system will display details about the license and clearly indicate to the user what the license covers. 

The SparkFun Qwiic python module implementations fall under the MIT license. 

### Source Code License Attribution
Each source file distributed with one of our python packags/modules must include the proper license attribution in the entry comment section of the code. 

The Qwiic Python packages are licensed using the MIT license and as such should include the following statement in the top/entry section of the code:
```python
#==================================================================================
# Copyright (c) 2019 SparkFun Electronics
#
# Permission is hereby granted, free of charge, to any person obtaining a copy 
# of this software and associated documentation files (the "Software"), to deal 
# in the Software without restriction, including without limitation the rights 
# to use, copy, modify, merge, publish, distribute, sublicense, and/or sell 
# copies of the Software, and to permit persons to whom the Software is 
# furnished to do so, subject to the following conditions:
#
# The above copyright notice and this permission notice shall be included in all 
# copies or substantial portions of the Software.
#
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR 
# IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY, 
# FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE 
# AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER 
# LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM, 
# OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE 
# SOFTWARE.
#==================================================================================
```

Installer/Package Creation
--------------------------
The Qwiic Python components are packaged using standard python package/install tools, and hosted within the Python Package Index (pypy.org).

Within the repository, the files that makeup the package are the following:
```
Qwiic_Example_Py
   + DESCRIPTION.rst          - A high level description of the package
   |
   + setup.cfg                - Specific options/settings for the package tools 
   |
   + setup.py                 - A python script that defines and builds the installer package

```

#### DESCRIPTION.rst
The file [DESCRIPTION.rst](https://github.com/sparkfun/Qwiic_Template_Py/blob/master/DESCRIPTION.rst) is a RST ([reStructured Text](https://gist.github.com/dupuy/1855764)) file that has a simple, high-level description of the package. When setup.py is executed, it reads the contents of this file and sets it as the description of the package. _(\***Note:** The title should read **Qwiic** <Package Name> and the number of `=` must be greater than the character length of the title.)_

```
Qwiic <Example Package Title>
=============================================
```

#### setup.cfg
The file [setup.cfg](https://github.com/sparkfun/Qwiic_Template_Py/blob/master/setup.cfg) contains options that the packaging tools use when creating the specific package. For the most part, the file in this template repo can be used. 

### setup.py
The file ```setup.py``` is a python script that is used to describe the package and build an install package. The file is used by the python package ```setuptools```, which is a collection of utilities that make it simple to build and distribute Python distributions. 

This template repository contains an example ```setup.py``` file for review and an overview of the file contents are below. For details on the structure of the file, please review the [setup.py section](https://packaging.python.org/tutorials/packaging-projects/#creating-setup-py) in the Packaging Python Projects document. 

___Description Section___

One of the first sections in ```setup.py``` is reading in the contents of *DESCRIPTION.rst*. 
```python
import io

here = path.abspath(path.dirname(__file__))

# get the log description
with io.open(path.join(here, "DESCRIPTION.rst"), encoding="utf-8") as f:
    long_description = f.read()
```
This reads the contents of the description fine and places the resulting string into the variable ```long_description```. This variable is passed into the call to ```setup()``` using the *```long_description```* keyword parameter.

Note: The ```io.open``` method is used to support *uft-8* file encoding in Python versions 2.7 and 3.*. 

___setuptools.setup( name=)___

This keyword is set to the name to publish the package under in PyPi.org and the name passed to the ```pip``` command for installing the package. _(\***Note:** The package name should be in the form of `sparkfun_qwiic_<package_name>`.)_

The following command shows this value for the qwiic bme280:
```python
setuptools.setup(
    # ...
    name='sparkfun_qwiic_bme280',
    # ...
   )
```

**NOTE:** For PyPi/Pip, underscores ```_``` and dashes ```-``` are interchangeable. 

___setuptools.setup( version=)___

This controls the package's release version on PyPI. _(\***Note:** Start off with the lowest release value until the package is finalized; then, the version can get "bumped up" to `1.0.0`. When uploading a package to PyPI, the version number needs to be "bumped up" for any package changes to take into effect.)_

```python
setuptools.setup(
   # ...
   # Versions should comply with PEP440.  For a discussion on single-sourcing
   # the version across setup.py and the project code, see
   # http://packaging.python.org/en/latest/tutorial.html#version
   version='0.0.1',
   #...
```

___setuptools.setup( description= and url=)___

Modify the description with the package's name and include the url for the associated product page.

```python
setuptools.setup(
   # ...
    description='SparkFun Electronics qwiic <package_name> package',
    long_description=long_description,

    # The project's main homepage.
    url='https://www.sparkfun.com/products/<Product Number>',
   #...
```

___setuptools.setup( install_requires=)___

The *```install_requires```* keyword arguement to ```setuptools.setup()``` is used to specify what other python packages this package depends on. 

An example of this is the ```sparkfun-qwiic-i2c``` package, which all Qwiic board python packages use. An example of this from the Qwiic Proximity package ```setup()``` is as follows:
```python
setuptools.setup(
    # ...
     
    install_requires=['sparkfun_qwiic_i2c'],

		# ...
   )
```

For the overall Qwiic package, which depends on all driver packages, this parameter has the following form:
```python
setuptools.setup(
    # ...
   setup_requires = ['sparkfun-qwiic-i2c']

   # Use the dir names of the submodules in the ./qwiic/drives directory
   sub_mods = os.listdir(here+os.sep+'qwiic/drivers')
   for daDriver in sub_mods:
      setup_requires.append('sparkfun-%s' % (daDriver.replace('_','-')))

    # ...
   )
```

___setuptools.setup(classifiers=[])___

The classifiers argument to ```setup()``` are attrbitues that describe the package and are used details specifics to the PyPi respository and users of the project. While a [detailed list of of valid classifier values](https://pypi.org/pypi?%3Aaction=list_classifiers) is available at pypy.org, the key values are the project maturity (is it Alpha, Beta, Production?) and what python versions are supported. 

The example script has the following classifiers:
```python
setuptools.setup(
    # ...
    # See https://pypi.python.org/pypi?%3Aaction=list_classifiers
    classifiers=[
        # How mature is this project? Common values are
        #   3 - Alpha
        #   4 - Beta
        #   5 - Production/Stable
        'Development Status :: 5 - Production/Stable',

        # Indicate who your project is intended for
        'Intended Audience :: Developers',
        'Topic :: Software Development :: Build Tools',

        # Pick your license as you wish (should match "license" above)
        'License :: OSI Approved :: MIT License',

        # Specify the Python versions you support here. In particular, ensure
        # that you indicate whether you support Python 2, Python 3 or both. 
        'Programming Language :: Python :: 2.7',
        'Programming Language :: Python :: 3.5',
        'Programming Language :: Python :: 3.6',
        'Programming Language :: Python :: 3.7',
   
    ],
    # ...
   )
```

You can see these detailed out on the SparkFun Qwiic package (sparkfun-qwiic) on the [PyPi.org repository.](https://pypi.org/project/sparkfun-qwiic/)

___setuptools.setup(packages=[])___

If your repository defines one or more packages (directories), the names of these packages are provided to the ```packages``` keyboard argument to setuptools. Note: this is the directory/package name the user references in python code, not the package name used by PyPi - which can also contain additional keywords. 

For the Qwiic package, this is just the Qwiic directory:
```python
setuptools.setup(
     # ...
     
    packages=['qwiic'],

   # ...
   )
```
or for the qwiic_micro_oled package, which includes a font subpackage:
```python
setuptools.setup(
     # ...
     
    packages=["qwiic_micro_oled", "qwiic_micro_oled/fonts"],

   # ...
   )
```
___setuptools.setup(package_data={})___

The packaging system will include python files (```.py```) files by default. If the package includes non-python files, these are specified via the ```pacakge_data``` keyword argument, which takes a dictionary. 

The provided dictionary key values are a specific location, and the value is the data files to include in the package. The data filenames can be specific names, or include wildcards. 

An example of this is used in the qwiic_micro_oled package, which includes font data files, named using a ```.bin``` file extension. These data files are located in the ```./fonts``` subdirectory of the package repository.
```python
setuptools.setup(
     # ...
     package_data={
         "qwiic_micro_oled/fonts" : ['*.bin']
    },

   # ...
   )
```
___setuptools.setup(py_modules=[])___

If the install package implements a module (source file) and not a python package (directory), the modules are specific to the ```setup()``` method call using the ```py_modules=[]``` keyword argument. The value of this keyword is an array that contains the names of the modules to include in the package. Note, the file suffix is not included in the provided names.  _(\***Note:** The module name should be in the form of `"qwiic_<package_name>"`.)_

For the Qwiic BME280 package, which is implemented in a single file, the module is specified as follows:
```python
setuptools.setup(
   # ...
    py_modules=["qwiic_bme280"],
   # ...
   )
```

Building and Uploading the Package
----------------------------------

When ready to build and upload a package to pypi.org, the following setups are performed.

#### Get an Account on PyPi.org
You'll need an account on PyPi.org - it's a simple sign up procedure.

To publish a new package, you can use this account. If you are updating or modifying an existing package, you'll need to be added as a *Maintainer* of the package by the package owner.

#### Build the Package distributions

To build and upload the packages, make sure the required python packages are installed - **setuptools**, **twine**, and **wheel**. 
```sh
sudo pip install setuptools twine wheel
```

Build the distribution packages using the following commands (executing in the package root directory). First create a standard distribution:
```sh
python setup.py sdist 
```
Then a distribution in the ```wheel``` format.
```sh
python setup.py bdist_wheel --universal
```
These commands will create distribution package files and place them in the ```./dist``` subdirectory. 

### Upload the Package to PyPi.org

The ```twine``` command is used to upload the install packages to pypi.org. To upload the packages, use the following command:

```sh
twine upload dist/*
```
This command will prompt for the *username* and *password* for the pypi account to use for the upload.

Once the upload is completed, the packages are now available for use via the pip installer. 

NOTE: Your PyPi.org username and password can be specified in the file ```~/.pypirc``` instead of entering with each call to twine. The format of this file:

```ini
[pypi]
username = <the username>
password = <the password>
```
Documentation Generation - ReadTheDocs.org
------------------------------------------

Details of the documentation generation process are contained in the file [DOCUMENTATION.md](DOCUMENTATION.md)

Adding the Module dependency  to the main Qwiic package, Qwiic_Py
------------------------------------------------------------------

Adding the Module dependency  to the main Qwiic package, Qwiic_Py 

The overall Qwiic package, which is hosted in the Qwiic_Py repository, defines dependencies to all the SparkFun  Qwiic python packages. This is accomplished by adding modules to the repo as git submodules. 

New drivers are added as git submodules in the Qwiic_Py/qwiic/drivers directory. 

Naming of the driver directory is important – it should map to the package name in PyPi, minus the initial ‘sparkfun-‘ name. 

So for the BME280 package, which is defined in PyPi as ‘sparkfun-qwiic-bme280’, would be placed in a directory named ‘qwiic_bme280’ in the drivers folder. 

To add a driver/package to the Qwiic repository, do the following steps:
* Clone the Qwiic repository 
```git clone git@github.com:sparkfun/Qwiic_Py.git```
* Move to the drivers directory
```cd Qwiic_Py/qwiic/drivers```
* Add the submodule, using the following command
``` git submodule add <repo to add> <name of driver folder>```

Example for the Titan GPS driver
``` git submodule add git@github.com:sparkfun/Qwiic_Titan_Gps_Py.git qwiic_titan_gps ```

_Note, if you get a failure due to permissions, you may need to use the complete URL for the \<repo to add\>. (\***Note:** Don't forget to include the submodule name (`qwiic_<package_name>`) after the link for the repo.)_

Example for the Titan GPS driver (with full URL)
``` git submodule add https://github.com/sparkfun/Qwiic_Titan_Gps_Py qwiic_titan_gps ```


* Add this new folder to the repo, commit it and push to GitHub 

Once completed, the Qwiic_Py package must be updated and uploaded to PyPi. 

* Bump up the version in the setup.py file. This step defines package dependencies for everything contained in the drivers subfolder, including the newly added submodule. 
* Follow the above package build and upload steps

Once completed, an update/install of the sparkfun-qwiic package will include the new submodule
