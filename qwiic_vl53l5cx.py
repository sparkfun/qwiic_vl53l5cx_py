#-------------------------------------------------------------------------------
# qwiic_vl53l5cx.py
#
# Python library for the SparkFun Qwiic , available here:
# https://www.sparkfun.com/products/18642
# 
# Many functions are a direct Python port of the underlying API functions from the vl53l5cx_api.cpp library:
# https://github.com/sparkfun/SparkFun_VL53L5CX_Arduino_Library/blob/main/src/vl53l5cx_api.cpp
#-------------------------------------------------------------------------------
# Written by SparkFun Electronics, November 2024
#
# This python library supports the SparkFun Electroncis Qwiic ecosystem
#
# More information on Qwiic is at https://www.sparkfun.com/qwiic
#
# Do you like this library? Help support SparkFun. Buy a board!
#===============================================================================
# Copyright (c) 2024 SparkFun Electronics
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
#===============================================================================

"""
qwiic_vl53l5cx
============
Python module for the [SparkFun Qwiic ToF Imager - VL53L5CX](https://www.sparkfun.com/products/18642)
This is a port of the existing [Arduino Library](https://github.com/sparkfun/SparkFun_VL53L5CX_Arduino_Library)
This package can be used with the overall [SparkFun Qwiic Python Package](https://github.com/sparkfun/Qwiic_Py)
New to Qwiic? Take a look at the entire [SparkFun Qwiic ecosystem](https://www.sparkfun.com/qwiic).
"""

# The Qwiic_I2C_Py platform driver is designed to work on almost any Python
# platform, check it out here: https://github.com/sparkfun/Qwiic_I2C_Py
import qwiic_i2c
import time
import os

# Define the device name and I2C addresses. These are set in the class defintion
# as class variables, making them avilable without having to create a class
# instance. This allows higher level logic to rapidly create a index of Qwiic
# devices at runtine
_DEFAULT_NAME = "Qwiic VL53L5CX"

# Some devices have multiple available addresses - this is a list of these
# addresses. NOTE: The first address in this list is considered the default I2C
# address for the device.
_AVAILABLE_I2C_ADDRESS = [0x52]
_AVAILABLE_I2C_ADDRESS.extend(range(0x08, 0x78))  # Add all possible addresses, 0x08 <= address <= 0x77

# Expected versioning information
_REVISION_ID = 0x02
_DEVICE_ID = 0xF0

# This class contains the results from a ranging operation
class RangingDataResults(object):
    """
    Class RangingDataResults contains the ranging results of VL53L5CX. 
    If user wants more than 1 target per zone, the results can be split into 2 sub-groups:
    - Per zone results. These results are common to all targets (ambient_per_spad, nb_target_detected, and nb_spads_enabled).
    - Per target results: These results are different relative to the detected target (signal_per_spad, range_sigma_mm, distance_mm, reflectance, target_status).
    """
    # TODO: these constants are also contained in the main class below, might be better to
    # abandon this class completely and just pull all the variables into the main class
    kResolution8x8 = 64
    kNbTartgetPerZone = 1

    def __init__(self):
        self.ambient_per_spad = [0] * 64
        self.ambient_per_spad = [0] * self.kResolution8x8
        self.nb_target_detected = [0] * self.kResolution8x8  # Number of valid target detected for 1 zone
        self.nb_spads_enabled = [0] * self.kResolution8x8  # Number of spads enabled for this ranging
        self.signal_per_spad = [0] * (self.kResolution8x8 * self.kNbTartgetPerZone)  # Signal returned to the sensor in kcps/spads
        self.range_sigma_mm = [0] * (self.kResolution8x8 * self.kNbTartgetPerZone)  # Sigma of the current distance in mm
        self.distance_mm = [0] * (self.kResolution8x8 * self.kNbTartgetPerZone)  # Measured distance in mm
        self.reflectance = [0] * (self.kResolution8x8 * self.kNbTartgetPerZone)  # Estimated reflectance in percent
        self.target_status = [0] * (self.kResolution8x8 * self.kNbTartgetPerZone)  # Status indicating the measurement validity (5 & 9 means ranging OK)

        # Motion Indicator Vars
        self.global_indicator_1 = 0
        self.global_indicator_2 = 0
        self.status = 0
        self.nb_of_detected_aggregates = 0
        self.nb_of_aggregates = 0
        self.spare = 0
        self.motion = [0] * 32


# Define the class that encapsulates the device being created. All information
# associated with this device is encapsulated by this class. The device class
# should be the only value exported from this module.
class QwiicVL53L5CX(object): 
    # Set default name and I2C address(es)
    device_name         = _DEFAULT_NAME
    available_addresses = _AVAILABLE_I2C_ADDRESS

    # VL53L5CX API Status defines
    kStatusOK = 0
    kMCUError = 1
    kStatusInvalidParam = 127
    kStatusError = 255

    kResolution4x4 = 16
    kResolution8x8 = 64

    kOffsetDataSize = 488
    kXTalkDataSize = 776
    kTempBufferSize = 1440

    kUiCmdStatus = 0x2C00
    kUiCmdStart = 0x2C04
    kUiCmdEnd = 0x2FFF

    kDciFreqHz = 0x5458

    kDciDssConfig = 0xAD38
    kDciZoneConfig = 0x5450


    kDciRangingMode = 0xAD30
    kRangingModeContinous = 1
    kRangingModeAutonomous = 3
    kDciSingleRange = 0xCD5C


    # Masks and shifts for the Block_header union
    kBlockHeaderTypeShift = 0
    kBlockHeaderTypeMask = 0x0F << kBlockHeaderTypeShift
    kBlockHeaderSizeShift = 4
    kBlockHeaderSizeMask = 0xFFF << kBlockHeaderSizeShift
    kBlockHeaderIdxShift = 16
    kBlockHeaderIdxMask = 0xFFFF << kBlockHeaderIdxShift

    # Definitions for Range results block headers
    kStartBh = 0x0000000D
    kMetadataBh = 0x54B400C0
    kCommonDataBh = 0x54C00040
    kAmbientRateBh = 0x54D00104
    kSpadCountBh = 0x55D00404
    kNbTargetDetectedBh = 0xCF7C0401
    kSignalRateBh = 0xCFBC0404
    kRangeSigmaMmBh = 0xD2BC0402
    kDistanceBh = 0xD33C0402
    kReflectanceBh = 0xD43C0401
    kTargetStatusBh = 0xD47C0401
    kMotionDetectBh = 0xCC5008C0

    kNbTargetPerZone = 1

    kDciOutputConfig = 0xCD60
    kDciOutputEnables = 0xCD68
    kDciOutputList = 0xCD78

    kMetadataIdx = 0x54B4
    kSpadCountIdx = 0x55D0
    kAmbientRateIdx = 0x54D0
    kNbTargetDetectedIdx = 0xCF7C
    kSignalRateIdx = 0xCFBC
    kRangeSigmaMmIdx = 0xD2BC
    kDistanceIdx = 0xD33C
    kReflectanceEstPcIdx = 0xD43C
    kTargetStatusIdx = 0xD47C
    kMotionDetectIdx = 0xCC50

    kPowerModeSleep = 0
    kPowerModeWakeup = 1

    kDciIntegrationTime = 0x545C
    kDciSharpenerPercent = 0xAED8
    kDciTargetOrder = 0xAE64

    kTargetOrderClosest = 1
    kTargetOrderStrongest = 2

    kNvmDataSize = 492
    kConfigurationSize = 972
    kOffsetBufferSize = 488
    kXTalkBufferSize = 776

    def __init__(self, address=None, i2c_driver=None, dataPath = "vl53l5cx_bin"):
        """
        Constructor

        :param address: The I2C address to use for the device
            If not provided, the default address is used
        :type address: int, optional
        :param i2c_driver: An existing i2c driver object
            If not provided, a driver object is created
        :type i2c_driver: I2CDriver, optional
        :param dataPath: The path to the data directory. Can be relative to this module script or absolute.
        :type dataPath: str
        """

        # Use address if provided, otherwise pick the default
        if address in self.available_addresses:
            self.address = address
        else:
            self.address = self.available_addresses[0]

        # Load the I2C driver if one isn't provided
        if i2c_driver is None:
            self._i2c = qwiic_i2c.getI2CDriver()
            if self._i2c is None:
                print("Unable to load I2C driver for this platform.")
                return
        else:
            self._i2c = i2c_driver

        if os.path.isdir(dataPath):
            self._dataPath = dataPath # User already supplied absolute path
        else:
            scriptDir = os.path.dirname(os.path.abspath(__file__))
            self._dataPath = os.path.join(scriptDir, dataPath) # User supplied relative path

        # Lists from the cpp lib
        self.offset_data = [0] * self.kOffsetDataSize
        self.xtalk_data = [0] * self.kXTalkDataSize
        self.temp_buffer = [0] * self.kTempBufferSize

        self.data_read_size = 0
        self.stream_count = 0


    def is_connected(self):
        """
        Determines if this device is connected

        :return: `True` if connected, otherwise `False`
        :rtype: bool
        """
        if  not self._i2c.isDeviceConnected(self.address):
            return False
        
        return True

    connected = property(is_connected)

    def check_data_directory(self):
        """
        Checks if the data directory exists and contains the necessary files

        :return: `True` if the data directory exists and contains the necessary files, otherwise `False`
        :rtype: bool
        """
        if not os.path.isdir(self._dataPath):
            return False

        for file in ['firmware.bin', 
                     'default_configuration.bin', 
                     'default_xtalk.bin', 
                     'get_nvm_cmd.bin']:
            if not os.path.isfile(os.path.join(self._dataPath, file)):
                return False

    def begin(self):
        """
        Initializes this device with default parameters

        :return: Returns `True` if successful, otherwise `False`
        :rtype: bool
        """
        # Confirm device is connected before doing anything
        if not self.is_connected():
            return False

        if not self.is_alive():
            return False
        
        # Verify that the data folder exists and contains necessary binaries
        if not self.check_data_directory():
            return False
        
        # Contents of the "vl53l5cx_init" function in the cpp lib
        pipe_ctrl = [self.kNbTargetPerZone, 0x00, 0x01, 0x00]
        single_range = 0x01

        # Sw reboot sequence
        self._i2c.wr_byte(self.address, 0x7fff, 0x00)
        self._i2c.wr_byte(self.address, 0x0009, 0x04)
        self._i2c.wr_byte(self.address, 0x000F, 0x40)
        self._i2c.wr_byte(self.address, 0x000A, 0x03)
        tmp = self._i2c.rd_byte(self.address, 0x7FFF)
        self._i2c.wr_byte(self.address, 0x000C, 0x01)
        self._i2c.wr_byte(self.address, 0x0101, 0x00)
        self._i2c.wr_byte(self.address, 0x0102, 0x00)
        self._i2c.wr_byte(self.address, 0x010A, 0x01)
        self._i2c.wr_byte(self.address, 0x4002, 0x01)
        self._i2c.wr_byte(self.address, 0x4002, 0x00)
        self._i2c.wr_byte(self.address, 0x010A, 0x03)
        self._i2c.wr_byte(self.address, 0x0103, 0x01)
        self._i2c.wr_byte(self.address, 0x000C, 0x00)
        self._i2c.wr_byte(self.address, 0x000F, 0x43)
        time.sleep(0.001)

        self._i2c.wr_byte(self.address, 0x000F, 0x40)
        self._i2c.wr_byte(self.address, 0x000A, 0x01)
        time.sleep(0.100)
        
        status = self.kStatusOK

        # Wait for sensor booted (several ms required to get sensor ready)
        self._i2c.wr_byte(self.address, 0x7FFF, 0x00)
        status |= self.poll_for_answer(1, 0, 0x06, 0xff, 1)

        self._i2c.wr_byte(self.address, 0x000E, 0x01)
        self._i2c.wr_byte(self.address, 0x7fff, 0x02)

        # Enable Fw access
        self._i2c.wr_byte(self.address, 0x03, 0x0D)
        self._i2c.wr_byte(self.address, 0x7fff, 0x01)
        status |= self.poll_for_answer(1, 0, 0x21, 0x10, 0x10)
        self._i2c.wr_byte(self.address, 0x7fff, 0x00)

        # Enable host access to GO1
        self._i2c.wr_byte(self.address, 0x0C, 0x01)

        # Power ON status
        self._i2c.wr_byte(self.address, 0x7fff, 0x00)
        self._i2c.wr_byte(self.address, 0x101, 0x00)
        self._i2c.wr_byte(self.address, 0x102, 0x00)
        self._i2c.wr_byte(self.address, 0x010A, 0x01)
        self._i2c.wr_byte(self.address, 0x4002, 0x01)
        self._i2c.wr_byte(self.address, 0x4002, 0x00)
        self._i2c.wr_byte(self.address, 0x010A, 0x03)
        self._i2c.wr_byte(self.address, 0x103, 0x01)
        self._i2c.wr_byte(self.address, 0x400F, 0x00)
        self._i2c.wr_byte(self.address, 0x21A, 0x43)
        self._i2c.wr_byte(self.address, 0x21A, 0x03)
        self._i2c.wr_byte(self.address, 0x21A, 0x01)
        self._i2c.wr_byte(self.address, 0x21A, 0x00)
        self._i2c.wr_byte(self.address, 0x219, 0x00)
        self._i2c.wr_byte(self.address, 0x21B, 0x00)

        # Wake up MCU
        self._i2c.wr_byte(self.address, 0x7fff, 0x00)
        self._i2c.wr_byte(self.address, 0x000C, 0x00)
        self._i2c.wr_byte(self.address, 0x7fff, 0x01)
        self._i2c.wr_byte(self.address, 0x0020, 0x07)
        self._i2c.wr_byte(self.address, 0x0020, 0x06)

        # Download FW into VL53L5
        self._i2c.wr_byte(self.address, 0x7fff, 0x09)
        self._i2c.wr_multi(self.address, 0, self.get_buffer_from_file('firmware.bin', 0, 0x8000))
        self._i2c.wr_byte(self.address, 0x7fff, 0x0a)
        self._i2c.wr_multi(self.address, 0, self.get_buffer_from_file('firmware.bin', 0x8000, 0x10000))
        self._i2c.wr_byte(self.address, 0x7fff, 0x0b)
        self._i2c.wr_multi(self.address, 0, self.get_buffer_from_file('firmware.bin', 0x10000, 0x15000))
        self._i2c.wr_byte(self.address, 0x7fff, 0x01)

        # Check if FW correctly downloaded
        self._i2c.wr_byte(self.address, 0x7fff, 0x02)
        self._i2c.wr_byte(self.address, 0x03, 0x0D)
        self._i2c.wr_byte(self.address, 0x7fff, 0x01)
        status |= self.poll_for_answer(1, 0, 0x21, 0x10, 0x10)
        self._i2c.wr_byte(self.address, 0x7fff, 0x00)
        self._i2c.wr_byte(self.address, 0x0C, 0x01)

        # Reset MCU and wait boot
        self._i2c.wr_byte(self.address, 0x7FFF, 0x00)
        self._i2c.wr_byte(self.address, 0x114, 0x00)
        self._i2c.wr_byte(self.address, 0x115, 0x00)
        self._i2c.wr_byte(self.address, 0x116, 0x42)
        self._i2c.wr_byte(self.address, 0x117, 0x00)
        self._i2c.wr_byte(self.address, 0x0B, 0x00)
        self._i2c.wr_byte(self.address, 0x0C, 0x00)
        self._i2c.wr_byte(self.address, 0x0B, 0x01)
        # TODO: might have to put a sleep here, previous libs have been upset when polling while coming out of boot
        status |= self.poll_for_answer(1, 0, 0x06, 0xff, 0x00)
        self._i2c.wr_byte(self.address, 0x7fff, 0x02)

        # Get offset NVM data and store them into the offset buffer
        self._i2c.wr_multi(self.address, 0x2fd8, self.get_buffer_from_file('get_nvm_cmd.bin'))
        status |= self.poll_for_answer(4, 0, self.kUiCmdStatus, 0xff, 0x02)

        self.temp_buffer[:self.kNvmDataSize] = self._i2c.rd_multi(self.address, self.kUiCmdStart, self.kNvmDataSize)
        self.offset_data[:self.kOffsetBufferSize] = self.temp_buffer[:self.kOffsetBufferSize]

        self.send_offset_data(self.kResolution4x4)

        # Set default Xtalk shape. Send Xtalk to sensor
        self.xtalk_data = self.get_buffer_from_file('default_xtalk.bin')[:self.kXTalkBufferSize]

        status |= self.send_xtalk_data(self.kResolution4x4)

        # Send default configuration to VL53L5CX firmware
        self._i2c.wr_multi(self.address, 0x2c34, self.get_buffer_from_file('default_configuration.bin'))

        status |= self.poll_for_answer(4, 1, self.kUiCmdStatus, 0xff, 0x03)

        status |= self.dci_write_data(pipe_ctrl, self.kDciPipeControl, len(pipe_ctrl))
        
        status |= self.dci_write_data(self.uint32_list_to_byte_list([single_range]), self.kDciSingleRange, 4)
        
        return (status == self.kStatusOK)
    

    def swap_buffer(self, buffer, size):
        """
        Used to swap a buffer. The buffer size is always a multiple of 4 (4, 8, 12, 16, ...).
        :param buffer: The byte buffer to swap
        :type buffer: list
        :param size: Buffer size to swap
        :type size: int
        """
        for i in range (0, size, 4):
            buffer[i], buffer[i+1], buffer[i+2], buffer[i+3] = buffer[i+3], buffer[i+2], buffer[i+1], buffer[i]


    def poll_for_answer(self, size, pos, addr, mask, expected_value):
        """
        This function is used to wait for an answer from the VL53L5CX sensor.
        :param size: The number of bytes to read
        :type size: int
        :param pos: The position in the buffer to check against expected_value
        :type pos: int
        :param address: The address to read from
        :type address: int
        :param mask: The mask to apply to the value read (at pos) before comparing to expected_value
        :type mask: int
        :param expected_value: The value to compare against the value read (at pos)
        :type expected_value: int
        :return: kStatusOk on success, other on failure
        :rtype: int
        """
        status = self.kStatusOK
        timeout = 0

        while True: # Equivalent of the do-while loop in the cpp lib
            data = self._i2c.rd_multi(self.address, addr, size)

            self.temp_buffer[:size] = data

            time.sleep(0.010)
            if timeout > 200: # 2s timeout
                status |= self.temp_buffer[2]
                return status # TODO: cpp lib doesn't have this, but probably should so that we break out on timeout
            else:
                if (size >= 4) and (self.temp_buffer[2] >= 0x7F):
                    status |= self.kMCUError
                else:
                    timeout += 1

            if self.temp_buffer[pos] & mask == expected_value:
                break
        
        return status

    def send_offset_data(self, resolution):
        """
        This function is used to set the offset data gathered from NVM.

        :param resolution: The resolution of the sensor 
        :type resolution: int
            Allowable values for resolution:
            - kResolution4x4
            - kResolution8x8
        :return: kStatusOk on success, other on failure
        """
        status = self.kStatusOK

        signal_grid = [0] * 64
        range_grid = [0] * 64

        dds_4x4 = [0x0F, 0x04, 0x04, 0x00, 0x08, 0x10, 0x10, 0x07]
        footer = [0x00, 0x00, 0x00, 0x0F, 0x03, 0x01, 0x01, 0xE4]

        self.temp_buffer[:len(self.offset_data)] = self.offset_data

        # Data extrapolation is required for 4X4 offset
        if resolution == self.kResolution4x4:
            self.temp_buffer[0x10:0x10+8] = dds_4x4
            self.swap_buffer(self.temp_buffer, self.kOffsetDataSize)
            signal_grid = self.temp_buffer[0x3C:0x3C+64]
            range_grid = self.temp_buffer[0x140:0x140+64]

            for j in range(4):
                for i in range(4):
                    signal_grid[i + (4 * j)] = (
                        signal_grid[(2 * i) + (16 * j) + 0] +
                        signal_grid[(2 * i) + (16 * j) + 1] +
                        signal_grid[(2 * i) + (16 * j) + 8] +
                        signal_grid[(2 * i) + (16 * j) + 9]
                    ) // 4
                    range_grid[i + (4 * j)] = (
                        range_grid[(2 * i) + (16 * j) + 0] +
                        range_grid[(2 * i) + (16 * j) + 1] +
                        range_grid[(2 * i) + (16 * j) + 8] +
                        range_grid[(2 * i) + (16 * j) + 9]
                    ) // 4
            
            # TODO: The cpp lib was a bit odd here, it appeared to memset well past the end of the arrays. Not sure if that was intentional or necessary
            # It's possible these were located at known memory locations in the cpp lib and we wanted to zero out the stuff directly after them as well
            range_grid[0x10:] = 0
            signal_grid[0x10:] = 0
            self.temp_buffer[0x3C:0x3C+64] = signal_grid
            self.temp_buffer[0x140:0x140+64] = range_grid
            self.swap_buffer(self.temp_buffer, self.kOffsetDataSize)
        
        for i in range (self.kOffsetDataSize - 4):
            self.temp_buffer[i] = self.temp_buffer[i + 8]

        self.temp_buffer[0x1E0:0x1E0+8] = footer
        self._i2c.wr_multi(self.address, 0x2e18, self.temp_buffer, self.kOffsetDataSize)
        status |= self.poll_for_answer(4, 1, self.kUiCmdStatus, 0xff, 0x03)

        return status
    
    def send_xtalk_data(self, resolution):
        """
        This function is used to set the Xtalk data from generic configuration, or user's calibration.
        :param resolution: The resolution of the sensor
        :type resolution: int
            Allowable values for resolution:
            - kResolution4x4
            - kResolution8x8
        :return: kStatusOk on success, other on failure
        """
        status = self.kStatusOK

        res4x4 = [0x0F, 0x04, 0x04, 0x17, 0x08, 0x10, 0x10, 0x07]
        dss_4x4 = [0x00, 0x78, 0x00, 0x08, 0x00, 0x00, 0x00, 0x08]
        profile_4x4 = [0xA0, 0xFC, 0x01, 0x00]
        signal_grid = [0] * 64

        self.temp_buffer[:len(self.xtalk_data)] = self.xtalk_data
        
        # Data extrapolation is required for 4x4 Xtalk
        if resolution == self.kResolution4x4:
            self.temp_buffer[0x08:0x08+8] = res4x4
            self.temp_buffer[0x20:0x20+8] = dss_4x4
            self.swap_buffer(self.temp_buffer, self.kXTalkDataSize)

            signal_grid = self.temp_buffer[0x34:0x34+64]
            for j in range(4):
                for i in range(4):
                    signal_grid[i + (4 * j)] = (
                        signal_grid[(2 * i) + (16 * j) + 0] +
                        signal_grid[(2 * i) + (16 * j) + 1] +
                        signal_grid[(2 * i) + (16 * j) + 8] +
                        signal_grid[(2 * i) + (16 * j) + 9]
                    ) // 4
            
            # TODO: The cpp lib was a bit odd here, it appeared to memset well past the end of the arrays. Not sure if that was intentional or necessary
            # It's possible these were located at known memory locations in the cpp lib and we wanted to zero out the stuff directly after them as well
            signal_grid[0x10:] = 0
            self.temp_buffer[0x34:0x34+64] = signal_grid
            self.swap_buffer(self.temp_buffer, self.kXTalkDataSize)
            self.temp_buffer[0x134:0x134+4] = profile_4x4
            self.temp_buffer[0x078:0x078+4] = 0x00
            
            self._i2c.wr_multi(self.address, 0x2cf8, self.temp_buffer, self.kXTalkDataSize)
            status |= self.poll_for_answer(4, 1, self.kUiCmdStatus, 0xff, 0x03)

            return status

    def dci_write_data(self, data, index, data_size):
        """
            This function can be used to write 'extra data' to DCI. The data can
            be simple data, or casted structure.
            :param data : This field can be a casted structure, or a simple
            array. Please note that the FW only accept data of 32 bits. So field data can
            only have a size of 32, 64, 96, 128, bits ..
            :type data : list
            :param index : Index of required value.
            :type index : int
            :param data_size : This field must be the structure or array size
            :type data_size : int
            :return status : 0 if OK
            :rtype : int
        """
        status = self.kStatusOK
        headers = [0x00, 0x00, 0x00, 0x00]
        footer = [0x00, 0x00, 0x00, 0x0f, 0x05, 0x01,
                  (data_size + 8) >> 8,
                  (data_size + 8) & 0xFF]
        
        address = self.kUiCmdEnd - (data_size + 12) + 1
        # Check if cmd buffer is large enough
        if data_size + 12 > self.kTempBufferSize:
            status |= self.kStatusError
        else:
            headers[0] = index >> 8
            headers[1] = index & 0xff
            headers[2] = (data_size & 0xff0) >> 4
            headers[3] = (data_size & 0xf) << 4
        
            # Copy data from structure to FW format (+4 bytes to add header)
            self.swap_buffer(data, data_size)
            for i in range(data_size - 1, -1, -1):
                self.temp_buffer[i + 4] = data[i]
            
            # Add headers and footer
            self.temp_buffer[0:4] = headers
            self.temp_buffer[data_size + 4:data_size + 12] = footer

            # Send data to FW
            self._i2c.wr_multi(self.address, address, self.temp_buffer, data_size + 12)
            status |= self.poll_for_answer(4, 1, self.kUiCmdStatus, 0xff, 0x03)

            self.swap_buffer(data, data_size)
        
        return status
    
    def dci_read_data(self, data, index, data_size):
        """
            This function can be used to read 'extra data' from DCI. Using a known
            index, the function fills the casted structure passed in argument.
            :param data: This field can be a casted structure, or a simple
            array. Please note that the FW only accept data of 32 bits. So field data can
            only have a size of 32, 64, 96, 128, bits ....
            :type data: list
            :param index: Index of required value.
            :type index: int
            :param data_size: This field must be the structure or array size
            :type data_size: int
            :return: status: 0 if OK
            :rtype: int
        """

        status = self.kStatusOK
        rd_size = data_size + 12
        cmd = [0x00, 0x00, 0x00, 0x00,
               0x00, 0x00, 0x00, 0x0f,
               0x00, 0x02, 0x00, 0x08]

        # Check if tmp buffer is large enough
        if (data_size + 12) > self.kTempBufferSize:
            status |= self.kStatusError
        else:
            cmd[0] = index >> 8
            cmd[1] = index & 0xff
            cmd[2] = (data_size & 0xff0) >> 4
            cmd[3] = (data_size & 0xf) << 4

            # Request data reading from FW
            self._i2c.wr_multi(self.address, self.kUiCmdEnd - 11, cmd, 12)
            status |= self.poll_for_answer(4, 1, self.kUiCmdStatus, 0xff, 0x03)

            # Read new data sent (4 bytes header + data_size + 8 bytes footer)
            data = self._i2c.rd_multi(self.address, self.kUiCmdStart, rd_size)
            self.swap_buffer(self.temp_buffer, rd_size)

            for i in range(data_size):
                data[i] = self.temp_buffer[i + 4]
        
        return status
    
    def dci_replace_data(self, data, index, data_size, new_data, new_data_size, new_data_pos):
        """
            This function can be used to replace 'extra data' in DCI. The data can
            be simple data, or casted structure.
            
            :param data: This field can be a casted structure, or a simple array. 
                        Please note that the FW only accepts data of 32 bits. 
                        So field data can only have a size of 32, 64, 96, 128 bits, etc.
            :type data: list
            :param index: Index of required value.
            :type index: int
            :param data_size: This field must be the structure or array size.
            :type data_size: int
            :param new_data: Contains the new fields.
            :type new_data: list
            :param new_data_size: New data size.
            :type new_data_size: int
            :param new_data_pos: New data position into the buffer.
            :type new_data_pos: int
            :return: status: 0 if OK
            :rtype: int
        """
        status = self.kStatusOK
        status |= self.dci_read_data(data, index, data_size)
        data[new_data_pos:new_data_pos+new_data_size] = new_data
        status |= self.dci_write_data(data, index, data_size)

        return status

    def is_alive(self):
        """
        Check if the device is alive

        :return: True if the device is alive, otherwise False
        :rtype: bool
        """
        self._i2c.wr_byte(self.address, 0x7fff, 0x00)
        device_id = self._i2c.rd_byte(self.address, 0)
        revision_id = self._i2c.rd_byte(self.address, 1)  
        self._i2c.wr_byte(self.address, 0x7fff, 0x02)

        return (device_id == _DEVICE_ID) and (revision_id == _REVISION_ID)
        
    def set_i2c_address(self, i2c_address):
        """
        Set the I2C address of the device

        :param i2c_address: The new I2C address to use
        :type i2c_address: int

        :return: True if the address was set successfully, otherwise False
        :rtype: bool
        """
        if i2c_address not in self.available_addresses:
            return False

        self._i2c.wr_byte(self.address, 0x7fff, 0x00)
        self._i2c.wr_byte(self.address, 0x4, i2c_address)
        self.address = i2c_address
        self._i2c.wr_byte(self.address, 0x7fff, 0x02)
        return True
    
    def get_i2c_address(self):
        """
        Get the I2C address of the device

        :return: The current I2C address
        :rtype: int
        """
        return self.address
    
    def set_ranging_frequency_hz(self, frequency_hz):
        """
            This function sets a new ranging frequency in Hz. Ranging frequency
            corresponds to the measurements frequency. This setting depends on
            the resolution, so please select your resolution before using this function.

            :param frequency_hz: Contains the ranging frequency in Hz.
                - For 4x4, min and max allowed values are: [1;60]
                - For 8x8, min and max allowed values are: [1;15]
            :type frequency_hz: int
            :return: True on success and False on error.
        """

        status = self.kStatusOK
        status |= self.dci_replace_data(self.temp_buffer, self.kDciFreqHz, 4, [frequency_hz], 1, 0x01)

        return status == self.kStatusOK

    def get_ranging_frequency_hz(self):
        """
        This function gets the current ranging frequency in Hz. Ranging
        frequency corresponds to the time between each measurement.
        
        :return: The current ranging frequency in Hz.
        :rtype: int
        """
        status = self.dci_read_data(self.temp_buffer, self.kDciFreqHz, 4)
        return self.temp_buffer[0x01]
    
    def set_resolution(self, resolution):
        """
            This function sets a new resolution (4x4 or 8x8).
            
            :param resolution: Use kResolution4x4 or kResolution8x8 to set the resolution.
            :type resolution: int
            :return: status: 0 if set resolution is OK.
            :rtype: int
        """
        status = self.kStatusOK

        if resolution == self.kResolution4x4:
            status |= self.dci_read_data(self.temp_buffer, self.kDciDssConfig, 16)
            self.temp_buffer[0x04] = 64
            self.temp_buffer[0x06] = 64
            self.temp_buffer[0x09] = 4
            status |= self.dci_write_data(self.temp_buffer, self.kDciDssConfig, 16)

            status |= self.dci_read_data(self.temp_buffer, self.kDciZoneConfig, 8)
            self.temp_buffer[0x00] = 4
            self.temp_buffer[0x01] = 4
            self.temp_buffer[0x04] = 8
            self.temp_buffer[0x05] = 8
            status |= self.dci_write_data(self.temp_buffer, self.kDciZoneConfig, 8)

        elif resolution == self.kResolution8x8:
            status |= self.dci_read_data(self.temp_buffer, self.kDciDssConfig, 16)
            self.temp_buffer[0x04] = 16
            self.temp_buffer[0x06] = 16
            self.temp_buffer[0x09] = 1
            status |= self.dci_write_data(self.temp_buffer, self.kDciDssConfig, 16)

            status |= self.dci_read_data(self.temp_buffer, self.kDciZoneConfig, 8)
            self.temp_buffer[0x00] = 8
            self.temp_buffer[0x01] = 8
            self.temp_buffer[0x04] = 4
            self.temp_buffer[0x05] = 4
            status |= self.dci_write_data(self.temp_buffer, self.kDciZoneConfig, 8)

        else:
            status = self.kStatusInvalidParam

        status |= self.send_offset_data(resolution)
        status |= self.send_xtalk_data(resolution)

        return status

    def get_resolution(self):
        """
            This function gets the current resolution (4x4 or 8x8).
            
            :return: The current resolution. 16 for 4x4 mode, and 64 for 8x8 mode.
            :rtype: int
        """
        self.dci_read_data(self.temp_buffer, self.kDciZoneConfig, 8)
        return self.temp_buffer[0x00] * self.temp_buffer[0x01]
    
    # TODO: might have to swap endianness of the bytes in the following functions
    # Can print from the arduino lib to see the order of the bytes and make sure we're aligned with that here
    def uint32_list_to_byte_list(self, uint32_list):
        """
            This function converts a list of uint32 values to a list of bytes.
            :param uint32_list: The list of uint32 values to convert.
            :type uint32_list: list
            :return: The list of bytes.
        """
        byte_list = []
        for i in range(len(uint32_list)):

            byte_list.append(uint32_list[i] >> 24)
            byte_list.append((uint32_list[i] >> 16) & 0xFF)
            byte_list.append((uint32_list[i] >> 8) & 0xFF)
            byte_list.append(uint32_list[i] & 0xFF)
        
        return byte_list
    
    def byte_list_to_uint32(self, byte_list):
        """
            This function converts a list of bytes to a single uint32 value

            :param byte_list: The list of bytes to convert.
            :type byte_list: list

            :return: The uint32 value
        """
        return (byte_list[0] << 24) | (byte_list[1] << 16) | (byte_list[2] << 8) | byte_list[3]

    def byte_list_to_uint32_list(self, byte_list, uint32_list):
        """
            This function converts a list of bytes into uint32 values and places at the start of the uint32 list.

            :param byte_list: The list of bytes to convert.
            :type byte_list: list
            :param uint32_list: The list of uint32 values to convert.
            :type uint32_list: list

            :return: 0 if successful, -1 if the byte list is not a multiple of 4, or if the uint32 list is too small.
        """
        if len(byte_list) % 4 != 0:
            return -1 
        if len(uint32_list) < len(byte_list) // 4:
            return -1

        for i in range(0, len(byte_list), 4):
            uint32_list[i//4] = ((byte_list[i] << 24) | (byte_list[i+1] << 16) | (byte_list[i+2] << 8) | byte_list[i+3])

        return 0

    
    def byte_list_to_uint16_list(self, byte_list, uint16_list):
        """
            This function converts a list of bytes to a list of uint16 values and places at the start of the uint16 list.

            :param byte_list: The list of bytes to convert.
            :type byte_list: list
            :param uint16_list: The list of uint16 values to convert.
            :type uint16_list: list
            :return: 0 if successful, -1 if the byte list is not a multiple of 2, or if the uint16 list is too small.
        """

        if len(byte_list) % 2 != 0:
            return -1
        if len(uint16_list) < len(byte_list) // 2:
            return -1

        for i in range(0, len(byte_list), 2):
            uint16_list[i//2] = ((byte_list[i] << 8) | byte_list[i+1])
    
        return 0
    
    def byte_list_to_int16_list(self, byte_list, int16_list):
        """
            This function converts a list of bytes to a list of int16 values and places at the start of the int16 list.

            :param byte_list: The list of bytes to convert.
            :type byte_list: list
            :param int16_list: The list of int16 values to convert.
            :type int16_list: list
            :return: 0 if successful, -1 if the byte list is not a multiple of 2, or if the int16 list is too small.
        """

        if len(byte_list) % 2 != 0:
            return -1
        if len(int16_list) < len(byte_list) // 2:
            return -1

        for i in range(0, len(byte_list), 2):
            int16_list[i//2] = ((byte_list[i] << 8) | byte_list[i+1])
            if int16_list[i//2] > 32767:
                int16_list[i//2] -= 65536
        
        return 0

        
    def set_ranging_mode(self, ranging_mode):
        """
            This function is used to set the ranging mode. Two modes are
            available using ULD: Continuous and autonomous. The default
            mode is Autonomous.
            
            :param ranging_mode: Use kRangingModeAutonomous, kRangingModeContinous 
            :type ranging_mode: int
            :return: status: 0 if set ranging mode is OK.
            :rtype: int
        """
        status = self.kStatusOK

        status |= self.dci_read_data(self.temp_buffer, self.kDciRangingMode, 8)

        if ranging_mode == self.kRangingModeContinous:
            self.temp_buffer[0x01] = 0x1
            self.temp_buffer[0x03] = 0x3
            single_range = self.uint32_list_to_byte_list([0])
        elif ranging_mode == self.kRangingModeAutonomous:
            self.temp_buffer[0x01] = 0x3
            self.temp_buffer[0x03] = 0x2
            single_range = self.uint32_list_to_byte_list([1])
        else:
            status = self.kStatusInvalidParam

        status |= self.dci_write_data(self.temp_buffer, self.kDciRangingMode, 8)
        status |= self.dci_write_data(single_range, self.kDciSingleRange, len(single_range))
        
        return status

    def get_ranging_mode(self):
        """
            This function is used to get the ranging mode. Two modes are
            available using ULD: Continuous and autonomous. The default
            mode is Autonomous.

            :return: The current ranging mode.
            :rtype: int
        """
        self.dci_read_data(self.temp_buffer, self.kDciRangingMode, 8)

        if self.temp_buffer[0x01] == 0x1:
            return self.kRangingModeContinous
        else:
            return self.kRangingModeAutonomous

    def start_ranging(self):
        """
            This function starts a ranging session. When the sensor streams, host
            cannot change settings 'on-the-fly'.
            
            :return: status: 0 if start is OK.
            :rtype: int
        """
    
        status = self.kStatusOK
        header_config = [0,0]

        cmd = [0x00, 0x03, 0x00, 0x00]

        resolution = self.get_resolution()
        self.data_read_size = 0
        self.stream_count = 255

        output_bh_enable = [
            0x00000007,
            0x00000000,
            0x00000000,
            0xC0000000
        ]

        # Send addresses of possible output
        output = [
            self.kStartBh,
            self.kMetadataBh,
            self.kCommonDataBh,
            self.kAmbientRateBh,
            self.kSpadCountBh,
            self.kNbTargetDetectedBh,
            self.kSignalRateBh,
            self.kRangeSigmaMmBh,
            self.kDistanceBh,
            self.kReflectanceBh,
            self.kTargetStatusBh,
            self.kMotionDetectBh
        ]

        # Enable selected outputs
        output_bh_enable[0] += 8    # VL53L5CX_ENABLE_AMBIENT_PER_SPAD
        output_bh_enable[0] += 16   # VL53L5CX_ENABLE_NB_SPADS_ENABLED
        output_bh_enable[0] += 32   # VL53L5CX_ENABLE_NB_TARGET_DETECTED
        output_bh_enable[0] += 64   # VL53L5CX_ENABLE_SIGNAL_PER_SPAD
        output_bh_enable[0] += 128  # VL53L5CX_ENABLE_RANGE_SIGMA_MM
        output_bh_enable[0] += 256  # VL53L5CX_ENABLE_DISTANCE_MM
        output_bh_enable[0] += 512  # VL53L5CX_ENABLE_REFLECTANCE_PERCENT
        output_bh_enable[0] += 1024 # VL53L5CX_ENABLE_TARGET_STATUS
        output_bh_enable[0] += 2048 # VL53L5CX_ENABLE_MOTION_INDICATOR

        # Send output addresses
        for i in range(len(output)):
            if (output[i] == 0) or ((output_bh_enable[i//32] & (1 << (i%32))) == 0):
               continue

            bh_ptr_type = (output[i] & self.kBlockHeaderTypeMask) >> self.kBlockHeaderTypeShift
            bh_ptr_size = (output[i] & self.kBlockHeaderSizeMask) >> self.kBlockHeaderSizeShift
            bh_ptr_idx = (output[i] & self.kBlockHeaderIdxMask) >> self.kBlockHeaderIdxShift

            if (bh_ptr_type >= 0x01) and (bh_ptr_type < 0x0d):
                if (bh_ptr_type >= 0x54d0) and (bh_ptr_idx < 0x54d0 + 960):
                    bh_ptr_size = resolution
                else:
                    bh_ptr_size = resolution * self.kNbTargetPerZone
                
                self.data_read_size += bh_ptr_type * bh_ptr_size
            else:
                self.data_read_size += bh_ptr_size

            self.data_read_size += 4

        self.data_read_size += 20

        status |= self.dci_write_data(output, self.kDciOutputList, len(output) * 4)

        header_config[0] = self.data_read_size
        header_config[1] = i + 1

        status |= self.dci_write_data(self.uint32_list_to_byte_list(header_config), self.kDciOutputConfig, 8)
        status |= self.dci_write_data(self.uint32_list_to_byte_list(output_bh_enable), self.kDciOutputEnables, 16)

        # Start xshut bypass (interrupt mode)
        status |= self._i2c.wr_byte(self.address, 0x7FFF, 0x00)
        status |= self._i2c.wr_byte(self.address, 0x09, 0x05)
        status |= self._i2c.wr_byte(self.address, 0x7FFF, 0x02)

        # Start ranging session
        status |= self._i2c.wr_multi(self.address, self.kUiCmdEnd - (4 - 1), cmd, len(cmd))
        status |= self.poll_for_answer(4, 1, self.kUiCmdStatus, 0xff, 0x03)

        return status

    def stop_ranging(self):
        """
            This function stops a ranging session. It must be used when the
            sensor streams, after calling vl53l5cx_start_ranging().
            
            :return: status: 0 if stop is OK.
            :rtype: int
        """
        status = self.kStatusOK

        auto_stop_flag = self._i2c.rd_multi(self.address, 0x2FFC, 4)
        
        # TODO: check endianess of the auto_stop_flag here
        if auto_stop_flag != [0x00, 0x00, 0x04, 0xFF]:
            self._i2c.wr_byte(self.address, 0x7fff, 0x00)

            # Provoke MCU stop
            self._i2c.wr_byte(self.address, 0x15, 0x16)
            self._i2c.wr_byte(self.address, 0x14, 0x01)

            # Poll for G02 status 0 MCU stop
            timeout = 0
            tmp = 0 
            while (tmp & 0x80) >> 7 == 0x00:
                tmp = self._i2c.rd_byte(self.address, 0x6)
                time.sleep(0.010)
                timeout += 1

                # Timeout reached after 5 seconds
                if timeout > 500:
                    status = self.kStatusError
                    break

        # Undo MCU stop
        status |= self._i2c.wr_byte(self.address, 0x7fff, 0x00)
        status |= self._i2c.wr_byte(self.address, 0x14, 0x00)
        status |= self._i2c.wr_byte(self.address, 0x15, 0x00)

        # Stop xshut bypass
        status |= self._i2c.wr_byte(self.address, 0x09, 0x04)
        status |= self._i2c.wr_byte(self.address, 0x7fff, 0x02)

        return status
    
    def check_data_ready(self):
        """
        This function checks if new data is ready by polling I2C. If new
        data is ready, a flag will be raised.
        
        :return: True if new data is ready, otherwise False
        :rtype: bool
        """
        
        # Check if new data is ready
        self.temp_buffer[0:4] = self._i2c.rd_multi(self.address, 0x0, 4)

        if  (    (self.temp_buffer[0] != self.stream_count) 
            and (self.temp_buffer[0] != 255) 
            and (self.temp_buffer[1] == 5)
            and (self.temp_buffer[2] & 0x5 == 0x5)
            and (self.temp_buffer[3] & 0x10 == 0x10)
        ): 
            return True
        
        else:
            return False

    def get_ranging_data(self):
        """
        This function gets the ranging data, using the selected output and the
        resolution.
        
        :return: The ranging data
        :rtype: RangingDataResults
        """
        status = self.kStatusOK
        data = RangingDataResults()

        # Get the data
        self.temp_buffer[0:self.data_read_size] = self._i2c.rd_multi(self.address, 0x0, self.data_read_size)
        self.stream_count = self.temp_buffer[0]
        self.swap_buffer(self.temp_buffer, self.data_read_size)
        
        # Start conversion at position 16 to avoid headers
        for i in range(16, self.data_read_size, 4):
            block_header = self.byte_list_to_uint32(self.temp_buffer[i:i+4])
            bh_ptr_type = (block_header & self.kBlockHeaderTypeMask) >> self.kBlockHeaderTypeShift
            bh_ptr_size = (block_header & self.kBlockHeaderSizeMask) >> self.kBlockHeaderSizeShift
            bh_ptr_idx = (block_header & self.kBlockHeaderIdxMask) >> self.kBlockHeaderIdxShift

            if (bh_ptr_type > 0x01) and (bh_ptr_type < 0x0d):
                msize = bh_ptr_type * bh_ptr_size
            else:
                msize = bh_ptr_size
            
            # TODO: could optionally check the return of each of these functions to make sure they're successful
            if bh_ptr_idx == self.kAmbientRateIdx:
                self.byte_list_to_uint32_list(self.temp_buffer[i + 4:i + 4 + msize], data.ambient_per_spad)
            elif bh_ptr_idx == self.kSpadCountIdx:
                self.byte_list_to_uint32_list(self.temp_buffer[i + 4:i + 4 + msize], data.nb_spads_enabled)
            elif bh_ptr_idx == self.kNbTargetDetectedIdx:
                data.nb_target_detected[0:msize] = self.temp_buffer[i + 4:i + 4 + msize]
            elif bh_ptr_idx == self.kSignalRateIdx:
                self.byte_list_to_uint32_list(self.temp_buffer[i + 4:i + 4 + msize], data.signal_per_spad)
            elif bh_ptr_idx == self.kRangeSigmaMmIdx:
                self.byte_list_to_uint16_list(self.temp_buffer[i + 4:i + 4 + msize], data.range_sigma_mm)
            elif bh_ptr_idx == self.kDistanceIdx:
                self.byte_list_to_int16_list(self.temp_buffer[i + 4:i + 4 + msize], data.distance_mm)
            elif bh_ptr_idx == self.kReflectanceIdx:
                data.reflectance[0:msize] = self.temp_buffer[i + 4:i + 4 + msize]
            elif bh_ptr_idx == self.kTargetStatusIdx:
                data.target_status[0:msize] = self.temp_buffer[i + 4:i + 4 + msize]
            elif bh_ptr_idx == self.kMotionDetectIdx:
                # TODO: check endianness and packing here...
                data.motion_indicator.global_indicator_1 = self.byte_list_to_uint32(self.temp_buffer[i + 4:i + 4 + 4])
                data.motion_indicator.global_indicator_2 = self.byte_list_to_uint32(self.temp_buffer[i + 8:i + 8 + 4])
                data.motion_indicator.status = self.temp_buffer[i + 12]
                data.motion_indicator.nb_of_detected_aggregates = self.temp_buffer[i + 13]
                data.motion_indicator.nb_of_aggregates = self.temp_buffer[i + 14]
                data.motion_indicator.spare = self.temp_buffer[i + 15]
                self.byte_list_to_uint32_list(self.temp_buffer[i + 16:i + 16 + 128], data.motion_indicator.motion)

            i += msize

        # Convert data into their real format 
        for i in range (self.kResolution8x8):
            data.ambient_per_spad[i] = data.ambient_per_spad[i] // 2048
        
        for i in range (self.kResolution8x8 * self.kNbTargetPerZone):
            if data.distance_mm[i] < 0:
                data.distance_mm[i] = 0
            data.range_sigma_mm[i] = data.range_sigma_mm[i] // 128
            data.signal_per_spad[i] = data.signal_per_spad // 2048
        
        for i in range (self.kResolution8x8):
            if data.nb_target_detected[i] == 0:
                for j in range (self.kNbTargetPerZone):
                    data.target_status[i * self.kNbTargetPerZone + j] = 255

        for i in range(32):
            data.motion_indicator.motion[i] = data.motion_indicator.motion[i] // 65535

        return data
    
    def get_power_mode(self):
        """
            This function is used to get the current sensor power mode.

            :return: The current power mode.
            :rtype: int
        """
        self._i2c.wr_byte(self.address, 0x7FFF, 0x00)
        tmp = self._i2c.rd_byte(self.address, 0x009)

        power_mode = self.kStatusError

        if tmp == 0x4:
            power_mode = self.kPowerModeWakeup
        elif tmp == 0x2:
            power_mode = self.kPowerModeSleep
        else:
            power_mode = self.kStatusError

        self._i2c.wr_byte(self.address, 0x7FFF, 0x02)

        return power_mode

    def set_power_mode(self, power_mode):
        """
            This function is used to set the sensor in Low Power mode, for example if the sensor is not used during a long time. 
            The macro kPowerModeSleep can be used to enable the low power mode. When user wants to restart the sensor, 
            they can use the macro kPowerModeWakeup. Please ensure that the device is not streaming before calling the function.

            :param power_mode: Selected power mode (kPowerModeSleep or kPowerModeWakeup)
            :type power_mode: int
            :return: status: 0 if set power mode is OK.
            :rtype: int
        """

        status = self.kStatusOK
        
        current_power_mode = self.get_power_mode()
        
        if power_mode != current_power_mode:
            if power_mode == self.kPowerModeWakeup:
                self._i2c.wr_byte(self.address, 0x7FFF, 0x00)
                self._i2c.wr_byte(self.address, 0x09, 0x04)
                status |= self.poll_for_answer(1, 0, 0x06, 0x01, 1)

            elif power_mode == self.kPowerModeSleep:
                self._i2c.wr_byte(self.address, 0x7FFF, 0x00)
                self._i2c.wr_byte(self.address, 0x09, 0x02)
                status |= self.poll_for_answer(1, 0, 0x06, 0x01, 0)
            else:
                status = self.kStatusError

            self._i2c.wr_byte(self.address, 0x7FFF, 0x02)
        
        return status
    
    def get_integration_time_ms(self):
        """
            This function gets the current integration time in ms.

            :return: The current integration time in ms.
            :rtype: int
        """
        self.dci_read_data(self.temp_buffer, self.kDciIntegrationTime, 20)

        p_time_ms = self.byte_list_to_uint32(self.temp_buffer[0:4])
        return p_time_ms // 1000
    
    def set_integration_time_ms(self, integration_time_ms):
        """
            This function sets a new integration time in ms. Integration time must
            be computed to be lower than the ranging period, for a selected resolution.
            Please note that this function has no impact on ranging mode continuous.
            
            :param integration_time_ms: Contains the integration time in ms. For all
                resolutions and frequency, the minimum value is 2ms, and the maximum is
                1000ms.
            :type integration_time_ms: int
            :return: status: 0 if set integration time is OK.
            :rtype: int
        """
        status = self.kStatusOK

        integration = integration_time_ms 
        if (integration < 2) or (integration > 1000):
            status |= self.kStatusInvalidParam 
        else:
            integration = integration * 1000
            status |= self.dci_replace_data(self.temp_buffer, self.kDciIntegrationTime, 20, self.uint32_list_to_byte_list([int(integration)]), 4, 0x00)
        
        return status
    
    def get_sharpener_percent(self):
        """
            This function gets the current sharpener in percent. Sharpener can be
            changed to blur more or less zones depending on the application.

            :return: The current sharpener in percent.
            :rtype: int
        """

        self.dci_read_data(self.temp_buffer, self.kDciSharpenerPercent, 16)
        
        return (self.temp_buffer[0xD] * 100) // 255

    def set_sharpener_percent(self, sharpener_percent):
        """
            This function sets a new sharpener value in percent. Sharpener can be
            changed to blur more or less zones depending on the application. Min value is
            0 (disabled), and max is 99.

            :param sharpener_percent: Value between 0 (disabled) and 99%.
            :type sharpener_percent: int
            :return: status: 0 if set sharpener is OK.
            :rtype: int
        """

        status = self.kStatusOK

        if sharpener_percent >= 100:
            status |= self.kStatusInvalidParam
        else:
            sharpener = (sharpener_percent * 255) // 100
            status |= self.dci_replace_data(self.temp_buffer, self.kDciSharpenerPercent, 16, self.uint32_list_to_byte_list([sharpener]), 1, 0xD)

        return status
    
    def get_target_order(self):
        """
            This function gets the current target order (closest or strongest).

            :return: The current target order.
            :rtype: int
        """

        self.dci_read_data(self.temp_buffer, self.kDciTargetOrder, 4)

        return self.temp_buffer[0x0]
    
    def set_target_order(self, target_order):
        """
            This function sets a new target order. Please use macros
            VL53L5CX_TARGET_ORDER_STRONGEST and VL53L5CX_TARGET_ORDER_CLOSEST to define
            the new output order. By default, the sensor is configured with the strongest
            output.

            :param target_order: Required target order.
            :type target_order: int
            :return: status: 0 if set target order is OK, or 127 if target order is unknown.
            :rtype: int
        """
        
        status = self.kStatusOK

        if (target_order == self.kTargetOrderClosest) or (target_order == self.kTargetOrderStronges):
            status |= self.dci_replace_data(self.temp_buffer, self.kDciTargetOrder, 4, [target_order], 1, 0x0)
        else:
            status = self.kStatusInvalidParam

        return status
    

    def wr_multi(self, reg, values):
        """
            This function writes multiple bytes to a register. Enables 16 bit register address writes.

            :param reg: The 16-bit register to write to.
            :type reg: int
            :param values: The values to write to the register.
            :type values: list
        """
        bytes_to_write = [(reg >> 8) & 0xff, reg & 0xff] + values

        # TODO: Ideally, the underlying drivers will make this work for very large sizes on each platform, 
        #       But we have to be able to write 32,768 bytes at a time, so this might have to 
        #       split up the writes into smaller chunks
        self._i2c.write_block(self.address, bytes_to_write[0], bytes_to_write[1:])

    def rd_multi(self, reg, num_bytes):
        """
            This function reads multiple bytes from a register. Enables 16 bit register address reads.

            :param reg: The 16-bit register to read from.
            :type reg: int
            :param num_bytes: The number of bytes to read from the register.
            :type num_bytes: int
            :return: The values read from the register.
            :rtype: list
        """
        bytes_to_write = [(reg >> 8) & 0xff, reg & 0xff]
        self._i2c.write_block(self.address, bytes_to_write[0], bytes_to_write[1])
        return self._i2c.read_block(self.address, None, num_bytes)

    def wr_byte(self, reg, value):
        """
            This function writes a byte to a register. Enables 16 bit register address writes.

            :param reg: The 16-bit register to write to.
            :type reg: int
            :param value: The value to write to the register.
            :type value: int
        """
        bytes_to_write = [(reg >> 8) & 0xff, reg & 0xff, value]
        self._i2c.write_block(self.address, bytes_to_write[0], bytes_to_write[1:])

    def rd_byte(self, reg):
        """
            This function reads a single byte from a register. Enables 16 bit register address reads.

            :param reg: The 16-bit register to read from.
            :type reg: int
            :return: The value read from the register.
            :rtype: int
        """
        bytes_to_write = [(reg >> 8) & 0xff, reg & 0xff]
        self._i2c.write_block(self.address, bytes_to_write[0], bytes_to_write[1])
        return self._i2c.read_byte(self.address, None)
    
    def get_buffer_from_file(self, fileName, startByte = 0, endByte = None):
        """
            This function gets the buffer from the file. 
            If endByte is None, the function will read until the end of the file.
            Bytes returned will be [startByte, endByte) (endByte not included)

            :param fileName: The name of the file to read from. 
            fileName should be relative to the dataPath set in the constructor.
            :type fileName: str
            
            :param startByte: The start byte to read from the file.
            :type startByte: int
            :param endByte: The end byte to read from the file.
            :type endByte: int

            :return: The buffer read from the file.
            :rtype: list
        """
        fName = os.path.join(self._dataPath, fileName)
        with open(fName, 'rb') as f:
            f.seek(startByte)
            if endByte is None:
                return list(f.read())
            else:
                return list(f.read(endByte - startByte))
            